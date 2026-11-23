"""Render the public status site from results/latest.json and results/main.json.

    python -m health.site            # uses GITHUB_TOKEN, if set, to list open fix PRs
    python -m health.site --offline  # no network: skips repo lookup and PR links

Writes into site/:
    index.html            every integration, searchable
    i/<slug>/index.html   one page per integration, titled with what actually fails,
                          so a developer searching an error lands on the answer
    badge/<slug>.json     a shields.io endpoint, so a vendor can show the status in a README
    sitemap.xml, robots.txt

The pages are for two readers: someone choosing a provider ("does it work with the
Pipecat I'm on?") and a vendor looking at their own integration ("what broke, and is a
fix already waiting?"). They state only what the nightly check measures.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
OUT = ROOT / "site"
REPO_URL = "https://github.com/Rehansanjay/pipecat-plugin-health"
# Absolute address the site is served from: canonical links, sitemap and badge URLs need it.
SITE_URL = os.environ.get("STATUS_SITE_URL", "https://rehansanjay.github.io/pipecat-plugin-health").rstrip("/")
CONTACT_EMAIL = os.environ.get("STATUS_CONTACT_EMAIL", "")  # set once the business address exists
AUTHOR = "Rehan Sanjay"
AUTHOR_URL = "https://github.com/Rehansanjay"
MERGED = {
    "Pipecat": "https://github.com/pipecat-ai/pipecat/pulls?q=is%3Apr+author%3ARehansanjay+is%3Amerged",
    "LiveKit Agents": "https://github.com/livekit/agents/pulls?q=is%3Apr+author%3ARehansanjay+is%3Amerged",
}

LABEL = {
    "ok": ("Works", "ok"),
    "partial": ("Partly works", "warn"),
    "broken": ("Doesn't load", "bad"),
    "pinned": ("Blocked by a version pin", "warn"),
    "uninstallable": ("Can't be installed", "bad"),
    "gated": ("Needs the vendor's SDK", "info"),
    "unreleased": ("Fixed, waiting for a release", "info"),
}
# Short wording and shields.io colour for the README badge.
BADGE = {
    "ok": ("works", "brightgreen"),
    "partial": ("partly works", "yellow"),
    "broken": ("doesn't load", "red"),
    "pinned": ("version pin", "orange"),
    "uninstallable": ("can't install", "red"),
    "gated": ("needs vendor SDK", "blue"),
    "unreleased": ("fix awaiting release", "blue"),
}
ORDER = {"broken": 0, "uninstallable": 1, "partial": 2, "pinned": 3, "unreleased": 4, "gated": 5, "ok": 6}


def _load(target: str) -> dict | None:
    path = RESULTS / f"{target}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _get(url: str):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "plugin-health"})
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def _repo(plugin: dict, offline: bool) -> str | None:
    if plugin.get("source_repo"):
        # Some docs pages still carry a template link (github.com/your-username/...).
        return None if "your-username" in plugin["source_repo"] else plugin["source_repo"]
    if offline:
        return None
    try:
        from health.repos import repo_for

        return repo_for(plugin["install"].split()[-1])
    except Exception:
        return None


def _open_prs(repo: str | None, offline: bool) -> list[dict]:
    m = re.match(r"https://github\.com/([^/]+)/([^/#?]+)", repo or "")
    if offline or not m:
        return []
    try:
        prs = _get(f"https://api.github.com/repos/{m[1]}/{m[2].removesuffix('.git')}/pulls?state=open&per_page=10")
    except Exception:
        return []
    return [{"url": p["html_url"], "title": p["title"], "number": p["number"]} for p in prs]


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "integration"


def explain(plugin: dict) -> str:
    """One plain sentence a builder or a vendor can act on."""
    status, reason = plugin["status"], plugin.get("reason") or ""
    if status == "pinned":
        base = "Its package requires an older Pipecat, so it can't be installed next to this one."
        if plugin.get("pin") == "compatible":
            return base + " With the pin lifted, the code itself loads fine: only the version range needs widening."
        if plugin.get("pin") == "incompatible":
            return base + " With the pin lifted it still fails, so the code needs updating too."
        return base
    if status == "uninstallable":
        if plugin.get("source") == "unpackaged":
            return "Its repository has no pyproject.toml or setup.py, so the published install command can't work."
        if "not found in the package registry" in reason:
            return "The published install command fails: the package isn't on PyPI."
        return "The published install command fails."
    if status == "gated":
        return "Needs an SDK the vendor distributes under licence. Not a fault; the check can't go further without it."
    if status == "unreleased":
        return "The released package fails, but the latest code in its repository works. It needs a new release."
    m = re.search(r"cannot import name '([^']+)' from '(pipecat[\w.]*)'", reason)
    if m:
        what = "Doesn't load" if status == "broken" else "Part of it doesn't load"
        return f"{what}: it uses `{m[1]}`, which Pipecat has since renamed or removed."
    if "not installed" in reason or "ModuleNotFoundError" in reason:
        return "Doesn't load: a dependency it needs isn't installed by its package."
    if status == "partial":
        return "The main package loads, but one of its modules fails."
    if status == "broken":
        return "Installs, but fails when loaded or when its services are created."
    return ""


def title_detail(plugin: dict) -> str:
    """A short, specific reason for a page title: what someone would search for."""
    status, reason = plugin["status"], plugin.get("reason") or ""
    if status == "pinned":
        m = re.search(r"pipecat-ai(?:\[[^\]]*\])?([<>=!~][^;]*?)\.?(?:;|$)", reason)
        return f"requires pipecat-ai{m[1].strip()}" if m else ""
    if status == "uninstallable":
        if plugin.get("source") == "unpackaged" or "pyproject.toml" in reason:
            return "no pyproject.toml"
        return "not on PyPI" if "not found in the package registry" in reason else ""
    if status in ("gated", "unreleased", "ok"):
        return ""
    return short_error(reason)


def short_error(reason: str) -> str:
    """The part of an error a developer would paste into a search box."""
    m = re.search(r"(\w+Error: .+?)(?:\s+\(|$)", reason)
    text = (m[1] if m else reason).strip()
    text = re.sub(r" from '[^']+'", "", text)  # the missing name is what people search; the module makes it long
    return text if len(text) <= 90 else text[:87].rstrip() + "..."


def rows(latest: dict, main: dict | None, offline: bool) -> list[dict]:
    on_main = {(p["name"], p["install"]): p for p in (main or {}).get("plugins", [])}
    out = []
    for p in latest["plugins"]:
        m = on_main.get((p["name"], p["install"]))
        row = {
            "name": p["name"],
            "docs": p["docs"],
            "install": p["install"],
            "categories": ", ".join(p["categories"]),
            "status": p["status"],
            "main_status": m["status"] if m else None,
            "main_reason": (m or {}).get("reason") or "",
            "explain": explain(p),
            "reason": p.get("reason") or "",
            "source": p.get("source"),
            "repo": None,
            "prs": [],
        }
        if p["status"] != "ok":
            row["repo"] = _repo(p, offline)
            row["prs"] = _open_prs(row["repo"], offline)
        out.append(row)
    # A name can appear twice (separate STT and TTS packages): tell them apart by category.
    names = [slugify(r["name"]) for r in out]
    for r, base in zip(out, names, strict=True):
        r["dup"] = names.count(base) > 1
        r["slug"] = f"{base}-{slugify(r['categories'])}" if r["dup"] else base
    seen: dict[str, int] = {}
    for r in out:
        n = seen[r["slug"]] = seen.get(r["slug"], 0) + 1
        if n > 1:
            r["slug"] = f"{r['slug']}-{n}"
    out.sort(key=lambda r: (ORDER.get(r["status"], 9), r["name"].lower()))
    return out


def _e(s: str) -> str:
    return html.escape(s, quote=True)


def _md_code(s: str) -> str:
    return re.sub(r"`([^`]+)`", lambda m: f"<code>{m[1]}</code>", _e(s))


def _badge(status: str | None) -> str:
    if not status:
        return '<span class="muted">not checked</span>'
    label, tone = LABEL.get(status, (status, "info"))
    return f'<span class="badge {tone}">{_e(label)}</span>'


def badge_json(row: dict, version: str) -> dict:
    message, color = BADGE.get(row["status"], (row["status"], "lightgrey"))
    return {"schemaVersion": 1, "label": f"pipecat {version}", "message": message, "color": color}


def badge_markdown(row: dict) -> str:
    endpoint = urllib.parse.quote(f"{SITE_URL}/badge/{row['slug']}.json", safe="")
    return f"[![Pipecat status](https://img.shields.io/endpoint?url={endpoint})]({SITE_URL}/i/{row['slug']}/)"


CSS = """
:root { --bg:#fbfaf7; --fg:#1d1d1b; --muted:#6b6a65; --line:#e4e1d8; --card:#ffffff;
  --ok:#1f7a45; --okbg:#e3f3e8; --bad:#b3261e; --badbg:#fbe7e5; --warn:#8a5a00; --warnbg:#fbf0d9;
  --info:#2d5b9a; --infobg:#e5edf8; --accent:#1d1d1b; }
@media (prefers-color-scheme: dark) { :root { --bg:#151513; --fg:#ecebe6; --muted:#9d9b94; --line:#2c2b27; --card:#1c1c19;
  --ok:#7fd19d; --okbg:#173323; --bad:#f2a49c; --badbg:#3a1a17; --warn:#f0c46b; --warnbg:#352a12;
  --info:#9cc0f2; --infobg:#172539; --accent:#ecebe6; } }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--fg); font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif; }
main { max-width:980px; margin:0 auto; padding:40px 16px 64px; }
h1 { font-size:clamp(1.7rem,4vw,2.4rem); line-height:1.15; margin:0 0 12px; letter-spacing:-0.01em; }
h2 { font-size:1.15rem; margin:40px 0 8px; }
p { margin:0 0 12px; }
a { color:inherit; }
.lede { color:var(--muted); max-width:62ch; }
.crumb { font-size:.9rem; color:var(--muted); margin-bottom:16px; display:inline-block; }
.stats { display:flex; gap:12px; flex-wrap:wrap; margin:24px 0; }
.stat { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:12px 16px; min-width:140px; }
.stat b { display:block; font-size:1.6rem; font-variant-numeric:tabular-nums; }
.stat span { color:var(--muted); font-size:.9rem; }
.tools { display:flex; gap:12px; flex-wrap:wrap; align-items:center; margin:8px 0 12px; }
input[type=search] { flex:1 1 240px; padding:10px 12px; border-radius:8px; border:1px solid var(--line); background:var(--card); color:var(--fg); font:inherit; }
label.toggle { color:var(--muted); font-size:.95rem; }
table { width:100%; border-collapse:collapse; background:var(--card); border:1px solid var(--line); border-radius:10px; overflow:hidden; }
th, td { text-align:left; padding:12px 14px; border-bottom:1px solid var(--line); vertical-align:top; }
th { font-size:.85rem; color:var(--muted); font-weight:600; }
tr:last-child td { border-bottom:0; }
.name { font-weight:600; text-decoration:none; } .name:hover { text-decoration:underline; }
.cat { color:var(--muted); font-size:.85rem; }
.why { margin:6px 0 0; font-size:.93rem; }
.badge { display:inline-block; padding:2px 10px; border-radius:999px; font-size:.85rem; white-space:nowrap; font-weight:600; }
.ok { color:var(--ok); background:var(--okbg); } .bad { color:var(--bad); background:var(--badbg); }
.warn { color:var(--warn); background:var(--warnbg); } .info { color:var(--info); background:var(--infobg); }
.muted { color:var(--muted); font-size:.9rem; }
.prs { font-size:.9rem; margin-top:6px; } .prs ul { margin:4px 0 0 18px; padding:0; }
details { margin-top:6px; font-size:.85rem; color:var(--muted); }
code { font-family:ui-monospace,SFMono-Regular,Consolas,monospace; font-size:.88em; }
code.err { display:block; white-space:pre-wrap; word-break:break-word; margin-top:4px; }
pre { background:var(--card); border:1px solid var(--line); border-radius:8px; padding:12px; overflow-x:auto; white-space:pre-wrap; word-break:break-all; }
.repo { display:inline-block; margin-top:6px; font-size:.85rem; color:var(--muted); }
.facts { display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:12px; margin:20px 0; }
.fact { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:14px 16px; }
.fact > span:first-child { display:block; color:var(--muted); font-size:.85rem; margin-bottom:4px; }
.cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:16px; margin-top:12px; }
.card { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:18px; }
.card h3 { margin:0 0 6px; font-size:1.02rem; }
.cta { display:inline-block; margin-top:6px; padding:9px 16px; border-radius:8px; background:var(--accent); color:var(--bg); text-decoration:none; font-weight:600; }
footer { margin-top:48px; color:var(--muted); font-size:.88rem; }
@media (max-width:640px) {
  thead { display:none; } table, tbody, tr, td { display:block; width:100%; }
  tr { border-bottom:1px solid var(--line); } td { border:0; padding:6px 14px; }
  td:first-child { padding-top:14px; } td:last-child { padding-bottom:14px; }
  td.next::before { content:attr(data-label) ": "; color:var(--muted); font-size:.85rem; }
}
"""


def _contact() -> str:
    if CONTACT_EMAIL:
        return f'<a class="cta" href="mailto:{_e(CONTACT_EMAIL)}?subject=Pipecat%20integration">Email me</a>'
    return f'<a class="cta" href="{REPO_URL}/issues/new">Open an issue</a>'


def _footer() -> str:
    merged = " and ".join(f'<a href="{u}">{n}</a>' for n, u in MERGED.items())
    return (
        f'<footer><p>Maintained by <a href="{AUTHOR_URL}">{AUTHOR}</a>, with fixes merged into {merged}. '
        "An independent project, not affiliated with Daily, Deepgram or the Pipecat team.</p></footer>"
    )


def _head(title: str, description: str, canonical: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_e(title)}</title>
<meta name="description" content="{_e(description)}">
<link rel="canonical" href="{_e(canonical)}">
<meta property="og:title" content="{_e(title)}">
<meta property="og:description" content="{_e(description)}">
<meta property="og:url" content="{_e(canonical)}">
<meta property="og:type" content="website">
<style>{CSS}</style>
</head>"""


def _row(r: dict, main_label: str) -> str:
    extra = []
    if r["explain"]:
        extra.append(f'<p class="why">{_md_code(r["explain"])}</p>')
    if r["prs"]:
        links = "".join(f'<li><a href="{_e(p["url"])}">#{p["number"]} {_e(p["title"])}</a></li>' for p in r["prs"][:3])
        extra.append(f'<div class="prs"><span>Fix proposed, waiting for the maintainer:</span><ul>{links}</ul></div>')
    main_cell = _badge(r["main_status"]) if r["main_status"] != r["status"] else '<span class="muted">same</span>'
    return f"""
      <tr data-name="{_e(r["name"].lower())} {_e(r["categories"].lower())}" data-ok="{"1" if r["status"] == "ok" else "0"}">
        <td><a class="name" href="i/{_e(r["slug"])}/">{_e(r["name"])}</a><div class="cat">{_e(r["categories"])}</div>{"".join(extra)}</td>
        <td>{_badge(r["status"])}</td>
        <td class="next" data-label="{_e(main_label)}">{main_cell}</td>
      </tr>"""


def render(latest: dict, main: dict | None, offline: bool = False, rs: list[dict] | None = None) -> str:
    rs = rs if rs is not None else rows(latest, main, offline)
    total = len(rs)
    working = sum(r["status"] == "ok" for r in rs)
    attention = total - working
    date = latest["checked_at"][:10]
    version = latest["pipecat"]
    main_label = f"Next release ({main['pipecat'].split('@')[0]})" if main else "Next release"
    contact = _contact()
    body_rows = "".join(_row(r, main_label) for r in rs)
    title = f"Pipecat integration status: which plugins work with Pipecat {version}"
    description = (
        f"Checked every night: {total} community Pipecat integrations (speech-to-text, text-to-speech, "
        f"LLMs, telephony) against Pipecat {version} and the next release. "
        f"{working} work, {attention} need attention."
    )
    return f"""{_head(title, description, SITE_URL + "/")}
<body>
<main>
  <h1>Pipecat integration status</h1>
  <p class="lede">Every night, each community integration listed in Pipecat's docs is installed with the latest Pipecat release and with the code that becomes the next release, then loaded and checked. Last run {_e(date)}, Pipecat {_e(version)}.</p>

  <div class="stats">
    <div class="stat"><b>{total}</b><span>integrations checked</span></div>
    <div class="stat"><b>{working}</b><span>work on {_e(version)}</span></div>
    <div class="stat"><b>{attention}</b><span>need attention</span></div>
  </div>

  <div class="tools">
    <input type="search" id="q" placeholder="Find a provider, e.g. Gnani, TTS, Asterisk" aria-label="Filter integrations">
    <label class="toggle"><input type="checkbox" id="bad"> Only those needing attention</label>
  </div>

  <table>
    <thead><tr><th>Integration</th><th>Pipecat {_e(version)}</th><th>{_e(main_label)}</th></tr></thead>
    <tbody id="rows">{body_rows}
    </tbody>
  </table>

  <h2>What this checks, and what it doesn't</h2>
  <p>It installs each integration's published package, imports it, and creates every Pipecat service it defines. That catches the usual reasons an integration stops working after a Pipecat upgrade: renamed or removed names, new required methods, version pins, packaging mistakes. It uses no API keys, so it doesn't call the provider's servers: an integration marked "Works" loads and starts, it hasn't been tested on a live call.</p>
  <p>When a release fails, the integration's own repository is checked too, so a fix that's written but not yet released shows as "Fixed, waiting for a release" instead of broken. Each integration has its own page with the full error and a status badge for its README. The code and the raw results are <a href="{REPO_URL}">on GitHub</a>.</p>

  <div class="cards">
    <div class="card">
      <h3>Is your integration on this list?</h3>
      <p>I fix and maintain Pipecat and LiveKit integrations: bring a broken one up to date, add tests, and keep it working as each release lands. This check sees the break the night it happens.</p>
      {contact}
    </div>
    <div class="card">
      <h3>Building a voice agent on Pipecat or LiveKit?</h3>
      <p>Cut-offs, slow replies, phone or SIP trouble, or an integration that won't behave: I work on these inside both frameworks.</p>
      {contact}
    </div>
  </div>

  {_footer()}
</main>
<script>
const q = document.getElementById('q'), bad = document.getElementById('bad');
function filter() {{
  const t = q.value.trim().toLowerCase();
  for (const tr of document.querySelectorAll('#rows tr')) {{
    const hit = !t || tr.dataset.name.includes(t);
    tr.hidden = !hit || (bad.checked && tr.dataset.ok === '1');
  }}
}}
q.addEventListener('input', filter); bad.addEventListener('change', filter);
</script>
</body>
</html>
"""


def render_plugin(r: dict, latest: dict, main: dict | None) -> str:
    version = latest["pipecat"]
    date = latest["checked_at"][:10]
    next_version = "the next release (Pipecat main)" if main else "the next release"
    label = LABEL.get(r["status"], (r["status"], "info"))[0]
    label = label[0].lower() + label[1:]
    name = f"{r['name']} ({r['categories']})" if r.get("dup") else r["name"]
    if r["status"] == "ok":
        title = f"{name} on Pipecat {version}: works"
        description = (
            f"{r['name']} ({r['categories']}) installs, loads and starts with Pipecat {version}. "
            f"Checked every night against the latest release and {next_version}."
        )
    else:
        detail = title_detail(r)
        title = f"{name} on Pipecat {version}: {label}" + (f" ({detail})" if detail else "")
        description = (
            f"{r['explain'] or label} Checked {date} against Pipecat {version}; full error, open fixes and what to do."
        )
    canonical = f"{SITE_URL}/i/{r['slug']}/"

    parts = [f"<p>{_md_code(r['explain'])}</p>" if r["explain"] else ""]
    if r["status"] != "ok" and r["reason"]:
        parts.append(f"<h2>Error from the check</h2><pre><code>{_e(r['reason'])}</code></pre>")
    if r["main_status"] and r["main_status"] != r["status"] and r["main_reason"]:
        parts.append(f"<h2>Error on the next release</h2><pre><code>{_e(r['main_reason'])}</code></pre>")
    if r["prs"]:
        links = "".join(f'<li><a href="{_e(p["url"])}">#{p["number"]} {_e(p["title"])}</a></li>' for p in r["prs"][:5])
        parts.append(f"<h2>Fixes waiting for the maintainer</h2><ul>{links}</ul>")

    links = [f'<a href="{_e(r["docs"])}">Pipecat docs page</a>']
    if r["repo"]:
        links.append(f'<a href="{_e(r["repo"])}">Source repository</a>')
    badge_md = badge_markdown(r)
    badge_img = (
        f"https://img.shields.io/endpoint?url={urllib.parse.quote(SITE_URL + '/badge/' + r['slug'] + '.json', safe='')}"
    )

    return f"""{_head(title, description, canonical)}
<body>
<main>
  <a class="crumb" href="../../">&larr; All Pipecat integrations</a>
  <h1>{_e(r["name"])} and Pipecat {_e(version)}</h1>
  <p class="lede">{_e(r["categories"])}. Checked {_e(date)}.</p>

  <div class="facts">
    <div class="fact"><span>Pipecat {_e(version)}</span>{_badge(r["status"])}</div>
    <div class="fact"><span>Next release (Pipecat main)</span>{_badge(r["main_status"])}</div>
    <div class="fact"><span>Install command</span><code>{_e(r["install"])}</code></div>
  </div>

  {"".join(parts)}
  <p>{" &middot; ".join(links)}</p>

  <h2>Status badge for your README</h2>
  <p><img src="{_e(badge_img)}" alt="Pipecat status for {_e(r["name"])}"></p>
  <p>It updates every night with this check. Paste this into the README:</p>
  <pre><code>{_e(badge_md)}</code></pre>

  <h2>What this checks</h2>
  <p>The published package is installed with Pipecat {_e(version)} and with {_e(next_version)}, imported, and every Pipecat service it defines is created. No API keys are used, so "Works" means it loads and starts, not that it was tested on a live call.</p>

  <div class="cards">
    <div class="card">
      <h3>Maintain {_e(r["name"])}?</h3>
      <p>I fix and maintain Pipecat and LiveKit integrations: bring one up to date, add tests, and keep it working as each release lands.</p>
      {_contact()}
    </div>
  </div>

  {_footer()}
</main>
</body>
</html>
"""


def sitemap(rs: list[dict], date: str) -> str:
    urls = [f"{SITE_URL}/"] + [f"{SITE_URL}/i/{r['slug']}/" for r in rs]
    body = "".join(f"<url><loc>{_e(u)}</loc><lastmod>{date}</lastmod></url>" for u in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>\n'


def build(latest: dict, main: dict | None, offline: bool, out: Path = OUT) -> list[dict]:
    rs = rows(latest, main, offline)
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(render(latest, main, offline, rs), encoding="utf-8")
    for r in rs:
        page = out / "i" / r["slug"]
        page.mkdir(parents=True, exist_ok=True)
        (page / "index.html").write_text(render_plugin(r, latest, main), encoding="utf-8")
        (out / "badge").mkdir(exist_ok=True)
        (out / "badge" / f"{r['slug']}.json").write_text(json.dumps(badge_json(r, latest["pipecat"])), encoding="utf-8")
    (out / "sitemap.xml").write_text(sitemap(rs, latest["checked_at"][:10]), encoding="utf-8")
    # Files served as-is at the site root, such as the Search Console verification file.
    for f in (ROOT / "static").glob("*"):
        if f.is_file():
            (out / f.name).write_bytes(f.read_bytes())
    (out / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n", encoding="utf-8")
    return rs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()
    latest = _load("latest")
    if not latest:
        raise SystemExit("results/latest.json missing")
    rs = build(latest, _load("main"), args.offline)
    print(f"{OUT} written: index, {len(rs)} integration pages, {len(rs)} badges, sitemap")


if __name__ == "__main__":
    main()
