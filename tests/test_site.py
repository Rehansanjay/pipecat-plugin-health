from health.site import explain, render


def _p(status, reason="", **kw):
    return {
        "name": "X",
        "install": "uv add pipecat-x",
        "docs": "https://d",
        "categories": ["Text-to-Speech"],
        "status": status,
        "reason": reason,
        **kw,
    }


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
    latest = {
        "pipecat": "1.16.0",
        "checked_at": "2026-11-18T08:00:00Z",
        "plugins": [_p("ok"), dict(_p("broken", "<script>x</script>"), name="Y<b>")],
    }
    page = render(latest, None, offline=True)
    assert "<script>x</script>" not in page and "Y&lt;b&gt;" in page
    assert ">2</b><span>integrations checked" in page and ">1</b><span>need attention" in page


def _latest(*plugins):
    return {"pipecat": "1.16.0", "checked_at": "2026-11-20T08:00:00Z", "plugins": list(plugins)}


def test_same_name_twice_gets_distinct_slugs():
    from health.site import rows

    rs = rows(
        _latest(
            dict(_p("ok"), name="Giggy", categories=["Speech-to-Text"]),
            dict(_p("ok"), name="Giggy", categories=["Text-to-Speech"]),
        ),
        None,
        offline=True,
    )
    assert sorted(r["slug"] for r in rs) == ["giggy-speech-to-text", "giggy-text-to-speech"]


def test_plugin_page_title_carries_the_error_people_search_for():
    from health.site import render_plugin, rows

    latest = _latest(
        dict(
            _p("broken", "import x: ImportError: cannot import name '_NotGiven' from 'pipecat.services.settings'"),
            name="Acme",
        )
    )
    r = rows(latest, None, offline=True)[0]
    page = render_plugin(r, latest, None)
    assert (
        "<title>Acme on Pipecat 1.16.0: doesn&#x27;t load (ImportError: cannot import name &#x27;_NotGiven&#x27;"
        in page
    )
    assert 'rel="canonical"' in page and "/i/acme/" in page


def test_plugin_page_escapes_the_error():
    from health.site import render_plugin, rows

    latest = _latest(dict(_p("broken", "<script>alert(1)</script>"), name="Acme"))
    page = render_plugin(rows(latest, None, offline=True)[0], latest, None)
    assert "<script>alert(1)</script>" not in page


def test_badge_is_a_shields_endpoint():
    from health.site import badge_json, rows

    r = rows(_latest(dict(_p("pinned"), name="Acme")), None, offline=True)[0]
    assert badge_json(r, "1.16.0") == {
        "schemaVersion": 1,
        "label": "pipecat 1.16.0",
        "message": "version pin",
        "color": "orange",
    }


def test_build_writes_pages_badges_and_sitemap(tmp_path):
    from health.site import build

    rs = build(_latest(dict(_p("ok"), name="Acme"), dict(_p("broken", "boom"), name="Beta")), None, True, tmp_path)
    for r in rs:
        assert (tmp_path / "i" / r["slug"] / "index.html").exists()
        assert (tmp_path / "badge" / f"{r['slug']}.json").exists()
    sm = (tmp_path / "sitemap.xml").read_text()
    assert sm.count("<loc>") == 3 and "/i/beta/" in sm
    assert 'href="i/acme/"' in (tmp_path / "index.html").read_text()
