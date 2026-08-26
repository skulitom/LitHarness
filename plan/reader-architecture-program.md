# The reader-architecture programme: perceiving quality is the goal, and a prompt is only one interface to it

The operator's direction, 2026-08-26, recorded verbatim because it redraws the search space:

> *"I'm not trying to discover new reader prompts, I'm trying to discover a way for the
> readers to perceive quality correctly. Whether this is achieved through prompts,
> multi-agent analysis, [logit] lens, or something else. Just as long as it is done through
> LLMs — if this was possible without them this sort of product would have been made
> before."*

And the distinction the operator asked to be recorded explicitly:

> **LitHarness is not searching for a quality metric. It is searching for an LLM-based
> cognitive system that perceives literary quality well enough to behave as a readership.**

## What this changes, and what it does not

`plan/handoff-reader-perception.md` boundary 5 said a model asked to judge its own phrasing
is the wrong instrument; six prompt rewrites of the same judgment question proved it. The
generalisation this programme works under: **the unit of search is the mechanism, not the
question wording.** A seventh phrasing of "which is better" is not a new mechanism; a system
in which the model does something checkable — writes, detects against visible references,
defends a span with verifiable evidence, spends a budget, or exposes its token
probabilities — is.

Nothing about the validation discipline moves. Every mechanism, whatever its architecture:

- validates on §141's follower gradient (H = 0.935 is the one thing this readership has
  proven it can read) before its reading on our own text is believed;
- carries the operator's acceptance test — our generated text near the bottom, the market's
  top clearly above — with the inverted result withdrawing the instrument, never flattering
  the text (boundary 3);
- keeps the verdict channel shut (§89, §97.4): scores come from what the system *does*,
  computed in code, and no model rates, ranks or prefers anywhere a claim depends on it;
- is registered before its first paid call, kills and readings fixed, distributions before
  bars (§61); and stays inside §95 (LLM-only), §97.1 (nothing feeds a prompt), RS1 (market
  text on the measurement side only).

## The mechanism families, and where each stands

| family | what it extracts | state in this repository |
| --- | --- | --- |
| **Generative tests** — rewrite, continue, compress, recall; quality inferred from what the model does | generative fluency, which stayed reliable where critical judgment went blind | `blurb_rewrite.v0` built and mid-validation (`plan/blurb-rewrite-validity.md`); if its gradient separates, continuation/compression/recall probes are the natural siblings |
| **Comparative reading with a reference shelf** — the register held in context, not recalled | perception of deviation against visible evidence | `blurb_shelf.v0.1` built; first run found the first non-inverted separation (ours flagged 12/12 across rotations), re-run queued under the amended construction |
| **Adversarial span tribunal** — one agent flags, another must defend the span with evidence code can verify | disagreement resolved by checkable evidence instead of a third opinion | `blurb_tribunal.v0` — being built now; the resolver is deterministic (a claimed parallel either exists in the reference text or does not), which is what keeps the third seat from becoming a judge |
| **Cross-family readers** — the evaluator unrelated to the generating model | self-familiarity attacked directly; a claude-written listing read by a model with no stake in claude's habits | ollama legs for the two shipped instruments — being built now; local models under the thermal governor (`latent_crossfamily.py` is the precedent for cross-family eligibility screens) |
| **Representation-level** — per-token surprisal, logit/activation lens | quality sensitivity that exists internally but dies in verbal self-report | handoff task 2 plus the operator's lens direction. GPU-only (no logprobs in the Messages API) and **parked deliberately**: F1, F2 and FX died in ways that will look like this from the inside, and `research/quality-measurement/BRIEF.md` is mandatory reading before the first line is designed |
| **Persistent reader simulation** — attention, expectation, confusion and voluntary stopping over a trajectory | reading as behaviour rather than as one isolated verdict | already exists as `bcr.v0` and `fcr.v0` (budgeted continuation; the costed feed with skim and abandonment) — built for chapters, not yet pointed at this defect class; connecting them runs through the same gradient validation as everything else |

Multi-agent reconciliation wider than the tribunal (independent noticers who challenge and
reconcile spans) is the tribunal's natural next size if the tribunal's evidence mechanism
survives its kills; it is not built first because a panel that reconciles by *agreement*
rather than by *verifiable evidence* is the verdict channel with extra steps.

## The order of belief, restated once

A mechanism earns attention by separating the market's own top from its own bottom, blind.
Only then is its reading of our text meaningful, and the meaning runs one way: it may
condemn our text, and it may be withdrawn — what it may not do is certify us against the
operator's judgment, which is the ground truth this programme exists to reach (boundary 3).
