"""Read the community-maintained plugins listed in Pipecat's docs.

The source of truth is the "Supported Services" table in pipecat-ai/docs. Every
row marked ``Community`` is a plugin owned by someone outside the Pipecat team,
with the install command its maintainers published.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import urllib.request
from dataclasses import dataclass, field
from typing import Any

DOCS_REPO = "pipecat-ai/docs"
DOCS_PATH = "api-reference/server/services/supported-services.mdx"
_USER_AGENT = "pipecat-plugin-health"

_ROW = re.compile(
    r"^\|\s*\[(?P<name>[^\]]+)\]\((?P<link>[^)]+)\)\s*\|\s*`(?P<cmd>[^`]+)`\s*\|\s*(?P<owner>\w+)\s*\|\s*$"
)
_HEADING = re.compile(r"^##\s+(?P<title>.+?)\s*$")


@dataclass
class Plugin:
    name: str
    specs: list[str]
    install: str
    categories: list[str] = field(default_factory=list)
    docs: str = ""

    @property
    def key(self) -> str:
        return " ".join(self.specs)


def github_api(url: str) -> Any:
    """Read one GitHub API endpoint, authenticated whenever a token is around.

    Unauthenticated callers get sixty requests an hour *per IP*, and Actions
    runners share outbound addresses with every other job on the pool. So the
    nightly fails whenever somebody else has spent that budget first -- not
    every night, just often enough to look random (2026-10-06, 2026-10-10).
    A token raises the ceiling to a thousand an hour for the repository, which
    two calls a night will never come near.
    """
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=30) as resp:
        return json.load(resp)


def fetch_docs() -> tuple[str, str]:
    """Return (commit sha, file text) for the supported-services page on main."""
    api = f"https://api.github.com/repos/{DOCS_REPO}/commits?path={DOCS_PATH}&per_page=1"
    sha = github_api(api)[0]["sha"]
    # raw.githubusercontent.com is a CDN rather than the API, and is not
    # metered the same way, so this one stays as it is.
    raw = f"https://raw.githubusercontent.com/{DOCS_REPO}/{sha}/{DOCS_PATH}"
    with urllib.request.urlopen(raw, timeout=30) as resp:
        return sha, resp.read().decode("utf-8")


def install_specs(cmd: str) -> list[str]:
    """Turn a published install command into pip requirement specs.

    ``uv add pipecat-gnani`` -> ["pipecat-gnani"]
    ``uv pip install git+https://...`` -> ["git+https://..."]
    ``uv add "pipecat-ai[tracing]" mlflow`` -> ["pipecat-ai[tracing]", "mlflow"]
    """
    words = shlex.split(cmd)
    if words[:2] == ["uv", "add"]:
        rest = words[2:]
    elif words[:3] == ["uv", "pip", "install"]:
        rest = words[3:]
    elif words[:2] == ["pip", "install"]:
        rest = words[2:]
    else:
        raise ValueError(f"unrecognised install command: {cmd}")
    return [w for w in rest if not w.startswith("-")]


def parse(text: str) -> list[Plugin]:
    """Community rows from the page, merged when one package serves several categories."""
    plugins: dict[str, Plugin] = {}
    category = ""
    for line in text.splitlines():
        heading = _HEADING.match(line)
        if heading:
            category = heading["title"]
            continue
        row = _ROW.match(line.strip())
        if not row or row["owner"] != "Community":
            continue
        specs = install_specs(row["cmd"])
        plugin = Plugin(
            name=row["name"],
            specs=specs,
            install=row["cmd"],
            docs="https://docs.pipecat.ai" + row["link"],
        )
        existing = plugins.setdefault(plugin.key, plugin)
        if category and category not in existing.categories:
            existing.categories.append(category)
    return list(plugins.values())


if __name__ == "__main__":
    sha, text = fetch_docs()
    found = parse(text)
    print(f"docs {sha[:7]}: {len(found)} community plugins")
    for p in found:
        print(f"  {p.name:<28} {', '.join(p.categories):<40} {p.key}")
