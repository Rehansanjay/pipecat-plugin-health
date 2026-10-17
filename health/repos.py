"""Find the source repository a plugin is published from.

The released wheel is not the truth. A maintainer can fix a plugin and never cut
a release: ``boson-ai/pipecat-boson`` has had the pipecat 1.8 import wrapped on
``main`` since 2026-09-30, while PyPI still serves 0.1.3 from before it. A
checker that only installs from PyPI calls that broken, which is both wrong and
the wrong message to send someone who has already done the work -- and it hides
the one thing that would help their users, which is a release.

PyPI metadata cannot be relied on for this. ``pipecat-boson`` declares no
Homepage, no Repository and no ``project_urls`` at all; the only mention of its
repository anywhere is a ``git clone`` line in the README. So the metadata is
read first and the README text is the fallback.

Everything here is a pure function over the PyPI payload except
:func:`repo_for`, so the resolution rules can be tested without a network.
"""

from __future__ import annotations

import functools
import json
import re
import urllib.error
import urllib.request
from collections import Counter

_UA = "pipecat-plugin-health"

# github.com/owner/repo in either the web or the ssh spelling, stopping before
# any deeper path (/tree/main, /issues) and dropping a trailing .git.
_GITHUB = re.compile(
    r"(?:https?://(?:www\.)?github\.com/|git@github\.com:)"
    r"(?P<owner>[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)/"
    # The delimiter set has to include @ and #: a requirement can pin a VCS ref
    # (``...pipecat-maya.git@v0.1.0``) or carry an egg fragment after the path.
    r"(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?(?=[/)\]\s\"'>,;@#&]|$)"
)

# First path segments on github.com that are site features rather than accounts.
_NOT_AN_ACCOUNT = frozenset(
    {
        "about",
        "apps",
        "collections",
        "contact",
        "customer-stories",
        "enterprise",
        "explore",
        "features",
        "login",
        "marketplace",
        "new",
        "notifications",
        "orgs",
        "pricing",
        "pulls",
        "readme",
        "search",
        "security",
        "settings",
        "sponsors",
        "topics",
        "trending",
        "users",
    }
)

# The framework and its own infrastructure. A community plugin is by definition
# maintained outside the Pipecat team, so a pipecat-ai link in a README is a
# reference to the framework, never the plugin's own source.
_NOT_THE_PLUGIN = frozenset({"pipecat-ai", "badges", "shields", "img", "actions", "astral-sh"})

_URL_KEYS = ("source", "source code", "repository", "repo", "code", "github", "homepage", "home")


def _normalise(owner: str, repo: str) -> str:
    return f"https://github.com/{owner}/{repo}"


def _candidates(text: str) -> list[tuple[str, str]]:
    """Every plausible owner/repo pair in a block of text, in order of appearance."""
    found = []
    for match in _GITHUB.finditer(text or ""):
        owner, repo = match["owner"], match["repo"].removesuffix(".git")
        if owner.lower() in _NOT_AN_ACCOUNT or owner.lower() in _NOT_THE_PLUGIN:
            continue
        if not repo or repo in {".", ".."}:
            continue
        found.append((owner, repo))
    return found


def _tokens(name: str) -> set[str]:
    return {t for t in re.split(r"[-_.]+", name.lower()) if t and t != "pipecat"}


def _pick(candidates: list[tuple[str, str]], project: str) -> str | None:
    """Choose the repository that is most likely the plugin's own.

    A README links plenty of repositories -- the framework, examples, whatever
    the vendor also ships -- so appearing is not enough. A repository whose
    name shares a distinguishing word with the distribution is preferred
    ("pipecat-boson" -> boson-ai/pipecat-boson), and only when nothing matches
    does the most frequently linked repository win.
    """
    if not candidates:
        return None

    wanted = _tokens(project)
    for owner, repo in candidates:
        if _tokens(repo) & wanted:
            return _normalise(owner, repo)

    ranked = Counter(candidates).most_common()
    top, count = ranked[0]
    # A single mention of something unrelated is a guess, not a resolution.
    if count < 2:
        return None
    return _normalise(*top)


def repo_from_metadata(info: dict) -> str | None:
    """A repository declared in project_urls or home_page, if there is one."""
    urls = info.get("project_urls") or {}
    ordered = sorted(
        urls.items(),
        key=lambda kv: next((i for i, k in enumerate(_URL_KEYS) if k == kv[0].strip().lower()), len(_URL_KEYS)),
    )
    for _label, url in ordered:
        found = _candidates(url or "")
        if found:
            return _normalise(*found[0])
    found = _candidates(info.get("home_page") or "")
    return _normalise(*found[0]) if found else None


def repo_from_readme(info: dict) -> str | None:
    """A repository mentioned in the long description, when the metadata has none."""
    return _pick(_candidates(info.get("description") or ""), info.get("name") or "")


def resolve(info: dict) -> str | None:
    """The plugin's source repository, from metadata first and the README second."""
    return repo_from_metadata(info) or repo_from_readme(info)


def project_name(spec: str) -> str:
    """The distribution name in a requirement spec: 'pipecat-x[all]>=1,<2' -> 'pipecat-x'."""
    spec = spec.strip()
    if spec.startswith("git+") or "://" in spec:
        return ""
    return re.split(r"[\[<>=!~;\s]", spec, maxsplit=1)[0]


@functools.lru_cache(maxsize=256)
def repo_for(project: str) -> str | None:
    """Resolve one PyPI project to a GitHub repository. None when it cannot be found."""
    if not project:
        return None
    request = urllib.request.Request(f"https://pypi.org/pypi/{project}/json", headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(request, timeout=30) as resp:
            info = json.load(resp)["info"]
    except (urllib.error.URLError, OSError, ValueError, KeyError):
        return None
    return resolve(info)


# Plugins whose repository cannot be resolved from PyPI, and is known from the
# install command Pipecat's docs publish. Simplismart is not on PyPI at all
# under the name its docs give, and pipecat-moss carries neither project_urls
# nor a repository link in its README -- so for these two the source is the
# only place their state can be read at all.
OVERRIDES = {
    "pipecat-moss": "https://github.com/usemoss/pipecat-moss",
    "pipecat-simplismart": "https://github.com/simpli-smart/pipecat-simplismart",
}


def repo_for_plugin(specs: list[str]) -> str | None:
    """The repository of the first spec that resolves to one.

    A spec can carry its own VCS URL -- Pipecat's docs install Maya as
    ``pipecat-maya @ git+https://github.com/MayaResearch/pipecat-maya.git@v0.1.0``
    -- in which case there is nothing to look up.
    """
    for spec in specs:
        if "git+" in spec:
            found = _candidates(spec)
            if found:
                return _normalise(*found[0])
    for spec in specs:
        name = project_name(spec)
        if name in OVERRIDES:
            return OVERRIDES[name]
        repo = repo_for(name)
        if repo:
            return repo
    return None
