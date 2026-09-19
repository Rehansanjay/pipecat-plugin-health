"""Runs inside a plugin's own virtualenv and reports whether the plugin loads.

Usage: python probe.py <output.json> <requested spec> [<requested spec> ...]

Two checks, both needing no API keys:

1. Import: every top-level package the plugin installs, then each of its
   submodules. A failing top-level import means nobody can use the plugin.
2. Abstract services: every pipecat FrameProcessor subclass the plugin defines
   must be instantiable, i.e. implement all abstract methods its pipecat base
   class declares. When pipecat adds one, plugins break at construction.

The script only uses the standard library besides pipecat itself, and never
lets an exception escape: the result file is always written.
"""

from __future__ import annotations

import importlib
import importlib.metadata as md
import inspect
import json
import re
import sys
import warnings

SKIP_SUBMODULES = re.compile(r"(^|\.)(tests?|examples?|docs?|conftest|__main__)(\.|$)")


def _canon(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _requested_names(specs: list[str]) -> set[str]:
    names = set()
    for spec in specs:
        if "://" in spec and " @ " not in spec:
            continue  # bare VCS URL, the name is only known after install
        m = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", spec)
        if m:
            names.add(_canon(m.group(1)))
    return names


def plugin_distributions(specs: list[str]) -> list[tuple[md.Distribution, bool]]:
    """Installed distributions that make up the plugin, each with whether it depends on pipecat-ai.

    Anything the user asked for by name (other than pipecat-ai itself), plus any
    installed distribution that depends on pipecat-ai (covers VCS installs).
    """
    wanted = _requested_names(specs) - {"pipecat-ai"}
    found = {}
    for dist in md.distributions():
        name = _canon(dist.metadata["Name"] or "")
        if not name or name == "pipecat-ai":
            continue
        requires = [_canon(re.split(r"[ ;<>=!~\[(]", r, maxsplit=1)[0]) for r in (dist.requires or [])]
        on_pipecat = "pipecat-ai" in requires
        if name in wanted or on_pipecat:
            found[name] = (dist, on_pipecat)
    return list(found.values())


def installed_modules(dist: md.Distribution) -> tuple[list[str], list[str]]:
    """(roots, submodules): the importable modules made from the files this distribution installed.

    Built from the file list rather than by walking packages, so a plugin that
    installs into pipecat's own namespace (pipecat/services/foo/...) is checked
    without also importing the rest of pipecat. A root is a module whose parent
    package the distribution didn't install itself.
    """
    names = set()
    for f in dist.files or []:
        parts = str(f).replace("\\", "/").split("/")
        if parts[0] in ("..", "") or parts[0].endswith((".dist-info", ".data")) or not parts[-1].endswith(".py"):
            continue
        parts[-1] = parts[-1][:-3]
        if parts[-1] == "__init__":
            parts.pop()
        if parts and all(p.isidentifier() for p in parts):
            names.add(".".join(parts))
    names = {n for n in names if not SKIP_SUBMODULES.search(n) and not n.startswith("_virtualenv")}
    roots = set()
    for name in names:
        if name.rpartition(".")[0] in names:
            continue
        top = name.split(".")[0]
        # pipecat_bey/transport.py with no pipecat_bey/__init__.py is a namespace package
        # of the plugin's own: import pipecat_bey as the root, check transport as a submodule.
        # pipecat's own namespace belongs to the host, so modules installed into it stay roots.
        roots.add(name if top == "pipecat" else top)
    return sorted(roots), sorted(names - roots)


_LOCAL_PATH = re.compile(r" \((?:[A-Za-z]:\\|/)[^)]*\)")


def _error(module: str, exc: BaseException) -> dict:
    message = str(exc).splitlines()[0] if str(exc) else ""
    return {
        "module": module,
        "type": type(exc).__name__,
        "message": _LOCAL_PATH.sub("", message)[:300],
    }


def main(out_path: str, specs: list[str]) -> None:
    warnings.filterwarnings("ignore")
    result: dict = {
        "pipecat": None,
        "distributions": [],
        "packages": [],
        "top_level_errors": [],
        "submodule_errors": [],
        "services": [],
        "abstract_services": [],
    }
    try:
        result["pipecat"] = md.version("pipecat-ai")
        from pipecat.processors.frame_processor import FrameProcessor

        dists = plugin_distributions(specs)
        result["distributions"] = [f"{d.metadata['Name']}=={d.version}" for d, _ in dists]
        modules = []
        for dist, on_pipecat in dists:
            roots, submodules = installed_modules(dist)
            result["packages"] += roots
            imported_roots = []
            for name in roots:
                try:
                    modules.append(importlib.import_module(name))
                    imported_roots.append(name)
                except BaseException as exc:  # noqa: BLE001 - a plugin can raise anything on import
                    result["top_level_errors"].append(_error(name, exc))
            if not on_pipecat:
                # A general-purpose package listed alongside (e.g. mlflow): importing
                # it is the check; its hundreds of submodules are not a pipecat plugin.
                continue
            for name in submodules:
                if not any(name.startswith(root + ".") for root in imported_roots):
                    continue  # its package already failed to import
                try:
                    modules.append(importlib.import_module(name))
                except BaseException as exc:  # noqa: BLE001
                    result["submodule_errors"].append(_error(name, exc))

        seen = set()
        for mod in modules:
            for obj in vars(mod).values():
                if not (inspect.isclass(obj) and obj.__module__ == mod.__name__):
                    continue
                if not issubclass(obj, FrameProcessor) or obj in seen:
                    continue
                seen.add(obj)
                qual = f"{obj.__module__}.{obj.__qualname__}"
                result["services"].append(qual)
                # Classes named Base*/Abstract* are meant to be subclassed.
                if inspect.isabstract(obj) and not re.match(r"_?(Base|Abstract)", obj.__name__):
                    result["abstract_services"].append({"class": qual, "missing": sorted(obj.__abstractmethods__)})
    except BaseException as exc:  # noqa: BLE001
        result["top_level_errors"].append(_error("<probe>", exc))

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
