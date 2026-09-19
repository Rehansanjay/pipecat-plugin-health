from health.sources import install_specs, parse

PAGE = """\
## Speech-to-Text

| Service | Install | Maintained by |
|---|---|---|
| [Deepgram](/api-reference/server/services/stt/deepgram) | `uv add "pipecat-ai[deepgram]"` | Pipecat |
| [Gnani](/api-reference/server/services/stt/gnani)       | `uv add pipecat-gnani`         | Community  |
| [Hakim](/api-reference/server/services/stt/hakim) | `uv pip install git+https://github.com/tryHakimAI/hakim-pipecat.git` | Community |

## Text-to-Speech

| [Gnani](/api-reference/server/services/tts/gnani)       | `uv add pipecat-gnani`         | Community  |
| [Maya](/api-reference/server/services/tts/maya) | `uv add "pipecat-maya @ git+https://github.com/MayaResearch/pipecat-maya.git@v0.1.0"` | Community |
"""


def test_only_community_rows_are_kept_and_merged_across_categories():
    plugins = {p.name: p for p in parse(PAGE)}

    assert set(plugins) == {"Gnani", "Hakim", "Maya"}
    assert plugins["Gnani"].categories == ["Speech-to-Text", "Text-to-Speech"]
    assert plugins["Gnani"].docs == "https://docs.pipecat.ai/api-reference/server/services/stt/gnani"


def test_install_commands_become_pip_specs():
    assert install_specs("uv add pipecat-gnani") == ["pipecat-gnani"]
    assert install_specs('uv add "pipecat-ai[tracing]" mlflow') == ["pipecat-ai[tracing]", "mlflow"]
    assert install_specs("uv pip install git+https://github.com/a/b.git") == ["git+https://github.com/a/b.git"]
    assert install_specs('uv add "pipecat-oruk==0.1.0rc1"') == ["pipecat-oruk==0.1.0rc1"]
    assert install_specs('uv add "pipecat-maya @ git+https://x/y.git@v0.1.0"') == [
        "pipecat-maya @ git+https://x/y.git@v0.1.0"
    ]
