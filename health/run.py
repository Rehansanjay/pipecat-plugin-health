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
import functools
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from health.repos import project_name, repo_for_plugin
from health.sources import Plugin, fetch_docs, github_api, parse

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
PROBE = Path(__file__).resolve().parent / "probe.py"

OK, PARTIAL, BROKEN, PINNED, UNINSTALLABLE = "ok", "partial", "broken", "pinned", "uninstallable"
# A plugin whose vendor SDK is licensed rather than published. Not broken --
# it works for that vendor's customers -- but not verifiable from outside.
GATED = "gated"
# A plugin whose source is already fixed and whose release is not. The
# maintainer has nothing left to do in the code; their users are still broken
# until a release is cut, and that is a different request to make of them.
UNRELEASED = "unreleased"
ORDER = {BROKEN: 0, PINNED: 1, UNINSTALLABLE: 2, PARTIAL: 3, UNRELEASED: 4, GATED: 5, OK: 6}

# Source verdicts. "unpackaged" is its own answer rather than a flavour of
# unknown: tryHakimAI/hakim-pipecat and havkerboi123/pipecat-upliftai-stt both
# hold a working plugin and neither has a pyproject.toml or a setup.py, so
# there is nothing for pip to install even though Pipecat's docs publish an
# ``uv add`` line for each. That is a fact about the repository, not a gap in
# this checker, and it is the one thing worth telling those maintainers.
FIXED, STILL_BROKEN, UNPACKAGED, SOURCE_UNKNOWN = "fixed", "still_broken", "unpackaged", "unknown"

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


@functools.lru_cache(maxsize=256)
def _on_pypi(name: str) -> bool | None:
    """Is there a PyPI project under this name? None when the question could not be asked.

    Module names and project names are not the same thing, so both the
    underscore and the dash spelling are tried. A None is deliberately distinct
    from a False: a network failure must not be read as "this package does not
    exist", because that would silently reclassify a broken plugin as a gated
    one.
    """
    for candidate in {name, name.replace("_", "-")}:
        try:
            with urllib.request.urlopen(f"https://pypi.org/pypi/{candidate}/json", timeout=15):
                return True
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                return None
        except (urllib.error.URLError, OSError):
            return None
    return False


def _gating_module(message: str) -> str | None:
    """The private package an import is waiting on, if that is what failed.

    A plugin that needs a vendor SDK distributed by licence rather than by
    PyPI is not broken -- it works for that vendor's customers, and no public
    checker can ever see it work. Reporting it as broken is simply wrong, and
    it is the maintainer who gets the blame for it.
    """
    match = re.search(r"No module named '([A-Za-z_][\w]*)'", message)
    if not match:
        return None
    module = match.group(1)
    if module.startswith("pipecat"):
        return None
    return module if _on_pypi(module) is False else None


def classify(probe: dict) -> tuple[str, str]:
    """Status and one-line reason for a plugin that installed, from its probe output."""
    if probe["top_level_errors"]:
        e = probe["top_level_errors"][0]
        gating = _gating_module(e["message"])
        if gating:
            return GATED, f"needs {gating}, which is not published on PyPI"
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


def behind_the_pin(plugin: Plugin, pipecat_req: str, uv: str, python: str, venv: Path, out: Path) -> dict:
    """Would the plugin's code work on this pipecat, if the pin allowed it?

    A pin failure says the plugin will not *resolve*. It does not say the code
    is broken. Those are different messages for a maintainer -- one is a
    one-line edit to a version range, the other is a real API break the pin has
    been hiding -- and reporting them as one row merges them.

    Suggested by Arhan Canli in response to the write-up, as "install it with
    --no-deps next to the current pipecat". That works, but --no-deps also
    skips the plugin's *own* SDK, so the import then fails for want of an
    unrelated package and the answer comes back unknown -- which is what
    happened to two of the five on the first run.

    uv's ``--overrides`` is the sharper instrument: the plugin resolves with
    all its real dependencies, and only pipecat-ai is forced to the version
    under test. That is exactly the question being asked.

    ``_involves_pipecat`` still guards the verdict, so anything failing for a
    reason this does not recognise leaves the answer "unknown" rather than
    guessing.

    Returns ``{"pin": compatible|incompatible|unknown, "pin_reason": str}``.
    """
    install = [uv, "pip", "install", "--torch-backend", "cpu", "--python", str(_venv_python(venv))]
    overrides = venv / "pipecat-override.txt"
    overrides.write_text(pipecat_req + "\n", encoding="utf-8")

    proc = _run([*install, "--overrides", str(overrides), pipecat_req, *plugin.specs], 900)
    if proc.returncode != 0:
        # Falling back keeps an answer available when the override cannot
        # resolve -- a plugin may pin something else that genuinely conflicts.
        proc = _run([*install, pipecat_req], 900)
        if proc.returncode != 0:
            return {"pin": "unknown", "pin_reason": "could not install pipecat on its own"}
        proc = _run([*install, "--no-deps", *plugin.specs], 900)
        if proc.returncode != 0:
            return {"pin": "unknown", "pin_reason": "would not install even with its pipecat pin overridden"}

    try:
        _run([str(_venv_python(venv)), str(PROBE), str(out), *plugin.specs], 300)
        probe = json.loads(out.read_text(encoding="utf-8"))
    except (subprocess.TimeoutExpired, OSError, ValueError) as exc:
        return {"pin": "unknown", "pin_reason": f"probe produced no result: {exc}"}

    blocking = [e for e in probe["top_level_errors"] if _involves_pipecat(e)]
    if blocking:
        e = blocking[0]
        return {"pin": "incompatible", "pin_reason": f"import {e['module']}: {e['type']}: {e['message']}"}
    if probe["top_level_errors"]:
        e = probe["top_level_errors"][0]
        # Something other than pipecat is missing; not evidence either way.
        return {"pin": "unknown", "pin_reason": f"could not tell: {e['message']}"}
    if probe["abstract_services"]:
        a = probe["abstract_services"][0]
        missing = ", ".join(a["missing"])
        return {"pin": "incompatible", "pin_reason": f"{a['class']} cannot be created, missing: {missing}"}
    return {"pin": "compatible", "pin_reason": "imports and constructs on this pipecat; only the pin blocks it"}


def _canonical(name: str) -> str:
    """PEP 503 normalisation, so pipecat_x and Pipecat-X compare equal."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _head_commit(repo: str) -> str | None:
    """The sha at the tip of a repository's default branch, or None."""
    slug = repo.removeprefix("https://github.com/")
    try:
        return github_api(f"https://api.github.com/repos/{slug}/commits?per_page=1")[0]["sha"]
    except (urllib.error.URLError, OSError, ValueError, KeyError, IndexError):
        return None


@functools.lru_cache(maxsize=256)
def _package_layout(repo: str, sha: str) -> tuple[str, str]:
    """Where the installable package sits in a repository, if it has one.

    Returns ``("ok", subdirectory)`` -- the subdirectory being "" at the root --
    or ``("unpackaged", "")`` when the tree carries no packaging metadata at
    all, or ``("unreadable", "")`` when the tree cannot be listed.

    This exists because ``uv pip install git+<url>`` has three very different
    failures that all arrive as one opaque message. The package can be in a
    subdirectory (supertone-inc/supertonic keeps it in ``py/``), there can be
    no package (two plugins ship a bare module and a requirements.txt), or the
    repository can simply not be there -- pipecat-firered-vad resolves to
    ``your-username/pipecat-firered-vad``, a placeholder left in its README,
    and git answers a 404 clone by prompting for credentials.
    """
    slug = repo.removeprefix("https://github.com/")
    try:
        tree = github_api(f"https://api.github.com/repos/{slug}/git/trees/{sha}?recursive=1")["tree"]
    except (urllib.error.URLError, OSError, ValueError, KeyError):
        return "unreadable", ""

    manifests = [
        entry["path"]
        for entry in tree
        if entry.get("type") == "blob" and entry["path"].rsplit("/", 1)[-1] in ("pyproject.toml", "setup.py")
    ]
    if not manifests:
        return "unpackaged", ""
    # The shallowest manifest is the distribution; anything deeper belongs to a
    # vendored copy or an example that happens to package itself.
    shallowest = min(manifests, key=lambda path: (path.count("/"), len(path)))
    return "ok", shallowest.rpartition("/")[0]


def from_git_head(plugin: Plugin, repo: str, pipecat_req: str, uv: str, python: str, venv: Path, out: Path) -> dict:
    """Does the plugin's current source work, when its release does not?

    The wheel on PyPI is a snapshot, and a maintainer can fix a plugin without
    cutting a release. boson-ai/pipecat-boson wrapped the pipecat 1.8 import on
    2026-09-30 and PyPI still serves 0.1.3 from before it, so installing from
    PyPI reports a plugin broken whose code has been correct for weeks.

    That is worth separating for two reasons. Telling a maintainer their plugin
    is broken when they already fixed it is simply wrong. And the useful thing
    to ask of them is not a patch, it is a release -- which is only visible once
    the two are measured apart.

    The install is pinned to the commit so the verdict names what it tested.
    Anything that fails for a reason this cannot read leaves the answer
    "unknown" rather than guessing in either direction.
    """
    sha = _head_commit(repo)
    install = [uv, "pip", "install", "--torch-backend", "cpu", "--python", str(_venv_python(venv))]
    found = {"source_repo": repo, "source_commit": sha or ""}

    # Without a commit there is no repository to read, and attempting the clone
    # anyway is how a placeholder URL burns the install timeout every night
    # waiting on a credential prompt that nobody will answer.
    if not sha:
        slug = repo.removeprefix("https://github.com/")
        return {
            **found,
            "source": SOURCE_UNKNOWN,
            "source_reason": f"{slug} could not be read: it is missing, private or renamed",
        }

    layout, subdirectory = _package_layout(repo, sha)
    if layout == "unpackaged":
        return {
            **found,
            "source": UNPACKAGED,
            "source_reason": "the repository has no pyproject.toml or setup.py, so there is nothing to install",
        }
    if layout == "unreadable":
        return {**found, "source": SOURCE_UNKNOWN, "source_reason": "the repository tree could not be listed"}

    requirement = f"git+{repo}@{sha}" + (f"#subdirectory={subdirectory}" if subdirectory else "")
    proc = _run([*install, pipecat_req, requirement], 900)
    if proc.returncode != 0:
        _, why = _install_failure(proc.stderr)
        return {**found, "source": SOURCE_UNKNOWN, "source_reason": f"could not install from source: {why}"}

    try:
        _run([str(_venv_python(venv)), str(PROBE), str(out), *plugin.specs], 300)
        probe = json.loads(out.read_text(encoding="utf-8"))
    except (subprocess.TimeoutExpired, OSError, ValueError) as exc:
        return {**found, "source": SOURCE_UNKNOWN, "source_reason": f"probe produced no result: {exc}"}

    # A repository can be resolved plausibly and still be the wrong one: the
    # Supertonic plugin resolves to supertone-inc/supertonic, the vendor's own
    # TTS model repo, because the names share a word. That one fails to install
    # and so answers "unknown" anyway -- but a wrong repository that happened to
    # be installable and import cleanly would promote the plugin to "fixed" on
    # the strength of somebody else's code. So the source has to have built the
    # distribution this plugin actually is.
    expected = {_canonical(project_name(spec)) for spec in plugin.specs if project_name(spec)}
    built = {_canonical(dist.split("==")[0]) for dist in probe.get("distributions") or []}
    if expected and not expected & built:
        return {
            **found,
            "source": SOURCE_UNKNOWN,
            "source_reason": "that repository does not build " + ", ".join(sorted(expected)),
        }

    status, why = classify(probe)
    if status == OK:
        return {**found, "source": FIXED, "source_reason": "imports and constructs from source"}
    if status == GATED:
        # A licensed SDK is missing either way, so the source says nothing here.
        return {**found, "source": SOURCE_UNKNOWN, "source_reason": why}
    return {**found, "source": STILL_BROKEN, "source_reason": why}


def maybe_from_source(
    plugin: Plugin, status: str, reason: str, pipecat_req: str, uv: str, python: str, workdir: Path
) -> dict:
    """Check the source of a plugin whose release failed, and promote it if it is fixed.

    Only failures where the source could change the answer are worth the extra
    install, and only when a repository can actually be found for the plugin.
    """
    if status not in (BROKEN, PARTIAL, UNINSTALLABLE):
        return {}
    repo = repo_for_plugin(plugin.specs)
    if not repo:
        return {}

    venv = Path(tempfile.mkdtemp(prefix="source-", dir=workdir))
    try:
        _run([uv, "venv", str(venv), "--python", python, "--quiet", "--allow-existing"], 300)
        found = from_git_head(plugin, repo, pipecat_req, uv, python, venv, venv / "probe.json")
    except subprocess.TimeoutExpired:
        found = {"source_repo": repo, "source": SOURCE_UNKNOWN, "source_reason": "install from source timed out"}
    finally:
        shutil.rmtree(venv, ignore_errors=True)

    if found.get("source") == FIXED:
        at = (found.get("source_commit") or "")[:9]
        found["released_reason"] = reason
        found["status"] = UNRELEASED
        found["reason"] = (
            f"fixed in {repo.removeprefix('https://github.com/')}"
            + (f"@{at}" if at else "")
            + f", but the release still fails: {reason}"
        )
    return found


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
            if status == PINNED:
                # The pin stopped the resolve. Find out whether the code would
                # have worked anyway -- a tight pin and a real break look
                # identical from here otherwise.
                shutil.rmtree(venv, ignore_errors=True)
                _run([uv, "venv", str(venv), "--python", python, "--quiet", "--allow-existing"], 300)
                entry.update(behind_the_pin(plugin, pipecat_req, uv, python, venv, out))
            else:
                # Nothing installed, so the release says nothing about the code.
                # For a plugin that is not on PyPI at all, the source is the
                # only place its state can be read.
                entry.update(maybe_from_source(plugin, status, reason, pipecat_req, uv, python, workdir))
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
        entry.update(maybe_from_source(plugin, status, reason, pipecat_req, uv, python, workdir))
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
