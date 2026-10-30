import json
import types
from pathlib import Path

import pytest

from health import run
from health.run import BROKEN, GATED, OK, UNRELEASED, _gating_module, classify
from health.sources import Plugin


def _probe(message: str) -> dict:
    """A probe result whose top-level import failed with this message."""
    return {
        "top_level_errors": [{"module": "pipecat_x", "type": "ImportError", "message": message}],
        "abstract_services": [],
        "submodule_errors": [],
        "distributions": ["pipecat-x"],
    }


def test_a_private_vendor_sdk_is_gated_not_broken(monkeypatch):
    """A plugin needing a licensed SDK works for that vendor's customers.

    Calling it broken blames the maintainer for a deliberate distribution
    choice, and no public checker can ever see it pass.
    """
    monkeypatch.setattr("health.run._on_pypi", lambda name: False)

    status, reason = classify(_probe("Missing module: No module named 'hecttor_sdk'"))

    assert status == GATED
    assert "hecttor_sdk" in reason
    assert "not published" in reason


def test_a_missing_but_published_package_is_still_broken(monkeypatch):
    """The package exists on PyPI, so the plugin simply failed to depend on it.

    That is a real fault with a one-line fix, and it must not hide behind the
    gated status.
    """
    monkeypatch.setattr("health.run._on_pypi", lambda name: True)

    status, _ = classify(_probe("No module named 'fireredvad'"))

    assert status == BROKEN


def test_an_unreachable_pypi_does_not_invent_a_gated_plugin(monkeypatch):
    """A network failure answers None, which must read as "don't know".

    Treating it as "not on PyPI" would quietly reclassify broken plugins as
    gated ones whenever the checker ran without a network.
    """
    monkeypatch.setattr("health.run._on_pypi", lambda name: None)

    status, _ = classify(_probe("No module named 'anything'"))

    assert status == BROKEN


def test_a_missing_pipecat_module_is_never_gated(monkeypatch):
    """pipecat is the framework under test, not somebody's private SDK."""
    monkeypatch.setattr("health.run._on_pypi", lambda name: False)

    assert _gating_module("No module named 'pipecat_flows'") is None
    assert _gating_module("No module named 'pipecat'") is None


def test_an_error_that_names_no_module_is_not_gated():
    """The _NotGiven break and friends are breakage, whatever PyPI says."""
    assert _gating_module("cannot import name '_NotGiven' from 'pipecat.services.settings'") is None


# --- the source pass: a fixed plugin with a stale release ---------------------


def _source(result: dict):
    """Stand in for the install-from-git pass, which needs a network and a venv."""

    def fake(plugin, repo, pipecat_req, uv, python, venv, out):
        return {"source_repo": repo, "source_commit": "abc123def456", **result}

    return fake


def _promote(monkeypatch, source: dict, status=BROKEN, reason="import x: ImportError: cannot import name 'y'"):
    monkeypatch.setattr("health.run.repo_for_plugin", lambda specs: "https://github.com/vendor/pipecat-x")
    monkeypatch.setattr("health.run.from_git_head", _source(source))
    monkeypatch.setattr("health.run._run", lambda cmd, timeout: None)
    plugin = Plugin(name="X", specs=["pipecat-x"], install="uv add pipecat-x")
    return run.maybe_from_source(plugin, status, reason, "pipecat-ai==1.12.0", "uv", "python", Path("."))


def test_a_fixed_source_with_a_stale_release_is_unreleased(monkeypatch, tmp_path):
    """boson-ai/pipecat-boson wrapped the 1.8 import weeks before the wheel moved.

    Reporting that as broken blames a maintainer who already did the work, and
    hides the only thing that would help their users: cutting a release.
    """
    found = _promote(monkeypatch, {"source": "fixed", "source_reason": "imports and constructs from source"})

    assert found["status"] == UNRELEASED
    assert "vendor/pipecat-x@abc123def" in found["reason"]
    assert "the release still fails" in found["reason"]
    # the released failure is kept, not replaced by the source verdict
    assert found["released_reason"].startswith("import x:")


def test_a_source_that_is_still_broken_does_not_promote(monkeypatch):
    found = _promote(monkeypatch, {"source": "still_broken", "source_reason": "same ImportError"})

    assert "status" not in found
    assert found["source"] == "still_broken"


def test_a_source_that_cannot_be_read_does_not_promote(monkeypatch):
    """An install that fails for its own reasons is not evidence of a fix."""
    found = _promote(monkeypatch, {"source": "unknown", "source_reason": "could not install from source"})

    assert "status" not in found


def test_a_working_plugin_is_never_rebuilt_from_source(monkeypatch):
    """The extra install only earns its runtime on a failure."""
    monkeypatch.setattr("health.run.repo_for_plugin", lambda specs: pytest.fail("resolved a repo for an ok plugin"))

    plugin = Plugin(name="X", specs=["pipecat-x"], install="uv add pipecat-x")
    assert run.maybe_from_source(plugin, OK, "", "pipecat-ai==1.12.0", "uv", "python", Path(".")) == {}
    assert run.maybe_from_source(plugin, GATED, "", "pipecat-ai==1.12.0", "uv", "python", Path(".")) == {}


def test_a_plugin_whose_repository_is_unknown_is_left_alone(monkeypatch):
    monkeypatch.setattr("health.run.repo_for_plugin", lambda specs: None)
    plugin = Plugin(name="X", specs=["pipecat-x"], install="uv add pipecat-x")

    assert run.maybe_from_source(plugin, BROKEN, "boom", "pipecat-ai==1.12.0", "uv", "python", Path(".")) == {}


def test_a_plausible_but_wrong_repository_cannot_promote(monkeypatch, tmp_path):
    """Supertonic resolves to supertone-inc/supertonic, the vendor's TTS model
    repo, because the names share a word -- not to the pipecat plugin.

    That one fails to install and answers "unknown" anyway. A wrong repository
    that happened to be installable and import cleanly would otherwise promote
    the plugin on the strength of somebody else's code, so the source has to
    have built the distribution this plugin actually is.
    """
    probe = {
        "top_level_errors": [],
        "abstract_services": [],
        "submodule_errors": [],
        "distributions": ["supertonic==1.4.0"],  # not pipecat-supertonic
    }
    out = tmp_path / "probe.json"
    out.write_text(json.dumps(probe), encoding="utf-8")

    monkeypatch.setattr("health.run._head_commit", lambda repo: "deadbeefcafe")
    monkeypatch.setattr("health.run._package_layout", lambda repo, sha: ("ok", "py"))
    monkeypatch.setattr(
        "health.run._run",
        lambda cmd, timeout: types.SimpleNamespace(returncode=0, stderr="", stdout=""),
    )
    plugin = Plugin(name="Supertonic", specs=["pipecat-supertonic"], install="uv add pipecat-supertonic")

    found = run.from_git_head(
        plugin, "https://github.com/supertone-inc/supertonic", "pipecat-ai==1.12.0", "uv", "python", tmp_path, out
    )

    assert found["source"] == "unknown"
    assert "does not build pipecat-supertonic" in found["source_reason"]


def test_the_plugin_s_own_source_is_accepted(monkeypatch, tmp_path):
    """The same path, with the distribution the plugin actually publishes."""
    probe = {
        "top_level_errors": [],
        "abstract_services": [],
        "submodule_errors": [],
        "distributions": ["pipecat_boson==0.1.3"],  # underscore spelling still matches
    }
    out = tmp_path / "probe.json"
    out.write_text(json.dumps(probe), encoding="utf-8")

    monkeypatch.setattr("health.run._head_commit", lambda repo: "0319e5310aaa")
    monkeypatch.setattr("health.run._package_layout", lambda repo, sha: ("ok", ""))
    monkeypatch.setattr(
        "health.run._run",
        lambda cmd, timeout: types.SimpleNamespace(returncode=0, stderr="", stdout=""),
    )
    plugin = Plugin(name="Boson", specs=["pipecat-boson"], install="uv add pipecat-boson")

    found = run.from_git_head(
        plugin, "https://github.com/boson-ai/pipecat-boson", "pipecat-ai==1.12.0", "uv", "python", tmp_path, out
    )

    assert found["source"] == "fixed"
    assert found["source_commit"] == "0319e5310aaa"


# --- reading the repository before trying to install from it ------------------


def _layout(monkeypatch, tmp_path, layout, sha="deadbeefcafe"):
    """Drive from_git_head with the tree read stubbed and the install recorded."""
    calls = []
    monkeypatch.setattr("health.run._head_commit", lambda repo: sha)
    monkeypatch.setattr("health.run._package_layout", lambda repo, s_: layout)

    def record(cmd, timeout):
        calls.append(cmd)
        return types.SimpleNamespace(returncode=0, stderr="", stdout="")

    monkeypatch.setattr("health.run._run", record)
    probe = {"top_level_errors": [], "abstract_services": [], "submodule_errors": [], "distributions": ["pipecat_x==1.0"]}
    out = tmp_path / "probe.json"
    out.write_text(json.dumps(probe), encoding="utf-8")
    plugin = Plugin(name="X", specs=["pipecat-x"], install="uv add pipecat-x")
    found = run.from_git_head(plugin, "https://github.com/vendor/pipecat-x", "pipecat-ai==1.12.0", "uv", "python", tmp_path, out)
    return found, calls


def test_a_package_in_a_subdirectory_is_installed_from_it(monkeypatch, tmp_path):
    """supertone-inc/supertonic keeps its package in py/, and a plain
    git+<url> answers 'does not appear to be a Python project'."""
    found, calls = _layout(monkeypatch, tmp_path, ("ok", "py"))

    requirement = next(arg for cmd in calls for arg in cmd if str(arg).startswith("git+"))
    assert requirement.endswith("#subdirectory=py")
    assert found["source"] == "fixed"


def test_a_repository_with_no_packaging_metadata_is_unpackaged_not_unknown(monkeypatch, tmp_path):
    """hakim-pipecat and pipecat-upliftai-stt ship a working module and no
    pyproject.toml, while Pipecat's docs publish 'uv add' for both. That is a
    fact about the repository, and the only thing worth reporting."""
    found, calls = _layout(monkeypatch, tmp_path, ("unpackaged", ""))

    assert found["source"] == "unpackaged"
    assert "nothing to install" in found["source_reason"]
    assert calls == [], "a repository with no package must not be installed from"


def test_a_repository_that_cannot_be_read_is_never_cloned(monkeypatch, tmp_path):
    """pipecat-firered-vad resolves to your-username/pipecat-firered-vad, a
    placeholder in its README. Cloning a 404 makes git ask for credentials and
    burns the install timeout every night."""
    found, calls = _layout(monkeypatch, tmp_path, ("ok", ""), sha=None)

    assert found["source"] == "unknown"
    assert "missing, private or renamed" in found["source_reason"]
    assert calls == []


def test_an_unlistable_tree_is_unknown_rather_than_a_verdict(monkeypatch, tmp_path):
    """A rate-limited or flaky API call must not be read as evidence."""
    found, calls = _layout(monkeypatch, tmp_path, ("unreadable", ""))

    assert found["source"] == "unknown"
    assert calls == []
