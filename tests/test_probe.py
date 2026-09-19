from health.probe import installed_modules


class FakeDist:
    def __init__(self, files):
        self.files = files


def test_regular_package():
    dist = FakeDist(["pipecat_anam/__init__.py", "pipecat_anam/transport.py", "pipecat_anam-0.1.0.dist-info/RECORD"])
    assert installed_modules(dist) == (["pipecat_anam"], ["pipecat_anam.transport"])


def test_namespace_package_without_init_is_rooted_at_the_package():
    # A failing optional module must not be mistaken for the plugin failing to import.
    dist = FakeDist(["pipecat_bey/transport.py", "pipecat_bey/utils.py"])
    assert installed_modules(dist) == (["pipecat_bey"], ["pipecat_bey.transport", "pipecat_bey.utils"])


def test_plugin_installed_into_pipecats_namespace_only_checks_its_own_files():
    dist = FakeDist(["pipecat/services/pinch/__init__.py", "pipecat/services/pinch/translate.py"])
    assert installed_modules(dist) == (["pipecat.services.pinch"], ["pipecat.services.pinch.translate"])


def test_tests_and_examples_are_skipped():
    dist = FakeDist(["finch.py", "tests/test_x.py", "finchpkg/__init__.py", "finchpkg/examples/demo.py"])
    assert installed_modules(dist) == (["finch", "finchpkg"], [])
