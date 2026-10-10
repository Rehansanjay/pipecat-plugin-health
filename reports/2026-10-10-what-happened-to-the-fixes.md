# I sent the fixes. Three weeks later, none of them have merged.

Sixteen days ago I published a count: of the 56 community plugins listed in Pipecat's docs, 18 didn't work. Broken imports, missing dependencies, version pins dragging pipecat backwards a year.

I also said I'd send PRs for the ones I could fix from outside, and I did — eleven of them, across eleven repositories, between 18 September and 1 October.

Here is what has happened since.

## The numbers, 16 days on

The nightly re-reads the docs page on every run, so the list grows by itself. It has:

| | 24 Sep | 10 Oct |
| --- | --- | --- |
| Plugins listed | 56 | 61 |
| Works | 38 | 42 |
| Partial | 1 | 1 |
| Broken on import | 10 | 10 |
| Pinned to an older pipecat | 4 | 5 |
| Can't be installed at all | 3 | 3 |
| **Not usable** | **18** | **19** |

Against pipecat-ai 1.12.0 now, where the first report was against 1.11.0.

Five plugins were added to the docs in that window; four of them work. The two newest, didlogic and Giggy, both arrived in the last few days — Giggy works against the current release and pins below `main`.

So the healthy count went up because the list got longer, not because anything got fixed.

**The ten broken plugins are the same ten.** Not a similar number — the same names, in the same state, failing on the same line:

> AwaazAI · FIRE RED VAD · Gnani · Hecttor · Moss · Replicate · Respeecher · Rumik AI · SonexLabs · Supertonic

Six of those still die on the `_NotGiven` import that pipecat 1.8 moved and renamed, which shipped on 26 August. That is now six and a half weeks.

## The eleven PRs

Every one of them is open. Every one is mergeable, not a draft, with no conflicts and nothing red.

```
22d  Gnani-AI-Mintlify/pipecat-gnani#2           ImportError on pipecat >= 1.8
22d  simpli-smart/pipecat-simplismart#15         ImportError on pipecat >= 1.8
21d  bnovik0v/pipecat-replicate#1                ImportError on pipecat >= 1.8
21d  sonexlabs/pipecat-sonex#2                   ImportError on pipecat >= 1.8
21d  ira-rumik/pipecat-rumik#1                   ImportError on pipecat >= 1.8
21d  respeecher/pipecat-respeecher#3             ImportError on pipecat >= 1.8
21d  architjambhule66-debug/pipecat-supertonic#1 ImportError on pipecat >= 1.8
21d  MayaResearch/pipecat-maya#2                 accept 1.11 patch releases
15d  awaazai/pipecat-awaazai#1                   InterruptionFrame rename
15d  usemoss/pipecat-moss#5                      LLM context frames removed in 1.8
 9d  vivekgupta-memcode/pipecat-memcode#3        allow 1.11 and 1.12
```

Nine of the eleven have had no human response at all. One has a single comment. One has a single review. Nothing has merged.

I want to be careful about what that does and doesn't mean. A community plugin is usually one engineer inside a vendor, with a roadmap that isn't this. An unreviewed PR from a stranger is one of the easiest things in the world to not get to, and none of these repositories owes me anything. I'm reporting the number because the number is the finding, not because anybody behaved badly.

## This is not upstream's fault, and it's worth saying plainly

It would be easy to read the `_NotGiven` cluster as Pipecat breaking its ecosystem. It isn't.

The 1.8.0 changelog flagged the change with a ⚠️ and spelled out the migration:

> `NOT_GIVEN`, `NotGiven`, `is_given()` and `assert_given()` now come from `pipecat.utils.types` and are no longer importable from `pipecat.services.settings`. The private `pipecat.services.settings._NotGiven` is now the public `pipecat.utils.types.NotGiven`.

They announced it, they documented the destination, and they correctly noted that the old name was private — plugin authors were importing an underscore-prefixed symbol out of someone else's module, which was always going to be fragile.

The supported-services page is equally clear about ownership:

> Services marked **Community** are distributed as separate packages — install them individually and report issues on their source repositories.

So upstream did the things you'd ask for. The breakage still happened, and six weeks later it still hasn't been repaired. That's the part I find interesting.

## What I got wrong in the first report

I ended the September write-up assuming the problem was that nobody was looking. Build the checker, publish the list, send the patches, and the table should start going green.

The table did not start going green. The information existed, the fixes existed and sat one click away, and the count stayed flat.

So the gap isn't detection and it isn't authorship. It's that **a community plugin has no owner whose job it is to notice.** Upstream has correctly delegated it. The vendor has shipped it and moved on to the product it supports. The user who hits the ImportError has no relationship with either party and silently picks a different vendor — which is the one signal that would actually prompt a fix, and it's the one signal nobody ever receives.

A list and a patch don't close that loop. I don't currently know what does.

## If you're choosing a plugin

The practical reading, which is the only part of this that helps anyone today:

- **Check the pin before you check the features.** Four of the five pinned plugins will silently downgrade pipecat in your environment rather than fail, and you'll debug it as something else entirely. Deepdub asks for `>=0.0.97,<0.1.0`; Wavix for `==0.0.105`.
- **An import test is a five-second question.** `python -c "import pipecat_<name>"` in a fresh environment tells you more than a README.
- **Check when the repo last moved.** All ten broken plugins have been broken since late August. That's visible from the outside before you commit to one.

The full table, both targets, refreshed every night:
**https://github.com/Rehansanjay/pipecat-plugin-health**

## The offer stands

If your plugin is on the list and you'd rather have a PR than a bug report, say so and I'll send one. The eleven already open will stay open; nothing in them expires, and I'll keep them rebased as pipecat moves.
