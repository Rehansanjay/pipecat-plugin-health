from health.run import BROKEN, GATED, _gating_module, classify


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
