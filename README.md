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

- **pipecat-ai 1.11.0** (2026-09-19): 36 works, 1 partial, 11 broken, 5 needs older pipecat, 3 can't install
- **pipecat-ai main@b60850bbd** (2026-09-19): 36 works, 1 partial, 11 broken, 5 needs older pipecat, 3 can't install

| Plugin | Category | pipecat 1.11.0 | pipecat main@b60850bbd | Why |
|---|---|---|---|---|
| [AwaazAI](https://docs.pipecat.ai/api-reference/server/services/serializers/awaazai) | Serializers | ❌ broken | ❌ broken | import pipecat_awaazai: ImportError: cannot import name 'StartInterruptionFrame' from 'pipecat.frames.frames' |
| [Beyond Presence](https://docs.pipecat.ai/api-reference/server/services/transport/beyond-presence) | Transports | ❌ broken | ❌ broken | import pipecat_bey.transport: ModuleNotFoundError: No module named 'daily' |
| [FIRE RED VAD](https://docs.pipecat.ai/api-reference/server/services/vad/fire-vad) | VAD | ❌ broken | ❌ broken | import pipecat_firered_vad: ModuleNotFoundError: FireRedVAD is not installed. |
| [Gnani](https://docs.pipecat.ai/api-reference/server/services/stt/gnani) | Speech-to-Text, Text-to-Speech | ❌ broken | ❌ broken | import pipecat_gnani: ImportError: cannot import name '_NotGiven' from 'pipecat.services.settings' |
| [Hecttor](https://docs.pipecat.ai/api-reference/server/services/audio-filters/hecttor) | Audio Filters | ❌ broken | ❌ broken | import pipecat_hecttor: ImportError: Missing module: No module named 'hecttor_sdk' |
| [Moss](https://docs.pipecat.ai/api-reference/server/services/knowledge-retrieval/moss) | Knowledge Retrieval | ❌ broken | ❌ broken | import pipecat_moss: ImportError: cannot import name 'LLMMessagesFrame' from 'pipecat.frames.frames' |
| [Replicate](https://docs.pipecat.ai/api-reference/server/services/image-generation/replicate) | Image Generation | ❌ broken | ❌ broken | import pipecat_replicate: ImportError: cannot import name '_NotGiven' from 'pipecat.services.settings' |
| [Respeecher](https://docs.pipecat.ai/api-reference/server/services/tts/respeecher) | Text-to-Speech | ❌ broken | ❌ broken | import pipecat_respeecher: ImportError: cannot import name '_NotGiven' from 'pipecat.services.settings' |
| [Rumik AI](https://docs.pipecat.ai/api-reference/server/services/tts/rumik) | Text-to-Speech | ❌ broken | ❌ broken | import pipecat_rumik: ImportError: cannot import name '_NotGiven' from 'pipecat.services.settings' |
| [SonexLabs](https://docs.pipecat.ai/api-reference/server/services/tts/sonex) | Text-to-Speech | ❌ broken | ❌ broken | import pipecat_sonex: ImportError: cannot import name '_NotGiven' from 'pipecat.services.settings' |
| [Supertonic](https://docs.pipecat.ai/api-reference/server/services/tts/supertonic) | Text-to-Speech | ❌ broken | ❌ broken | import pipecat_supertonic: ImportError: cannot import name '_NotGiven' from 'pipecat.services.settings' |
| [Deepdub](https://docs.pipecat.ai/api-reference/server/services/tts/deepdub) | Text-to-Speech | 📌 needs older pipecat | 📌 needs older pipecat | pins pipecat-ai>=0.0.97,<0.1.0 |
| [Maya](https://docs.pipecat.ai/api-reference/server/services/tts/maya) | Text-to-Speech | 📌 needs older pipecat | 📌 needs older pipecat | pins pipecat-ai==1.8.1; pipecat-ai==1.8.1. |
| [Oruk](https://docs.pipecat.ai/api-reference/server/services/stt/oruk) | Speech-to-Text | 📌 needs older pipecat | 📌 needs older pipecat | pins pipecat-ai>=1.8.1,<1.9 |
| [Roark](https://docs.pipecat.ai/api-reference/server/services/analytics/roark) | Analytics & Monitoring | 📌 needs older pipecat | 📌 needs older pipecat | pins pipecat-ai>=0.0.40,<1; pipecat-ai>=0.0.104,<1; pipecat-ai>=0.0.40,<1. |
| [Wavix](https://docs.pipecat.ai/api-reference/server/services/serializers/wavix) | Serializers | 📌 needs older pipecat | 📌 needs older pipecat | pins pipecat-ai[deepgram]==0.0.105; pipecat-ai==0.0.105. |
| [Hakim](https://docs.pipecat.ai/api-reference/server/services/stt/hakim) | Speech-to-Text, Text-to-Speech | ⛔ can't install | ⛔ can't install | <checkout> does not appear to be a Python project, as neither `pyproject.toml` nor `setup.py` are present in the directory |
| [Simplismart](https://docs.pipecat.ai/api-reference/server/services/llm/simplismart) | Large Language Models, Speech-to-Text, Text-to-Speech | ⛔ can't install | ⛔ can't install | Because pipecat-simplismart was not found in the package registry and you require pipecat-simplismart, we can conclude that your requirements are unsatisfiable. |
| [Uplift AI](https://docs.pipecat.ai/api-reference/server/services/stt/upliftai) | Speech-to-Text | ⛔ can't install | ⛔ can't install | <checkout> does not appear to be a Python project, as neither `pyproject.toml` nor `setup.py` are present in the directory |
| [Boson Higgs Realtime](https://docs.pipecat.ai/api-reference/server/services/s2s/boson) | Realtime LLM | 🟡 partial | 🟡 partial | import pipecat_boson.realtime.llm: ImportError: cannot import name 'assert_given' from 'pipecat.services.settings' |
| [Acefone](https://docs.pipecat.ai/api-reference/server/services/serializers/acefone) | Serializers | ✅ works | ✅ works |  |
| [Anam](https://docs.pipecat.ai/api-reference/server/services/video/anam) | Video | ✅ works | ✅ works |  |
| [Anannas AI](https://docs.pipecat.ai/api-reference/server/services/llm/anannas) | Large Language Models | ✅ works | ✅ works |  |
| [Arctan](https://docs.pipecat.ai/api-reference/server/services/audio-filters/arctan) | Audio Filters | ✅ works | ✅ works |  |
| [Asterisk](https://docs.pipecat.ai/api-reference/server/services/serializers/asterisk) | Serializers | ✅ works | ✅ works |  |
| [Bandwidth](https://docs.pipecat.ai/api-reference/server/services/serializers/bandwidth) | Serializers | ✅ works | ✅ works |  |
| [Finchvox](https://docs.pipecat.ai/api-reference/server/services/analytics/finchvox) | Analytics & Monitoring | ✅ works | ✅ works |  |
| [Floe](https://docs.pipecat.ai/api-reference/server/services/llm/floe) | Large Language Models, Speech-to-Text, Text-to-Speech | ✅ works | ✅ works |  |
| [floe-guard](https://docs.pipecat.ai/api-reference/server/services/analytics/floe) | Analytics & Monitoring | ✅ works | ✅ works |  |
| [Future AGI](https://docs.pipecat.ai/api-reference/server/services/analytics/future-agi) | Analytics & Monitoring | ✅ works | ✅ works |  |
| [Gandr](https://docs.pipecat.ai/api-reference/server/services/tts/gandr) | Text-to-Speech | ✅ works | ✅ works |  |
| [Lokutor](https://docs.pipecat.ai/api-reference/server/services/tts/lokutor) | Text-to-Speech | ✅ works | ✅ works |  |
| [MCP](https://docs.pipecat.ai/api-reference/server/services/transport/mcp) | Transports | ✅ works | ✅ works |  |
| [MemorySync](https://docs.pipecat.ai/api-reference/server/services/memory/memorysync) | Memory | ✅ works | ✅ works |  |
| [MLflow](https://docs.pipecat.ai/api-reference/server/services/analytics/mlflow) | Analytics & Monitoring | ✅ works | ✅ works |  |
| [Murf AI](https://docs.pipecat.ai/api-reference/server/services/tts/murf) | Text-to-Speech | ✅ works | ✅ works |  |
| [Noveum Trace](https://docs.pipecat.ai/api-reference/server/services/analytics/noveum-trace) | Analytics & Monitoring | ✅ works | ✅ works |  |
| [OpenInference](https://docs.pipecat.ai/api-reference/server/services/analytics/openinference) | Analytics & Monitoring | ✅ works | ✅ works |  |
| [Pinch](https://docs.pipecat.ai/api-reference/server/services/translation/pinch) | Translation | ✅ works | ✅ works |  |
| [Pipecat Backchannel](https://docs.pipecat.ai/api-reference/server/extensions/pipecat-backchannel) | Extensions | ✅ works | ✅ works |  |
| [Pipecat TTS Cache](https://docs.pipecat.ai/api-reference/server/services/tts/tts-cache) | Text-to-Speech | ✅ works | ✅ works |  |
| [pipecat-effects](https://docs.pipecat.ai/api-reference/server/services/audio-filters/pipecat-effects) | Audio Filters | ✅ works | ✅ works |  |
| [Protoface](https://docs.pipecat.ai/api-reference/server/services/video/protoface) | Video | ✅ works | ✅ works |  |
| [Quickdial](https://docs.pipecat.ai/api-reference/server/services/stt/quickdial) | Speech-to-Text, Text-to-Speech | ✅ works | ✅ works |  |
| [Ringg AI](https://docs.pipecat.ai/api-reference/server/services/stt/ringg) | Speech-to-Text | ✅ works | ✅ works |  |
| [SILMA AI](https://docs.pipecat.ai/api-reference/server/services/tts/silma) | Text-to-Speech | ✅ works | ✅ works |  |
| [SLNG](https://docs.pipecat.ai/api-reference/server/services/stt/slng) | Speech-to-Text, Text-to-Speech | ✅ works | ✅ works |  |
| [SmolVLM](https://docs.pipecat.ai/api-reference/server/services/vision/smolvlm) | Vision | ✅ works | ✅ works |  |
| [Synap](https://docs.pipecat.ai/api-reference/server/services/memory/synap) | Memory | ✅ works | ✅ works |  |
| [TEN VAD](https://docs.pipecat.ai/api-reference/server/services/vad/ten-vad) | VAD | ✅ works | ✅ works |  |
| [ThunderPhone](https://docs.pipecat.ai/api-reference/server/services/s2s/thunderphone) | Realtime LLM | ✅ works | ✅ works |  |
| [Typecast](https://docs.pipecat.ai/api-reference/server/services/tts/typecast) | Text-to-Speech | ✅ works | ✅ works |  |
| [Uplift AI](https://docs.pipecat.ai/api-reference/server/services/tts/upliftai) | Text-to-Speech | ✅ works | ✅ works |  |
| [Vakyam AI](https://docs.pipecat.ai/api-reference/server/services/tts/vakyam) | Text-to-Speech | ✅ works | ✅ works |  |
| [Voice.ai](https://docs.pipecat.ai/api-reference/server/services/tts/voiceai) | Text-to-Speech | ✅ works | ✅ works |  |
| [XTTS-vLLM](https://docs.pipecat.ai/api-reference/server/services/tts/xtts-vllm) | Text-to-Speech | ✅ works | ✅ works |  |

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
