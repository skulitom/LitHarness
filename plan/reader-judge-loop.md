# The reader → writer loop, with Readers and Judges as separate roles

**Written 2026-08-19, before any code in this design was written and before any verdict was
routed through it.** §1 is the pre-registration the measurement firewall (I1) requires; it is
committed in the same commit as the tables that enforce it and before the first row exists.

Today nothing a reader says about prose reaches the thing that writes the next prose, by any
path. `audit_samples` holds 0 rows, `calibrations` holds 0 rows, and the one machine channel
that touches drafting — `plan_search`'s licensed judge — renders *verdicts*, which is the frame
this project has now measured dead three times. This document is the design that closes the
loop with two sources whose licences are measured rather than assumed.

---

## 0. The split is valence-versus-location, and each half's licence is a measurement

Three independent attempts asked a machine for a **verdict** on prose. None failed marginally.

| attempt | result | where |
|---|---|---|
| T0 axiom battery | **DISQUALIFIED**. A6 positional bias **0.8151 chose-A over 568 decided**, ~15 SE from indifference and the largest such figure in the project. A2 *inverts* — preference for the undamaged text is strongest at the smallest dose. A4 puts ~14 points of a verdict on the question's wording. | `plan/judge-validity-program.md` §2, stage-0 §86.6 |
| §89 Track E, E1/E2 | **VOID** on their own precondition: chose-A **0.6408 over 142 decided**, and each of the three B6 families is out of band on its own. | stage-0 §89.4 |
| persona reader, first form | `keep-reading` on **195 of 196** passages. A constant function. | stage-0 §70, `plan/persona-reader-validity.md` |

One frame survived. **E6 — "name the single most salient difference" — clears 3 of 3 families**
(40/40 `stat_flatten`, 30/32 `repair_emdash`, 18/36 `interiority_strip_matched` against measured
nulls of 0.21/0.36/0.26), reports *"the passages are identical"* on the placebo and *"double
spaces after periods"* on the sham. §89 states the limit in one line: **E6 reports a difference,
never a preference.**

So the two roles are defined by the question each is licensed to answer:

- **READER — owns valence, and nothing else may.** Would I keep reading. Which of these two
  would I rather continue. Expensive, scarce, noisy, and the only source of this that has ever
  survived a validity check. §61's bar is a reader instrument.
- **JUDGE — owns location and axis, and never valence.** What differs between these two
  passages, on which axis, and where. Cheap, scalable, and in the E6 frame only, demonstrably
  not confabulating.

### 0.1 May any current model staff the Judge role at all, given T0? Yes, and only in E6's frame

Argued explicitly because the answer is not obvious and the wrong answer is expensive in both
directions.

**The case against.** T0 disqualified the incumbent panel, and the incumbent panel is the same
model family this design would seat as Judge. A disqualified instrument is disqualified.

**The case for, which is the one this design takes.** Every T0 arm that fired is a property of
the *verdict channel*, not of the model's access to the text:

- A6 is computed as chose-A over **decided comparisons**. A protocol that asks for no choice
  produces no decided comparisons and A6 has nothing to count. §89.4 says this in code —
  `orientation_symmetry` exists precisely because "reporting `positional_bias` would be a
  precondition that cannot fail" for E6.
- A2's inversion and A4's wording sensitivity were measured on preference elicitations.
- The decisive number is §89's own: §81 measured the panel on `stat_flatten` at **0.5437 —
  BLIND, with the estimate on the wrong side of indifference**. E6 asked the same model family
  about the same pairs and got the axis named **40 times out of 40**. Nothing about the model's
  access to the text changed between those two numbers. Only the question did.

**So the Judge is admitted, confined to E6's frame, with four rails that are not optional:**

1. The question is `E6_QUESTION` **byte-for-byte** and the scoring is `AXIS_MATCHERS`
   **byte-for-byte**, both copied from `research/quality-measurement/elicitation_study.py` with
   a test that fails on divergence. A reworded question is a different protocol with no validity
   evidence; a matcher edited after reading responses is a rubric fitted to its own answers.
2. **The judge never picks a side.** Which side of an axis a passage sits on is decided by the
   deterministic counter, never by the judge. The judge decides *which axis is salient* and
   *where* — the two things a counter cannot do.
3. **A confabulation control rides every batch.** A byte-identical placebo pair is judged in the
   same batch; a judge that names a prose axis on it voids the batch.
4. **An orientation-symmetry control rides every batch**, E6's own substitute for a positional
   precondition: the axis-naming rate must not depend on which slot the higher-counter text sits
   in.

**What that leaves empty, stated so nobody reads a licence into it.** JudgeBench A2's verdict
layer is still empty. §82 is untouched: `PREFERENCE` remains a human's blinded choice. Nothing
here upgrades any evidence class, moves any licence, or makes a counter a judge.

### 0.2 The composition rule

- A **reader** establishes, over few and expensive verdicts, the **direction** of an axis.
- A **judge** applies, cheaply and per span, the **discrimination** on that axis.
- Direction without discrimination cannot be applied to a draft. Discrimination without
  direction cannot say which way to move. **Only the pair is a signal.**
- **A judge may only speak on an axis a reader has given a direction to.** In code this is a
  constructor precondition, not a convention: `FeedbackItem` refuses to exist without a
  `Direction` that clears its bar, and a judged difference on an undirected axis is discarded
  and counted.

---

## 1. PRE-REGISTRATION — the measurement firewall (I1)

**Committed before the first verdict is routed through any part of this design.** Nothing below
this line may be edited after a steering verdict exists; a changed split is a new registration
with a new id and the old one stays on the record.

### 1.1 Two pools, assigned deterministically, before routing

    reader pool     STEERING | MEASUREMENT     assigned by content hash of the reader id
    passage pool    STEERING | MEASUREMENT     assigned by content hash of (revision_id, logical_id)

Both draws are content-derived and non-re-rollable, inheriting `domain/audit.py`'s discipline
verbatim: a replayed assignment converges, an operator who dislikes an assignment cannot re-roll
it, and "why is this reader in this pool" is arithmetic anyone can repeat. The salt and the
share are fields of a **write-once `PoolRegistration` row** whose id is content-addressed over
its own parameters, so a second, different registration is refused rather than silently
overwriting the first.

### 1.2 What each half of the split actually buys, stated precisely

**The reader split is the lock.** §61's claim dies if prose is shaped by the readers who later
judge it. A reader is in exactly one pool for life; steering verdicts and §61 measurement
verdicts are answered by disjoint sets of people.

**The passage split is the weaker second lock, and pretending otherwise would be dishonest.**
If the loop works at all, *every* scene of a steered book is shaped by steering feedback, and no
passage-level split undoes that. What the passage split buys is narrower and still worth having:
a passage's **own** reader verdicts never feed back into the prose that passage is later
compared as. It also makes the §61 comparison set derivable before any verdict exists rather
than by post-hoc exclusion.

### 1.3 Judges are calibrated on steering-pool readers only

Calibrating a judge on measurement-pool verdicts and then steering with that judge is the same
contamination with one extra hop. `Direction` is computed from steering-pool reader verdicts on
steering-pool passages, and from nothing else. Enforced in `directions_from`, which filters
before it counts.

### 1.4 What is enforced mechanically and what is not

**Enforced mechanically, and all four landed:**

- **The draw takes a side.** `pair-draw` filters accepted scenes by passage pool — sibling pairs
  from the steering side, external §61 pairs from the measurement side — and prints how many
  scenes it held back. A span answers one question or the other and never both. The filter is at
  the *draw* rather than at the verdict because a pair nobody in the matching reader pool may
  answer is a queue that cannot drain.
- **A reader may not answer across the split.** `pair-judge` and `pair-import` refuse, naming
  which pool each side is in; `litharness pairs --reader X` shows only what X may answer, so a
  reader is handed a list that is entirely theirs rather than one half of which will be refused.
- **`AxisDirection` counts steering-pool readers only**, in `axis_observations` rather than in a
  caller that might forget.
- **Nothing routes at all before a registration exists.** `pair-draw`, `directions` and the
  pool functions themselves refuse — "before the first verdict is routed" is only meaningful if
  nothing can be routed first. This is the change with the widest blast radius in the whole
  design: it puts one operator command in front of §61's existing runbook, and every
  operator-surface test in `tests/test_preference.py` now starts with it, exactly as an operator
  now does.

**Not enforced, and it cannot be:** nothing stops the operator from giving one physical person
two reader ids that land in different pools. The firewall is over reader *identifiers*. That is
stated in the runbook and in `pools`' own output, and it is the residual an honest reading of
I1 leaves.

---

## 2. Axes — named, counted, and only three of them

The shortcut §7 of the directive names: the first human read (§74) named **flat stats, no
interiority, em dashes**, and those are the same three axes E6 clears on. That is n=1 and not a
calibration, but it is enough to **pre-register three direction hypotheses** and have readers
confirm or refute them rather than discovering axes from scratch.

| axis id | counter | pre-registered direction hypothesis | source of the hypothesis |
|---|---|---|---|
| `stat_flatten` | `system_digit_count` | readers prefer the side with **more** concrete numbers | §74 defect 1, §81, §89 E6 40/40 |
| `interiority` | `interior_per_1k` | readers prefer the side with **more** interiority | §74 defect 2, §85's repair direction |
| `em_dash` | `em_per_1k` | readers prefer the side with **fewer** prose em dashes | §74 defect 3, §75's 5.50/1k against a pre-LLM median of 0.00 |

**The hypotheses are recorded so they can be refuted, and every one of them may be.** §78.3's
em-dash arm is VOID with the surviving point estimate leaning *toward* the mark; §81 measured
the panel BLIND on `stat_flatten`. A hypothesis this project holds and a direction readers
establish are different objects and the code never confuses them: a hypothesis emits nothing.
Only a measured `Direction` reaches a prompt.

### 2.1 How the registry grows, and it is the only way it grows

All three incumbents share one birth story, and that story is now the admission rule rather than
a coincidence: **a human read named a defect (§74), a deterministic counter was built for it, E6
was shown to clear the family, and readers were asked for a direction.** An axis enters by one of
exactly two doors and never by speculation about what ought to matter to readers.

1. **A named defect from a human read.** This is how all three arrived. It also gives every
   future human read a *defined product*: a read is a **defect harvest**, and each named defect
   is a candidate axis with its provenance attached, rather than a page of impressions that has
   to be re-derived later.
2. **A nomination from the discard corpus** (§4.2a) — the E6 sentences that named no registered
   axis. A nomination is a hypothesis and never a finding.

**The rail on the second door, stated so nobody trips it.** The discard corpus may *nominate* a
candidate axis; it may never *validate* one. A matcher drafted from those sentences and then
scored against those sentences is a rubric fitted to its own answers, which is exactly what
freezing `AXIS_MATCHERS` exists to prevent. So a nominated axis takes the full path — a
deterministic counter, an E6-family validation on **fresh pairs the nomination corpus never
touched**, and a reader-established direction — before it emits anything.

**Once admitted, an axis and its E6 family stay in the battery permanently**, the way a compiler
never deletes the regression test for a fixed miscompile. `Axis.admitted_via` records which read
or which nomination each one came through, so the registry carries its own history instead of a
docstring elsewhere carrying it.

There is deliberately **no enforcement machinery** for any of this. Admission is an operator act
(§84's rule), and a rule the code could apply is a rule somebody could satisfy without having
done the work.

**Counters are deterministic, live in `domain/axes.py`, and are ported with their provenance.**
They restate `research/quality-measurement/latent_fixtures.py::p0_features` and `ablate.py`'s
protected-span rules rather than importing them, because `domain` may not depend on `research`
(the layering rule `test_dependencies_only_point_outward_to_inward` enforces). A test pins the
three against the research implementations on shared fixtures.

---

## 3. The reader half — from verdicts to a direction

### 3.1 Where the contrast comes from: sibling candidates, not transforms

A direction needs pairs that differ on **one named axis**. Two sources were considered:

- **Certified single-axis transforms** (`ablate`-style: strip the interiority, flatten the
  stats). Clean attribution by construction. Rejected as the *first* build: it needs the whole
  transform-plus-certificate apparatus in `src`, and it estimates the direction on artificial
  damage rather than on the material the direction will be applied to.
- **Sibling candidates that the loop already produces.** `--plan-search` drafts K alternatives
  per span and `domain/candidates.py` already mints all C(K,2) sibling pairs, both orientations,
  through the same table humans judge. **Free, real, and already wired.**

**Chosen: siblings.** A sibling pair is admitted as evidence for axis X when **exactly one**
registered counter separates the two texts. Single-axis by *measurement* rather than by
construction.

**The cost of that choice, stated rather than buried.** "Exactly one *registered* counter
separates them" does not mean exactly one thing differs — two drafts of the same beat differ on
everything unregistered. So a direction estimated this way is confounded with whatever else
covaries with the counter in this generator's output. A certified transform would not be. This
is why the transform route stays designed-and-not-built in §8 rather than deleted: if the yield
or the confound makes siblings unusable, it is the successor, not a new idea.

### 3.2 The bar, and I7's four checks run before it is committed

The direction on axis X is the win rate of the **higher-counter side**, over steering-pool
readers, with `preference.win_rate_lower_bound`'s two-way cluster bootstrap.

    range         win rate and both bounds live in [0, 1]; the bar 0.5 is interior      OK
    direction     a lower bound > 0.5 reads HIGH; the same statistic computed on the
                  inverted outcomes reads LOW. Exactly one can fire; the pair of
                  alpha/2-quantile checks is one two-sided test at alpha              OK
    unit          decisive judgments under the protocol's declared tie policy, counted
                  in (reader, pair) CELLS — both orientations of one pair by one reader
                  is ONE decision, not two. §89 item 6: a floor counted in comparisons
                  did not bind when four personas were one judge four times           OK
    non-empty     `win_rate_lower_bound` already refuses fewer than two clusters of
                  either kind — and at that floor its own docstring records the band
                  can have NO WIDTH AT ALL. A bar passable on four judgments is not a
                  bar. Floors: >= 3 reader clusters, >= 8 pair clusters, >= 30 decided
                  cells, and a bootstrap spread strictly greater than zero            OK

**Two corrections the check itself produced, before any verdict existed.**

- **`MIN_READER_CLUSTERS` is 5, not 3, and the constant is `DESCRIPTIVE_CLUSTER_FLOOR`.**
  `win_rate_lower_bound` refuses fewer than two clusters of either dimension, but its own
  docstring records that below roughly five per dimension the percentile bootstrap is
  *descriptive rather than calibrated*. Reading a direction off a descriptive number would be
  reading an interval that had not earned its level. The floor is now the repo's own constant
  rather than a round number chosen here.
- **A zero-width-band refusal was written and then removed, and removing it is the finding.**
  The rule read "both one-sided bounds summing to 1.0 is degenerate, refuse". At the *two*-reader
  floor that is §85's zero-width defect; at *these* floors it is **unanimity** — thirty cells over
  five readers and eight pairs all pointing one way, which is the strongest evidence this channel
  can produce. The rule would have refused it. That is a bar wrong in the direction of **false
  failure**, which is precisely what T0's registered bar did to a good judge 82–100% of the time,
  and the cluster floors already exclude the four-observation case the rule was aimed at. Caught
  by running the operating characteristic before committing the threshold, which is what I7 asks
  for and is the reason it asks.

**And I7's second half, which is the one that is usually skipped.** T0's own registered bar
disqualified a *good* judge 82–100% of the time until its operating characteristic was measured.
So `directions.attainability()` computes, by simulation at the declared shape, (a) the smallest
k that clears the bar and (b) the probability the bar fires at true rates 0.55/0.60/0.65/0.70.
Both print in `litharness directions --attainability`, and both are computed rather than
asserted. **Measured, at the declared floors** (30 cells, 5 readers, 8 pairs):

    smallest clearing k    22 of 30 cells (0.733)

    true rate   power at 30 cells   cells for 80% power
      0.55            0.031                 220
      0.60            0.094                  90
      0.65            0.225                  60
      0.70            0.432                  50
      0.80            0.871                  30

**The floor is a coherence floor, not a sample size, and the two are easy to confuse exactly
once.** At a true 0.60 the floor fires under a tenth of the time, so a null from thirty judgments
would say nothing about the axis — an operator who read only `MIN_CELLS` would buy thirty
verdicts and conclude from silence. The last column is what a batch is sized against, and it
lands where §61's own sizing landed independently: 90 cells at 0.60 against §61's "roughly
100–150 decisive judgments" at the same rate.

### 3.3 What a direction is not

It is not a quality score, it is not a gate, and it does not license refusing any text. It is
one bit — which pole readers preferred — plus the interval that bit rests on.

---

## 4. The judge half — from a contrast pair to a located difference

### 4.1 The contrast surface is the tournament, and that is forced

Every single-passage frame tested has died, so a judge cannot be handed one scene and asked what
is wrong with it. It must be handed two things and asked how they differ. The loop already
produces two: `--plan-search`'s K siblings. The judge channel is built there rather than on a
second comparison surface invented for it.

**Not the §61 pairing.** Contrasting a candidate against matched published prose is §61's own
pairing, and spending it on steering destroys the measurement. `JudgePanel` refuses any pair
whose protocol is not an internal one.

### 4.2 The protocol, and the division of labour with the counter

Per contrast pair the judge is asked `E6_QUESTION` verbatim and answers one sentence. Then:

1. `AXIS_MATCHERS` decides **which axis** the sentence named. No match → discarded, counted.
2. The axis has a reader `Direction`, or the answer is discarded and counted. (§0.2.)
3. The **counter**, not the judge, decides which of the two texts is higher on that axis. If the
   counter does not separate them, the answer is discarded and counted — the judge claimed a
   difference the material does not carry.
4. The **span** is extracted from the higher-counter text by the axis's own locator (the
   digit-bearing status line, the interiority-marker sentence, the em-dashed clause). Located by
   the counter's own definition, so a judge cannot mislocate.

**So the judge supplies exactly one thing the deterministic layer cannot: which axis, of several
present, is the salient one — and it supplies it in the only frame measured able to.** That is a
smaller role than "judge" suggests and it is the role the evidence supports.

### 4.2a The discard bucket is retained verbatim, because counting it is not enough

Steps 1–3 above each *discard* a judge sentence. Counting those discards would throw away the
most interesting thing this channel produces.

**An unmatched sentence is a field report about a salient difference the axis registry cannot yet
name** — the same object the §74 human read produced, arriving from a channel that runs at volume
instead of once. These sentences are the discovery corpus for every future axis, and a corpus not
persisted from the first batch is gone. So every one is stored **verbatim**, with the provenance
needed to re-read it later: pair addresses, batch id, orientation, the judge's id, the counters
that separated the pair, and whether the batch's controls held.

Four reason codes, because they are different facts about different things:

    unmatched     no registered axis was named. The discovery corpus proper.
    undirected    a registered axis was named and no reader has pointed it. The composition
                  rule biting — and the queue of what reader evidence would unlock.
    unseparated   an axis was named that no counter separates on this pair: the judge claiming
                  a difference the material does not carry, which is a JUDGE-quality signal.
    ambiguous     more than one separating axis named, so "the single most salient" was not.
    control       a placebo or sham response, retained because a confabulating judge's own
                  sentence is the evidence that it confabulated.

**A sentence from a VOID batch is retained and marked VOID.** It is evidence about the judge
rather than about prose, and the row says which.

This is a table and a write, not a feature: no clustering, no analysis, no new axis machinery.
`litharness discards` surfaces it read-only, and prints the nominate-never-validate rail beneath
every listing, because a rail that lives only in a design document is a rail nobody reads.

### 4.3 Controls, per batch, refusing rather than reporting

    placebo_identical    a byte-identical pair in the same batch. The judge must not name
                         a prose axis on it. If it does -> BATCH VOID, nothing is written.
    rewhitespace_sham    a whitespace-only variant. Naming a prose axis -> BATCH VOID.
    orientation          axis-naming rate by slot must sit within +-0.20. Outside -> VOID.
                         E6's substitute for positional bias, because E6 asks for no choice
                         and `positional_bias` would be a precondition that cannot fail.

A void batch writes no `LocatedDifference` and records why. §89's placebo and sham are the
measured precedent: 0.0625 and 0.0000 confabulation against measured nulls.

---

## 5. Both halves reaching a draft prompt

### 5.1 The seam: the system message, materialised at enqueue

Feedback is an **instruction about how to write**, not established context, so it does not go in
the context packet — the packet's own contract is "established and may be relied on; do not
contradict it", and a craft instruction is neither. It goes in `render_prompt`'s **system**
message, alongside `target_words` and the status-line instruction, which are the two existing
inputs of the same kind.

**Materialised at enqueue, never rebuilt at render time (I5).** `make_plan_selector` resolves
the feedback set, renders it into `system`, and writes both the rendered text and the structured
set onto the job payload. The payload is the record of what was actually asked, and per-attempt
replay fidelity depends on it. A handler that rebuilt the prompt from live tables would make
every replay a different experiment.

### 5.2 What each source contributes to the text

- **Reader → standing, book-level, per-axis.** One sentence per directed axis, in the axis's own
  words: *"Readers, comparing passages blind, preferred the version with more interiority."*
  This is the reader reaching the writer.
- **Judge → located, per-span, one-shot.** One sentence naming the axis and quoting the span
  from the book's own prior prose: *"In the previous scene two drafts differed on em dashes;
  the one readers' evidence disprefers reads: '…'"* This is the judge reaching the writer.

Both are **named and located, never scalar (I2)**. There is no star, no 1–5, no aggregate
quality number anywhere in the payload, the tables, or the rendered text. The only numbers that
exist are the interval on a direction and the counters, and neither reaches a prompt.

### 5.3 Retirement — three mechanisms, because accumulation is the failure mode

Feedback that only accumulates becomes an unreadable prompt and a system that cannot show
improvement.

1. **Located judge items are one-shot.** Minted for one span's next draft, marked `spent` when
   materialised into a payload, never materialised twice.
2. **Standing directions retire on staleness**, by the §72 expiry-on-use pattern: each
   `Direction` carries the digest of the steering verdict set it was computed from, and a
   direction whose digest has moved emits nothing until it is recomputed. Evidence moving under
   a claim retires the claim.
3. **Retirement by satisfaction.** An axis stops emitting located items for a book once the last
   `SATISFACTION_WINDOW` accepted scenes all sit on the preferred side of that book's own
   running median for that counter. This is the mechanism that lets the system *show*
   improvement rather than repeating an instruction the prose already follows.

Plus a hard cap of `MAX_FEEDBACK_ITEMS` per prompt. **The cap is reported, never silent** —
overflow prints and lands in the daily digest, because a bound coverage reads as "covered
everything" when it did not (§89's rail).

### 5.4 Provenance, including the negative case (I4)

Every drafted scene records the feedback set that shaped it:

- The **job payload** carries `feedback` (a list, **`[]` when there was none**) and
  `feedback_digest` (a real digest of the empty list, never null). Frozen at enqueue, crash-safe,
  and the primary record.
- The **`scene_feedback` table** is the queryable projection, written on acceptance and keyed by
  the resulting revision and node — including a row with an empty item list and
  `provenance='none'` for a scene drafted with no feedback. **A scene drafted with no feedback
  records an explicit empty set, not a missing field.**
- Every verdict records **which role and which pool** produced it: reader rows carry the reader's
  pool, judge rows carry `judge:`-prefixed provenance in their own table and never touch
  `pair_samples`.

### 5.5 Blame: the read side of the provenance

`scene_feedback` and the payload's `feedback_digest` make what shaped each scene a complete
record; `litharness blame --axis X` is the query over it. For one book and one axis it walks
accepted scenes in reading order and prints the counter value beside the feedback set that was
live when each was drafted.

**When a counter trend turns, this answers "which standing direction or located item was in the
prompt when it turned" the way a bisect answers which commit** — from rows that already exist.
Read-only, no new writes, no thresholds. Per I2 it renders values and provenance and never a
score; per I3 nothing it prints can refuse anything.

It is worth having *now* and worth nothing *yet*: blame over an empty provenance table blames
nothing, and it becomes useful the day the first axis is directed.

### 5.6 Neither source may block (I3)

§10.4 stands. `FeedbackItem` has no path to a `GateOutcome`; nothing in the feedback modules
imports `policy`; a direction cannot construct a gate, park a unit, or set `blocking`. **A
reader-derived gate is still a gate** — so the rule is enforced by an architecture test that
fails if any module on the feedback path constructs a `GateOutcome` at all, rather than by the
absence of a caller.

What readers and judges *may* do is shape a prompt (§5.1) and select among candidates: when a
tournament's siblings are separated by a counter on a directed axis, the candidate on the
preferred pole wins. That is selection, which §61 Add 3 already licenses, and it falls through to
the existing tie-break when no direction exists — so it can never park a unit.

---

## 6. The prerequisite: the laundering path

`plan/judge-validity-program.md` §1.1 and stage-0 §86.1 name it: `plan_search` writes a licensed
judge's verdicts through the same pair machinery humans use, and `analysable_judgments` never
inspected `reader_id`, so one licensed tournament put machine answers into the pool the next
`PREFERENCE` calibration is denominated in.

**It was closed by a parallel session before this work began** (merge `14cdca8`, recorded as
§86.6): `MACHINE_READER_PREFIX = "judge:"`, minted at `plan_search`'s single write site by
`machine_reader_id`, excluded in `analysable_judgments` by `is_machine_reader`, kept in
`pair_verdicts_digest_for` on purpose so the judge's writes still stale its own licence, and
guarded by `test_a_machine_written_row_can_never_denominate_a_preference_holdout`.

**Two residual holes this design closes, because separating the roles makes volume the point and
volume is what turns an open path into a laundered pool.**

1. **The prefix was opt-in at one write site and unreserved everywhere else.** `pair-judge` and
   `pair-import` accepted any reader id, including one starting with `judge:`. A human row
   wearing the prefix vanishes from the denominator silently; more to the point, the namespace
   had no owner. Both human write paths now **refuse** a reserved-prefix reader id, so the prefix
   means exactly one thing: written by the in-process judge path.
2. **The Judge role never writes a `PREFERENCE`-shaped row at all.** `LocatedDifference` is its
   own table with its own columns. There is no verdict, no pair sample, and therefore no
   laundering surface for the half of this design that runs at volume — by construction rather
   than by filter.

**What still cannot be enforced:** an operator can import machine verdicts under a human-looking
reader id. Provenance of an imported row is a claim by the importer and no predicate can check
it. What landed is the honest half — `pair-import --source` is **required**, and the declared
source is recorded on the event of every row the file writes, so a bulk dump cannot arrive
anonymously even though it can arrive mislabelled.

---

## 7. The ablation (I6) — stated before it runs, at the n actually available

`research/quality-measurement/feedback_ablation.py`. **Four arms, same beats, same seeds:**

    off           no feedback in the system message. The control.
    reader_only   standing directions only. No located judge items.
    judge_only    located items only, on axes whose direction exists but is not stated.
    both          the full loop.

Ablating the two sources separately is not optional: with only `off` against `both` the result
cannot say which half did the work.

**Two readouts, and only one of them is runnable today.**

- **Machine-side, runnable at zero readers and zero spend.** The deterministic counter on each
  target axis, per arm, with the pre-registered direction of expected movement; plus every
  *other* registered counter (single-variable check); plus word-count ratio and layout identity
  (§78's confound — an on-target move produced by length or layout drift is reported as drift,
  never as effect). **This can falsify the wiring on its own**: if feedback-on does not move the
  counter, the feedback never reached the prose and the reader-side arm is not worth buying.
- **Reader-side, blocked.** Blinded, position-swapped pairs between arms, minted into the pair
  table under a declared steering protocol. `audit_samples` is at 0 rows and no reader has been
  paid, so this reads **UNDECIDABLE — awaiting N verdicts**, and prints the attainability table
  beside it. It is not sized for a hoped-for n; it says what n it has.

**What has been run, and it is a wiring pilot rather than a test.** `--selftest` passes (ten
claims over constructed profiles, offline). `--wiring --scenes 6` drives all four arms through
the real loop on the padded fake provider with a *synthetic* direction:

    arm            scenes carrying feedback    target counter
    off                       0                 baseline
    reader_only               6                 unchanged
    judge_only                0                 unchanged (see below)
    both                      6                 unchanged
    overall read: INERT_GENERATOR
    reader side:  UNDECIDABLE — 0/30 cells, 0/5 readers, 0/8 pairs

Two things it establishes and one it deliberately refuses to say. It establishes that the
feedback text reaches the frozen payload of every drafted scene in the arms that should have it
and none of the arms that should not, and that provenance lands for all four. It refuses to read
the flat counters as a null: **`INERT_GENERATOR` is its own verdict**, because a generator that
answers every prompt identically has said nothing about the loop, and a bare NULL would be
quotable as "feedback does not work". §57's lesson, wired in rather than remembered.

`judge_only` carried nothing and the report says why in its own field: the pilot runs no
tournament, so that arm is the control under another name — **by construction, not by
measurement**. Exercising it needs `--plan-search` and a judge batch, which is a live run.

**Falsification, pre-committed.** If the ablation shows no separation, it is archived beside the
four refuted line-level metrics in `research/quality-measurement/refuted_metrics.py`. If the
judge half shows no separation once the reader half is held fixed, that is a finding about judges
and it belongs in `plan/judge-validity-program.md`.

---

## 8. Sequencing, and what is deliberately not built

**Forced order.** The judge half is inert until reader evidence gives an axis a direction, and
`audit_samples` is at 0 rows. Readers run first. Building both halves and expecting both to
function is not available.

1. Pools registered. (Operator act. Nothing routes before it.)
2. A book runs under `--plan-search`; sibling pairs accrue in the steering pool.
3. Steering-pool readers answer them. `directions` reports which axes are directed, and which
   are short of which floor.
4. The first `Direction` clears its bar → standing guidance reaches the next draft prompt.
5. Only then does the judge channel produce anything: it refuses to speak on an undirected axis.
6. The ablation's machine-side readout runs at every step; its reader-side readout waits.

**Not built, and each has a reason rather than a backlog entry:**

- **Certified single-axis transforms** as a second source of direction pairs (§3.1). The
  successor if sibling yield or confounding makes siblings unusable.
- **Any absolute reader question.** `audit`'s keep-reading/would-stop queue stays exactly as it
  is; the direction path uses pairwise verdicts only, because the absolute form is the one that
  returned a constant function.
- **The gate-retry feedback gap.** `PLAN.md` §4.2 line 404 specifies "retry, with structured
  feedback from the failed gate"; the implementation re-reads a frozen prompt and varies only
  the sampler seed. Noted and left: that is a **gate** loop — deterministic, blocking, in-process
  — and a different source with a different standing.
- **A paraphrase sham.** `rewhitespace_sham` catches a judge that names prose axes on
  surface-identical pairs. It cannot catch a judge *or a counter* that fires on surface features
  carrying no reader-visible difference; a same-content, different-surface sham would. It is a
  register entry rather than a task because constructing one honestly is the hard part — who
  certifies "same content"? — and a sham whose own premise is unverified is a control that
  cannot fail.
- **The promise/payoff ledger as a candidate counter family** (a setup introduced and never paid
  off; a payoff referencing nothing established). Deterministic, span-locating and judge-free,
  which is the right shape — and strictly a **hypothesis axis under §2.1's admission path**: it
  earns nothing until a human read names it or the discard corpus nominates it, and nothing at
  all until readers give it a direction. Recorded here with that condition attached so it cannot
  be picked up later as an approved axis.
- **A judge batch as a conductor job.** `litharness contrast` runs one by hand. A job type would
  no-op on every tick until an axis is directed, which is the "documented promise whose only
  caller is a test" defect §19.1 keeps recording, so it waits for the first direction.
- **Renaming the `pair-*` verbs.** The CLI verb `judge` *is* renamed — it recorded a *reader*
  verdict, which is backwards under this split, and the cost of the rename grows with every row.
  It is now `read`, with `judge` retained as a deprecated alias that warns and behaves
  identically. The `pair-judge` verb keeps its name: it records a reader's pairwise verdict, and
  "judge" there is the ordinary English verb rather than this document's role.

---

### 8.1 How this relates to the two loop documents already in `plan/`

Three documents now describe a loop and that is two too many to leave unreconciled.

- **[reader-in-loop.md](reader-in-loop.md)** wires the *persona panel* into selection, behind
  relative fences and a recall-mediated choice. Its subject is a **machine** reader and its
  whole design is an answer to one objection: a selector transfers its own taste onto what it
  selects, and this panel's taste is measured. It is **not superseded** and it is not this
  document: nothing here seats a persona panel anywhere, and nothing there establishes a
  direction. If both are ever built, its fences and this document's directions are about the
  same three axes and would need reconciling then — its fence membership rule ("a fence is
  added when a human read names a defect, never because the panel dislikes something") is
  already the same admission rule as §2.1's first door, which is a good sign rather than a
  coincidence.
- **[revision-loop.md](revision-loop.md)** spends the budget on *revising* one draft rather
  than selecting among K, on the strength of §87.1's oracle bound. Its §6 waits on "one axis
  licensed by external human agreement" — which is exactly what §3 of this document produces.
  So it is downstream: a directed axis is the input its first funded iteration needs, and this
  document does not build a revision loop or claim to.

The through-line: all three wait on the same missing thing, which is a reader.

## 8a. Where the built thing differs from this document as first drafted

Recorded rather than silently reconciled, because a design document edited to match its
implementation stops being a design document.

- **§3.2's floors moved and one rule was deleted**, both from running the bar's operating
  characteristic before committing it. Written up in §3.2 rather than here, because the deleted
  rule is a finding about bars rather than a change of plan.
- **The firewall turned out to bind §61's existing runbook**, not just the new loop. The first
  draft of §1.4 said "a steering pair may not be drawn over a measurement-pool passage"; the
  built rule is symmetric — an *external* pair may not be drawn over a steering-pool passage
  either — because otherwise the passage split protects the steering side and leaves §61's own
  side open, which is the wrong half to leave open.
- **The judge's discard bucket is persisted, which the first draft only counted.** §4.2a. This
  arrived as an operator addendum mid-build and it is the one change that would have lost data
  by waiting: every batch run without it discards its corpus permanently.
- **Nothing in the addendum conflicted with what was already built.** The three additions are
  strictly additive and the two register entries are register entries.

## 9. Invariant check

| | invariant | how |
|---|---|---|
| I1 | measurement firewall, pre-registered | §1. Write-once `PoolRegistration`, deterministic reader and passage draws, refusal at every routing entry point, directions from steering readers only. Residual (one person, two ids) stated in §1.4. |
| I2 | named and located, never scalar | §5.2. No rating anywhere in the tables, the payload, or the rendered text. |
| I3 | neither source may block | §5.6. Enforced by an architecture test on `GateOutcome` construction, not by absence of a caller. |
| I4 | provenance, including the negative case | §5.4. `feedback: []` and a real digest on every payload; a `scene_feedback` row with `provenance='none'`. |
| I5 | the frozen prompt survives | §5.1. Materialised at enqueue into `system` and the payload; nothing rebuilt at render time. |
| I6 | ships with its own ablation | §7. Four arms, sources ablated separately, comparison stated before running, machine readout runnable at n=0 readers — run, and reading `INERT_GENERATOR` / `UNDECIDABLE`. |
| I7 | the declared bar can do what it says | §3.2. Range, direction, unit, non-emptiness checked; a computed operating characteristic that **caught a false-failure rule in this design's own bar** and removed it; and a sample-size column beside the floor, because the floor is not one. |
