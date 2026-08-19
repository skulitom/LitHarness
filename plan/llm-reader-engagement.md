# Maximising engagement with LLM reader simulations — and the promise & payoff workstreams that feed it

**Status: DRAFT design and handoff prompt, 2026-08-19.** Written to be handed to an
executing session as its task prompt. Not a pre-registration: nothing below is registered
until the numbered constants are frozen and committed alongside the code that enforces
them, in the same commit, before the first row exists — the discipline
[reader-judge-loop.md](reader-judge-loop.md) §1 set.

**Regime.** Every measurement in this program is machine-side. No human feedback enters
the product's core loop — steering, selection, prompts, gates, calibration targets.
Human-written material appears in exactly two **out-of-loop** places: the §A6 comparison
baseline, and W4's small owner-read validation set. The claim this program can license is
worded operationally and only this way: *held-out LLM reader simulations, under a fixed
reading budget, allocate more of it to this book and abandon it later.* That is the working
definition of engagement here.

**Three channels, and which is licensed for what** — the taxonomy that keeps this document
consistent with the refutation ledger:

- The **verdict channel** (ask a model to prefer a side or rate a text) is dead three times
  over (chose-A 0.8151 over 568; E1/E2 VOID at 0.6408 over 142; "keep-reading" on 195 of
  196). Nothing in this document uses it, including as a study leg.
- The **report channel** (E6: *name the single most salient difference*, byte-frozen
  question and matchers) is the one licensed verbal frame. W3 and W4's reader questions
  ride it and nothing else.
- The **behavioral channel** (BCR, Part A) is new. It elicits no verbal verdict — the
  signal is what a budgeted reader *does* — so it is not an A/B preference leg; and it
  borrows no validity from E6: it must earn its own licence through §A2–A3 before any row
  counts.

---

## Part A — the Budgeted Continuation Reader (BCR)

**Why this instrument shape and no other.** The three verdict-channel deaths share one
structure: an unconstrained verbal report costs the model nothing and reflects its trained
disposition rather than the text. BCR removes both properties at once:

- **Behavioral, never verbal.** The signal is what the reader does with a scarce budget.
  Verbal residue is retained verbatim as a discard-style nomination corpus and never scored.
- **Scarcity is constructed.** Continuation is free for a model, so the budget makes it
  expensive: every chunk of book A read is a chunk of book B unread. The 195/196 result is
  exactly what continuation looks like when it costs nothing.
- **Contrast-shaped.** Head-to-head between two texts, blinded and position-swapped — the
  one frame that has survived every validity check in this project.

### A1. The instrument, v0

A session is one reader model, fresh context, and a shelf of **two** texts (`M = 2` in v0;
a larger naturalistic shelf is a later replication, not the primary). Both texts are served
in fixed-size chunks (`CHUNK_TOKENS ≈ 400`, boundaries at paragraph breaks), so length
cannot masquerade as interest. The reader holds a budget of `B` fetches (`B ≈ 12`) and
**must spend all of it** — spending is forced, allocation is the choice, so "stopping"
cannot be performed as free diligence. Each step: choose which text to continue; the next
chunk of that text is revealed.

Recorded per session: the full fetch sequence; allocation share `S(target) ∈ [0, 1]`;
abandonment position (last fetch of each text); binarized outcome (which text took the
larger share, ties per a declared policy).

Constants and discipline:

- **The system prompt is minimal, behavioral, and byte-frozen**, with a test that fails on
  divergence — T0's A4 put ~14 points of a verdict on wording, so a reworded prompt is a
  different instrument with no evidence. No quality vocabulary, no evaluation framing: the
  persona is someone reading for pleasure with a fixed amount of reading ahead of them.
- **Draws and seeds are content-derived** (digest-keyed, replayable, non-re-rollable),
  inheriting `domain/audit.py`'s discipline. Position is swapped across replicates.
- **Loop substrate is this system's own generated prose only.** CDG's death is the reason:
  a model's familiarity with published text swings model-based measures harder than real
  structural damage does. Own prose is un-memorized by construction. Distractors come from
  a **pinned reference shelf** of own-generated books, content-addressed so every target is
  measured against the same opponents. Published human prose enters exactly one place — the
  out-of-loop baseline arm of §A6 — and nowhere near steering, selection, or a prompt.
- **Statistics reuse the existing machinery.** Binarized outcomes drop into
  `preference.win_rate_lower_bound`'s two-way clustered bootstrap with (model-family ×
  persona) as the reader dimension and pairs as the other; its floors and its attainability
  simulation come with it.

### A2. Seating a reader model — preconditions, per model, before its rows count

A model that fails any precondition is unseated, and the failure is recorded the way the 4B
model's positional failure was. Expect the capability floor above 4B-class models; the
candidates are the pinned frontier tier plus `gpt-oss:20b` / `phi4` locally (MirrorBench
venv, duty-cycle governor and checkpoint-per-unit for anything sustained on the 4090).

| id | control | pass condition | can it fail? |
|---|---|---|---|
| P1 | placebo shelf: two byte-identical texts | `S` within a pre-declared band around 0.5 | yes — a labeling/slot artifact moves it |
| P2 | positional symmetry across swapped replicates | allocation by slot within ±band | yes — A6-of-T0's failure mode, measured before anything else runs |
| P3 | whitespace sham | band around 0.5 | yes — a reader of surface artifacts fails it |
| P4 | rename sham (entities re-named, stopword-bug lesson applied) | band around 0.5 | yes — the CDG killer, kept standing even on own prose |
| V1 | variance floor over ≥20 own-generated texts | between-text variance in `S` exceeds replicate noise at a declared ICC floor | yes — a uniform allocator is the 195/196 constant function wearing a budget |

### A3. Validity battery — kill conditions for the instrument itself

Run once per seated model, pre-registered before the first optimization arm:

- **D1 — dose-response on certified damage.** Graded paragraph shuffle, matched-word-count
  random deletion, `stat_flatten`, `interiority_strip` at increasing dose versus the intact
  original. Allocation against the damaged side must increase with dose, monotone by
  isotonic fit. **An A2-style inversion — strongest preference at the smallest dose — kills
  the instrument**, not the arm. (If W3's cadence discrimination survives, its cadence
  variants join this battery as an engagement-relevant manipulation family.)
- **D2 — transplant sensitivity, and it is core competence rather than optional.** Mid-book
  chunks replaced by length-matched chunks from a *different own-generated book* (same
  generator and profile, so style is held near-constant and story membership is what
  varies). Continuation past the transplant must drop relative to an intact control. The
  persona panel was near-blind to transplant, which capped it at clause-to-paragraph scale;
  **a continuation instrument that does not care whether the text belongs to its book is
  not measuring wanting-to-continue, and transplant-blindness is a kill.**
- **D3 — budget invariance.** Rankings at `B` and `2B` agree above a declared Kendall-tau
  floor; an instrument whose ordering depends on the budget is measuring the budget.
- **D4 — cross-family agreement, necessary and not sufficient.** Two-plus disjoint model
  families; agreement beyond a declared band is required for any pooled number, and
  disagreement is reported per family rather than averaged away. Agreement can still be
  shared training bias — that residual is stated, not solved.
- **Attainability before spend** (the declared-bars rule): simulate, at the declared
  replicate and pair counts, the power to detect allocation shifts of 0.05 / 0.10 / 0.15,
  and size batches from that table rather than from the floor.

### A4. The optimization experiment — selection pressure

Selection-only pressure at this stage, because best-of-K is bounded rejection sampling with
arithmetic the project already trusts (BRIEF §6 item 6), and §61 Add 3 already licenses
selection.

- **Substrate.** New books drafted by the standard loop under `--plan-search` (K = 3
  siblings per beat), paired premises and seeds across arms.
- **Arms.** `SEL-BCR`: sibling selection by steering-family BCR head-to-heads. `SEL-CTRL`:
  the existing tie-break selection. Same beats, same budgets.
- **The family firewall — the machine version of I1, and it is the load-bearing rule.** The
  **steering family** selects and never measures. The **measurement families** evaluate
  finished books and never steer. Measurement families are disjoint from the steering
  family **and from the generator's family** (self-preference is a known LLM failure mode
  and one generator gives no way to control it in-band; excluding kin from measurement is
  the honest containment). Declared before the first run, write-once, exactly as `pools`
  already does for its two pools.
- **Primary endpoint, exactly one:** area under the whole-book continuation curve by
  measurement families (the target book against the pinned reference shelf, position-swapped
  replicates). Median abandonment position is secondary. Anything further divides alpha and
  says so.
- **Goodhart tripwires, computed in the same pass, reported beside the headline always:**
  registered axis counters (`em_per_1k`, `interior_per_1k`, `system_digit_count`) for
  drift; `scene_echo` / `repeated_span`; word-count ratio and layout identity (§78's
  confound); and the promise/payoff ledger's open-versus-paid density — **the cheapest way
  to game a continuation metric is stated now: open loops and never pay them.** A book that
  wins BCR while opened-promise density diverges from paid-promise density has found the
  disease, not an improvement. (W1's typed ledger upgrades this tripwire from raw density
  to per-kind density; W4's landing check, if it survives, closes the "paid but never
  landed" variant of the same exploit.)
- **Outcomes, pre-committed.** Measurement-family separation with a clean tripwire panel is
  the finding. Separation *with* a fired tripwire is an exploit map — archived as a result
  about the instrument's attack surface, which is worth having. No separation archives the
  design beside `refuted_metrics.py`, per house discipline.
- **Escalation rule.** Any increase of optimization pressure beyond best-of-K re-runs
  §A2–A3 on the *post-optimization* distribution first, because pressure moves the
  deployment distribution off the passive one the battery was measured on, and that voids
  the evidence (BRIEF §6 item 6's second half). §A5 states the one budgeted exception.

### A5. Iterated optimization under a bounded budget

"Gradient" first, so the word doesn't promise what the architecture forbids: there is no
literal gradient available. The generator is a pinned frontier provider that cannot be
trained, and §1a.5 is why a trainable local generator is not the answer — a weaker
generator adopted to make optimization convenient is the quality defect the no-fallback
decision exists to prevent. What is available is the **textual gradient**, and the repo has
already built its carrier: BCR supplies an axis its *direction* (the allocation win-rate of
the higher-counter side, through the same clustered bound, floors, and attainability table
the `Direction` object already declares), E6 names *which axis and where* between the high-
and low-allocation sibling, and the feedback seam
([reader-judge-loop.md](reader-judge-loop.md) §5.1) carries the named, located difference
into the next draft prompt. The composition rule survives intact: a judged difference on an
axis BCR has not directed is discarded into the nomination corpus, never prompted —
confabulated feedback is the failure that rule exists to stop, and iteration multiplies
whatever it is fed.

Iteration under budget is five disciplines, each of which buys most of its win for a small
fraction of the naive cost:

1. **Optimize the policy, not the book.** The unit of iteration is the drafting policy —
   the standing craft directives in the system message — never an individual manuscript. A
   book improved once is one book; a policy improved once amortizes over every book after
   it. Population of `P = 8` policy variants, mutated between generations by the textual
   gradient (the E6-named differences between each generation's winners and losers, on
   directed axes only). W2's payoff windows are a natural policy lever here: cadence
   directives are exactly the kind of standing instruction a policy variant can carry.
2. **Racing, not full evaluation.** Successive halving, pre-registered: 8 → 4 → 2 → 1
   across generations, each survivor earning more BCR sessions than the round before.
   Losers are cut on few sessions; only the final pair gets an attainability-sized batch. A
   wrongly cut variant costs one mutation slot, not the campaign.
3. **Local families steer, frontier families confirm.** The inner loop runs entirely on
   seated local models (§A2 gates which ones may sit) under the 4090's duty-cycle governor
   — steering verdicts at effectively zero marginal cost. Frontier measurement families run
   only at generation boundaries, and the boundary check is two-sided: if the frontier
   ordering of survivors diverges from the local ordering beyond a declared band, the inner
   loop has been optimizing the cheap proxy, the divergence is the finding, and the
   generation is re-scored on the frontier families before anything is promoted.
4. **Tripwires every iteration, because they are free.** The deterministic panel —
   registered counters, `scene_echo`/`repeated_span`, ledger open-versus-paid density (per
   kind, once W1 lands), length and layout drift — costs no model calls and runs per
   generation, so an exploit is caught at the iteration that found it rather than at the
   end of the campaign.
5. **Bounded generations, and the battery re-run checkpointed.** `G ≤ 5`, declared before
   the first generation. §A4's escalation rule is honored at the *end* of the campaign —
   the full §A2–A3 battery re-run on the post-optimization distribution — rather than per
   generation. That is the deliberate budget compromise, and its residual is stated:
   pressure accumulates across generations while the battery sleeps, so an exploit subtle
   enough to dodge the free tripwires is caught only at the checkpoint. The per-generation
   tripwires are what make that gap survivable.

**Sample budget at the declared shape** (G = 4, halving 8→4→2→1, 6-scene books at K = 3,
measured ~$0.30/scene): 15 fitness books ≈ **$81** of frontier drafting; inner-loop BCR
≈ 1,000–1,500 local sessions ≈ **$0** marginal (a few days of governed GPU time,
checkpoint-per-unit); frontier boundary confirmations ≈ 3 × 90 sessions ≈ **$30–60**. The
campaign's winner then enters §A4's A/B as the `SEL-BCR` arm's policy, confirmed against
the untouched control by held-out families and §A6's baseline — roughly **$250–300 end to
end**, with the replay caches making every re-analysis free.

What is deliberately *not* done under budget: no surrogate model ever picks a winner (a
counters-to-allocation surrogate may prune, never promote — the surrogate is the Goodhart
magnet this repo's whole ledger warns about); no naturalistic multi-book shelf replication
until a winner exists; no per-generation battery re-runs.

### A6. The human-prose baseline — out of the loop, in the measurement

Published prose (the RoyalRoad corpus already in hand, MIT-licensed) is a **baseline to
compare results against and nothing else**: it never steers, never seeds a selection, and
never appears in a prompt. Its one role is the comparison arm that turns §A4's endpoint
into a headline with the §61 shape, restated for this regime:

> the lower bound of the clustered 95% CI on held-out reader-sim allocation share, our book
> against matched published-human chapters, blinded, position-swapped, exceeds 0.5.

Matching is on tags, era, and chapter length, from the shards in hand — the *prose* is the
baseline, not its popularity columns, so nothing here touches the refuted conversion label.

**The memorization control is mandatory on this arm, not advisory.** A reader-sim may
allocate budget to published text because it has read it in training, and CDG measured that
familiarity term outswinging real damage. Two rails, pre-registered:

1. **Both sides run entity-renamed** (with the stopword-bug lesson applied), so neither
   side carries its trained-on surface.
2. **Per published text, the rename-delta is measured**: allocation with original names
   minus allocation renamed. A text whose delta exceeds a declared band is excluded as
   familiarity-driven, and the exclusion count prints beside the headline — a silent
   exclusion would read as "matched corpus" when it was "corpus the models forgot".

Popular serials are the *most* memorized, so the exclusion rule biases the surviving
baseline toward obscurity; that bias is stated on the result rather than argued away, and
the matched-on-tags requirement bounds how far it can drift.

### A7. Cost and sequencing within Part A

Instrument + battery is mostly local-model spend plus bounded frontier calls over existing
corpora and manipulations — the manipulation generators already exist in
`research/quality-measurement/`. Order: seat models (§A2) → battery (§A3) → freeze
constants and register → arms (§A4) / campaign (§A5). Nothing in §A4–A5 starts before
§A3's kills have had their chance.

---

## Part B — Task: develop the unbuilt half of promises & payoffs

### Goal, in reader-effect terms

PLAN.md quality goal 3 (line ~180): "Promises planted get paid, on a cadence a reader can
feel; stakes ratchet rather than reset." The existing machinery detects *unpaid* and
*late*. This task develops the other types of promise/payoff work: typed promises,
planner-scheduled payoffs, cadence as a felt quantity, and verification that a payoff
actually landed. Every proposed metric must be stated as an effect on a reader, not a
critic standard (house philosophy).

### Read first (do not skip)

- `src/litharness/domain/promises.py` and `migrations/023_promises.sql` — the ledger, and
  the three traps that made it a separate table.
- `src/litharness/application/summarize.py` — the extended summary call that writes the
  ledger (`promises_opened`/`promises_paid`/`due_hint`/`delta`); §15's fold-asks lesson:
  one invocation, no new model call.
- `src/litharness/domain/integrity.py` — `promise.overdue.v0` (advisory MINOR) and
  `craft.scene_delta.v0` (INFO); §10.4 is the only promotion path out of advisory.
- `src/litharness/application/outline.py` — milestones (4–8, anti-stasis validation,
  PROPOSED records placed at beats).
- PLAN.md §9.1 (~line 676): planner-scheduled payoff windows and the LitRPG progression
  schedule — the declared destination for this work.
- `plan/stage-0-decisions.md` §87–§91 and [reader-judge-loop.md](reader-judge-loop.md) —
  what the reader instrument can and cannot carry (see Non-negotiables).

### W1 — Typed promises (enabler, code-only)

The ledger is untyped; "the book owes a duel" and "the book owes a tonal register" are
different debts with different payoff shapes. Add a `kind` column (migration 028+, STRICT,
additive): start from {plot, character, progression, mystery, tone} but derive the final
set from what the summary model actually reports when asked — run the fold-ask on existing
summarized scenes and let the observed distribution prune the taxonomy before freezing it.
Constraints: `promise_id` stays sha256(book_id + subject) — a re-reported kind under the
same subject is the same row, never a duplicate; unknown/absent kind degrades to untyped,
never blocks. Extend the summary schema in the same invocation. Done when: replayed
re-summarization converges to identical rows.

### W2 — Planner-scheduled payoffs (PLAN §9.1)

Milestones schedule *state*; nothing schedules *payment*. Extend the outline ask so open
promises fed into the outline call come back with target payoff windows (scene ranges in
`beats_for` keys), validated like milestones are: a window must name existing scenes, at
least one promise per act must pay before the final scene (no "everything resolves at the
end" schedule — the anti-stasis rule's sibling), and a non-chronological template abstains
entirely. Scheduled windows are PROPOSED-grade, ride the packet as debts ("owes: … pay
within s07–s09"), never as fact. The existing overdue detector stays the evaluator side; do
not duplicate it. Done when: tests cover convergent replay, abstention, and the window
validation rejecting an all-at-the-end schedule.

### W3 — Cadence as a felt quantity (research-first; NO detector yet)

"Cadence a reader can feel" is an unmeasured claim. Before any detector: a pre-registered
study in `research/quality-measurement/` that manipulates payoff cadence (e.g.
front-loaded / even / starved-then-dumped variants of the same material) and asks whether
the reader instrument can *name the difference* — E6-style report-channel naming, not
preference. Only a discrimination that survives becomes a candidate metric; if nothing
survives, the null is the result and W3 stops there — record it and move on.

*Interlock with Part A:* a surviving cadence discrimination does two further things —
its variant generator joins §A3's D1 battery as an engagement-relevant manipulation
family, and cadence becomes a candidate axis eligible for a BCR-supplied direction
(§A5's textual gradient can then carry it into drafting policy).

### W4 — Did the payoff land? (research-first)

Payment is currently asserted by the same summary call that reports it — self-grading.
Design a separate landing question (a paid promise's opening excerpt + paying excerpt;
report channel: what debt does the second scene pay, named blind). Pre-register agreement
bars against a small human-read set before trusting it. If it survives, wire it as an
advisory finding (`promise.landing.v0`, MINOR) through §10.4's path; if not, record the
null.

*Regime note:* the human-read set here is owner-supplied, out-of-loop validation of the
instrument — the same standing as §A6's baseline — and never a feedback source into
drafting. *Interlock with Part A:* a surviving landing check closes the "marked paid but
never landed" variant of §A4's cheapest-gaming exploit.

### Non-negotiables (measured lessons — violating these repeats a recorded failure)

1. Reader questions ride the REPORT channel. §89: the verdict channel weighted position
   over text ~4,676x; E1/E2 (prefer a side) are VOID, E6 (name the difference) survives.
   No A/B preference legs. (Part A's behavioral channel is not a preference leg — no
   verbal verdict is elicited — and it earns its own licence through §A2–A3, borrowing
   nothing from E6.)
2. Declared bars must be attainable: before registering any bar, check range, direction,
   unit, and non-emptiness of the quantity it names (seven prior declarations failed
   exactly this).
3. Fold asks: no new model invocation where an existing call can carry the question
   (summary call for W1, outline call for W2).
4. Everything model-sourced stays advisory (MINOR/INFO) until §10.4 promotes it. Nothing
   in this task blocks or parks.
5. Abstain over guess: no story keys outside `beats_for`'s minting; templates that aren't
   chronological get no rows, no windows, no findings.
6. Debt register in the packet: rendered lines must read as owed, not as established fact
   (`describe_owed`'s rule).
7. Research mechanics: MirrorBench venv; digest-keyed replay caches; raw JSONL + summary
   JSON in `research/quality-measurement/results/`. If any leg runs local GPU inference,
   use the duty-cycle/checkpoint-per-unit recipe (thermal hard-shutdown risk on the 4090
   box).
8. Process: start by writing `plan/promise-payoff-development.md` and a new
   stage-0-decisions entry (next free §, currently §92) declaring scope and the
   pre-registered bars BEFORE running anything. Parallel sessions run on this repo — keep
   changes additive and don't renumber or rewrite others' sections.

### Out of scope

- The LitRPG progression schedule against the Game-System Engine (§9.1's third bullet) —
  verify the engine's state and note it in the plan doc, but do not build against it here.
- Promoting any finding past advisory — that is §10.4's job, not this task's.
- Touching `state_records`, `open_threads`, `detect_contradictions`, or
  `has_story_vocabulary` — the ledger's separateness is the design.

---

## Part C — interlock, execution order, deliverables

### How the parts feed each other

- **W1 → A4/A5:** the typed ledger upgrades the Goodhart tripwire from raw
  open-versus-paid density to per-kind density — a book gaming continuation by opening
  cheap mystery hooks while paying only tone debts becomes visible.
- **W2 → A5:** payoff windows are the concrete standing directive the policy-iteration
  campaign mutates; "cadence a reader can feel" becomes a policy parameter with a
  measurable behavioral consequence.
- **W3 → A3 and the axis registry:** a surviving cadence discrimination supplies both a
  battery manipulation family and a candidate axis for a BCR direction. A null stops W3
  and leaves Part A unchanged.
- **W4 → A4:** a surviving landing check closes the paid-but-never-landed exploit; as an
  advisory finding it also rides the daily digest, where a campaign generation that games
  it shows up between boundary confirmations.

### Execution order for the handoff session

1. **B8 first:** `plan/promise-payoff-development.md` + the stage-0 §92 entry, scope and
   pre-registered bars declared before anything runs.
2. **W1 then W2** — code-only, additive migrations, replay-convergence tests. Cheapest and
   unblocking.
3. **A2 seating + A3 battery** in parallel where session capacity allows (research-side;
   MirrorBench venv, governor discipline). Freeze Part A's constants and register only
   after the battery.
4. **W3 and W4 studies** (report channel; nulls are results and are recorded as such).
5. **A4 arms / A5 campaign last** — nothing here starts before A3's kills have had their
   chance and the tripwires are typed (W1).

### Deliverables

1. `plan/promise-payoff-development.md` + stage-0 § entry with pre-registered bars.
2. W1 and W2 implemented with migrations and tests (idempotent replay proven).
3. W3 and W4 study results (including nulls) in `results/`, each with a one-paragraph
   verdict in the plan doc.
4. Part A: per-model seating results, battery results including kills, the frozen
   registration, and — if reached — the campaign readout with its tripwire panel and §A6
   baseline headline.
5. A closing PLAN.md note mapping what shipped against §9.1's ledger bullet.

### Relation to what stands

The Reader/Judge split survives with the reader role staffed by BCR: valence stays
behavioral and contrast-shaped, and the E6 judge channel is unchanged — it names axes and
locations, here between high- and low-allocation siblings, through the existing discard
door for anything unregistered. `pools`, the replay caches, the clustered bound, and the
attainability harness are reused rather than rebuilt. Re-wording §61's headline bar under
this regime is a stage-0 decision for the owner and is out of scope for this document.
