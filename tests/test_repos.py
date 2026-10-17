"""Resolving a plugin to its source repository.

Every case here is one a real plugin produced. The rules matter because the
wrong repository is worse than no repository: it would report a verdict about
somebody else's code under this plugin's name.
"""

from health import repos


def test_metadata_is_preferred_over_the_readme():
    """A declared repository is the maintainer's own answer; a README is inference."""
    info = {
        "name": "pipecat-x",
        "project_urls": {"Repository": "https://github.com/vendor/pipecat-x"},
        "description": "see also https://github.com/vendor/examples",
    }

    assert repos.resolve(info) == "https://github.com/vendor/pipecat-x"


def test_a_clone_line_in_the_readme_is_enough():
    """pipecat-boson declares no Homepage, no Repository and no project_urls.

    Its repository appears nowhere but a `git clone` line in the README, in the
    ssh spelling. Without this fallback the one plugin whose source is already
    fixed is the one that cannot be checked.
    """
    info = {
        "name": "pipecat-boson",
        "project_urls": None,
        "home_page": None,
        "description": "## Install\n\n```\ngit clone git@github.com:boson-ai/pipecat-boson.git\n```\n",
    }

    assert repos.resolve(info) == "https://github.com/boson-ai/pipecat-boson"


def test_a_spec_can_carry_its_own_repository():
    """Pipecat's docs install Maya straight from a tag, so there is nothing to look up."""
    spec = "pipecat-maya @ git+https://github.com/MayaResearch/pipecat-maya.git@v0.1.0"

    assert repos.repo_for_plugin([spec]) == "https://github.com/MayaResearch/pipecat-maya"


def test_the_framework_is_never_taken_for_the_plugin():
    """Every plugin README links pipecat-ai/pipecat. None of them *is* it.

    A community plugin is by definition maintained outside the Pipecat team, so
    a pipecat-ai link is a reference to the framework.
    """
    info = {"name": "pipecat-x", "description": "Built on https://github.com/pipecat-ai/pipecat."}

    assert repos.resolve(info) is None


def test_one_unrelated_link_is_not_a_resolution():
    """A single mention of some other repository is a guess, and guessing here
    would attribute another project's state to this plugin."""
    info = {"name": "pipecat-x", "description": "Thanks to https://github.com/someone/unrelated for the idea."}

    assert repos.resolve(info) is None


def test_a_repeated_link_wins_when_nothing_matches_the_name():
    """A repository the README keeps pointing at is the plugin's own, even when
    its name shares no word with the distribution."""
    info = {
        "name": "traceai-pipecat",
        "description": (
            "docs at https://github.com/vendor/observability-sdk and "
            "issues at https://github.com/vendor/observability-sdk/issues"
        ),
    }

    assert repos.resolve(info) == "https://github.com/vendor/observability-sdk"


def test_site_features_are_not_accounts():
    """github.com/sponsors/x and friends are pages, not repositories."""
    info = {"name": "pipecat-x", "description": "https://github.com/sponsors/vendor https://github.com/sponsors/vendor"}

    assert repos.resolve(info) is None


def test_deeper_paths_are_trimmed_to_the_repository():
    info = {
        "name": "pipecat-x",
        "project_urls": {"Source": "https://github.com/vendor/pipecat-x/tree/main/src"},
    }

    assert repos.resolve(info) == "https://github.com/vendor/pipecat-x"


def test_project_name_drops_extras_and_constraints():
    assert repos.project_name("pipecat-ai[tracing]>=1.11,<1.12") == "pipecat-ai"
    assert repos.project_name("arctan-vi[pipecat]") == "arctan-vi"
    assert repos.project_name("git+https://github.com/a/b") == ""


def test_an_override_answers_for_a_plugin_that_is_not_on_pypi(monkeypatch):
    """Simplismart is not on PyPI under the name its docs give, so no amount of
    metadata reading will find it -- and the source is then the only place its
    state exists at all."""
    monkeypatch.setattr(repos, "repo_for", lambda name: None)

    assert repos.repo_for_plugin(["pipecat-simplismart"]) == ("https://github.com/simpli-smart/pipecat-simplismart")
