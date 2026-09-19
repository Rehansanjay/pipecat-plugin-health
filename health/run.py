"""Check every community Pipecat plugin against a Pipecat version.

    python -m health.run --target latest    # newest pipecat-ai release on PyPI
    python -m health.run --target main      # pipecat-ai main branch (early warning)

Each plugin gets a fresh virtualenv, is installed together with the target
pipecat-ai, and is probed by ``probe.py``. Results go to results/<target>.json;
changes since the previous run go to results/<target>-changes.md.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from health.sources import Plugin, fetch_docs, parse

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
PROBE = Path(__file__).resolve().parent / "probe.py"

OK, PARTIAL, BROKEN, PINNED, UNINSTALLABLE = "ok", "partial", "broken", "pinned", "uninstallable"
ORDER = {BROKEN: 0, PINNED: 1, UNINSTALLABLE: 2, PARTIAL: 3, OK: 4}

# An absolute path on Windows (C:\...) or POSIX (/...), up to the next whitespace.
_LOCAL_PATH = re.compile(r"(?:[A-Za-z]:\\|(?<![\w:])/(?:home|tmp|Users|root|var|opt|runner)/)\S*")


def _get_json(url: str):
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.load(resp)


def resolve_target(target: str) -> tuple[str, str]:
    """Return (label, requirement) for the pipecat-ai version under test."""
    if target == "latest":
        version = _get_json("https://pypi.org/pypi/pipecat-ai/json")["info"]["version"]
        return version, f"pipecat-ai=={version}"
    if target == "main":
        sha = _get_json("https://api.github.com/repos/pipecat-ai/pipecat/commits/main")["sha"]
        return f"main@{sha[:9]}", f"pipecat-ai @ git+https://github.com/pipecat-ai/pipecat@{sha}"
    raise ValueError(target)


def _run(cmd: list[str], timeout: int) -> subprocess.CompletedProcess:
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    return subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, env=env
    )


def _venv_python(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _install_failure(stderr: str) -> tuple[str, str]:
    text = stderr.strip()
    lines = [ln for ln in text.splitlines() if ln.strip()]
    # uv explains an unsatisfiable resolution in a "Because ..." paragraph.
    reason = next((ln.strip() for ln in lines if "Because" in ln or "because" in ln), lines[-1] if lines else "")
    reason = re.sub(r"^[^A-Za-z]*", "", reason)  # uv's tree glyphs: ×, ╰─▶
    reason = re.sub(r"^(?:(?:hint|cause|error):\s*)+", "", reason, flags=re.I)
    reason = _LOCAL_PATH.sub("<checkout>", reason)  # uv cache paths are machine-specific
    if "pipecat-ai" in text and ("No solution found" in text or "unsatisfiable" in text):
        # "... depends on pipecat-ai>=1.8.1,<1.9 and you require ..." -> "pins pipecat-ai>=1.8.1,<1.9"
        pins = re.findall(r"depends? on (pipecat-ai(?:\[[^\]]*\])?[<>=!~][^\s,]*(?:,[<>=!~][^\s,]*)*)", text)
        if pins:
            return PINNED, "pins " + "; ".join(dict.fromkeys(pins))
        return PINNED, reason
    return UNINSTALLABLE, reason


def _involves_pipecat(error: dict) -> bool:
    """True when a submodule fails because of pipecat itself, not a missing optional package.

    "No module named 'pipecat.utils.x'" and "cannot import name 'Y' from 'pipecat.z'"
    count; "No module named 'livekit'" or 'pipecat_flows' do not.
    """
    return re.search(r"'pipecat(?:\.[\w.]+)?'", error["message"]) is not None


def classify(probe: dict) -> tuple[str, str]:
    """Status and one-line reason for a plugin that installed, from its probe output."""
    if probe["top_level_errors"]:
        e = probe["top_level_errors"][0]
        return BROKEN, f"import {e['module']}: {e['type']}: {e['message']}"
    if probe["abstract_services"]:
        a = probe["abstract_services"][0]
        return BROKEN, f"{a['class']} cannot be created, missing: {', '.join(a['missing'])}"
    if not probe["distributions"]:
        return UNINSTALLABLE, "installed, but no package depending on pipecat-ai was found"
    # Submodules that only fail for want of another framework (livekit, crewai,
    # ...) are optional integrations, not breakage.
    pipecat_errors = [e for e in probe["submodule_errors"] if _involves_pipecat(e)]
    if pipecat_errors:
        e = pipecat_errors[0]
        return PARTIAL, f"import {e['module']}: {e['type']}: {e['message']}"
    return OK, ""


def check(plugin: Plugin, pipecat_req: str, uv: str, python: str, workdir: Path) -> dict:
    started = time.monotonic()
    venv = Path(tempfile.mkdtemp(prefix="plugin-", dir=workdir))
    out = venv / "probe.json"
    entry: dict = {"name": plugin.name, "install": plugin.install, "categories": plugin.categories, "docs": plugin.docs}
    try:
        _run([uv, "venv", str(venv), "--python", python, "--quiet", "--allow-existing"], 300)
        # CPU-only PyTorch: the GPU builds are gigabytes and nothing here needs a GPU.
        install = [uv, "pip", "install", "--torch-backend", "cpu", "--python", str(_venv_python(venv))]
        proc = _run([*install, pipecat_req, *plugin.specs], 900)
        if proc.returncode != 0:
            status, reason = _install_failure(proc.stderr)
            entry.update(status=status, reason=reason)
            return entry
        try:
            _run([str(_venv_python(venv)), str(PROBE), str(out), *plugin.specs], 300)
            probe = json.loads(out.read_text(encoding="utf-8"))
        except subprocess.TimeoutExpired:
            entry.update(status=BROKEN, reason="importing the plugin hung for 5 minutes")
            return entry
        except (OSError, ValueError) as exc:
            entry.update(status=BROKEN, reason=f"probe produced no result: {exc}")
            return entry
        entry["probe"] = probe
        entry["distributions"] = probe["distributions"]
        status, reason = classify(probe)
        entry.update(status=status, reason=reason)
        return entry
    except subprocess.TimeoutExpired:
        entry.update(status=UNINSTALLABLE, reason="install timed out")
        return entry
    finally:
        entry["seconds"] = round(time.monotonic() - started, 1)
        shutil.rmtree(venv, ignore_errors=True)


def changes(previous: dict | None, current: dict) -> list[str]:
    if not previous:
        return []
    before = {p["name"] + "|" + p["install"]: p for p in previous.get("plugins", [])}
    lines = []
    for p in current["plugins"]:
        old = before.get(p["name"] + "|" + p["install"])
        if old is None:
            lines.append(f"- **{p['name']}** is new in the docs: {p['status']}")
        elif old["status"] != p["status"]:
            lines.append(
                f"- **{p['name']}**: {old['status']} → {p['status']}" + (f" ({p['reason']})" if p["reason"] else "")
            )
    return lines


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=["latest", "main"], default="latest")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--only", nargs="*", help="plugin names to check (default: all)")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument(
        "--reclassify", action="store_true", help="re-apply the status rules to saved results, no installs"
    )
    args = parser.parse_args()

    if args.reclassify:
        path = RESULTS / f"{args.target}.json"
        saved = json.loads(path.read_text(encoding="utf-8"))
        for e in saved["plugins"]:
            if "probe" in e:
                e["status"], e["reason"] = classify(e["probe"])
        saved["plugins"].sort(key=lambda e: (ORDER[e["status"]], e["name"].lower()))
        path.write_text(json.dumps(saved, indent=2) + "\n", encoding="utf-8")
        print(f"reclassified {len(saved['plugins'])} plugins in {path.name}")
        return

    uv = shutil.which("uv") or str(Path(sys.executable).parent / ("uv.exe" if os.name == "nt" else "uv"))
    label, pipecat_req = resolve_target(args.target)
    docs_sha, text = fetch_docs()
    plugins = parse(text)
    if args.only:
        plugins = [p for p in plugins if p.name in args.only]
    print(f"pipecat-ai {label}: checking {len(plugins)} plugins from docs {docs_sha[:7]} with {args.workers} workers")

    RESULTS.mkdir(exist_ok=True)
    workdir = Path(tempfile.mkdtemp(prefix="pipecat-plugin-health-"))
    started = time.monotonic()
    entries = []
    try:
        with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(check, p, pipecat_req, uv, args.python, workdir): p for p in plugins}
            for fut in cf.as_completed(futures):
                e = fut.result()
                entries.append(e)
                print(f"  {e['status']:<13} {e['name']:<26} {e['seconds']:>6}s  {e['reason'][:110]}", flush=True)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    entries.sort(key=lambda e: (ORDER[e["status"]], e["name"].lower()))
    py_version = _run([args.python, "-c", "import sys; print('%d.%d.%d' % sys.version_info[:3])"], 60)
    result = {
        "target": args.target,
        "pipecat": label,
        "checked_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "docs_commit": docs_sha,
        "python": py_version.stdout.strip(),
        "seconds": round(time.monotonic() - started),
        "plugins": entries,
    }

    out = RESULTS / f"{args.target}.json"
    previous = json.loads(out.read_text(encoding="utf-8")) if out.exists() else None
    if args.only:
        # Recheck of a few plugins: print them, and update just those rows in the
        # saved results when they were produced against the same pipecat.
        diff = []
        if previous and previous["pipecat"] == label:
            fresh = {(e["name"], e["install"]) for e in entries}
            previous["plugins"] = [p for p in previous["plugins"] if (p["name"], p["install"]) not in fresh] + entries
            previous["plugins"].sort(key=lambda e: (ORDER[e["status"]], e["name"].lower()))
            out.write_text(json.dumps(previous, indent=2) + "\n", encoding="utf-8")
            print(f"updated {len(fresh)} rows in {out.name}")
    else:
        diff = changes(previous, result)
        out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        (RESULTS / f"{args.target}-changes.md").write_text("\n".join(diff) + ("\n" if diff else ""), encoding="utf-8")

    counts = {s: sum(e["status"] == s for e in entries) for s in ORDER}
    print(f"done in {result['seconds']}s: " + ", ".join(f"{n} {s}" for s, n in counts.items() if n))
    for line in diff:
        print("CHANGE", line)


if __name__ == "__main__":
    main()
