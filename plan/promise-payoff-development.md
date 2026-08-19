# Promises and payoffs: the unbuilt half, and the reader instrument that would price it

**Status: PRE-REGISTRATION, 2026-08-19.** Written before the first row of any study below
exists, which is the only thing that makes it a pre-registration rather than a report.
Executing [plan/llm-reader-engagement.md](llm-reader-engagement.md); the stage-0 entry is §94.
Every numbered constant here is frozen in the module that enforces it and copied into that
module's result files, per the discipline [reader-judge-loop.md](reader-judge-loop.md) §1 set
and `axiom_battery.py` follows.

**Regime.** Machine-side measurement only. No human feedback enters steering, selection,
prompts, gates or calibration targets. Human-written material appears in exactly two
**out-of-loop** places, both of them comparison arms and neither of them a feedback source:
Part A's §A6 published-prose baseline, and W4's owner-read validation set.

---

## 0. What already exists, so this document only adds

The promise ledger landed as §61 Add 2 and it is smaller than PLAN.md §9.1's bullet:

| piece | state | where |
|---|---|---|
| promises opened / paid, written from the summary call | **built** | `application/summarize.py`, migration 023 |
| `promise_id` = sha256(book + subject); re-report converges | **built** | `domain/promises.py` |
| overdue arithmetic, MINOR/advisory | **built** | `domain/integrity.py` `promise.overdue.v0` |
| open promises rendered as debts in the packet | **built** | `describe_owed`, packet THREADS |
| **promise kind** — what sort of debt this is | **absent** → W1 |
| **scheduled payoff windows** — when the planner intends payment | **absent** → W2 |
| **cadence as a felt quantity** | **unmeasured claim** → W3 |
| **did the payoff land** | **self-graded by the reporting call** → W4 |

Two properties of the built half are load-bearing for everything below and are not re-argued
here: the ledger is deliberately **not** a THREAD state record (migration 023's header records
the three ways that would break `open_threads`, `detect_contradictions` and
`has_story_vocabulary`), and every row is model-sourced, so nothing built on it may block or
park.

### 0.1 The Game-System Engine, verified rather than assumed

§9.1's third bullet — the LitRPG progression schedule planned *against* the Game-System Engine
so the plan is mechanically satisfiable — is out of scope for this work, and the reason is a
verified absence rather than a scheduling preference. Checked in source on 2026-08-19:

- There is **no forward Game-System Engine interface in this repository**. `grep` for
  `GameSystem`, `WorldRule`, `BookWorldState` across `src/` returns nothing. PLAN.md §8.4
  settled that the LitRPG rule and predicate vocabulary is owned by the game-mechanics pack
  **inside ContinuityEvaluation**, and §8.1's forward interface — sheet, legal actions, pending
  obligations in the context packet — "has no consumer until Stage 0/1 exists".
- What this repository has instead is `domain/extraction.py`'s `progression_target`, which
  reads the nearest `PROPOSED` milestone at or after a story position, and
  `application/outline.py`'s `_milestones`, which validates a schedule against the book's own
  seed sheet and refuses one that invents statistics, schedules stasis, or schedules an
  impossible state (`impossible_fields`). That is a schedule *validator*, not a simulator.

So W2 schedules **payoffs**, which need no engine — a payoff window names scenes, and scenes
are `beats_for`'s own minting — and says nothing about levels or currency. Scheduling
progression against a simulator stays where §8.4 put it.

---

## 1. W1 — typed promises (code-only, enabler)

**The reader effect this is about.** "The book owes a duel" and "the book owes a tonal
register" are different debts with different payoff shapes, and a reader feels a missed duel
and does not feel a missed register. An untyped ledger cannot tell those apart, so neither can
any counter built over it — including Part A's cheapest-gaming tripwire, which is the concrete
reason to build this first (§5).

**Mechanism.** A `kind` column on `promises` (migration 028, STRICT, additive), reported by the
**same summary invocation** that already reports `promises_opened` — §15's fold-asks rule:
no new model call where an existing one can carry the question.

**The taxonomy is derived, not declared.** The starting set is
`{plot, character, progression, mystery, tone}`; the final set is what the summary model
actually reports when asked over already-summarised scenes. The derivation run is
`research/quality-measurement/promise_kinds.py` and it is a **read of the observed
distribution**, not a study with a bar: a kind nothing ever reports is removed before the set is
frozen, and a kind the model keeps inventing is either admitted or explicitly refused, in
writing. The reason to prune before freezing is the same one that killed twenty-one proxies —
a category invented because it sounded like part of a complete taxonomy is a category with no
evidence behind it.

**Constraints, each of which is a way this could go wrong:**

1. `promise_id` stays `sha256(book_id + subject)`. A re-reported *kind* under the same subject
   is the **same row**, never a duplicate. This is the property that makes replay converge and
   it is not negotiable for a typing feature.
2. **Unknown or absent kind degrades to untyped and never blocks.** A model that answers a kind
   outside the frozen set has produced a usable promise with an unreadable annotation, exactly
   as a fumbled `delta` already produces a usable summary with a missing annotation.
3. **Write-once, like the row.** The kind is written when the row is inserted. A later
   re-summarisation that reports a different kind for the same subject changes nothing — the
   `INSERT OR IGNORE` that makes the ledger converge is also what fixes the kind, and a kind
   that could be updated would make "what did this book owe" depend on when you asked.

**Done when:** replayed re-summarisation converges to byte-identical rows, including on a
re-report under a changed kind; an out-of-set kind lands as untyped and the summary is
otherwise unaffected; the untyped ledgers written before migration 028 read back as untyped
rather than as an error.

### 1.1 Pre-registered reading for the derivation run

Not a bar — a rule for reading the distribution, written before it is seen so it cannot be read
to suit the answer:

- A kind reported on **zero** of the observed promises is **cut** from the frozen set.
- A kind reported on fewer than **5%** of them is cut unless it is the *only* kind reported for
  some promise, in which case it is kept and the count is printed beside it.
- An **out-of-set** kind reported on ≥ 10% of promises is reported as a **nomination** and is
  admitted only by an operator act, never automatically — the axis-registry admission rule
  (`domain/axes.py`) applied one layer over, for the same reason.
- The distribution is reported per model, never pooled across models: two models' taxonomies
  averaged together are a taxonomy neither of them has.

---

## 2. W2 — planner-scheduled payoff windows (PLAN §9.1)

**The reader effect.** Milestones schedule *state*; nothing schedules *payment*. A book with
no payment schedule pays when the summariser happens to notice a payoff, which is how
"everything resolves in the last scene" gets written — the shape §52 measured in the ledger
(31 status records holding two distinct states) arriving in the promise dimension.

**Mechanism, folded into the existing outline call.** Open promises are already available where
the outline handler runs; the outline ask gains a `payoff_windows` array, validated exactly the
way milestones are, and the accepted windows ride the packet as debts:
`owes: … (due by s12, pay within s07–s09)`.

**The validation rules, and each one is a way a schedule can be worthless:**

| rule | what it refuses | why |
|---|---|---|
| a window names existing scenes | `s99` on a ten-scene book | milestones' rule; a window on a scene that does not exist is unsatisfiable |
| `first ≤ last` | an inverted window | a range that cannot contain a scene is a declared bar that cannot be met (I7) |
| the window opens at or after the promise opened | paying before the debt exists | a payoff scheduled before its promise is bookkeeping, not a schedule |
| the window ends at or before the promise's `due_key` | scheduling a payment after it is overdue | the schedule would plan the finding the detector exists to raise |
| **at least one window per act closes before the final scene** | "everything resolves at the end" | the anti-stasis rule's sibling, and the one rule here that is about the *reader* rather than about coherence |
| a non-chronological template abstains entirely | a guessed coordinate | `beats_for` refuses to mint keys there; so does this |

**Grade and blast radius.** Windows are **PROPOSED**-grade. They do not become findings; the
existing `promise.overdue.v0` stays the whole evaluator side and is not duplicated. A window
that passes and is then missed produces nothing new — which is deliberate, because a
model-scheduled window missed by a model-reported payoff is two model claims disagreeing and
neither of them is entitled to raise a finding about the other.

**Where "at least one per act" gets its acts.** From the beat sheet's own thirds, not from a
new act model: beats 1..n split into three contiguous spans by ordinal. A book too short to
have three distinct spans (fewer than 3 scenes) is exempt rather than refused — the rule cannot
mean anything there and a rule that fires on a book it cannot describe is the failure mode I7
catalogues.

**Done when:** tests cover convergent replay (the same outline answer produces the same
windows), abstention on a non-chronological template, and each validation rule rejecting its
own case — in particular the all-at-the-end schedule, which is the rule that exists for the
reader rather than for the arithmetic.

---

## 3. W3 — cadence as a felt quantity (research-first, no detector)

**The claim under test is PLAN.md §1a.3 item 3's own words**: promises paid "on a cadence a
reader can feel". Nothing in this project has measured whether that cadence is perceptible at
all, and building a cadence detector before measuring it would be the twenty-second proxy.

**Channel: report only.** §89 measured the verdict channel weighting position over text
~4,676×; E1/E2 (prefer a side) are VOID and E6 (*name the single most salient difference*)
survives. So the question is **"name the single most salient difference between these two
passages"**, byte-frozen, scored by a frozen matcher, and there is **no preference leg**.

**The manipulation.** Same material, three payoff cadences over a fixed scene span:

| variant | what it does | why it is in |
|---|---|---|
| `even` | payoffs distributed across the span | the reference, and the hypothesised preferred pole |
| `front_loaded` | payoffs clustered early, a starved tail | tests whether *emptiness later* is nameable |
| `starved_dumped` | nothing paid until a terminal cluster | the "everything resolves at the end" shape W2 refuses to schedule |

Manipulation is **structural and deterministic**: payoff-bearing paragraphs are relocated
within the span by the same length-preserving machinery `ablate.paragraph_shuffle` uses, so
word count and layout are held and the variant differs in *where the payments sit*. The
"payoff-bearing" selector is the ledger's own `paid_at_key` positions where a ledger exists,
and a declared lexical fallback where it does not — and the fallback's selections are printed,
because a selector nobody can inspect is a manipulation nobody can check.

### 3.1 Pre-registered bars, checked for attainability before they are committed

The unit is the `(pair, orientation)` cell — §89 item 6's correction: personas are replicates on
a cell, not independent judges, and a judge that ignores personas cannot reach a cell floor by
seating more of them.

- **Discrimination bar.** The frozen matcher names *cadence* on a cell at a rate whose 95%
  clustered lower bound (`preference.win_rate_lower_bound`, clusters = judge × pair) exceeds
  the **measured null** for the same matcher on the same pairs — never a nominal 0.5. The null
  is the matcher's rate on the **placebo pair** (a variant against itself) and on the
  **whitespace sham**, both of which ride every batch.
- **Both shams must hold** or the batch is VOID and reports no rate, per §89's controls rule.
- **Attainability first.** `directions.attainability` is run at the declared cell count before
  the first call, and the batch is sized from `cells_for_power`, not from the floor. A bar whose
  smallest clearing k does not exist at the declared shape is not registered — the check that
  caught seven prior declarations.

**The null is the result.** If cadence is not nameable, W3 stops: no detector, no candidate
axis, and the null is recorded in `results/` and in one paragraph here. That outcome is
expected often enough that it is written down first.

**If it survives**, two things follow and neither is automatic: the variant generator joins
Part A's D1 battery as an engagement-relevant manipulation family, and *cadence* becomes a
**nominated** axis — which under `domain/axes.py`'s admission rule means a deterministic
counter, an E6-family validation on fresh pairs the nomination corpus never touched, and a
reader-established direction, before it emits anything at all.

---

## 4. W4 — did the payoff land? (research-first)

**The defect.** Payment is asserted by the same summary call that reports the promise. A model
that reports `promises_paid: ["sealed_crate"]` has graded its own homework, and the ledger has
no independent evidence that a reader would experience the second scene as paying the first.

**The instrument.** A separate **report-channel** question over two excerpts — the scene that
opened a promise and the scene the ledger says paid it — asking blind: *what debt does the
second passage pay?* Named, not rated. Scored by whether the named debt matches the ledger's
own `subject`/`description` under a frozen matcher.

**Controls, riding every batch:**

- **Unpaid control.** A promise the ledger records as still open, paired with an arbitrary
  later scene. The instrument must name **no** debt there more often than on the paid pairs; an
  instrument that always finds a payoff has found nothing.
- **Mismatched control.** A paid promise paired with the scene that paid a *different*
  promise. This is the control that separates "this scene pays something" from "this scene pays
  *that*".
- **Placebo.** The opening scene paired with itself.

### 4.1 The out-of-loop human set, and exactly what it is for

A small owner-read set — the operator reading N promise pairs and marking landed / not landed —
is the **validation** target for the agreement bar. Its standing is §A6's: out-of-loop, never a
feedback source, never in a prompt, never a steering verdict. Under the LLM-only regime this is
the one shape human reading may take, and the reason it is admissible is that it validates an
*instrument* and does not steer a *book*.

**The bar, pre-registered:** the landing check's agreement with the owner's marks, on the
held-out half of that set, clears the agreement its own **mismatched control** achieves, at the
declared cell count and clustered lower bound. Agreement against chance is not the bar —
agreement against the control that shares every nuisance property is.

**If it survives**, it wires as `promise.landing.v0`, **MINOR/advisory**, through §10.4's
promotion path and no other. If it does not, the null is recorded and the ledger keeps
self-grading with that fact written next to it.

---

## 5. Part A — the Budgeted Continuation Reader, and where its substrate stops

The instrument is `research/quality-measurement/bcr.py`; its pre-registration is the frozen
constant block at the top of that module, copied into every result file it writes. This section
records only what a reader of *this* document needs: what the instrument is for, and the
substrate finding that bounds what it can currently say.

**What it is.** A session is one reader model, fresh context, and a shelf of two texts served
in fixed-size chunks. The reader holds a budget of fetches and **must spend all of it**;
spending is forced and only allocation is chosen, so "stopping" cannot be performed as free
diligence. The signal is the allocation share — what a budgeted reader *does* — and no verbal
verdict is elicited. Verbal residue is retained verbatim as a nomination corpus and never
scored, exactly as `JudgeDiscard` retains E6's unmatched sentences.

**Why this shape.** The three verdict-channel deaths (chose-A 0.8151 over 568; E1/E2 VOID at
0.6408 over 142; keep-reading on 195 of 196) share one structure: an unconstrained verbal
report costs the model nothing. BCR makes continuation expensive by construction. It is not an
A/B preference leg, and it borrows no validity from E6 — it earns its own licence through the
seating controls and the battery or it earns none.

### 5.1 The substrate finding, measured 2026-08-19, before any call was bought

At the registered shape (`BUDGET = 12` fetches of `CHUNK_WORDS = 300`) a text must hold at
least 3,600 words or the budget exhausts it and there is no allocation to observe. Counted:

    own-generated prose in this repository
      corpora/toll.db (= corpora/toll-scenes.json)   10 scenes,  10,049 words   1 book
      exports/book-snapshots.db                       2 books,   ~950 words each — IMPORTED, not generated
      litharness_contracts golden fixtures            2 books,   ~800 words each — AUTHORED fixtures

So there is **exactly one own-generated text long enough to be a shelf member**, and the
consequences are asymmetric across the battery rather than uniform:

| leg | needs | runnable now |
|---|---|---|
| P1 placebo, P2 positional symmetry, P3 whitespace sham, P4 rename sham | one text vs. a transform of itself | **yes** |
| **P5 non-degeneracy** *(added after the pilot; see §7)* | any six sessions | **yes** |
| D1 dose-response on certified damage | one text vs. damaged self | **yes** |
| D3 budget invariance | D1's shelves at `B` and `2B` | **yes** |
| D4 cross-family agreement | any shelf, two disjoint families | **yes** |
| **V1 variance floor** | **≥ 20 own-generated texts** | **no** |
| **D2 transplant sensitivity** | **a second own-generated book as donor** | **no** |
| §A4 arms, §A5 campaign, §A6 baseline | a pinned reference shelf of own-generated books | **no** |

**V1 and D2 are recorded as NOT RUN with a cost rather than skipped**, because a battery
reporting four of six passes and silently omitting two reads as a seated model. D2's status is
the sharper one: the plan document calls transplant-blindness a **kill**, so a model that has
not been asked cannot be seated no matter how the other five read. The cost to close both is
the same purchase — the fitness books §A5 budgets at roughly $81 of frontier drafting — and
until it is made, every BCR number in this repository is a statement about the instrument's
controls and not about any book.

### 5.2 What Part B hands Part A

- **W1 → the Goodhart tripwire.** The cheapest way to game a continuation metric is to open
  loops and never pay them. The typed ledger upgrades that tripwire from raw open-versus-paid
  density to **per-kind** density, which is what makes visible a book that opens cheap mystery
  hooks while paying only tone debts.
- **W2 → the policy lever.** Payoff windows are a standing craft directive, which is exactly
  the unit §A5's campaign mutates.
- **W3 → the battery and the axis registry**, on survival only.
- **W4 → the paid-but-never-landed exploit**, closed on survival only.

Each of those is conditional on a measurement, and each null leaves Part A exactly as it was.

---

## 6. Non-negotiables, and where each is enforced

1. **Reader questions ride the report channel.** W3 and W4 ask models to *name* things.
   Neither has a preference leg. Part A elicits no verbal verdict at all.
2. **Declared bars must be attainable.** Range, direction, unit and non-emptiness checked
   before commit, and an attainability simulation at the declared shape. Enforced as a
   `--selftest` that fails, not as a habit.
3. **Fold asks.** W1 rides the summary call; W2 rides the outline call. No new invocation.
4. **Everything model-sourced stays advisory.** MINOR/INFO until §10.4 promotes it. Nothing
   here blocks or parks.
5. **Abstain over guess.** No story keys outside `beats_for`'s minting; a non-chronological
   template gets no rows, no windows, no findings.
6. **Debts read as owed.** `describe_owed`'s register rule extends to the scheduled window.
7. **Research mechanics.** MirrorBench venv for anything touching torch; digest-keyed replay
   caches; raw JSONL + summary JSON in `research/quality-measurement/results/`; the
   duty-cycle/temperature governor on every leg that touches the 4090.
8. **Additive, parallel-safe.** New migration numbers, new modules, no renumbering of anyone
   else's stage-0 sections.

---

## 7. Verdicts

One paragraph per study, written when it runs, empty until then.

**What is deliberately not here: the D1 battery and everything downstream of it.** The design's
own order is seat, then battery, then freeze and register, then arms — and the seating is the
step in progress. Running D1 first would be the sequencing error §A7 exists to prevent, and it
would be run on a model nothing has seated. Its cost at the declared shape is five families x
four doses x replicates x two orientations x twelve fetches, which is thousands of calls and
hours of governed GPU time; `--families` and `--doses` are how to buy it in pieces. §A4's arms
and §A5's campaign stay untouched, because they are downstream of kills this battery has not
been given the chance to make.

**W1 taxonomy derivation.** Run 2026-08-19 on two disjoint local families over the ten-scene
own-generated book, 60 calls each, two arms per model. **`tone` is cut and the other four
stand.** Across 120 reported promises neither `qwen3:14b` nor `gemma3:12b` typed a single debt
`tone`; `mystery` (53% / 45%) and `plot` (39% / 41%) dominate both distributions, and
`character` (2% / 13%) and `progression` (6% / 1%) are each kept by one family and cut by the
other — which the rule's "per model, never pooled" clause settles by keeping both, because two
models disagreeing at low rates is not evidence for either. The cut rests on one book, and
re-admitting `tone` takes the nomination path rather than an edit.

Two things the run found that the design did not predict. **The open-vocabulary arm has no
taxonomy at all**: asked for one word of its own choosing, `qwen3:14b` produced 21 categories
over 54 promises and `gemma3:12b` produced 26 over 53, almost all singletons — which is the
argument for a closed enum stated as a measurement rather than as a preference. One nomination
cleared its threshold, `revelation` at 13.2% on gemma's open arm, and it is recorded and not
admitted. And **the registered intersection rule is defective**, which running it is what
showed: the open arm's vocabulary is free, so a registered kind can be absent from it because
the model chose a synonym — `obligation` and `debt` where the constrained arm says `plot` — and
requiring the label verbatim asks the model to share our terminology, which `AXIS_MATCHERS`'
own rule forbids. The defect is recorded in the pre-registration and the corrected reading
prints beside it as a proposal, per §87's precedent; it is not quietly swapped in.

**W3 cadence discrimination.** Run 2026-08-19 on two families, five spans each, three cadence
contrasts and two controls per span, both orientations.

    family          cadence   null    fisher p   controls   verdict
    qwen3:14b        3/30     0/20     0.207     clean      DOES_NOT
    gemma3:12b       2/30     1/20     0.651     placebo fired   VOID

**NULL on the one family whose controls held, and no rate at all from the other.** gemma3:12b
answered the byte-identical placebo with *"an exact duplicate of the first, differing only in
the inclusion of a final status report at the end"* — a confabulated difference on identical
text, which fires the matcher and voids its batch by the pre-registered rule. Reporting its
2/30 beside qwen's would be reading a rate from a judge that invents differences. So: cadence
is not a candidate axis, no detector is built, and W3 stops there.

**Why the surviving family's null is not "the reader saw nothing."** A post-hoc diagnostic,
labelled as one and in no bar, counts responses claiming that one passage "includes additional
details" the other "omits": **22 of 30 on qwen's cadence arm against 0 of 20 on its controls.**
Those claims are false about the text — `certify` asserts the three variants carry identical
word multisets, identical character counts and identical paragraph counts, checked before a
call was bought. That family **detects the manipulation reliably and names it as deletion
rather than as placement**, and the frozen matcher is doing its job by refusing to read that as
a cadence hit.

**And the second family is what stops that from becoming a claim about the channel.**
gemma3:12b's omission rate is 3 of 30, not 22 — so displacement-read-as-deletion is a property
of one model at this passage length, not of E6 at 2,000 words. A single-family run would have
supported the wider sentence and it would have been wrong.

What this leaves behind is one register entry, not a repair: the **byte-identical placebo
cannot catch a displacement artifact**, because shown two identical passages a model correctly
says identical while the failure is live one step away. A word-identical *reordering* control —
ordinary paragraphs moved, no payoffs involved — is the control that would, and it is named and
not built here, on §90's paraphrase-sham precedent.

**W4 payoff landing.** Run 2026-08-19 on qwen3:14b, 72 pairs. **SCORER_UNUSABLE, and the run
that says so cost about twelve minutes.** Two substrate absences were known before the first
call — no owner-read set, and no paid promise anywhere to build a `paid` or `mismatched` arm
from — so what ran was the false-positive half. It came back **0 of 32 matches on unpaid pairs
and 0 of 8 on the placebo**, which reads as clean false-positive behaviour and is not.

A constructed positive, added after the first run and labelled DIAGNOSTIC, is what showed it:
the paying passage built out of the ledger's *own sentence*, where any reader that reads at all
should score a match. **It fires on 6 of 32.** So the scoring ceiling is 19%, a zero elsewhere
is what a near-dead matcher produces, and the module now **withholds** every rate in the run
rather than printing one — `latent_crossfamily`'s withholding rule, for its reason: a number
that cannot be read is worse than no number, because the number is what gets quoted.

**The cause is a scorer that does not transfer, and it was a defensible choice that turned out
wrong.** `summarize.check_open_threads` was reused deliberately — it is the shipped matcher for
"does this prose mention this recorded thread" and it carries its own argued-for rule — but it
was built for a *summary of the same prose*, where the words recur. Here it is asked whether a
one-sentence **paraphrase** names the same debt, and the answers are paraphrases: *"The identity
and origin of the crate's contents and sender are settled"* against a ledger saying *"The
crate's contents, its unfamiliar wax mark, and who sent it must be revealed"* is a correct
answer that shares almost no distinctive word.

So W4 stops one step earlier than the design expected. It is not a null about payoff landing —
it is a null about the scorer, and the instrument cannot be run at all until a scorer exists
that scores paraphrase rather than overlap. Nothing was wired; `promise.landing.v0` does not
exist.

**Part A — the model screen, and a control the design did not have.** Six sessions per family
(three shelves, both orientations, twelve forced fetches each) over four local families,
2026-08-19. The instrument's very first output was a finding:

    family          scorable   fetch pattern                    P5      reading
    qwen3:14b        6/6       ABABABABABAB, every session      FAIL    taking turns
    gemma3:12b       6/6       AAAAAAAAAAAA, every session      FAIL    never leaves slot A
    phi4:latest      6/6       all-in per session, slot varies  PASS    the only live candidate
    gpt-oss:20b      0/6       no answer at all                 NOT RUN broken local install

**Two of four families are fixed-pattern allocators, and they would have passed every declared
control.** A strict alternator spends exactly half its budget on each side of every shelf, so
the placebo, both shams and the positional check all read *perfectly clean* — and measure
nothing. That is the 195/196 constant function wearing a budget, which the design names as V1's
kill and V1 cannot run here for want of twenty own-generated texts. So **P5** was added: the
standard deviation of the *slot* share across a run's sessions must exceed a floor. It needs no
substrate the corpus lacks, it catches both degeneracies at six sessions, and without it this
programme would have spent its whole GPU budget seating a coin.

**P5's own first formulation was wrong and the next pilot caught it.** It read the *target*
share, and because the orientation swap moves the target between slots, `gemma3:12b`'s
answer-A-every-time reader scores maximal target-share variance — a check that would have
reported the most rigidly positional family available as the most discriminating one. The slot
share is the quantity that is constant for a fixed-pattern reader and variable for a
content-driven one.

`gpt-oss:20b` is **NOT SCREENABLE rather than failed**: its transport returns
`tensor "blk.0.ffn_down_exps.weight" size overflow`, a broken install, and §87.3 is the
precedent for keeping that distinct — folding it into "ineligible" would let a broken install
masquerade as evidence about readers.

**No model is seated and none can be on this corpus.** V1 and D2 are NOT RUN for want of
twenty own-generated texts and a second own-generated book, D2's transplant-blindness is a
declared kill, and an unasked kill is not a passed one. What the screen bought is the right to
spend the seating budget on one family instead of four.
