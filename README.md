# Pipecat plugin health

Every night this repo installs each **community-maintained plugin** listed in
[Pipecat's supported services](https://docs.pipecat.ai/api-reference/server/services/supported-services)
into a fresh environment, together with:

- the **latest pipecat-ai release** on PyPI, which is what a new user gets today, and
- **pipecat-ai `main`**, which is what users will get in the next release. A plugin
  that breaks here can be fixed before the release ships.

It then imports the plugin and checks that every Pipecat service class it defines
can still be created. No API keys are used, so this catches install, import and
API-shape breakage (renamed or removed Pipecat names, new abstract methods, version
pins), not problems talking to a provider's servers.

The plugin list is read from the docs on every run, so new plugins are picked up
automatically.

## Status

- **pipecat-ai 1.11.0** (2026-09-19): 36 works, 2 partial, 10 broken, 5 needs older pipecat, 3 can't install

| Plugin | Category | pipecat 1.11.0 | Why |
|---|---|---|---|
| [AwaazAI](https://docs.pipecat.ai/api-reference/server/services/serializers/awaazai) | Serializers | ❌ broken | import pipecat_awaazai: ImportError: cannot import name 'StartInterruptionFrame' from 'pipecat.frames.frames' |
| [FIRE RED VAD](https://docs.pipecat.ai/api-reference/server/services/vad/fire-vad) | VAD | ❌ broken | import pipecat_firered_vad: ModuleNotFoundError: FireRedVAD is not installed. |
| [Gnani](https://docs.pipecat.ai/api-reference/server/services/stt/gnani) | Speech-to-Text, Text-to-Speech | ❌ broken | import pipecat_gnani: ImportError: cannot import name '_NotGiven' from 'pipecat.services.settings' |
| [Hecttor](https://docs.pipecat.ai/api-reference/server/services/audio-filters/hecttor) | Audio Filters | ❌ broken | import pipecat_hecttor: ImportError: Missing module: No module named 'hecttor_sdk' |
| [Moss](https://docs.pipecat.ai/api-reference/server/services/knowledge-retrieval/moss) | Knowledge Retrieval | ❌ broken | import pipecat_moss: ImportError: cannot import name 'LLMMessagesFrame' from 'pipecat.frames.frames' |
| [Replicate](https://docs.pipecat.ai/api-reference/server/services/image-generation/replicate) | Image Generation | ❌ broken | import pipecat_replicate: ImportError: cannot import name '_NotGiven' from 'pipecat.services.settings' |
| [Respeecher](https://docs.pipecat.ai/api-reference/server/services/tts/respeecher) | Text-to-Speech | ❌ broken | import pipecat_respeecher: ImportError: cannot import name '_NotGiven' from 'pipecat.services.settings' |
| [Rumik AI](https://docs.pipecat.ai/api-reference/server/services/tts/rumik) | Text-to-Speech | ❌ broken | import pipecat_rumik: ImportError: cannot import name '_NotGiven' from 'pipecat.services.settings' |
| [SonexLabs](https://docs.pipecat.ai/api-reference/server/services/tts/sonex) | Text-to-Speech | ❌ broken | import pipecat_sonex: ImportError: cannot import name '_NotGiven' from 'pipecat.services.settings' |
| [Supertonic](https://docs.pipecat.ai/api-reference/server/services/tts/supertonic) | Text-to-Speech | ❌ broken | import pipecat_supertonic: ImportError: cannot import name '_NotGiven' from 'pipecat.services.settings' |
| [Deepdub](https://docs.pipecat.ai/api-reference/server/services/tts/deepdub) | Text-to-Speech | 📌 needs older pipecat | pins pipecat-ai>=0.0.97,<0.1.0 |
| [Maya](https://docs.pipecat.ai/api-reference/server/services/tts/maya) | Text-to-Speech | 📌 needs older pipecat | pins pipecat-ai==1.8.1 |
| [Oruk](https://docs.pipecat.ai/api-reference/server/services/stt/oruk) | Speech-to-Text | 📌 needs older pipecat | pins pipecat-ai>=1.8.1,<1.9 |
| [Roark](https://docs.pipecat.ai/api-reference/server/services/analytics/roark) | Analytics & Monitoring | 📌 needs older pipecat | pins pipecat-ai>=0.0.40,<1; pipecat-ai>=0.0.104,<1 |
| [Wavix](https://docs.pipecat.ai/api-reference/server/services/serializers/wavix) | Serializers | 📌 needs older pipecat | pins pipecat-ai[deepgram]==0.0.105 |
| [Hakim](https://docs.pipecat.ai/api-reference/server/services/stt/hakim) | Speech-to-Text, Text-to-Speech | ⛔ can't install | <checkout> does not appear to be a Python project, as neither `pyproject.toml` nor `setup.py` are present in the directory |
| [Simplismart](https://docs.pipecat.ai/api-reference/server/services/llm/simplismart) | Large Language Models, Speech-to-Text, Text-to-Speech | ⛔ can't install | Because pipecat-simplismart was not found in the package registry and you require pipecat-simplismart, we can conclude that your requirements are unsatisfiable. |
| [Uplift AI](https://docs.pipecat.ai/api-reference/server/services/stt/upliftai) | Speech-to-Text | ⛔ can't install | <checkout> does not appear to be a Python project, as neither `pyproject.toml` nor `setup.py` are present in the directory |
| [Boson Higgs Realtime](https://docs.pipecat.ai/api-reference/server/services/s2s/boson) | Realtime LLM | 🟡 partial | import pipecat_boson.realtime.llm: ImportError: cannot import name 'assert_given' from 'pipecat.services.settings' |
| [Finchvox](https://docs.pipecat.ai/api-reference/server/services/analytics/finchvox) | Analytics & Monitoring | 🟡 partial | import finchvox.audio_recorder: ModuleNotFoundError: No module named 'pipecat.utils.tracing.conversation_context_provider' |
| [Acefone](https://docs.pipecat.ai/api-reference/server/services/serializers/acefone) | Serializers | ✅ works |  |
| [Anam](https://docs.pipecat.ai/api-reference/server/services/video/anam) | Video | ✅ works |  |
| [Anannas AI](https://docs.pipecat.ai/api-reference/server/services/llm/anannas) | Large Language Models | ✅ works |  |
| [Arctan](https://docs.pipecat.ai/api-reference/server/services/audio-filters/arctan) | Audio Filters | ✅ works |  |
| [Asterisk](https://docs.pipecat.ai/api-reference/server/services/serializers/asterisk) | Serializers | ✅ works |  |
| [Bandwidth](https://docs.pipecat.ai/api-reference/server/services/serializers/bandwidth) | Serializers | ✅ works |  |
| [Beyond Presence](https://docs.pipecat.ai/api-reference/server/services/transport/beyond-presence) | Transports | ✅ works |  |
| [Floe](https://docs.pipecat.ai/api-reference/server/services/llm/floe) | Large Language Models, Speech-to-Text, Text-to-Speech | ✅ works |  |
| [floe-guard](https://docs.pipecat.ai/api-reference/server/services/analytics/floe) | Analytics & Monitoring | ✅ works |  |
| [Future AGI](https://docs.pipecat.ai/api-reference/server/services/analytics/future-agi) | Analytics & Monitoring | ✅ works |  |
| [Gandr](https://docs.pipecat.ai/api-reference/server/services/tts/gandr) | Text-to-Speech | ✅ works |  |
| [Lokutor](https://docs.pipecat.ai/api-reference/server/services/tts/lokutor) | Text-to-Speech | ✅ works |  |
| [MCP](https://docs.pipecat.ai/api-reference/server/services/transport/mcp) | Transports | ✅ works |  |
| [MemorySync](https://docs.pipecat.ai/api-reference/server/services/memory/memorysync) | Memory | ✅ works |  |
| [MLflow](https://docs.pipecat.ai/api-reference/server/services/analytics/mlflow) | Analytics & Monitoring | ✅ works |  |
| [Murf AI](https://docs.pipecat.ai/api-reference/server/services/tts/murf) | Text-to-Speech | ✅ works |  |
| [Noveum Trace](https://docs.pipecat.ai/api-reference/server/services/analytics/noveum-trace) | Analytics & Monitoring | ✅ works |  |
| [OpenInference](https://docs.pipecat.ai/api-reference/server/services/analytics/openinference) | Analytics & Monitoring | ✅ works |  |
| [Pinch](https://docs.pipecat.ai/api-reference/server/services/translation/pinch) | Translation | ✅ works |  |
| [Pipecat Backchannel](https://docs.pipecat.ai/api-reference/server/extensions/pipecat-backchannel) | Extensions | ✅ works |  |
| [Pipecat TTS Cache](https://docs.pipecat.ai/api-reference/server/services/tts/tts-cache) | Text-to-Speech | ✅ works |  |
| [pipecat-effects](https://docs.pipecat.ai/api-reference/server/services/audio-filters/pipecat-effects) | Audio Filters | ✅ works |  |
| [Protoface](https://docs.pipecat.ai/api-reference/server/services/video/protoface) | Video | ✅ works |  |
| [Quickdial](https://docs.pipecat.ai/api-reference/server/services/stt/quickdial) | Speech-to-Text, Text-to-Speech | ✅ works |  |
| [Ringg AI](https://docs.pipecat.ai/api-reference/server/services/stt/ringg) | Speech-to-Text | ✅ works |  |
| [SILMA AI](https://docs.pipecat.ai/api-reference/server/services/tts/silma) | Text-to-Speech | ✅ works |  |
| [SLNG](https://docs.pipecat.ai/api-reference/server/services/stt/slng) | Speech-to-Text, Text-to-Speech | ✅ works |  |
| [SmolVLM](https://docs.pipecat.ai/api-reference/server/services/vision/smolvlm) | Vision | ✅ works |  |
| [Synap](https://docs.pipecat.ai/api-reference/server/services/memory/synap) | Memory | ✅ works |  |
| [TEN VAD](https://docs.pipecat.ai/api-reference/server/services/vad/ten-vad) | VAD | ✅ works |  |
| [ThunderPhone](https://docs.pipecat.ai/api-reference/server/services/s2s/thunderphone) | Realtime LLM | ✅ works |  |
| [Typecast](https://docs.pipecat.ai/api-reference/server/services/tts/typecast) | Text-to-Speech | ✅ works |  |
| [Uplift AI](https://docs.pipecat.ai/api-reference/server/services/tts/upliftai) | Text-to-Speech | ✅ works |  |
| [Vakyam AI](https://docs.pipecat.ai/api-reference/server/services/tts/vakyam) | Text-to-Speech | ✅ works |  |
| [Voice.ai](https://docs.pipecat.ai/api-reference/server/services/tts/voiceai) | Text-to-Speech | ✅ works |  |
| [XTTS-vLLM](https://docs.pipecat.ai/api-reference/server/services/tts/xtts-vllm) | Text-to-Speech | ✅ works |  |

## What the statuses mean

| Status | Meaning |
|---|---|
| ✅ works | Installs with that Pipecat version, imports, and all its services can be created |
| 🟡 partial | The main package imports, but one of its submodules fails to import |
| ❌ broken | Installs, but importing it fails, or one of its services can't be created |
| 📌 needs older pipecat | Its version pin rules out that Pipecat version, so it can't be installed alongside it |
| ⛔ can't install | The published install command fails (e.g. the package isn't on PyPI) |

## Run it yourself

```bash
pip install uv
python -m health.run --target latest              # all plugins vs the latest release
python -m health.run --target main --only Gnani   # one plugin vs pipecat main
python -m health.report                           # rebuild this README
```

## Maintainers

If your plugin shows as broken, the **Why** column has the first error. The full
probe output, including every failing submodule, is in
[`results/latest.json`](results/latest.json) and [`results/main.json`](results/main.json).
Status changes are also filed as issues in this repo.

This is an independent project, not affiliated with Daily or the Pipecat team.
