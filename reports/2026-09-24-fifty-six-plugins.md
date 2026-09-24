# I installed all 56 Pipecat community plugins. 18 of them don't work.

Pipecat's docs list every community-maintained plugin on one page: speech-to-text, text-to-speech, serializers, VAD, analytics, transports. Pick a vendor, `pip install`, follow the snippet.

For 18 of the 56 listed this morning, that doesn't work. The install fails, or the import raises, or the package pins a version of pipecat from a year ago and quietly drags your whole environment backwards.

Nobody is hiding this. It's just that nothing was checking.

## What the checker does

Every night, for each plugin on the supported-services page:

1. Create a fresh environment.
2. Install the plugin together with **the latest pipecat-ai release on PyPI** — what a new user gets today.
3. Do it again against **pipecat-ai `main`** — what users get in the next release.
4. Import the plugin and construct every Pipecat service class it defines.

No API keys are used anywhere, so this doesn't test whether a provider's servers answer. It tests the part that breaks far more often: install, import, and API shape — renamed or removed Pipecat symbols, new abstract methods, version pins.

The plugin list is re-read from the docs on every run, so new plugins are picked up automatically.

Results as of the run on 24 September 2026, against pipecat-ai 1.11.0:

| Status | Count |
| --- | --- |
| Works | 38 |
| Partial | 1 |
| Broken on import | 10 |
| Pinned to an older pipecat | 4 |
| Can't be installed at all | 3 |

The numbers are identical against `main`, which means nothing currently in flight makes this better or worse.

## The failures cluster, and that's the interesting part

**Six plugins died on the same line.** In pipecat 1.8, the settings sentinel `_NotGiven` was removed from `pipecat.services.settings` — it is `NotGiven` in `pipecat.utils.types` now. Six plugins that still install at all import the old name, so they raise `ImportError` before doing anything else:

```
ImportError: cannot import name '_NotGiven' from 'pipecat.services.settings'
```

Gnani, Replicate, Respeecher, Rumik AI, SonexLabs, Supertonic. Six different companies, six separate repos, one upstream rename. Each fix is a single import line.

**Three more broke on renamed frames.** AwaazAI imports `StartInterruptionFrame`, Moss imports `LLMMessagesFrame`, and Boson's realtime LLM imports `assert_given` — none of which exist under those names any more. Boson is the one "partial": the package installs and part of it imports, but the realtime path doesn't.

**Two are missing their own dependency.** Hecttor needs `hecttor_sdk` and FIRE RED VAD needs `FireRedVAD`; neither is installable from where the plugin expects it.

**Four pin pipecat backwards.** Deepdub requires `pipecat-ai>=0.0.97,<0.1.0`. Wavix wants `==0.0.105`. Oruk allows `>=1.8.1,<1.9`. Maya pins `==1.8.1` exactly. These don't error — which is worse. Your resolver silently downgrades pipecat, or refuses to solve, and the reason isn't obvious from the traceback you eventually get.

**Three can't be installed at all.** Hakim and Uplift AI's STT checkout has neither a `pyproject.toml` nor a `setup.py`, so there's nothing to install. Simplismart isn't on PyPI under the name the docs use.

## Why this keeps happening

Community plugins live in their own repositories, usually maintained by one engineer at the vendor. Pipecat ships often and moves fast, which is a virtue. But a plugin repo has no CI that installs against pipecat `main`, so an upstream rename doesn't produce a red build anywhere — it produces a broken install six weeks later, for a user who has no relationship with either party and will simply choose a different vendor.

That's the gap: the breakage is public, deterministic and cheap to detect, and there was no place where anyone looked at all of them at once.

## It measures recovery too

Between the 20th and the 24th, Roark loosened its pin and moved from "needs older pipecat" to "works". That's the part I didn't expect to enjoy: the table isn't a wall of shame, it's a live picture. Anything on it can move, and most of these are one-line changes away from moving.

Running against `main` as well as the current release is deliberate, and it's the part I'd most like vendors to use. A plugin that breaks against `main` today has until the next pipecat release to fix it, rather than finding out from an issue after the fact.

## I've been sending the fixes

Rather than just publishing a list, I opened PRs for the ones I could fix from outside: Gnani (three, including a TTS socket that never reconnects after an interruption and an STT socket that leaks on a failed handshake), Replicate, Respeecher, Rumik, SonexLabs, Supertonic, Maya and Simplismart.

If your plugin is on the broken list and you'd like the fix as a PR rather than a bug report, say so and I'll send one.

The repo, with the full table and the nightly results:
**https://github.com/Rehansanjay/pipecat-plugin-health**
