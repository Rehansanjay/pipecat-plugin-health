"""Render README.md from results/latest.json and results/main.json."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"

ICON = {
    "ok": "✅ works",
    "partial": "🟡 partial",
    "broken": "❌ broken",
    "pinned": "📌 needs older pipecat",
    "uninstallable": "⛔ can't install",
}

ABOUT = """\
# Pipecat plugin health

Every night this repo installs each **community-maintained plugin** listed in
[Pipecat's supported services](https://docs.pipecat.ai/api-reference/server/services/supported-services)
into a fresh environment, together with:

- the **latest pipecat-ai release** on PyPI, which is what a new user gets today, and
- **pipecat-ai `main`**, which is what users will get in the next release. A plugin
  that breaks here can be fixed before the release ships.

It then imports the plugin and checks that every Pipecat service class it defines
can still be created. No API keys are used, so this catches install, import and
API-shape breakage (renamed or removed Pipecat names, new abstract methods, version
pins), not problems talking to a provider's servers.

The plugin list is read from the docs on every run, so new plugins are picked up
automatically.
"""

LEGEND = """\
## What the statuses mean

| Status | Meaning |
|---|---|
| ✅ works | Installs with that Pipecat version, imports, and all its services can be created |
| 🟡 partial | The main package imports, but one of its submodules fails to import |
| ❌ broken | Installs, but importing it fails, or one of its services can't be created |
| 📌 needs older pipecat | Its version pin rules out that Pipecat version, so it can't be installed alongside it |
| ⛔ can't install | The published install command fails (e.g. the package isn't on PyPI) |
"""

FOOTER = """\
## Run it yourself

```bash
pip install uv
python -m health.run --target latest              # all plugins vs the latest release
python -m health.run --target main --only Gnani   # one plugin vs pipecat main
python -m health.report                           # rebuild this README
```

## Maintainers

If your plugin shows as broken, the **Why** column has the first error. The full
probe output, including every failing submodule, is in
[`results/latest.json`](results/latest.json) and [`results/main.json`](results/main.json).
Status changes are also filed as issues in this repo.

This is an independent project, not affiliated with Daily or the Pipecat team.
"""


def _load(target: str) -> dict | None:
    path = RESULTS / f"{target}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _summary(run: dict) -> str:
    counts: dict[str, int] = {}
    for p in run["plugins"]:
        counts[p["status"]] = counts.get(p["status"], 0) + 1
    parts = [f"{counts[s]} {ICON[s].split(' ', 1)[1]}" for s in ICON if counts.get(s)]
    return f"**pipecat-ai {run['pipecat']}** ({run['checked_at'][:10]}): " + ", ".join(parts)


def render() -> str:
    latest, main = _load("latest"), _load("main")
    runs = [r for r in (latest, main) if r]
    if not runs:
        return ABOUT
    names: list[tuple[str, str]] = []
    by_run = []
    for run in runs:
        index = {}
        for p in run["plugins"]:
            key = (p["name"], p["install"])
            index[key] = p
            if key not in names:
                names.append(key)
        by_run.append(index)

    order = {"broken": 0, "pinned": 1, "uninstallable": 2, "partial": 3, "ok": 4}

    def worst(key):
        return min(order[idx[key]["status"]] for idx in by_run if key in idx)

    names.sort(key=lambda k: (worst(k), k[0].lower()))

    header = "| Plugin | Category | " + " | ".join(f"pipecat {r['pipecat']}" for r in runs) + " | Why |"
    rule = "|---|---|" + "---|" * len(runs) + "---|"
    rows = []
    for key in names:
        entries = [idx.get(key) for idx in by_run]
        first = next(e for e in entries if e)
        why = next((e["reason"] for e in entries if e and e["reason"]), "")
        cells = [ICON[e["status"]] if e else "" for e in entries]
        rows.append(
            f"| [{_cell(first['name'])}]({first['docs']}) | {_cell(', '.join(first['categories']))} | "
            + " | ".join(cells)
            + f" | {_cell(why)[:160]} |"
        )

    status = "## Status\n\n" + "\n".join(f"- {_summary(r)}" for r in runs)
    table = "\n".join([header, rule, *rows])
    return "\n".join([ABOUT, status, "", table, "", LEGEND, FOOTER])


if __name__ == "__main__":
    (ROOT / "README.md").write_text(render(), encoding="utf-8")
    print("README.md written")
