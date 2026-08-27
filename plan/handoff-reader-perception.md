# Handoff: the readers cannot see the defect, and six ways of asking did not help

**Historical handoff — superseded 2026-08-27.** Its experiment results remain evidence, but its
description of a listing writer consuming appetite answers is no longer the live architecture.
The current boundary is [`reader-architecture-program.md`](reader-architecture-program.md): raw
answers remain observations, and only a separately qualified mechanism may reach an editorial
intervention and immutable plan revision.

Written 2026-08-26 at the end of a long session that did not achieve its objective. Read the
boundaries before the tasks; two of them exist because this session spent quota learning them.

## Boundaries

1. **The objective is a readership that notices quality, not a statistic that correlates with
   it.** The operator, closing the session: *"We shouldn't use such crude methods to find flaws.
   Our goal is to make the agent model readers notice quality, not to measure statistical
   correlation between two words... that approach isn't scalable."* The n-gram counter in
   §143 is a **located diagnosis and not the instrument** — it says what class of defect this
   is, and it is not the thing to build on.

2. **Do not re-run a pick-between-two screen expecting resolution.** It is settled blind.
   `render_pick_request` returns our listings over published ones at 15/16, at 16/16 with the
   readers' declared taste removed entirely, and at **24 of 24 against the operator's own named
   favourites** (`plan/anchor-set.md`: Paranoid Mage, 17,850 followers; Mark of the Crijik).
   Position balanced, both conditional rates 1.0. A question that returns 1.0 against every pool
   is not short of resolution and is not short of a better pool.

3. **The operator's judgment is the ground truth and it has not moved across three sessions.**
   Our listings are below the bar; RoyalRoad's top listings clear it. Every instrument that says
   otherwise is wrong, and §142 is the entry that got this backwards and was withdrawn. Treat a
   result that flatters our own text as a defect in the instrument until proven otherwise.

4. **The defect class is named and it is not clarity.** From every session: *"wtf is a patch of
   notes, nobody says that"*, *"lines are not things that get nerfed, incorrect use of
   terminology"*, *"keys don't take, they open things"*, *"'dropped flush' isn't a phrase I heard
   anyone ever say"*, *"sounds like somebody trying to describe a litrpg they read once"*. Not
   unfollowable, not vague — **idiomatically wrong in a way a fluent reader of the genre hears
   instantly.** The comprehension screen measures *definition* where `house.CLARITY` specifies
   *consequence*, which is why it scores our listings at half the market's rate.

5. **A model asked whether its own phrasing is idiomatic is the wrong instrument on principle.**
   Six probes, all model-based, all blind or inverted (§143.2). That is not six coincidences and
   the seventh phrasing of the same question will not be different. The tasks below are all
   attempts to stop asking a model to *judge* and start making it *do* something.

6. **Nothing costs the operator a read that a counter could have caught.** The operator, and it
   is the process complaint underneath all of this: *"I feel like I keep giving the same feedback
   back and nothing changes otherwise."* Five defect classes have been named repeatedly; one has
   an instrument and it is uncalibrated. Until that changes, the operator **is** the instrument.

## What is built and works

`uv run litharness listing` is the loop, end to end: one cast writer drafts the listing, the
steering pool says where it left them and what they expect, the same writer revises, titles it, a
`WebSearch` lookup says whether the title is already somebody's, and `--scenes` creates the book
under that title. `--rivals` puts a published competitor in the measurement screen.

`domain/rivals.py` admits a competitor by external evidence only — above four stars, or 1,000+
followers (the shards carry no `overall_score` at all), in one of this readership's genres.
`research/quality-measurement/rival_pool.py` builds pools from the cached shards; **use all
twelve**, not two, which was a plain error early in this session.

The reader channel was rewritten to the operator's direction: readers are stopped at
`text.stop_point` (§124's paragraph boundary near 60%), they answer `felt` / `expect_next` /
`hoping_for` / `dreading` all pinned to *what happens next in the story*, and the block the
writer reads no longer claims those words outrank its craft rules. The continuation names the
rival and does not show it, so going to look costs this chapter.

Also landed this session and unrelated to the above: `world accept` no longer carries a
declaration a later one replaced (§139.3 — this was blocking every scene of every book the
Architect seeded), `make_plan_selector` can finally pass a writer, and `_say` stops the CLI
dying on an em dash.

## Where the measurement got to

| instrument | reading |
| --- | --- |
| paired pick, tasted readers | ours 15/16 |
| paired pick, no declared taste | ours 16/16 |
| paired pick vs the operator's summits | **ours 24/24** |
| uncashable terms | ours 5.75 against the market's 12.5-13.8 |
| quote-a-span: unfollowable / reread / empty | blind, blind, **summits worse** |
| corpus bigrams, on the two rated listings | **ours 0.302 [0.254, 0.350] vs 0.101 [0.041, 0.161]** |
| corpus bigrams, on eight newer listings | 0.139 [0.103, 0.176] — overlap, blind |

The last two rows are §143 and they are the only separation anyone has achieved. It is partial:
it works on the listings the operator rated and not on the ones drawn since, and the confound —
both rated listings share a software subject, so rarity may be topic — is unresolved.

**One thing the readership demonstrably can do**, and it is the only validity any of this has:
it separates a 12,448-follower serial from a 0-follower one at **H = 0.935** with word count
matched pair for pair, position clean (§141). Any new instrument should be checked against that
gradient before its verdict on our own work is believed.

## Tasks

### 1. Make the reader produce rather than judge

The strongest untried idea, and it follows directly from boundary 5. A model's *generative*
fluency is reliable where its *critical* judgment is not: it will rarely write "a patch of
notes", even though it cannot reliably flag one.

So: give a reader the listing and ask it to **write the same sentence as it would appear in a
book of this genre**. Then diff. Where the rewrite silently repairs a phrase, that phrase was
off; where it comes back unchanged, it was not. The measurement is the diff, computed in code —
no verdict slot, nothing rated, nothing ranked, which is what makes it admissible under §89 and
§97.4 at all.

Two things to get right. The diff must be **span-level and code-computed**, or this becomes a
model reporting on itself again. And the reader must not be told what is wrong with the text or
that anything is: the ask is *"write this the way it would be written"*, not *"fix this"*.

Validate on the follower gradient before believing anything it says about ours.

### 2. Surprisal, which is the principled version of §143's counter

The force programme already has token-logprob machinery, and `plan/force-program.md` records why
it is GPU-only: the Messages API returns no logprobs. Per-token surprisal of a listing under a
model conditioned on genre text is the continuous, scalable form of *"this phrase does not occur
in the genre"* — the same idea as §143 without the crude threshold, and it runs per listing
rather than per corpus pass.

**Read `research/quality-measurement/BRIEF.md` before building this.** F1, F2 and FX are dead in
ways that will look like this one from the inside, and F2's numbers were withdrawn for scoring
the token *after* the one it matched on 6,744 of 6,744 sites.

### 3. Show the reader the shelf

Every probe so far asked a model to judge from memory. A reader shown five real listings from
this market *and then* ours has a concrete reference rather than a recalled one. This is
measurement-side, so RS1 permits it — anchor and corpus text may enter measurement and may never
enter a drafting, revision or planning prompt.

Cheap, no GPU, and it is the smallest change to the existing screen that is not a seventh
rephrasing of the same question. The risk to design against is that the reader starts pattern
matching on surface (length, tag dumps, release notes) rather than phrasing; the gradient check
in §141 is what catches that.

### 4. Then, and only then, the four defect classes with no counter

Vagueness, sentences that do not connect, over-specificity, titles that describe rather than
name. Each has been named repeatedly by the operator and none has an instrument. They are listed
last on purpose: a counter built before task 1, 2 or 3 works will be validated against the same
blind readership that produced this table.

## What was tried and did not work, so it is not tried again

- **Rewriting the reader's question, six times.** Which-do-you-start, with taste and without;
  quote the unfollowable; quote what you re-read; quote what names nothing. Blind, blind,
  blind, blind, blind, and one that says the operator's favourites are worse.
- **Removing the readers' declared taste** (`readers.BLIND`). The hypothesis was that their
  `drops_on` clauses were our own prompt's rules read back — which the reasons did support, every
  one of fifteen being *"starts him at zero"* or *"a real cost"*. Removing them made the
  preference **stronger**, 16/16. Kept in the tree as a refuted hypothesis.
- **A better rival pool.** Twelve shards instead of two, then the operator's own named works.
  24/24. The pool is not the variable.
- **The uncashable-term counter for blurbs.** It asks *"words you were never told the meaning
  of"* and flags `sects`, `slayers`, `class` — which the operator reads as *"extremely clear and
  clever"*. `house.CLARITY` specifies the test it should be asking: *whether they could say what
  it changes for the person it happens to*.
- **Trigrams over 40,000 chapters.** Every text scored above 0.45 unseen, the operator's
  favourites included. A sample-size failure; bigrams over 200,000 chapters separate.
- **Believing a result that flattered us.** §142 concluded the market was the problem and was
  withdrawn the same session. The operator had already said the opposite twice.

## Cost, stated because it should inform what the next session risks

This session spent roughly **$70** and produced one partial separation. The listing loop, the
title check, the supersession fix and the reader-channel rewrite are real and shipped; the
central objective — a readership that sees what the operator sees — was **not met**, and six of
the seven approaches tried are recorded above as dead so that the next session starts from task
1 rather than from a seventh rephrasing.
