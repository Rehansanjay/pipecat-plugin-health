from health.site import explain, render


def _p(status, reason="", **kw):
    return {"name": "X", "install": "uv add pipecat-x", "docs": "https://d", "categories": ["Text-to-Speech"],
            "status": status, "reason": reason, **kw}


def test_explains_a_removed_pipecat_name():
    s = explain(_p("broken", "import x: ImportError: cannot import name '_NotGiven' from 'pipecat.services.settings'"))
    assert "`_NotGiven`" in s and s.startswith("Doesn't load")


def test_pin_that_hides_working_code_says_so():
    assert "only the version range" in explain(_p("pinned", "pins pipecat-ai==1.8.1", pin="compatible"))


def test_unpackaged_repo_is_a_packaging_problem():
    assert "pyproject.toml" in explain(_p("uninstallable", source="unpackaged"))


def test_licensed_sdk_is_not_called_a_fault():
    assert "Not a fault" in explain(_p("gated"))


def test_render_escapes_and_counts_offline():
    latest = {"pipecat": "1.16.0", "checked_at": "2026-11-18T08:00:00Z",
              "plugins": [_p("ok"), dict(_p("broken", "<script>x</script>"), name="Y<b>")]}
    page = render(latest, None, offline=True)
    assert "<script>x</script>" not in page and "Y&lt;b&gt;" in page
    assert ">2</b><span>integrations checked" in page and ">1</b><span>need attention" in page
