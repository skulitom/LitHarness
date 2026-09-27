# LitHarness Lite: opening-chapter comparison

27 September 2026 · One brief, one new chapter, one historical baseline

## Recommendation

**Continue developing the clean version. Keep LitHarness as the reference implementation
and retain it for existing serials until the clean version demonstrates continuity across
several chapters.** This pilot supports spending the next increment of development on the
small tool; it does not support retiring the incumbent.

The new chapter gives its protagonist a more consequential choice and stronger interpersonal
conflict, with comparable sentence-level control. Two blinded model reads preferred it in
both presentation orders. The lightweight run also used much less orchestration. Its actual
defects are small and identifiable; nothing in this chapter suggests that recreating the
entire incumbent architecture is the right first response.

These are scoped editorial observations. One pair and an uncalibrated model judge cannot
establish general literary superiority, reader retention, or long-book reliability.

## What was built

[LitHarness Lite](../../README.md) is an independent, 264-line Python runtime using only the
standard library and a signed-in Codex CLI. It imports no LitHarness code. Its production
path is **brief → compact plan → whole chapter**, with two model calls. It saves exact
requests, raw provider events, token/time receipts and input/output hashes. It can resume
an interrupted run without repeating completed stages, rejects changed saved artifacts,
and preserves failed attempts. Model tools and inherited project context are disabled.

Evaluation and presentation utilities are separate from the drafting runtime. There is no
database, agent queue, recruited writer roster, custom contracts dependency, grading loop,
automatic rewriting or model fallback. This is an opening-chapter prototype, with optional
author context; it does not yet provide a serial's evolving canon or the incumbent's
transactional recovery, world validation and publication features.

For scale, the frozen incumbent snapshot contains 130 runtime Python files / 65,877 lines
and 39 SQL migrations. That is a whole-system comparison, not equivalent feature coverage.
The [engineering record](engineering.json) identifies the snapshot and archive digest.

## Comparable inputs, unequal histories

The original brief was:

> System apocalypse. When the System arrives, every person on Earth receives exactly one
> Slot for one skill. The protagonist, a man in his twenties, receives a Slot that can hold
> as many skills as he can take. Invent the rest.

Both outputs used **gpt-6-astra, medium effort**, and the same native CLI binary by SHA-256.
Lite targeted the baseline's 3,962 words and produced 4,069, 2.7% longer. Both are close-third,
past-tense opening chapters. Lite received only the original brief and its own generated plan.
It did not see the incumbent's chapter, world, writer dossier, plans, gates or evaluation.

- **Heavy:** [Every Skill a Handhold](baseline/chapter-one.md), generated 24 September,
  `read-21/draw-6`, writer `marsh`, source revision
  `07b077f2ce64375d47df2dc2d7f32425432247b3`.
- **Lite:** [One Slot, Open Water](lite/chapter.md), first and only new generation on
  27 September. No editorial changes or candidate selection after generation.
- [Open the side-by-side reading copy](comparison.html).

The baseline was the only complete `chapter-one.md` found in the chapter-one lane and was
selected before reading it. It completed chapter generation, but **had no recorded chapter
gate pass**. Earlier concept/listing/world checkpoints had passed. It was draw 6 after
earlier iterations, whose costs are not included below. Different writer instructions,
invented stories and historical model service state remain confounds. This is a comparison
of two complete approaches on one brief, not a causal isolation of orchestration alone.

## Quality observations

The rubric was fixed before generation. Scores are uncalibrated ordinal model judgments
on a 1–5 scale: serious failure, weak, competent, strong, exceptional. Each cell gives the
first / reversed-order read, mapped back to the underlying chapter. No pooled quality
percentage, statistical significance or independent-sample count is inferred from them.

| Dimension | Heavy | Lite | Interpretation on this pair |
| --- | --- | --- | --- |
| Brief fidelity | 5 / 5 | 4 / 4 | Heavy explicitly states the protagonist's age; Lite leaves it off the page. |
| Dramatic causality | 4 / 4 | 5 / 5 | Lite connects a lie to lost evacuation time and a later irreversible choice. |
| Character and dialogue | 4 / 4 | 5 / 5 | Lite gives several people legitimate, conflicting priorities. |
| Prose control | 4 / 4 | 4 / 4 | Both are concrete and readable; neither clearly wins at sentence level. |
| Progression as drama | 4 / 5 | 5 / 5 | Heavy has strong embodied skill learning; Lite ties capability to a sacrificed escape route. |
| Continuation pull | 4 / 4 | 5 / 5 | Lite's ending follows from the protagonist's choice and forces a next action. |

Both reads preferred **Lite overall**, each with medium confidence. The progression judgment
changed from a Lite advantage to a tie when order was reversed; that instability is retained.
These are two readings of one pair, not two independent chapter comparisons.

**Where Lite is stronger.** Elias lies about the flood deadline to protect his brother:
“Elias had bought Jamie time with theirs.” That lie changes what other people do. Saira's
“You tell me what the water does. I’ll tell you what people can manage.” expresses a concrete
conflict over authority. Finally, his use of Wedge breaks the return mechanism: “Break it,
and there would be no winding the gate shut again.” The ending is a consequence of a choice
he understands, with his brother's safety still unconfirmed.

**What Heavy does well.** Owen's climbing knowledge matters on the page. Air Step expires
when he hesitates, and he learns how to commit his weight. “His grip steadied. The pain in
his wrist did not disappear.” preserves physical consequences despite advancement. Leanne
is practical and distinct, and the rescue depends on cooperation. Its closing objective—
finding a route that other people can use—extends this social thread.

**What holds Heavy back here.** Much of the chapter reiterates hand placement, breath
recovery, wrist pain and repeat crossings. The immediate rescue resolves successfully,
while the next expedition remains an intention. Air Step arrives exactly when the return
wall fails and supplies the precise missing solution, making the solution feel convenient.

**Lite's defects, retained in the output.**

1. The plan identifies Elias as 26, but the chapter never states his age. This leaves the
   literal “man in his twenties” requirement unconfirmed on the page; it does not establish
   that he is actually the wrong age. The one-Slot/multiple-skills exception is demonstrated.
2. He stores three breaths, uses the reserve underwater, then reports “Three breaths left.
   Maybe less.” The qualification makes it ambiguous rather than a certain numerical
   contradiction, but it weakens the clarity of an important resource limit.
3. “He had lost the helmet somewhere, he realised; that was his skull.” introduces an
   unestablished helmet and briefly muddles the physical action.
4. The conveniently placed kernels are a device in both chapters. Removing orchestration
   has not, in this sample, eliminated that tendency or the shared infrastructure-rescue plot.

No prose was repaired after discovering these defects. Preserving the original draft keeps
the comparison inspectable and avoids quietly turning a first-draft test into an edited one.

## Evaluation controls

All four checks passed:

| Check | Observed result |
| --- | --- |
| Reversed presentation order | Both reads preferred the Lite chapter. |
| Identical-text null | Tie overall, with equal scores on every dimension. |
| Severe paragraph-reordering damage | Intact Lite won overall and on dramatic causality. |
| Quote grounding | All 48 quotations were found verbatim in their assigned chapters. |

The final result is recorded in [evaluation-summary.json](evaluation-summary.json), with
full rationales and automatically located quotations in [judgments.json](judgments.json).

The method uses swapped order, an identical-text null, a severe paragraph-reordering
control and exact quote checks. Passing these controls does not validate sensitivity to
subtle literary quality. The same model family generated and judged both chapters, and no
reader-retention signal or cross-book replication was measured. Feedback never entered
either generation loop. [The frozen protocol](PROTOCOL.md) records the decision scope.

## Measured effort

| Measure | Heavy: full recorded pipeline | Heavy: chapter stage only | Lite: plan + chapter |
| --- | ---: | ---: | ---: |
| Model calls | 33 | 16 | 2 |
| Sum of model call time | 33m 48s | 18m 25s | 4m 09s |
| Input tokens, including cached | 383,764 | 114,598 | 8,729 |
| Cached input tokens | 166,656 | 9,856 | 0 |
| Output tokens, as reported | 27,396 | 15,063 | 7,175 |
| Total input + output tokens | 411,160 | 129,661 | 15,904 |

Against the chapter stage alone, Lite used **8 times fewer calls, 4.45 times less model
time, and 8.15 times fewer total tokens**. Against the full recorded pipeline the time
ratio was 8.16 and token ratio 25.85. The full pipeline also creates a listing and persistent
world state, so those savings are not equivalent-work estimates. The chapter stage likewise
includes continuity/state work absent from Lite.

Times sum provider receipts, exclude human checkpoint waits, and were measured on different
days. Earlier heavy draws are excluded. Evaluation calls are separate in
[metrics.json](metrics.json). Tokens are not dollar costs or subscription credits; cached
input makes direct price inference especially misleading.

## Next development choice

Continue from the clean version, adding only capabilities demonstrated to be missing:

1. Preserve literal brief facts in the actual prose and check named resource accounting.
   The age and breath defects are the first concrete regression cases.
2. Test a short continuation with a compact plain-text canon/state file and the preceding
   chapter, keeping calls bounded. Check whether established rules, injuries and unresolved
   promises survive across chapters.
3. Repeat on different briefs with fresh matched baselines before claiming a general
   advantage. Use the retained incumbent when testing long-serial durability.

Do not port the queue, world graph or research machinery merely to recreate feature parity.
Keep a component when a concrete task requires it. This recommendation concerns what to
develop next; it is not approval to migrate or delete existing books or LitHarness.

## Reproduction and evidence

- New project: `C:/DEV/LitHarnessLite`; no LitHarness source or existing book was edited.
- Initial local protocol/implementation commit: `365b021`.
- `freeze.json` binds runtime, evaluation prompts, protocol and baseline files before calls.
- `baseline/traces/` retains all 33 historical raw transport receipts.
- `lite/calls/` retains the two actual new requests, final responses and provider events.
- `evaluation/` retains each blinded/control request, response and receipt.
- Rebuild measurements and the reading copy: `python analyze.py`.
- Verify runtime and evidence-handling behavior: `python -m unittest discover -s tests -v`.
- Final verification: all 12 deterministic tests passed; frozen inputs, all 33 historical
  traces, and all six new generation/evaluation receipts passed SHA-256 integrity checks.
- A new generation requires a new output directory; rerunning the comparison consumes
  subscription quota. This report's observed chapter is immutable, not a fixed-seed promise.

This report and all artifacts remain local. No upstream change, publication or migration
was performed.
