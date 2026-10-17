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
