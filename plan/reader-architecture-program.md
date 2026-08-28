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

## Production control boundary, implemented 2026-08-27

The production architecture no longer reads raw steering rows into a drafting prompt. At an
opted-in chapter boundary it freezes one durable job per steering reader and records a versioned
observation with source, context, prompt, schema, persona, provider, and model provenance.
Mechanism versions are append-only and explicitly `experimental`, `qualified`, or `withdrawn`.
Only a complete panel produced by the current, exact qualified version is eligible for the next
stage; making a withdrawn version current also refuses already-frozen controller work before it
can spend or dispatch direction.

That stage records an immutable editorial intervention with one of five decisions: `satisfy`,
`defer`, `subvert`, `refuse`, or `challenge_lock`. The controller sees the reader evidence, the
current plan, eligible future scenes, and author locks, but not a prose-editing instruction.
Only `satisfy` and `subvert` may dispatch direction; they submit a machine-authored chapter note
to the existing Narrative Planner. `challenge_lock` makes a conflict visible and has no override
path. Before dispatch, a deterministic fingerprint check refuses a directive that repeats a
reader's six-word phrase or an eight-word span from a longer response; the controller has to
abstract the underlying need rather than laundering reader vocabulary. The Narrative Planner
still validates scope, refuses edits to accepted scenes, downgrades machine attempts to mint
locks, and commits a new immutable plan revision. Thus simulated readers are an objective signal
within author feasibility constraints, not lower-authority decoration and not higher-authority
raw prompt text.

The bundled `reader.anticipation.v0` version remains **experimental** because the transfer result
has not licensed it. `--reader-checkpoints` may collect evidence, but cannot make it steer. The
control plane is ready for a mechanism that earns qualification; it does not manufacture that
qualification from its own existence.

Qualification is now an operational, closed artifact rather than an arbitrary digest. It requires
held-out books and transformation implementations, edit-fingerprint and memorisation controls,
full-volume/cross-volume/growing-prefix results, transfer, and the operator's fixed acceptance test.
`reader-mechanism qualify` refuses a missing or failed field; `withdraw` closes already-queued work.
Accepted targeted scenes record durable realizations, proving delivery without claiming efficacy.
The listing command now retains appetite as experimental evidence only and has no raw-feedback
renderer or revision call.

## The mechanism families, and where each stands

| family | what it extracts | state in this repository |
| --- | --- | --- |
| **Generative tests** — rewrite, continue, compress, recall; quality inferred from what the model does | generative fluency, which stayed reliable where critical judgment went blind | `blurb_rewrite.v0` and its frozen registration are built; no new run is required for the architecture work |
| **Comparative reading with a reference shelf** — the register held in context, not recalled | perception of deviation against visible evidence | `blurb_shelf.v0.2` is built with amended controls; its empirical result remains separate from production qualification |
| **Adversarial span tribunal** — one agent flags, another must defend the span with evidence code can verify | disagreement resolved by checkable evidence instead of a third opinion | `blurb_tribunal.v0` is built and has run once. The resolver is deterministic (a claimed parallel either exists in the reference text or it does not), and the run's market legs are transport-clean with KG separated 8 of 8 — so the family's gradient precondition is met. Its **`ours` leg is void for transport**: every failure in that run was one weekly-limit 429 and all eighteen landed there, so nothing it says about our listings has been measured yet. Stage-0 §145; re-run owed |
| **Cross-family readers** — the evaluator unrelated to the generating model | self-familiarity attacked directly | adapter seams exist, but local-model execution is parked and is not a dependency of production or this programme's engineering |
| **Representation-level** — per-token surprisal, logit/activation lens | quality sensitivity that exists internally but dies in verbal self-report | handoff task 2 plus the operator's lens direction. GPU-only (no logprobs in the Messages API) and **parked deliberately**: F1, F2 and FX died in ways that will look like this from the inside, and `research/quality-measurement/BRIEF.md` is mandatory reading before the first line is designed |
| **Persistent reader simulation** — attention, expectation, confusion and voluntary stopping over a trajectory | reading as behaviour rather than as one isolated verdict | already exists as `bcr.v0` and `fcr.v0` (budgeted continuation; the costed feed with skim and abandonment) — built for chapters, not yet pointed at this defect class; connecting them runs through the same gradient validation as everything else |

Multi-agent reconciliation wider than the tribunal (independent noticers who challenge and
reconcile spans) is the tribunal's natural next size if the tribunal's evidence mechanism
survives its kills; it is not built first because a panel that reconciles by *agreement*
rather than by *verifiable evidence* is the verdict channel with extra steps.

## Research update, 2026-08-27

Current creative-writing research and the repository's own results point to salience as the
bottleneck: models can produce plausible criticism while missing the largest defect, and they
systematically overweight style relative to event and character. The next common substrate is a
causal salience battery with hidden, code-checkable damage keys; prompts, multi-agent mechanisms,
and activation probes compete on that same battery rather than defining their own targets. The
call-free census, first ecological state generator, fingerprint matching, evidence manifests, and
serial-distance rungs are now implemented. The evidence, construction, kills, and scope boundary
are in
[`reader-perception-research.md`](reader-perception-research.md).

## The order of belief, restated once

A mechanism earns attention by separating the market's own top from its own bottom, blind.
Only then is its reading of our text meaningful, and the meaning runs one way: it may
condemn our text, and it may be withdrawn — what it may not do is certify us against the
operator's judgment, which is the ground truth this programme exists to reach (boundary 3).

That screen licenses **one faculty**: reading the registered follower gradient. PLAN.md
§1a.3's continuation hypotheses are other faculties. A mechanism can pass the gradient
and still prefer polish to event — already what the listing inversion measured. The
causal salience battery exists to test those faculties separately; a gradient pass does
not buy dramatic function, progression-as-drama, or payoff.
