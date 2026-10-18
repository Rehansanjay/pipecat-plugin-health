# The released wheel is not the truth

For three weeks this checker called a plugin broken if installing it from PyPI and importing it failed. That is the right question to ask on behalf of a user, who gets the wheel. It is the wrong question to ask about a maintainer, who may have fixed it already.

One plugin proved it.

## Boson

`pipecat-boson` failed on `cannot import name 'assert_given' from 'pipecat.services.settings'` — the same pipecat 1.8 move that six other plugins still die on. I opened a PR for it on 30 September. It was closed, because the maintainer had already landed their own fix the same day:

```python
try:
    from pipecat.utils.types import assert_given, is_given
except ImportError:  # pipecat-ai < 1.8.0
    from pipecat.services.settings import assert_given, is_given
```

That is on `main`, and has been since 30 September. PyPI still serves 0.1.3, published before it. So the plugin's code has been correct for over two weeks while this dashboard kept printing a red row with that maintainer's name on it.

Two things wrong with that. It blames someone for work they have already done. And it hides the only thing that would actually help their users, which is not a patch — it is a release.

## So the checker now asks both questions

When a release fails, the plugin's own source is installed from its repository, pinned to the commit under test, and probed again. A plugin whose source imports and constructs gets a new status, **`unreleased`**, which keeps the released failure alongside it and names the commit that passed.

Finding the repository turned out to be the hard part, because PyPI metadata cannot be trusted for it.

**`pipecat-boson` declares nothing at all** — no Homepage, no Repository, no `project_urls`. Its repository is mentioned in exactly one place: a `git clone` line in the README.

**FIRE RED VAD is worse.** All four of its published URLs are placeholders that were never filled in before release:

```
Homepage      https://github.com/your-username/pipecat-firered-vad
Repository    https://github.com/your-username/pipecat-firered-vad
Bug Tracker   https://github.com/your-username/pipecat-firered-vad/issues
Changelog     https://github.com/your-username/pipecat-firered-vad/releases
```

Anyone who installs that package and hits a problem follows the Bug Tracker link to a 404. Their report never arrives, and there is no route from the package page back to the repository. I only found the real one because the install error named the dependency.

So resolution reads the metadata first and falls back to the README. That gets **58 of 67** plugins, and every plugin that is currently failing.

## The guard that matters more than the feature

A repository can be resolved plausibly and still be the wrong one.

`pipecat-supertonic` resolves to **`supertone-inc/supertonic`** — the vendor's own TTS model repository, 13,000 stars — because the two names share a word. The plugin actually lives at `architjambhule66-debug/pipecat-supertonic`.

That one fails to install, so it answers `unknown` either way. But a wrong repository that happened to be installable and to import cleanly would have promoted the plugin to "fixed, not released" on the strength of somebody else's code, and published that claim under a maintainer's name. The fix is that the source build has to produce the distribution the plugin actually is, compared with PEP 503 normalisation, or the answer is `unknown`.

Measuring something means you can be wrong about it in public. The guards are the work.

## What the first full pass found

Thirteen plugins fail against pipecat-ai 1.12.0. Rebuilt from their own source:

| | count |
| --- | --- |
| Still broken when built from source | **7** |
| Fixed in source, stale on PyPI | **1** |
| Could not be read, reported `unknown` | 3 |
| Had a real diagnosis for the first time | 1 |

The full table now reads: 48 work, 9 broken, 5 pinned to an older pipecat, 3 uninstallable, 1 gated behind a licensed SDK, 1 fixed-but-unreleased.

I had expected several in that last row. I went looking because I assumed vendors had quietly merged fixes without releasing them, which would have meant a pile of easy wins — tell each one their users are still broken and a release closes it. There is exactly one.

**Zero of the nine vendors has fixed their own plugin.** I read the HEAD of each repository to check. Two looked fixed and were my own false positives: `pipecat-sonex` still imports `_NotGiven` from the old path, and `pipecat-awaazai` still uses the pre-1.8 `StartInterruptionFrame`, which my first grep matched as a substring of the new name.

## The one that gained something

**Simplismart** is not on PyPI under the name its docs publish, so for three weeks its row said `can't install` and nothing else. There was no diagnosis to give, because nothing could be installed to diagnose.

Built from source, it produces a real one. Same `_NotGiven` import as the others.

That is the part of this I would keep if I could only keep one thing: for a plugin that was never published, the source is not a second opinion. It is the only place its state exists at all.

---

The checker, the full table and the nightly results: **https://github.com/Rehansanjay/pipecat-plugin-health**
