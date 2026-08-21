# LitHarness: Autonomous Book-Production System Plan

**Version:** 2.2 (supersedes PLAN-v1-authoring-tool.md, archived in this folder)
**Status:** Master plan; **Stages 0, 1 and 2 met against their exit clauses — with Stage 0's endurance clause *evidenced rather than met* and Stage 2's propagation number a *dev-set* one that does not generalise; both caveats are in §17 beside the claims they qualify. 787 passing tests + 8 opt-in live; operable via `litharness tick`; a book goes in (`import`), drafts itself against a context packet, is refused when a planted defect stands against it, repairs a located finding within a serial cap (`evaluate_revision`/`repair_finding`), notifies out of the outbox to a configured sink (`--notify-file`), can have its plan history read and rolled back (`plans`/`revert-plan`), re-checks the scenes a repair's change reaches instead of only the scene it repaired (`propagate`, dev-set precision 1.000 against a 0.481 base rate), and comes out readable (`export`); Stage 3 (Book Zero) is now startable rather than blocked — a book with no imported snapshot drafts, states its game state on the page, and reads it back; two of §19's seven clauses met outright — scorecard in §19.1**

*(Corrected here, because this line was the instance: it read "four of §19's seven clauses met" while §19.1's table said two. §19.1 contains a paragraph recording that exact drift happening once before, four lines above the table that contradicted it, and the header carrying the same wrong number went unnoticed through three revisions. The readiness number this project reports about itself is the number to distrust first.)*
**Role:** An autonomous system that plans, drafts, evaluates, repairs, and versions LitRPG books to a measured quality bar — directed by a human, never blocked on one. *("24/7" struck by [stage-0 §61](plan/stage-0-decisions.md): always-on operation served a cadence goal the project no longer holds; the loop still runs without human input, as a foreground session.)*
**Inspection baseline:** Local projects inspected 2026-08-12; v2 rewrite same day; §7/§8/§13/§15/§17/§20 re-verified later the same day (v2.1); **§7/§8.4/§13/§17/§20 re-verified against all nine repositories that evening (v2.2)**

**What v2.1 adds.** A core philosophy section (§1a): **the text is the product.**
v2 was strong on integrity, autonomy and mechanically-checkable correctness, and
had almost nothing to say about whether the prose is any good — its stated Stage 4
target was "readable", a bar that cannot fail. §1a makes text quality the goal that
the rest of the document serves, names the six things quality actually means here,
and identifies the structural hazard: this plan's incentive gradient points at
whatever is gateable, and none of the deterministic gates measure quality at all.
Threaded into §2, §3, §10, §17 and §19.

**What v2.2 corrects, and the pattern it should finally settle.** v2.1 opened by
noting that v2 "consistently *understated* subsystem maturity" and struck two
already-complete actions. A same-evening re-verification against all nine
repositories found v2.1 had done it again: **§20.1 was completed eight minutes
before the edit that called it the cheapest unblock**; §20.2's pack was done and
§7/§8.4 still described the package as empty; §20.7's A3d was built *and its
decomposition had already answered the question the action existed to ask*; §20.4
undercounted its own test suite by 46; §20.5's second wall was owned elsewhere; and
§20.8's blocker had moved. Two things go the other way and are worth as much:
§7's "byte-reproducible" claim about LongRangeContext is the plan's one
**over**statement, and §20.4's diagnosis that three remaining items "all need
subsystems that do not exist yet" was **wrong about the one that was actually
buildable** — the real obstacle was a missing column no document named. The
standing instruction that follows: **an unstruck action in §20 is a claim to
re-verify, not a task to start.** Every row in §7 now carries what was checked.

**What v2.3 refounds (2026-08-17, [stage-0 §61](plan/stage-0-decisions.md)): the goal
is superiority, and it is allowed to fail.** The goal is now superhuman literary
quality, operationalised in §1a.5 as a pre-registered pairwise bar: the lower bound of
a 95% confidence interval on blinded, position-swapped pairwise win rate against
matched published-human prose exceeds 0.5, judged by paid genre readers. Throughput,
uptime and publication cadence are no longer goals.

> **Superseded twice since, and the original is left standing because the reversals only
> make sense against it.** (1) *"Judged by paid genre readers"* is dead: the **scope axiom**
> of 2026-08-19 ([stage-0 §95](plan/stage-0-decisions.md)) is *no solicited human judgment,
> ever — not hired, not operator, not one blinded pair*, and §95.1 retires the `PREFERENCE`
> class the bar rested on for machines at every grain. The replacement is unsolicited
> behaviour: a simulated readership as reward model, the library population as settlement
> layer, and the operator as a one-bit acceptance gate that trains nothing (§97). (2)
> *"Publication cadence is no longer a goal"* is also reversed: §101 makes the unit of
> production an **open-ended serial** published chapter-wise **at cadence**, with the
> six-scene books demoted from product to measurement substrate. The superiority goal itself
> — superhuman literary quality, allowed to fail — is unchanged.

The refoundation is licensed by
the measurement record, not by ambition: every other evidence channel is measured dead
(BRIEF §2's 21 proxies; unpaid solicited judgment at 2 verdicts per 104 pairs;
revealed-preference labels refuted at §56.3 and craft-corpus §4.4; raw model judges at
BRIEF §2 Pass 4), §57 voided the roadmap ordering Stage 5 was built on, and §59 built
the exact bound/family/cluster machinery the bar's statistics need. §3's "better than
human is not a measurable target" is superseded in place — the operationalisation is
what makes it one. Each cut and addition lands as its own stage-0 entry citing its
licensing measurement; this header is the pointer, not the record.

**What v2.1 corrects.** The v2 inventory was written from a partly stale reading and
consistently *understated* subsystem maturity, which mattered because it scheduled
work that was already finished and mis-premised work that was not yet possible.
Two actions in §20 were already complete (BookWorldState's commit/license/tag, and
the RevisionJudge pair export); the nominated "cheapest unblock" pointed at the
wrong repository; §8.1's route into BookWorldState's predicate registry is not
currently buildable; §8.2's status-block rule was under-specified in two ways the
golden fixture disproves; §8.3's gate has a vacuous leg and a false-green path; and
§7 and §8 assigned the same invariants over the same fixture to two projects. All
corrected in place, with the superseded claims kept visible where the direction of
the error is itself informative. Companion document:
[plan/provider-adapters.md](plan/provider-adapters.md).

## 0. What changed from v1 and why

v1 designed a human-in-the-loop authoring tool: every consequential change routed
through author approval, a full editor UI carried the consent burden, and autonomy
was an explicit non-goal. A review judged it correctly: *"this plan will reliably
prevent an AI from ruining a book. It does not yet contain the machinery for an AI
to write one."*

v2 keeps everything the review called strong — the detect → scoped repair → verify
architecture, the state-layer separation, the trust posture ("no proposal becomes
canon merely because a model returned it"), the provenance and promotion discipline —
and changes the product identity:

1. **Autonomy is the product.** A policy engine (the Conductor) replaces the inline
   human gate. Humans direct, audit, and calibrate asynchronously; the system makes
   progress 24/7 without them.
2. **Two new pillar subsystems:** Narrative Planning (the creative half v1 assumed
   an author would do) and the Game-System Engine (LitRPG mechanics as a
   deterministic simulation, the genre's cheapest and most defensible quality claim).
3. **Book Zero is a scheduled milestone:** a complete, deliberately ugly 50k+ word
   draft produced end-to-end early, whose concrete failures reprioritize the
   research programs.
4. **The human quality-calibration program is on the critical path** — it is the
   prerequisite for any trusted autonomous accept/reject gate.
5. **Scope cut:** full editor UI, plugin sandbox, DOCX/EPUB polish, branch-merge UI,
   and the commercial-SaaS operational bar are deferred. The UI is a director's
   console, not an editor.
6. **Serial publication** (Royal Road-shaped chapter cadence) is a first-class
   export target; book-shaped export follows.

## 1. Executive summary

LitHarness is an always-on fiction factory. Since §101 (2026-08-21) its unit of
production is an **open-ended serial** — arc, chapter, scene — published chapter-wise at
cadence, rather than a fixed short book; the six-scene books this document describes
throughout are now **measurement substrate**. The human is a **one-bit acceptance gate**
rather than a director in the loop: no instrument here is ever trained, calibrated or
selected on operator traces (§97.1). It runs on a cron-like heartbeat: every tick, the Conductor ingests any new human directives,
selects the highest-value unit of work (draft a scene, evaluate a chapter, repair a
finding, propagate an accepted change, recompute derived artifacts), executes it
within budget, applies machine-checkable acceptance policy, and commits or
escalates. A human can steer at any time — premise, constraints, tone notes,
structural direction, vetoes — and reviews an exception queue and daily digest, not
every commit.

The architectural bet, supported by RevisionBench's measurements, is unchanged:
**detect → scoped repair → verify**, never open-ended "improve this" revision.
Unchanged text is structurally ineligible for revision unless a located complaint
licenses it. Model self-report is never a correctness signal (MirrorBench).
Acceptance is earned by passing deterministic gates first, calibrated critics second,
and sampled human audit third.

The sibling projects remain research incubators feeding validated pieces into this
product behind versioned contracts. `litharness-contracts` v0.2.0 now exists with
two span-exact golden fixtures (a six-scene mystery and a six-scene LitRPG book with
planted, mechanically checkable defects) that ship inside the package; all subsystems
consume it rather than importing each other.

## 1a. Core philosophy: the text is the product

**The purpose of this system is books a genre reader chooses to keep reading, and
recommends to someone else.** Everything else in this document — the Conductor, the
gate ladder, the provenance chain, the immutable revision store, the Game-System
Engine, the 24/7 operation — is scaffolding in service of that. Autonomy is *how*
the books get made. It is not what makes them good, and no amount of it substitutes
for the text being good.

This section is load-bearing, not preamble. Five consequences follow, and each one
cuts against something the rest of this plan would otherwise drift toward.

### 1a.1 Measurable is not the same as important

The plan's centre of gravity drifts toward whatever is mechanically checkable,
because that is what can be gated, tested, and reported green. Game-system
integrity is the extreme case: cheap, precise, defensible, and genuinely the
genre's best deterministic quality claim (§8) — **and a book with flawless ledger
arithmetic can still be dead on the page.**

Deterministic gates establish a **floor**: no contradictions, no impossible states,
no arithmetic errors, no continuity breaks. They say nothing whatever about whether
a scene lands. So:

- Every deterministic gate is **necessary and insufficient**. Passing the full
  ladder means the draft is not broken; it does not mean the draft is good.
- **Watch the effort ratio.** If a month of work moved only the floor, the project
  is off target however green the suite is. The suite cannot detect this — it is a
  judgment the director has to make deliberately, at review time, against this
  section.
- Beware the metric that is easy *because* it is shallow. Word count, scenes
  accepted per day, findings closed, and tokens spent are all trivially
  instrumentable and none of them is quality.

### 1a.2 Quality-first does not license open-ended revision

This is the trap a quality-first philosophy usually walks into, and the evidence
against it is already in hand: RevisionBench measured that order-consistent judges
preferred the *human originals* about 80% of the time. Models asked to improve prose
made it worse. Naive "polish this until it sings" loops would therefore lower
quality while burning budget.

The architecture stands unchanged: **detect → scoped repair → verify**, never
open-ended "improve this". Ambition about quality is expressed in what the system
**plans** and what it **detects** — richer craft detection, better beat design,
sharper located complaints — never in loosening the revision discipline. Unchanged
text stays structurally ineligible for revision unless a located complaint licenses
it.

### 1a.3 What "quality" means here, in priority order

Vague ambition is unactionable, so this is the concrete list, ordered by how much
each one moves a reader:

1. **Dramatic function.** Every scene changes something: a want pursued, a cost
   paid, a relationship or state altered. Scenes that only *convey information* are
   the single most common failure of generated prose, and they pass every
   deterministic gate in this document.
2. **Progression as drama, not bookkeeping.** LitRPG's system exists to create
   tension — scarcity, tradeoff, risk, the cost of a choice. A perfectly simulated
   system that never costs the protagonist anything is the genre's characteristic
   failure, and note that §8's engine makes this failure *easier* to ship, because
   the numbers will all reconcile.
3. **Escalation and payoff.** Promises planted get paid, on a cadence a reader can
   feel; stakes ratchet rather than reset.
4. **Voice.** A particular, consistent narrator; dialogue that distinguishes
   characters from each other.
5. **Line-level craft.** Concrete specificity over abstraction, varied sentence
   rhythm, no filler, no padding to length.
6. **Absence of AI tells.** Register drift, summarizing instead of dramatizing,
   tidy emotional resolution, the tricolon habit, the same three sentence shapes.

The floor gates in §4.2 cover none of items 1–6. That asymmetry is the central
engineering problem of this project, and naming it is the point of this section.

### 1a.4 Human judgment is the only ground truth for items 1–6

Which makes §10's calibration program not a scheduled nicety but **the measuring
instrument for the product's actual goal.** Two rules follow:

- **Any craft proxy is a hypothesis about human judgment until validated against
  it.** Pacing mix, tension curves, hook presence, dialogue ratio, sentence-length
  distribution — instrumentation, not gates, until held-out calibration shows they
  predict human preference. This is already §10's discipline; what changes is that
  it is the spine rather than a later stage.
- **A gold corpus of *good* prose is missing and needs authoring.** Both golden
  fixtures are *defect-detection* fixtures — planted errors and negative controls.
  Nothing in the program currently encodes what good looks like, so there is
  nothing for craft work to be measured against. Fixing this is a prerequisite for
  items 1–6 being anything but opinion.
  *(Amended — see the next paragraph. The corpus is still required; **authoring** it is
  not, because it can be selected.)*

**Amendment: solicited judgment and revealed judgment are not the same scarcity, and
this section conflated them.** Human judgment remains the only ground truth. But the
above was read — including by this plan's own §10.3 — as requiring *solicited* judgment:
sessions, rubrics, pairwise forms, a human deciding to sit down. That is operationally
self-defeating for a system whose entire product claim is that it runs without one, and
the evidence is already in: RevisionJudge was built, works, and has collected **two**
verdicts against 104 exported pairs. Planning for more sessions is planning for that
result again.

**Revealed judgment** — readers who followed, favourited, kept reading or abandoned, for
their own reasons, with nobody asking them anything — is the same ground truth, already
collected, at a scale no session reaches. It is also structurally free of the two failures
§10.3 spends its design controlling for: there are no demand characteristics and no
positional artifacts when nobody was asked a question. And §1a.5 already words this
project's own bars in revealed terms — *"a majority of sampled chapters earn 'I would keep
reading'"*, *"retention across consecutive chapters is measured"*. Those are claims about
behaviour, which revealed preference measures directly and a rubric only proxies.

So the rule stands with one word added: **any craft proxy is a hypothesis until validated
against human judgment, solicited *or revealed*.** Details, measured labels and the
validity limits of each direction are in
[plan/craft-corpus.md](plan/craft-corpus.md).

**Second amendment (2026-08-17, §61): the revealed half died on its labels, and the
solicited half is being funded.** The amendment above pivoted to revealed judgment on
the measured failure of *unpaid* solicited judgment — two verdicts against 104 exported
pairs. Since then the revealed labels available to this project have been measured too,
and they do not reach prose: conversion does not separate prose at the decile grain
(stage-0 §56.3), and a corpus selected from its deciles pairs on story size and era,
not craft ([plan/craft-corpus.md](plan/craft-corpus.md) §4.4, refused before selection).
Raw model judges died earlier (RevisionBench: 43–65% positional artifacts, survivors
preferring human originals ~80%), and the one model-based instrument died to its own
memorisation sham (stage-0 §58). What remains is the channel this project never funded:
**paid, blinded, position-swapped pairwise judgment from external genre readers** —
solicited, but bought rather than volunteered, which is the variable the 2-of-104
measurement never tested. It was the primary instrument (§61), and it never ran.

> **Retired 2026-08-19 and the paragraph above is kept as the record of what was tried.**
> The **scope axiom** ([stage-0 §95](plan/stage-0-decisions.md)) closed this channel
> permanently — *no solicited human judgment, ever — not hired, not operator, not one blinded
> pair* — so "the channel this project never funded" is now the channel it will not fund.
> §95.1 retires `PREFERENCE` for machines at every grain; the single exception is the
> operator's **one-bit** accept/reject at book grain, which carries no diagnostic and trains
> nothing (§97.1).
>
> The rule it closes with survives in an altered form and is worth restating precisely,
> because it is what the whole force programme is built on: **any craft proxy is a hypothesis
> until validated against reader behaviour** — unsolicited, revealed by what a population
> did, never asked for. The validation target moved from a verdict to a behaviour; the
> demand for validation did not move at all.

### 1a.5 Set a bar that can fail, and refuse volume as a proxy

"A genre reader rates it readable" (§17 Stage 4, as written) is not a quality
target — it is a floor restated. The first bar below can be failed, and it is the
project's definition of its own goal (§61): "superhuman" means exactly this and
nothing more.

- **The superiority bar.** In blinded, position-swapped pairwise comparison against
  matched published-human prose (same genre, comparable premise and length), judged
  by paid genre readers, the lower bound of a 95% confidence interval on the win
  rate exceeds 0.5. **[RETIRED 2026-08-19 — the judging half only.]** The scope axiom
  (stage-0 §95) forbids soliciting this judgment from anyone, so the bar as stated can
  never be evaluated. The five pre-registrations below are *not* retired with it: every
  one of them — clustered intervals, a tie policy declared in advance, exclusion on
  recognition, a comparator frame fixed before the first comparison, and a bar that can
  fail — carries over intact to the behavioural instruments that replaced it (§95's force
  harness, §97's simulated readership), and several were re-learned the hard way there
  anyway. What changed is who answers, not what a defensible answer requires. Five pre-registrations, each bought by a measurement: the
  interval is clustered over both readers and items (§59's `clusters` lesson — a
  binomial interval over correlated judgments carries confidence it has not
  earned); the tie policy is declared before the first judgment; judgments where
  the reader recognises either passage are excluded (§58 measured familiarity
  swinging a score several times harder than damage, and human judges do not get
  an exemption); the comparator sampling frame is declared before the first reader
  is paid, because beating median tier-matched serials and beating the genre's
  best are different claims and **the frame is the claim**; and if more than one
  book could have been reported, the confidence level is divided by the number of
  candidates (BRIEF §6.4 applies to the headline claim too).
- A majority of sampled chapters earn "I would keep reading" from readers who were
  not told what produced them — subsidiary evidence, collected by the same
  pipeline, never a substitute for the bar above.
- ~~Blinded genre readers cannot reliably distinguish accepted chapters from
  published human LitRPG at the same tier.~~ *(Struck by §61: parity was the
  ceiling this plan dared to name, and the goal is now above it. Note what the
  strike does to [plan/craft-corpus.md](plan/craft-corpus.md) §4.2, which called
  this "the bar the plan already wrote": a discriminator separating system prose
  from human no longer proves the bar failed, because distinguishable-and-preferred
  passes the superiority bar. §4.2 survives as a cheap adversarial probe, not as
  the bar's proxy.)*
- ~~Once serialized, retention across consecutive chapters is measured and does not
  decay faster than a comparable human-written serial.~~ *(Struck by §61: cadence
  is no longer a goal, so there is no serial to measure retention on. The pairwise
  bar replaces it as the falsifiable target.)*

And one explicit anti-goal: **word count is not a success metric.** A 50k-word book
that reads is worth more than a 120k-word book that does not. This needs saying
because the autonomy machinery makes volume nearly free and quality expensive, so
the system will drift toward volume unless the plan forbids it.

A related constraint from the adapter layer
([plan/provider-adapters.md](plan/provider-adapters.md)): small local models are
appropriate for mechanical work — extraction, ledger replay input, summaries,
status-block rendering — and must **never** write prose that reaches an accepted
revision. Routing cheap models onto the page is the fastest available way to
violate this section.

## 2. Product goals

- **Produce LitRPG books worth reading** — planned, drafted, evaluated, repaired,
  and versioned — with no human action required for forward progress. Text quality
  is the goal (§1a); completeness and autonomy are how it gets delivered, and
  neither counts as success on its own.
- Accept human direction asynchronously at every altitude: premise, world rules,
  arc structure, chapter notes, line vetoes. Direction is durable and versioned;
  the system honors it without waiting for it.
- Guarantee game-system integrity: stat math, resource ledgers, level curves, skill
  and quest state machines are simulated deterministically and are never wrong in
  accepted prose.
- Maintain objective canon, character knowledge/belief, plans, and evidence as
  distinct layers; detect located continuity failures before inviting changes;
  repair within explicit scope and verify the complaint resolves.
- Keep every generated claim, finding, revision, and decision traceable to exact
  inputs, tool/model versions, and the policy that accepted it.
- Operate continuously within hard token/cost budgets, degrade gracefully, recover
  from crashes without losing or corrupting accepted work.
- ~~Publish serially (chapter cadence with hooks and recaps) and export whole books.~~
  Export whole books (`litharness export`); publication is a manual act taken when the
  book clears the quality bar, not a pipeline (§62).
- ~~Work with local models or API providers behind adapters. Four: a deterministic
  fake, the local Claude Code session (default), the local Codex CLI (fallback),
  and Ollama (iterative testing and all mechanical calls).~~ One pinned frontier
  provider (the local Claude Code session) plus the deterministic fake for tests
  (§64): silent mid-book fallback to a weaker model is a quality defect, not
  resilience — an unhealthy provider parks the unit; it never degrades the book.
  See [plan/provider-adapters.md](plan/provider-adapters.md) (superseded, kept as
  the measured record).

## 3. Non-goals

- Inline human approval as a required step of the production loop. (Humans gate
  *policies*, exceptions, and samples — not each commit.)
- ~~A promise that generated prose is objectively "better" than human prose. The
  claim this project will actually defend is narrower and testable: accepted prose
  meets a measured bar against human judgment (§1a.5), and its game-system
  arithmetic is never wrong. "Better than human" is not a measurable target;
  "indistinguishable from published genre work to a blinded reader" is.~~
  *Superseded by §61, and the struck sentence names its own error: "better than
  human" was unfalsifiable only for lack of an operationalisation. §1a.5's
  superiority bar supplies one, so the claim is now measurable, now pre-registered,
  and now the goal. What stays a non-goal is any superiority assertion **outside**
  that measurement — "superhuman" spoken without a comparator frame, a clustered
  interval and a declared candidate family is still marketing, and this plan still
  refuses it.*
- Publication cadence, uptime, and throughput as success measures (§61). The system
  still runs without human input; nothing about the quality goal restores an inline
  human gate — human judgment enters asynchronously as calibration evidence, gating
  promotions, never ticks.
- One universal style/structure/pacing formula; craft targets are per-book profiles.
- A general-purpose authoring editor for human writers. (v1's §14 UI is cut.)
- Autonomous publication to external platforms without an explicit human-set
  publication policy for that book. (Autonomous *drafting* needs no such gate;
  outward-facing posting always follows a configured policy.)
- Plugin marketplace, real-time collaboration, model self-confidence as evidence,
  mechanistic-interpretability machinery in the request path.
- Replacing legal review, sensitivity reading, or rights decisions.

## 4. The Conductor: 24/7 operating model

The Conductor is the subsystem v1 lacked. It is a durable scheduler plus a policy
engine — the "author" role decomposed into machine-checkable parts.

### 4.1 Heartbeat and scheduling

*(Amended by §63: the deployment model is a foreground session driving `tick` in one
process — §57 measured the one-process loop as what a daemon does, and cheaper. The
cron framing below is retained as record; leader election, durable pause, and outbox
delivery went with it. Ticks stay idempotent and one-bounded-unit; a killed session
restarts safely because expired job leases are reclaimed and replayed ticks converge.)*

- ~~A cron-style tick (Windows Task Scheduler / cron; every 5–15 minutes) launches or
  wakes the Conductor. A lease/lock guarantees single-instance execution; a missed
  heartbeat is observable. A resident daemon with the same tick contract is an
  optimization, not a requirement.~~
- Each tick: (1) ingest directives, (2) reconcile state (crashed jobs, expired
  leases, stale approvals), (3) select work, (4) execute one bounded unit, (5)
  commit artifacts + events atomically, (6) update the digest. Ticks are idempotent;
  all work runs through the existing durable job/outbox machinery.
- Work selection is a policy over the book's state: unblocked scenes to draft,
  findings to repair (severity-ordered), propagation plans to execute, derived
  artifacts to recompute, evaluations to run at milestones. A blocked or parked item
  never stalls the queue — the Conductor works elsewhere in the book.

### 4.2 Acceptance policy engine

Every candidate artifact meets a policy ladder instead of an author:

1. **Shape gates (deterministic, blocking):** parseable, in-scope span, length and
   structure limits, locked-content untouched, no unauthorized deletion.
2. **Integrity gates (deterministic, blocking):** game-system validation (§8),
   state/knowledge/POV checks, ledger arithmetic, continuity detectors at the
   current promotion tier, mechanical vetoes from RevisionBench (length movement,
   slop markers, punctuation/style drift, unintended deletion).
3. **Craft gates (calibrated, advisory → blocking after calibration):** critic
   thresholds only after the calibration program (§10) has measured them against
   human labels for that task. Uncalibrated critics annotate; they never gate.
4. **Budget gates:** per-operation, per-day, and per-book token/cost ceilings —
   metered in **invocations as well as tokens**. Both CLI adapters carry a fixed
   per-call harness tax (measured: ~24k input tokens for `claude -p`, ~14.8k for
   `codex exec`, the latter never caching), so token accounting alone hides a cost
   that scales with call count.

Decisions: **accept** | **retry** (bounded, with structured feedback from the failed
gate) | **repair** (spawn a detect→repair job for a located complaint) |
**regenerate** (fresh candidate, capped) | **park** (mark the unit stuck, move on) |
**escalate** (exception queue). Retry ladders are bounded everywhere; the failure
mode is a parked unit plus an exception, never a spin loop.

### 4.3 Human touchpoints (direct, don't operate)

- **Direction inbox:** a durable queue (file/DB) where the director drops premises,
  constraints, arc notes, tone guidance, vetoes, or "more dungeon crawling" at any
  time. The Conductor ingests at tick, converts directives into versioned locked
  plan constraints via the Narrative Planner, and records the interpretation for
  audit. Sort of like messaging an always-on agent: the book is the long-running
  session.
- **Exception queue:** escalations that policy cannot resolve (repeated gate
  failure, contradiction between locked constraints, budget exhaustion, publication
  decisions). Exceptions park only their unit of work.
- **Calibration sessions:** batch blinded judgments (RevisionJudge's protocol) that
  train and re-anchor the craft gates. Scheduled, bounded (30–60 min), and the only
  place human quality opinion enters the system.
- **The Director role (stage-0 §91, [plan/director-role.md](plan/director-role.md)).** This
  section's inbox now has a second kind of writer: a named machine personality that says what
  a book is about, one bounded directive per six accepted scenes, running with nothing from a
  person. It is safe for the opposite reason to the Reader/Judge split — it is *generative and
  upstream*, so it measures nothing and cannot measure wrongly — and it is contained rather
  than licensed: interpretive kinds only (a veto is authority, not direction), never a locked
  plan item, never a word about prose, and **never shown the prose**. Off by default behind
  `--director`; a director is an arm and no director is its control. Human direction still
  outranks it in this queue, always.
- **Daily digest:** words drafted/accepted, findings opened/closed, spend vs.
  budget, escalations, samples for spot-reading.
- **Controls:** pause/resume per book, kill switch, policy editing (gate thresholds,
  budget ceilings, publication policy) — all config, all versioned.

## 5. Architecture at a glance

```text
        Direction inbox        Exception queue / digest
               \                     /
                ── Conductor ───────
                (scheduler + acceptance policy + budget governor)
                        |
   Narrative Planner    |     Game-System Engine
        \               |        /
Manuscript IR & version store ---- Event log / jobs / outbox
   |          |          |                    |
 Plans   World State  Dependency Graph   Observability
   |          |          |
   +---- Context Assembly ----+
              |               |
         Generation       Evaluation
              |               |
      Candidate patch   Structured findings
              \              /
          Revision planner
                 |
        Acceptance policy (gates)
                 |
        New immutable revision → serialization/export
```

Subsystems communicate through versioned contracts and immutable artifact
references. Model adapters stay at the edge. The Conductor owns workflow state and
transactions; no subsystem mutates canon directly.

## 6. Research dependency and integration graph

```mermaid
flowchart LR
  MB["MirrorBench<br/>trust boundary"] -.-> LH["LitHarness<br/>autonomous product"]
  RB["RevisionBench<br/>revision evidence"] --> CE["ContinuityEvaluation"]
  RB --> LH
  BWS["BookWorldState"] --> GSE["Game-System Engine<br/>(new)"]
  BWS --> LRC["LongRangeContext"]
  BWS --> CE
  GSE --> NP["Narrative Planning<br/>(new)"]
  GSE --> LH
  NP --> LH
  LRC --> CE
  LRC --> LH
  CE --> RP["RevisionPropagation"]
  CE --> LH
  RP --> LH
  CONTRACTS["litharness-contracts v0.2.0<br/>(exists)"] --- LH
```

Priority order for the autonomous goal: Game-System Engine and Narrative Planning
outrank RevisionPropagation. LongRangeContext, ContinuityEvaluation, and
RevisionPropagation earn integration through Book Zero's observed failures, not
through a priori scheduling.

## 7. Subsystem inventory

Re-verified by direct inspection **2026-08-12 evening (v2.2 pass; supersedes the
two earlier passes the same day)**. The earlier row values are kept in the notes
where they were wrong, because the *direction* of the error matters — this plan
consistently understated maturity and therefore scheduled work that was already
done, and **the v2.1 pass did it again in six more places**:

**The litharness-contracts row was re-inspected on 2026-08-17** when the fixtures moved
into the package, and it had gone stale on five separate facts — schema version, test
count, remote, tags and license — none of which the move touched. The struck values are in
that row's notes. Nothing else in this table was re-checked that day, so treat every other
row as carrying its 2026-08-12 date.

| Project | State | Role in v2 |
|---|---|---|
| litharness-contracts | **Re-verified at the pin 2026-08-17: package v0.2.0, wire schema 1.2.0, 130 tests, 30 schemas, mystery + litrpg golden fixtures.** Git repo (branch `main`, 7 commits, clean tree), public remote `github.com/skulitom/litharness-contracts`, tag `v0.2.0`, Apache-2.0 LICENSE | Shared schemas + gold benchmarks. §20.3's minors have shipped except the game-system schemas, which stay deferred for want of a consumer. Version (don't freeze) after Book Zero. **The fixtures now ship inside the package** (`src/litharness_contracts/fixtures/golden/`) behind one accessor, and LitHarness consumes the repo as a git rev pinned in `uv.lock` — see plan/stage-0-decisions.md §60. *(Struck: "untracked, no git repo" and "version-controlling it is the single cheapest unblock" — the commit landed 2026-08-12 17:36, eight minutes **before** the v2.1 edit that still called it untracked. Struck at the 2026-08-17 pass, and every one of them was a fact this table asserted rather than checked: "wire schema 1.1.0" — 1.2.0 shipped in `404eb9a`; "124 tests" — 126 at the previous pin and 130 now; "no remote" — origin has existed since before `32d9728`; "no tags" — `v0.2.0` exists; "Still no LICENSE / README says License: TBD" — Apache-2.0 landed 2026-08-13 **in `32d9728`, the very commit this plan's CI had pinned**, and the README line outlived it until 0.2.0.)* |
| **LitHarness (this repo)** | **Stages 0–2 met against their exit clauses (§17 carries the caveats): 787 tests passing + 8 opt-in live (2026-08-17; the header restates this number and the two have drifted apart once — when they disagree, the suite is the referee), ruff clean, mypy strict clean (`warn_unreachable` on). Under version control** (`.gitattributes` pins `eol=lf`; `core.autocrlf=true` is set globally on this machine and has already bitten this project once) | The product. **This table previously audited every sibling's VCS status and had no row for the product repo, which was itself untracked.** |
| BookWorldState | Committed, Apache-2.0, tagged `v0.1.0`, pushed to GitHub; **13 commits, working tree clean**; 100 tests passing. Ships an authenticated versioned WSGI API, transactional outbox with capped-exponential-retry worker, signed webhook publication, migration checksums, online backup/restore + destructive-corruption drill — **Milestone 4/5 infrastructure, not "~Milestone 2"**. What is *not* done is M3's evaluation corpus | State substrate. Its closed predicate registry is **not** injectable yet (§20.5) — but §8.4 routes around this deliberately, so it is not a blocker for §8. *(Struck: "working tree is not clean", "4 commits", "~Milestone 2 complete", "the real blocker for §8" — all four false.)* |
| RevisionBench | Mature (**411** tests). A2d complaint-gated repair, the LitRPG stratum, **and A3d** have landed — A3d shipped *under the name A2d*, and best-of-N repair ranked by minimal intervention closed the last element in `22a228d` | Source of repair policy, mechanical vetoes, LitRPG stratum evidence. **Its M5 decomposition is done and has already answered the question §20.7 was scheduled to ask** — see the redirect there. *(Struck: "405 tests", "A3d is next".)* |
| RevisionJudge | Built; 104 pairs exported, exactly 2 verdicts collected; one uncommitted file (`data/verdicts.jsonl`) | **Demoted from the calibration instrument to a confirmation sample** (§10.3 as amended). Two verdicts against 104 pairs is the measured throughput of a design that needs a human to decide to sit down, and it is why revealed preference is now primary. Still the right tool for spot-confirming a calibration derived elsewhere; `litharness audit` is the same shape and collects as a by-product of drafting. The verdict *consumer* remains unbuilt |
| **RoyalRoad-1.61M corpus** *(external data, not a repo)* | `OmniAICreator/RoyalRoad-1.61M` on HuggingFace; 1,613,875 chapters, 12.5 GB, MIT-licensed compilation; ~19% `LitRPG`. **Verified against the data, not the card: all five score columns are 100% null**; engagement (followers/favourites/views/rating counts) is populated | The calibration target for §10 and the reference distribution for §1a.5's first bar. Read by `tools/build_craft_profile.py` behind the optional `corpus` extra; only derived statistics are committed (`plan/craft-profile.json`), never prose, since the underlying fiction is its authors' copyright. Design, measured labels and validity limits in [plan/craft-corpus.md](plan/craft-corpus.md) |
| MirrorBench | M0–M4 done, M5.0 landed (1,317 tests). One **unpushed** commit; its own README still says "M5 not started", contradicting its plan.md | Methodological invariants only; **verified zero coupling in both directions** — no import, no shared schema, no fixture exchange |
| LongRangeContext | M0 complete, gated, reported (17 tests). **Now a git repo, Apache-2.0 LICENSE added, contracts pin relaxed to `>=0.1.0`** | Promote further milestones when Book Zero shows distant-context failures (it will); simple baseline until then. **"Byte-reproducible" was this plan's one *over*statement, and is now true rather than claimed**: three distinct machine-specific leaks fixed (an absolute checkout root in both reports, absolute artifact paths built by its own contracts loader, and CRLF from text-mode writes), each pinned by a mutation-tested guard. The test that carried "reproducible" in its name never compared bytes; one now does |
| ContinuityEvaluation | LitRPG rules pack (six deterministic detectors, span-exact, mutation-tested) **plus the first advisory craft detector, a structural advisory/blocking partition, and a UTF-8 live-book process boundary — 60 tests.** Frozen plans and live shared-contract bundles reach the same runner; Apache-2.0 LICENSE | Owner of the LitRPG rule and predicate vocabulary (§8.4), and now of the bar that stops an uncalibrated proxy becoming a gate. **Further craft detectors are blocked on §10.6's corpus, not on effort** — see §10.6, and `research/quality-measurement/BRIEF.md` §2 for the refutation ledger. *(Struck: "five working deterministic detectors, 20 tests… hard-gated to the mystery fixture only".)* |
| RevisionPropagation | Plan only — literally one file (the row this plan has consistently had right) | Deterministic invalidation slice only, when Book Zero's edit churn demands it. Note its M0 proposes authoring change/impact/plan/event schemas **that contracts already ships**, and its plan never mentions contracts |
| **Narrative Planning** | **Bounded directive producer now lives in LitHarness; standalone incubator not created** | §9. One scoped directive can produce a guarded immutable plan revision; full-book generation, foreshadowing, progression, and plan-quality benchmarks remain the creative gap |
| **Game-System Engine** | **Does not exist — create** | §8. The genre half; highest-precision quality claim. Ships as a detector pack inside ContinuityEvaluation first, promoted to its own package when a generator exists to constrain (§8.4) |

Two structural facts this table used to hide. **BookWorldState does not consume
litharness-contracts at all** — `dependencies = []`, and no reference to
contracts, conductor, litrpg or game-system anywhere in its tree; the
shared-schema integration is unstarted, not partial. And on version control: of
the eight subprojects **plus this one**, BookWorldState, RevisionBench,
RevisionJudge, MirrorBench, litharness-contracts and LitHarness are now git
repositories. **Only RevisionPropagation is not, and it is one file** — the
version-control gap this plan tracked across three revisions is closed.
~~Remaining licensing gaps, both deliberate: litharness-contracts says "License:
TBD" and ContinuityEvaluation has none~~ — **litharness-contracts is Apache-2.0
and has been since `32d9728` (2026-08-13); only its README still said "License:
TBD", and that line is corrected as of contracts 0.2.0.** Naming a license
remains the owner's call rather than a task an agent should complete.

## 8. Game-System Engine (new pillar)

LitRPG's defining property: part of the fiction is a formal system. Exploit it.

### 8.1 Responsibility

A deterministic, model-free simulation of the book's game mechanics, layered on
BookWorldState's closed predicate registry:

- character sheets: stats, HP/MP ceilings, XP and level curves, skills with
  acquisition events and level requirements;
- economy: currency ledgers, inventory with acquisition/transfer/consumption
  events, unique-item constraints, loot tables authored as world rules;
- quest and progression state machines: accepted → active → completed transitions
  bound to narrative events;
- system voice: blue-box/status-window rendering as first-class manuscript blocks
  (a `Block` kind in the IR with structured payload + rendered text), diffable and
  verifiable like any other span.

### 8.2 Contract with generation

Generation is **constrained by** the engine (the context packet includes the
current sheet, legal actions, and pending obligations) and **validated against** it
(every accepted scene's extracted events must replay cleanly through the
simulation; every status block must equal the simulated state at that story
position). A scene that grants an unearned level or spends gold that isn't there
fails an integrity gate — no critic involved, no human involved.

**Resync, don't carry forward — and only simulate what events can derive.** The
sentence above, read as a pure fold, is wrong in two ways that the litrpg fixture
exposes concretely, so the semantics are pinned here:

1. **Report-then-resync.** After emitting a mismatch at a story position, the
   sheet resyncs to the *asserted* value before continuing. A carry-forward fold
   over the fixture's gold ledger yields four findings (s3 20-vs-15, then s4, s5,
   and s6 5-vs-0) where gold labels exactly one — and the spurious s6 divergence
   lands on a span byte-identical to the negative control
   `f-control-status-repetition`, so pure fold fails the control clause by span
   collision. One defect must produce one finding, not a cascade.
2. **Simulate only what the event vocabulary supports.** In the fixture that is
   `gold` and `level`. No record carries an HP or MP delta — the complete event
   vocabulary is `purchased, paid, used_skill, consumed, leveled_up, used_item,
   acquired_skill, quest_completed` — yet snapshots move HP 24→22→34→27 for
   reasons that exist only in prose. `hp/mp/hp_max/mp_max` are snapshot-supplied
   and checked by the intra-snapshot ceiling rule, never simulated. Simulating
   them emits false positives at s3, s5 and s6.

### 8.3 Evidence base and gates

The litrpg golden fixture in litharness-contracts (gold ledger arithmetic, HP
ceiling, level monotonicity, skill-before-acquisition, quest-state, ghost item) is
the conformance suite; RevisionBench's LitRPG stratum (99% recall / 88% precision
cross-chapter on templated prose) is the evidence this class of check scales.
Promotion gates: 100% recall on the fixture's planted defect classes, zero findings
on its negative controls, replay determinism, and validation of model-written (not
templated) chapters — the known gap RevisionBench has already flagged.

**Four clauses, and only three are reachable before Stage 1.** Model-written
chapters do not exist until generation does, so fixture work closes three of four
and is explicitly *not* promotion. Say so when reporting it; a green fixture gate
otherwise reads as more than it is.

**The stated gate is also not sufficient on its own.** Three defects in it, each
verified against the fixture, each of which would let a false green through:

- **Recall is the wrong measure — grade exact-set equality** on
  `(category, subtype, rule_or_critic_id, primary_span)`. `consumed red_potion`
  has no acquisition record anywhere, making it structurally identical to the
  planted silver-key ghost, yet it is not a labeled defect. A principled ghost
  rule emits seven findings against six gold; recall-only passes it. The only
  mechanical discriminator is `used_item` vs `consumed`, and narrowing to
  `used_item` leaves a population of exactly one — a check indistinguishable from
  `assert True`. Escalate that as a fixture inconsistency rather than hardcoding
  around it.
- **The negative-control clause is vacuous for record-based checks.** Both
  controls are prose-only phenomena with prose-only rule ids (`style.flavor.v0`,
  `repetition.format.v0`) and no backing state records, so a record-only engine
  cannot fire on them at all. Replace that leg with **mutation testing**: perturb
  the fixture in memory (set s3 gold to 20, s4 HP to 30, s5 level to 4, move the
  skill-acquisition order key earlier) and require the corresponding detector to go
  *silent*; then perturb a conforming step and require a new finding. Three of the
  six checks have a fixture population of one and zero negative examples, so
  without this leg half the suite is tautological.
- **Strip the answer key before the engine sees state.** `note` is a declared
  field on `StateRecord`, and five of six planted defects are annotated with their
  own finding id (*"Gold 15 is what the prose says; the ledger-correct value is 20.
  See f-gold-ledger."*). A 6/6 gate is reachable by regexing `note` for `See f-`.
  ContinuityEvaluation's corpus builder **already closes this by construction** —
  it projects each state record onto a fixed field list that does not include
  `note` — which is one more reason to build there rather than against raw
  `state.json` (§8.4). Preserve the property deliberately: keep `note` out of the
  corpus projection and assert the detector modules never reference the field.

### 8.4 Where this gets built, and who owns the vocabulary

§7 and §8 previously assigned the identical invariants over the identical fixture
to two different projects, which would produce two divergent predicate
vocabularies over one fixture and a permanent reconciliation tax. Resolved: **the
LitRPG rule and predicate vocabulary is owned by the game-mechanics pack, and that
pack lives inside ContinuityEvaluation until a generator exists to constrain.**

Build the six checks and the gold-ledger fold there, not greenfield. That repo
already has the fixture loader, the deterministic-detector registry, a
schema-validating Finding emitter (`rule_or_critic_id`, `confidence_basis:
"deterministic"`, content-addressed finding ids, claim objects), the
`input_digest`/`config_hash` determinism machinery, and a conformance harness
*stricter* than a new one would start out — it already asserts total finding
count, the precision gate a recall-only design omits.

**This is now done — the paragraph above describes a decision, not pending work.**
*(Struck: "It also has a reserved, empty `detectors/rules/` package whose one-line
docstring reads 'Closed world-rule detectors are reserved for a later milestone.'
The only obstacle is a self-inflicted `contract_fixture_id != "mystery"` check
that raises before the litrpg fixture can load, plus a three-branch predicate
translator that silently drops every predicate it does not recognise." The package
is full, the fixture gate is an enum, and the translator is table-driven — see
§20.2 and [plan/litrpg-rules-pack.md](plan/litrpg-rules-pack.md).)*

A standalone Game-System Engine package earns its existence at §8.2's *forward*
interface — the context packet carrying sheet, legal actions and pending
obligations — which has no consumer until Stage 0/1 exists. A simulator that only
runs backwards over one fixture is an evaluator, and evaluators belong in the
evaluator. Promoting the fold out later is a move, not a redesign.

Keep BookWorldState behind an unimplemented port for now. §8.1's "layered on
BookWorldState's closed predicate registry" is not currently buildable (§20.4),
and BookWorldState has no WorldRule implementation to host the fixture's two
`author_locked` rules in any case.

## 9. Narrative Planning (new pillar)

The hard creative problem v1 delegated to an absent author.

### 9.1 Responsibility

- Generate and maintain the book plan: premise → arc structure → act/chapter
  outline → scene beat sheets, all as versioned `PlanSnapshot` items with
  authority levels (directive-locked / intended / possible).
- Maintain a **foreshadow-payoff ledger**: every planted promise carries a target
  window; the planner schedules payoffs and the evaluator flags overdue ones.
- Maintain a **progression schedule** (LitRPG-specific): level-up cadence, power
  milestones, new-mechanic introduction rate — planned against the Game-System
  Engine so the plan is mechanically satisfiable.
- Convert human directives into plan deltas with recorded interpretation;
  replan downstream beats when the director changes course, through the standard
  change/propagation machinery.
- Serialization awareness: chapter-end hook placement, recap needs, arc positioning
  within a serial cadence.

### 9.2 Discipline

Plans are proposals against gates like everything else: structural validity
(beats reference real entities/threads), mechanical satisfiability (progression
schedule replays), constraint consistency (no beat contradicts a locked directive),
and — once calibrated — craft critics for arc shape. Planning research runs as its
own incubator with the same benchmark discipline as the others: authored gold
outlines, adversarial cases (directive conflicts, mid-book pivots), and
plan-quality measured by downstream draft outcomes, not plan aesthetics.

### 9.3 Implemented transaction foundation and bounded directive producer

The proposal/accept boundary is provider-independent.
An imported valid plan becomes a content-addressed immutable root; a `PlanProposal` names
that exact baseline and carries its edits, directive readings, rationale, expected outcome,
and provider/model/profile provenance. Acceptance rechecks the head under SQLite's write
transaction and commits the child snapshot, directive interpretations, locked constraints,
`PlanChanged` event, and acceptance policy decision together. A moved head records a conflict without
overwriting either plan. Rollback is a new child revision whose contents restore an earlier
snapshot, so both the mistake and correction remain in lineage.

A bounded first creative slice now consumes one unambiguously scoped premise, arc, tone, or
chapter directive per job. It asks the configured generation provider for strict structured
output, admits at most 12 edits, preserves explicit targets, forbids canonical authority and
locked-item mutation, validates the single-premise invariant, and records provider usage in
the accepting or refusing policy decision. The model never writes storage directly. An
accepted proposal, its decision, directive reading, plan revision, and events commit
atomically; a moved head regenerates rather than overwriting newer direction. Exact
constraints and vetoes retain their higher-priority model-free lane. Every accepted plan
change advances the plan epoch and cancels queued scene prompts frozen against the old plan.

This is deliberately not the full Narrative Planner in §9.1. It does not generate a book
plan from scratch, ~~schedule foreshadowing or progression~~ *(§9.4: foreshadowing now, but
not progression)*, replace the fixed beat template, or run structural,
mechanical-satisfiability, or calibrated arc-quality critics.

### 9.4 The foreshadow-payoff ledger against §9.1's bullet, scored

§9.1's second bullet asks for three things: *every planted promise carries a target window; the
planner schedules payoffs; the evaluator flags overdue ones*. Stage-0 §94 closes the first two
and had already closed the third. What each cost, and what is deliberately still missing:

| §9.1 asks for | state | where |
|---|---|---|
| a promise ledger | **shipped** (§61 Add 2) | migration 023, `domain/promises.py` |
| every promise carries a target window | **shipped** (§94 W2) | migration 029, `outline._payoff_windows` |
| the planner schedules payoffs | **shipped** (§94 W2) | the outline call, folded per §15 |
| the evaluator flags overdue ones | **shipped** (§61 Add 2) | `promise.overdue.v0`, MINOR/advisory |
| *(not asked for; the tripwire needs it)* promise **kind** | **shipped** (§94 W1) | migration 028 |
| a progression schedule against the Game-System Engine | **not built, and the engine is not here** | §8.4 |
| "a cadence a reader can feel" as a measured quantity | **question asked, detector refused** | §94 W3 |
| an independent check that a payoff landed | **designed, substrate absent** | §94 W4 |

**Three of those rows are refusals rather than omissions and each carries its reason.** The
progression schedule needs a forward Game-System Engine interface, and §8.4 put that vocabulary
in the game-mechanics pack inside ContinuityEvaluation — verified absent from `src/` rather than
assumed. The cadence detector is refused *until measured*: "a cadence a reader can feel" is an
unmeasured claim in §1a.3's own words, and building a detector for a property nobody has shown a
reader can perceive is how twenty-one proxies entered this project. And the landing check is
blocked on a substrate finding worth stating plainly, because it is a measurement of this
system's own output: **the only promise ledger this repository holds records 32 promises opened
and none paid across a ten-scene book.** That is §1a.3 item 3's defect, in our own book, counted.

**What did not move.** Windows are PROPOSED-grade, mint no finding and cannot refuse anything;
`promise.overdue.v0` remains the entire evaluator side. A "missed its window" sibling was
considered and deliberately not built — a model-scheduled window missed by a model-reported
payoff is two model claims disagreeing, and neither is entitled to raise a finding about the
other.

## 10. Quality gates and the calibration program (critical path)

This section is the measuring instrument for §1a — the product's actual goal — not
merely the gate that lets autonomy run unattended. Read it that way: the
deterministic ladder below protects the floor, and everything in steps 2–5 is the
only machinery in this document that can register whether the text is any good.

Autonomy requires a trusted accept/reject signal. Today, none exists: RevisionBench
measured that raw model-judge verdicts were 43–65% positional artifacts, and
order-consistent survivors preferred human originals ~80% of the time. So:

1. **Deterministic floor now.** Game-system integrity, continuity detectors,
   mechanical vetoes, schema/scope checks. These gate from day one.
2. **Craft instrumentation next.** Cheap, deterministic proxies logged per scene
   and chapter — pacing profile (action/dialogue/exposition mix), tension-curve
   heuristics, chapter-end hook presence, dialogue ratio, sentence-length
   distribution, repetition beyond the intentional-motif ledger, progression-payoff
   cadence vs. plan. Instrumented from Book Zero; **advisory** until validated.
   Add proxies aimed at §1a.3's list, which the existing set barely touches:
   **scene dramatic function** (does state change across the scene, or is the scene
   pure information transfer — the most common generated-prose failure),
   **progression cost** (does a level, skill or item acquisition carry a paid cost,
   or does the system only ever give), **voice consistency** across chapters, and
   **dialogue distinctiveness** between characters. These are harder and less
   reliable than counting sentence lengths, which is exactly why they are worth
   building — the easy proxies measure the things that matter least.
3. **Calibration against human judgment, ~~and revealed judgment is the primary
   source~~.** *(Superseded by §61 and §1a.4's second amendment: the revealed labels
   available to this project were subsequently measured dead for prose claims — §56.3,
   craft-corpus §4.4 refused — and the primary instrument is now paid, blinded,
   position-swapped pairwise judgment through the preference engine. The paragraphs
   below stand as the record of why unpaid sessions were demoted; that demotion was
   correct and remains.)*
   The calibration target is a corpus of *published* LitRPG carrying reader behaviour —
   follower conversion, retention, abandonment — not a schedule of judging sessions. See
   [plan/craft-corpus.md](plan/craft-corpus.md) for the corpus, the measured label, and the
   validity limits of each direction. Output is unchanged: calibrated thresholds tying
   critic scores and craft metrics to human judgment, per task and genre.

   **This inverts what v2.2 said, and the reason is measured rather than aesthetic.** The
   original read: "weekly bounded RevisionJudge sessions over current output: blinded,
   order-randomized, with planted-defect attention controls". Blinding and randomization are
   necessary *because the asking distorts the answer* — and a system whose quality evidence
   depends on a recurring human appointment is a system that will report no quality evidence.
   RevisionJudge is built, works, and has collected two verdicts against 104 exported pairs;
   that is the measured throughput of the scheduled-session design. Revealed preference has
   neither failure mode and arrives in millions.

   Solicited sessions are **not** deleted — they are demoted to a confirmation sample, which
   is what §10.5's standing audit already is and is sized for. ~~The measured label
   (`followers / total_views`, a conversion rate that divides out discovery) shows 9× spread
   between its 10th and 90th percentiles and Spearman ρ = 0.44 against raw follower count, so
   it discriminates and is not merely popularity restated.~~ **Measured further, and the
   label failed its own control at the grain a calibration would use it**
   (`plan/stage-0-decisions.md` §56.3, 2026-08-17): its top-against-bottom deciles are
   recoverable from `followers` alone at AUC 0.814 while the best prose metric reaches
   0.367, and the division never removed what it claimed — `total_views` counts *staying* as
   well as discovery, so conversion falls as chapters-read-per-reader rises. Revealed
   preference remains the direction; this label at this grain is not the instrument.
   [plan/craft-corpus.md](plan/craft-corpus.md) §3–§4.1 carry the corrected reading and the
   prose-blind covariate control any successor states before it runs.
4. **Critic promotion.** A critic (or metric) becomes a blocking gate only after
   held-out calibration shows usable precision at an acceptable workload, with
   order-consistency and abstention measured. Until then the Conductor treats it as
   annotation.

   **§10.4 now has a second door that is not a gate, and the distinction is the point.**
   [plan/reader-judge-loop.md](plan/reader-judge-loop.md) (stage-0 §90) routes reader
   evidence into a *draft prompt* rather than into a threshold, so it needs no promotion
   and can refuse nothing: readers and judges may shape a prompt and select among
   candidates, and neither may set `blocking`, construct a gate, or park a unit — a
   reader-derived gate is still a gate. The two roles are split by what each is licensed
   to answer rather than by human-versus-machine: a **reader** owns valence, a **judge**
   owns location and axis and never valence, and neither is a signal without the other.
   Nothing in it is live: no axis has a direction and no reader has been paid, so every
   book drafts with an explicitly empty feedback set.
5. **Standing audit — demoted to a smoke check (§67).** Even at full autonomy, a
   sample of accepted scenes (5%, content-derived draw) stays available for human
   spot-reading, and audit disagreement still re-opens calibration. It is a
   confirmation sample, never the evidence plan: the measured throughput of
   judgment-by-sitting-down is 2 verdicts per 104 pairs. Its deterministic draw is
   the sampling discipline the pairwise engine (§61 Add 1) inherits.
6. **A craft reference corpus.** Both golden fixtures encode *defects* — planted
   errors with negative controls. Nothing in the program encodes what good looks
   like, so craft work currently has nothing to be measured against (§1a.4).
   Author one: passages that exemplify each item in §1a.3, paired where possible
   with a weaker variant of the same beat, so a proxy can be tested for whether it
   separates them. Human work, and a prerequisite rather than a nice-to-have —
   without it, every craft claim in this project reduces to opinion.

   **This is now the measured, blocking constraint rather than a scheduled aspiration.**
   A design pass over nine candidate craft proxies (three lenses, two independent
   adversarial reviews) promoted exactly one, and the rejections were not failures of
   implementation. Recorded here because the same proxies will otherwise be re-proposed:

   - **The cheapest repair that satisfies the metric is often the disease.**
     `progression_cost` goes green if a token gold decrement is inserted beside each
     level-up — one ledger line, generatable by the very engine §1a.3 item 2 warns
     about, with nothing a reader feels changed. A proxy whose gradient is satisfied by
     bookkeeping does not merely fail to measure item 2; it rewards the failure.
   - **Two proxies would have flagged the fixture's best prose.** `silent_ledger` and
     `state_change_prose_trace` fire wherever a stat moves without a number on the page —
     and the fixture renders HP qualitatively every time it moves ("warmth climbed his
     ribs like a tide coming in"). Their only repair pushes prose toward the machine
     register, degrading items 5 and 6 to satisfy an item-2 proxy.
   - **One was falsified against the fixture outright.** `scene_change_profile` assumes
     ledger delta tracks dramatic change. Mystery scene-6 — the confession and arrest —
     carries **zero** state records; scene-1, pure exposition, carries the most. It ranks
     the book upside down, because record density measures annotation coverage, not
     scene function.
   - **The two proxies §10.2 names by name are not buildable on this evidence.** Measured,
     not assumed: Burrows Delta separates within-book from between-book by 0.6% at ~120
     prose tokens per scene, and the whole program contains **77 words of dialogue**.
     Voice consistency and dialogue distinctiveness need a corpus, not a better method.

   The through-line: §1a.3 items 1–4 cannot be reached from defect fixtures at all. Six
   120-word scenes carrying one promise and one thread apiece can prove a detector
   *precise*; nothing in them can show that a proxy tracks human judgment. **Authoring
   this corpus is the gating item for craft work, and it is human work that no amount of
   engineering substitutes for.** What did ship is `repetition.exact.v1` in
   ContinuityEvaluation — advisory only, aimed at item 5, and explicitly not a claim that
   craft is now measured.

   **Four more proxies refuted, this time against 13,000 chapters of published LitRPG.**
   The running count lives in
   [research/quality-measurement/BRIEF.md](research/quality-measurement/BRIEF.md) §2, which is
   canonical for it — twenty dead as of the compression pass — and is not restated here,
   because it was carried in two places and drifted within a single session. **That brief is
   required reading before proposing a craft metric**, and its structural diagnosis (every
   refuted proxy was static, absolute and correlational) is the fastest way to tell a fresh
   idea from the twenty-first of the same shape.
   `plan/craft-profile.json`, built by `tools/build_craft_profile.py` from the RoyalRoad
   1.61M-chapter corpus, measures rank AUC for each of the four metrics
   `domain/craft.py` instruments — all four named by §10.2 or §1a.3 item 6, none previously
   tested. Holding the era fixed (2025 chapters whose author declared `AI-Assisted Content`
   against 2025 chapters that did not), every one lands within 0.06 of chance:

   | proxy | declared-AI vs undeclared, 2025 | vs pre-2023 | control: undeclared vs pre-2023 |
   |---|---|---|---|
   | `dialogue_ratio` | 0.445 | 0.481 | 0.531 |
   | `opening_shape_repetition` | 0.455 | 0.404 | 0.450 |
   | `sentence_length_cv` | 0.461 | 0.500 | 0.534 |
   | `tricolon_rate` | **0.528** | 0.629 | 0.606 |

   **The last row is the one to learn from, and it is the same lesson as
   `scene_change_profile`.** `tricolon_rate` at 0.629 against pre-LLM prose is the only
   number in this table that looks like a finding, and it survives exactly as long as it
   takes to read the control beside it: *undeclared* 2025 chapters separate from the same
   baseline at 0.606. The metric detects **the year, not the machine** — 2025 RoyalRoad
   differs from 2021-22 RoyalRoad whether or not anyone ticked the box. Without the temporal
   control this would have been reported as the project's first working AI-tell detector.
   **Any future craft proxy measured against this corpus needs the control computed in the
   same pass, or its headline number means nothing.**

   Three confounds keep this at "no separation detected" rather than "no signal exists": the
   declared-AI cohort is 55 stories, self-declaration is certainly under-reported, and the
   cohorts differ enormously in maturity (median followers 16, 88, 314), so a separation
   could have been story-size rather than prose.

   **Four paragraph-grain proxies refuted, and the same corpus reused as a book corpus.**
   Grouping chapters by `fiction_id` reconstructs 163 pre-2023, 165 undeclared-2025 and 31
   declared-AI books, which makes *cross-chapter* structure testable and not only per-chapter
   style. Four formulations were measured with a fixed-window control and a fixed-seed
   shuffle control, then adversarially refuted; declared-vs-undeclared AUC in brackets.
   Minimum cross-paragraph compression distance **(0.325)** is a coverage artifact — a
   minimum-over-pairs statistic is a lottery, and forcing large human books to exhaustion
   *reverses* the ranking. A compression dendrogram over paragraphs **(0.412)** is a clean
   null whose seed-to-seed swing, 0.228 to 0.545, exceeds its distance from chance.
   Nearest-predecessor lag **(0.375)** inverts on the target defect and awards the looping
   book the best score in the corpus, because duplicated scenes are adjacent and lag 1 cannot
   distinguish "continues" from "is being rewritten". A cumulative novelty-decay exponent
   **(0.589)** scored a perfect 1.000 against the machine cohort and is reproduced outright by
   `Counter(trigrams)`. §17's rule held in all four: the temporal control was computed in the
   same pass, and it killed every headline.

   **One metric was kept, and it is a repetition reporter rather than a proxy.**
   `craft.repeated_span.v0` reports the longest run of words a scene repeats verbatim from
   another accepted scene. It exists because `scene_echo` demonstrably misses the defect it
   was built for: a run repeated a 28-word paragraph byte-identically across two scenes whose
   whole-scene NCD is 0.695, well clear of that metric's alarm, since a ratio over the whole
   scene dilutes a fixed duplicated span. It makes no authorship claim and the measurement
   forbids one — published human serials repeat verbatim spans up to 93 words, longer than
   this project's worst generated book at 59. Advisory, threshold-free, non-blocking; §10.4 is
   untouched. See `plan/stage-0-decisions.md` §49, which also corrects §48's claim that human
   prose has no near-duplicate pairs: true at scene grain, false at paragraph grain.

   **What the corpus does and does not supply.** It is *published* LitRPG, not *good* LitRPG,
   and the difference is not rhetorical: the dataset card advertises `overall_score`,
   `style_score`, `story_score`, `grammar_score` and `character_score`, and **all five columns
   are 100% null in the data** — verified across two full shards, 68,676 chapters. What is
   populated is engagement (followers, favourites, views, rating counts), and §1a.1 forbids
   treating that as quality: popularity tracks update cadence, tags, cover art, launch timing
   and an author's existing audience at least as much as prose. So the corpus **does not close
   §10.6**. What it does supply is a *reference distribution* — `percentile_of` places a
   generated scene against published LitRPG, which makes an outlier a fact rather than a
   hypothesis — and a standing method for refuting proxies cheaply, which is how four of them
   were refuted in an afternoon rather than surviving to Book Zero.

   **That reference distribution has since been stratified by length, and it had to be.** The
   profile pooled every chapter over 300 words with no upper bound, so a percentile compared a
   900-word scene against a corpus whose median chapter is **2,074 words**. Measured over 4,000
   chapters, `opening_shape_repetition` falls monotonically with length (ρ = −0.391; 0.0536 at
   300-700 words down to 0.0204 above 4,000) because more sentences means more distinct
   openings — so a scene the pooled ladder placed at the 50th percentile sits at the **19th**
   among chapters its own size. `craft-profile.json` now carries per-band ladders,
   `percentile_of` takes the scene's length as a required argument, and it **abstains rather
   than extrapolating** when no band covers the length or a band is too thin. It also had no
   production caller until now; `craft_gates` takes the scene's length and writes the placement
   into each gate's `detail`. The first thing that reported: Book Zero's 138-to-205-word scenes
   are all *below* the corpus's 300-word floor, so the system correctly says nothing about
   where they sit rather than answering from the pooled ladder as it used to. See
   `plan/stage-0-decisions.md` §50, which also records why the two statistics proposed by
   `research/quality-measurement/hierarchical-compression-information-texture.md` were
   refuted, and that a control which
   cannot fail is not a control.

   **The authoring requirement is withdrawn; the corpus requirement is not.** This section's
   claim that the corpus "is human work that no amount of engineering substitutes for" was
   true of a *hand-authored, attributed* corpus and false of the thing that corpus was needed
   for. ~~A paired good/weak set can be **selected** rather than written: top and bottom
   deciles of reader conversion (`followers / total_views`), matched on tag set, era, length
   and author, gives thousands of pairs where this section hoped for dozens.~~ **Run, and
   selection is refused** (`plan/stage-0-decisions.md` §56.3; §56.6 item 4: "do not select
   §4.4's corpus from conversion deciles"): the deciles are recoverable from `followers` at
   AUC 0.814 and from in-shard chapter count at 0.308, so pairs selected from them are
   paired on story *size*, and whether their halves differ on prose is unknown without
   exactly the attribution work selection was meant to avoid. What selection was already
   known to lose is *attribution* — a hand-authored pair says "these differ in dramatic
   function", a selected pair says "readers converted on one and not the other" and is
   silent about why — so §1a.3's item-by-item ordering stays unvalidated under either
   approach, which means authoring was never buying that either. **§10.6's corpus question
   is therefore open again**: authored is withdrawn, selected is refused, and what gates
   craft work is back to data acquisition — per-chapter retention and reader reviews, both
   public and neither in this dataset — set out with the refusal in
   [plan/craft-corpus.md](plan/craft-corpus.md) §4.

## 11. Manuscript IR and state architecture

Carried from v1 §9 with one addition. The IR remains a typed ordered tree
(Book → Part? → Chapter → Scene → Block → TextSpan) with stable logical IDs,
immutable versions, branch scoping, reorder-friendly position keys, content hashes,
locks, tombstones. **Addition:** `Block` gains a structured kind for game-system
displays (status windows, level-up notices, quest text) carrying both machine
payload and rendered text, so diffing, evidence spans, detection, and export treat
system voice as data, not decoration.

State layers are unchanged and remain the plan's spine: manuscript truth / author
canon (now: **director canon**) / plans / objective story state / perspective state
/ derived artifacts / proposals. No proposal becomes accepted prose or canon
merely because a model returned it — acceptance is a policy decision with recorded
gates.

Revision identity, event/outbox architecture, persistence approach (relational +
blob + FTS; SQLite acceptable for single-node alpha), reproducibility levels, and
failure recovery carry over from v1 (§9.3, §13, §16, §19) unchanged in substance.
They are what makes 24/7 unattended operation survivable, and they were the best
part of v1.

## 12. The autonomous production loop

Per unit of work (scene draft shown; repair/replan analogous):

1. **Select** — Conductor picks the next unblocked beat from the plan.
2. **Assemble** — context packet from frozen revision: local prose, beat sheet,
   locked constraints, game state + legal actions, POV-visible knowledge, open
   threads, distant callbacks (simple baseline until LongRangeContext promotes).
3. **Generate** — provider adapter, frozen profile, candidate artifact.
4. **Gate: shape** — parse, scope, length, locks. Fail → bounded retry with
   structured feedback.
5. **Extract** — state candidates (events, ledger movements, knowledge changes)
   via provider-independent extraction; replay through Game-System Engine.
6. **Gate: integrity** — simulation replay, status-block equality, continuity
   detectors, mechanical vetoes. Fail → retry / detect→repair / park + escalate.
7. **Gate: craft** — calibrated thresholds if promoted; otherwise annotate.
8. **Commit** — accept candidate + state records + provenance + events atomically;
   policy decision recorded with every gate result.
9. **Propagate** — invalidate/recompute derived artifacts; schedule follow-on work
   (summaries, evaluations, next beat).
10. **Digest** — append to the daily report; sample for audit per policy.

Director directives can inject at any tick; they land as plan deltas (step 1's
input), never as mid-flight mutation of a running job.

## 13. Contracts

`litharness-contracts` v0.2.0 exists and is the interchange layer (IDs, evidence
spans, envelopes, findings, change sets, gold suites; **30 schemas**; two golden
fixtures with span-exact annotations, which as of 0.2.0 ship *inside* the package
and are read through `litharness_contracts.fixtures.golden_path`). It is **now
under version control** (7 commits, clean tree, tagged `v0.2.0`, pushed) — §20.1.
Policy for v2:

- **Version, don't freeze.** Expect additive minor versions after Book Zero; treat
  the first breaking rework (2.0) as a scheduled consequence of Book Zero's
  lessons, not a failure. The wire `SCHEMA_VERSION` is **`1.2.0`** — 1.1.0 shipped under §20.3, and 1.2.0 added
  `JobStatus.PARKED` so §4.2's park-vs-exhaustion distinction is representable on the wire — and
  the compatibility gate rejects a differing major, so additions ship as **1.x
  minors** regardless of this document calling them "v2".
- **What an additive minor actually requires here** (learned in 1.1.0, and not
  obvious): a new field must default to `None`. The serializer omits `None` and only
  `None`, so any other default appends a key to every artifact ever written and
  changes every content address derived from it. And bumping the wire version
  rebuilds the golden fixtures, changing their SHA-256 — so every consumer that
  records a fixture digest needs re-running in the same change.
- **What contracts does and does not pin.** It fixes the vocabulary — the
  `JobStatus` state machine, `JobRecord`'s `idempotency_key`/`input_digest`/
  `attempts`, `position_key` as a string (the fixture demonstrates gap-10
  `"010".."060"`), single-parent `parent_revision_id`, and the *absence* of a
  manuscript-span resource kind, which settles v1's TextSpan-node-versus-coordinate
  question in favour of coordinates. It pins almost none of the invariants: every
  schema is `additionalProperties: true` with thin `required` lists. Leases are
  absent entirely and are genuinely net-new.
- **Additions needed for v2 pillars** (minor versions): plan-graph artifacts
  (beat, arc, foreshadow-payoff ledger entries, progression schedule), game-system
  schemas (character sheet, ledger event, quest state, status-block payload),
  Conductor artifacts (directive, policy decision record, exception, digest entry).
- Consumption rules stand: siblings depend on contracts, never on each other;
  negative controls in the fixtures are as load-bearing as defects.

## 14. Director console (was: full editor UI)

A thin surface over the queues and config, in priority order: direction inbox
composer; exception queue with decision actions; daily digest with sampled reading
view (with provenance drill-down); plan browser (arc → chapter → beat, with
directive lineage); findings browser; budget/policy editor; pause/kill controls.
Reading and steering, not editing — line edits enter as directives ("veto this
sentence", "rewrite this scene with X"), which become located complaints for the
standard repair path. The v1 editor, branch-merge UI, and context-inspection
panels are deferred until a human editing workflow is actually wanted.

## 15. Cost model and throughput (to validate in Book Zero)

**The throughput half of this section is retired as a goal (§62).** Scenes-per-tick,
drafts-per-fortnight, and cadence as an operating target are no longer goals (§61) — and
they never had code: no throughput accounting exists anywhere in src/, so retiring them
changes no behaviour. The cost half — the measured harness tax below, the ceilings, the
spend accounting — is the budget governor's basis and stays load-bearing (§18, §4.2
gate 4).

Order-of-magnitude estimate, marked as hypothesis: a 100k-word draft ≈ 140–160
scenes. Per accepted scene: generation 2–4k output tokens, extraction ~1k,
evaluation ~1–2k, retries/repairs amortized ×1.5–2.5 → roughly **10–20k model
tokens per accepted scene**, i.e. **2–4M tokens per clean draft pass**, 5–10M with
revision passes. At local-model cost: hardware time only. At API mid-tier pricing:
tens of dollars per draft. Throughput: even one accepted scene per 10-minute tick
sustains a draft in under two weeks of wall-clock with large margin; the binding
constraint will be gate failure rates, not raw generation. Book Zero instruments
all of this: tokens and wall-clock per accepted scene, retry distribution, gate
failure taxonomy, cost per chapter. Budget governor enforces per-day and per-book
ceilings with parking + escalation on exhaustion.

**Add the per-invocation harness tax — it is not in the estimate above and it is
larger than the payload.** Measured 2026-08-12 (details in
[plan/provider-adapters.md](plan/provider-adapters.md)): `claude -p` carries ~24k
input tokens of its own system prompt and tool definitions per call, of which ~19k
cache-reads and ~5k is re-written every time, giving a floor of ~$0.013 per call on
Haiku and ~3.5–4.2 s wall; `codex exec` carries ~14.8k and **never** caches. At
~1,000 invocations for a draft that is ~7M overhead tokens on Claude or ~15M on
Codex, against a 2–4M payload estimate — 2–7× the actual work. Two consequences:
mechanical calls (extraction, gate feedback, summaries, status-block rendering)
route to Ollama even in production, and multiple asks fold into one invocation
rather than chaining calls that each re-pay the tax.

**Two amendments from the first frontier run, measured
([plan/stage-0-decisions.md](plan/stage-0-decisions.md) §56.1).** The "tens of dollars"
above is scoped to a *100k-word draft at API-key pricing* and had been read as a reason not
to run a frontier arm at all. `ClaudeCodeProvider` passes no credential — it inherits the
local `claude` install's auth — so on a subscription that figure is quota rather than money,
and `DEFAULT_ORDER` puts `claude_code` first with `generation` deliberately outside
`CHEAP_CALL_CLASSES`: **the frontier arm is the unflagged default, and every run in the
decision log needed `--prefer ollama` to avoid it.** And one cost is missing from the model
entirely: `Conductor.tick` clears the health cache every tick, each cron tick is a fresh
process, and `ClaudeCodeProvider.health()` is a real billed round trip — measured $0.3386
cold — that passes neither `budget_check` nor any recorded decision, so no ceiling can see
it.

## 16. Serial publication *(retired, §62)*

**Retired, licensed by measurement rather than preference: this pillar was never
built.** Its entire code footprint measures out at two inert vocabulary values —
`LockKind.PUBLISHED` and `ExceptionKind.PUBLICATION_DECISION`, both contract-coupled
and both kept — plus the whole-book export, which already exists in exactly the demoted
form the refoundation asks for (`litharness export`, the "(export only)" manual mode
below, already in real use). No chapter-release unit, no hook placement, no recap
generation, no posting scheduler, no publication table in migrations 001–020.
Publication is now an export someone runs when the book is good. Recaps survive only
inverted, as the published-serial calibration datum behind the duplication threshold
(`DUPLICATE_SPAN_WORDS`) — that belongs to the quality area and is untouched. The
design as written, kept for the record:

LitRPG's native form is serialized chapters (Royal Road cadence), so serialization
precedes book-shaped export:

- chapter release units with hook placement (planner concern) and recap
  generation (context concern) as explicit artifacts;
- per-chapter export: clean HTML/Markdown with correctly rendered status blocks;
- a **publication policy** per book, human-set: manual (export only), queued
  (human clicks post), or scheduled (autonomous posting at cadence). Outward
  publication always follows the configured policy; drafting never waits on it;
- published chapters become high-preservation spans: post-publication retcons go
  through propagation with an explicit erratum/consistency policy rather than
  silent rewrites;
- whole-book Markdown export follows; DOCX/EPUB polish is deferred (§18).

## 17. Roadmap

Gates, not dates. Stages 0–2 are largely v1's foundation, slimmed; Stage 3 is the
pivot v1 never had.

### Stage 0 — Foundation
~~Version-control litharness-contracts~~ (§20.1 — done; LitHarness itself too).
Scaffold LitHarness: manuscript IR
(including status-block kind), immutable revisions, jobs/outbox, the four provider
adapters, Conductor skeleton (tick, lease, job selection, digest stub). Contracts
already exist; add the schema additions as 1.x minors.
**Exit:** revisions, patches, events, and restore work end-to-end without a model;
the Conductor ticks idempotently for a week unattended (no-op workload); each
configured adapter passes a conformance suite (schema conformance, usage reporting,
a round-trip health probe, timeout, and a forced fallback); and `LITHARNESS_ENV=test`
provably cannot reach a paid provider.

**Met, with one caveat this document already records and should keep recording.** All four
clauses have passing tests (`test_a_job_can_commit_a_revision_and_its_event_atomically`,
`test_a_week_of_no_op_ticks_changes_nothing`, the four-adapter `CONFORMANCE_CASES`, and
`assert_no_billing_reachable`). The caveat is the endurance clause: it is **evidenced, not
met** — 2,016 ticks at the 5-minute cadence with injected time, which measures unbounded
state growth and non-idempotent accumulation but not a long-lived process surviving real
scheduling, sleep and clock changes. Do not let "Stage 0 green" be reported as the week
having been run.

Six slices rather than the four originally scoped, because the operator-grade audit (§19.1)
found the stage was buildable but not *operable*: slices 5 and 6 added the acceptance
decision record, the direction inbox, and the book-import entry point the whole system
lacked. 268 tests.
*(Struck from Stage 0: "commit/license/tag BookWorldState" — already done.)*

### Stage 1 — Closed autonomous slice
Six-scene golden book drafted end-to-end **with no human in the loop**: template
planner (fixed beat sheet), simple context baseline, game-system replay validation
(sheets and ledgers — built per §8.4 as a ContinuityEvaluation rules pack, not a
separate package), deterministic gates, bounded retries, exception queue
functioning.
**Exit:** the mystery and litrpg fixture books regenerate from premise to accepted
six-scene draft autonomously; zero silent mutation; every acceptance carries a
recorded policy decision; planted-defect injection is caught by gates, not luck.
**All four clauses met (slices 7–9).** Both fixture books reach six accepted scenes with no
human in the loop — `import` then bare `tick`s, nothing enqueued by hand
(`tests/test_planner.py`). Every acceptance carries a recorded decision, and "zero silent
mutation" became checkable rather than asserted once `revert` was made to attribute itself
and `litharness verify` learned to report revisions no decision explains.

**The fourth clause closed with slice 9, and the wording it closed under matters.** The
ladder now runs shape then integrity, and the integrity gate refuses a candidate that any
unresolved, deterministic, major-or-worse finding stands against. Injection is over the
fixtures' *own* `findings.json` rather than hand-built findings — a fabricated one would only
prove the gate can read a dataclass the test wrote — and the assertions are that the beat's
node is still **empty** afterwards, that the decision names the integrity gate, that the veto
is one the retry ladder classified, and that the unit parks and escalates after its budget.
Run over the litrpg fixture with its six planted defects ingested, three beats park with
`continuity_breach` and the other three draft: `test_the_defect_stops_that_beat_without_stalling_the_book`
is the one that matters, because a gate that blocked the branch would convert one defect into
a dead book, which is the more expensive failure and the easier one to ship by accident.

**What slice 9 did *not* do, stated so a green clause is not read as more than it is.** §8.4
owns the LitRPG rule and predicate vocabulary and puts it in ContinuityEvaluation, and §13
keeps siblings depending on contracts rather than on each other — so LitHarness ingests an
`EvaluationArtifact` and does not reimplement the six detectors. Exactly one detector runs
in-process, `state.contradiction.v0`, chosen because it is the one corruption no sibling can
see: canon records disagreeing at a single story position, which is what §12 step 5's
extraction will produce the first time it writes a record contradicting an accepted one. It
emits zero findings on both golden fixtures, and §8.3's mutation leg replaces the vacuous
negative-control clause — perturb a conforming book and the detector must fire, repair it and
it must go silent. **Running CE's pack inside a tick was Stage 2's named work** ("integrate the
LitRPG deterministic detector pack"). It is now available through the configured live
subprocess adapter; an unconfigured installation remains gated on shape and contradiction
alone. §8.3's fourth promotion clause — validation on model-written rather than templated
chapters — remains where §8.3 puts it.

**The gate runs in two places, and the split is §19.1's rule applied a third time.** A
finding already standing against a node is checked *before* the provider call and parks the
unit revivably without charging an attempt or a token; a finding about the candidate itself
is checked after generation and charged like the work it judges. The first version charged
both, which poisoned every blocked beat twelve model calls before a human could dismiss the
finding that stopped it — see §19.1, where the defect and what actually caught it are
recorded. `replan` was added in the same pass, because it was named by two docstrings and a
migration comment and did not exist.

Two invariants are enforced at the gate rather than documented, and both are the kind that
looks like a detail until it is wrong once. A finding's **status overrides its severity**:
both fixtures ship negative controls a *correct* detector emits — the rain-on-glass motif,
Julian's deliberate lie — and a gate blocking on every finding would refuse a book for its
intentional devices, leaving "weaken the detector" as the only way past. And an
**uncalibrated critic cannot block** (§10.4), enforced here as well as in
`PolicyDecision.__post_init__`, so a non-deterministic verdict never reaches the constructor
that would raise on it.

**Slice 8 built the objective-story-state layer and the context packet, and it is worth
recording that these were one slice rather than two.** §11's spine lists seven state layers
and exactly one had no table — objective story state — and *both* remaining Stage 1 items sit
on it: §12 step 2's packet needs open threads and POV-visible knowledge to read, and §12
steps 5-6's integrity gate needs somewhere to write extracted candidates and something to
replay them against. Building either first would have meant inventing a private store for it.
The fixtures had been shipping `state.json` beside `manuscript.json` and `plans.json` since
0.1.0 and `import` read two of the three.

Three things this slice found, each of which would have been a silent wrong answer:

- **`context_gold.json` existed all along and nothing referenced it.** The contracts
  `GoldContextSuite` states, span-exact and hash-checked, what the packet for the mystery's
  scene 6 must contain and must not: four mandatory items spanning scenes 1, 2 and 4, and one
  forbidden POV leak. The measuring instrument for this work predated the work by the whole
  project, which is the strongest form of §20.3's consumer-first sequencing — the shape was
  not guessed at all.
- **`StateRecordKind.EVENT` is referenced as `ResourceKind.STATE_EVENT`.** The two
  vocabularies differ in exactly one member, so the obvious `ResourceKind(record.kind.value)`
  raises on that one and works on all the others — and the golden suite names that exact
  resource kind. Mapped by an explicit table, mutation-tested.
- **An absent POV must *exclude* a restricted record, not admit it.** The suite settles this
  by forbidding `rec-brandt-knows-letter` in a case whose query names no POV at all.
  Defaulting the other way would make "forgot to pass the POV" mean "leak everything
  private", with nothing downstream able to tell.

**What the packet honestly is, stated so it is not overclaimed.** §12 words step 2 as a
"simple baseline until LongRangeContext promotes", and this packs by a fixed priority order
— premise, constraints, threads, facts, prose — not by relevance. Under a budget that binds
it drops the oldest prose rather than the least relevant and has no way to know the
difference. What it therefore owes, and what is tested, is that **every omission is
recorded** with its reason, on the artifact and on the job payload. On six-scene fixtures the
budget never binds, so this limit is currently invisible; it will not be at Book Zero length.
Only `draft_scene` is served — the suite's four `evaluate` and `repair` cases are named as
ungraded rather than skipped, so implementing one without grading it fails the suite.

**State extraction is now built, and it closed the loop rather than adding a feature.**
§12 step 5 (`domain/extraction.py`) reads every accepted scene for the facts it establishes,
writes them in the revision's own transaction, and runs *before* the integrity gate so a
candidate contradicting established canon is refused while refusing is still free. That
matters because `state.contradiction.v0` had no in-process producer — nothing in `src/`
constructed a `StateRecord` at all — so its zero findings on both fixtures were a clean
negative control and also the sound of a check with nothing to check. It now fires: perturb a
conforming litrpg status line and exactly one MAJOR names the position; restore it and the
detector goes quiet. End to end, the two-place gate split is exercised by a defect the system
produced itself rather than one an operator ingested — the candidate's own contradiction costs
an attempt, and the next tick meets the finding standing and parks pre-flight for free.

**It mints nothing, which is the part to carry forward.** The story position is read back out
of the book's own imported evidence and abstains where the book is silent or ambiguous; the
subject must already exist in canon; the value is the prose's, uncorrected, so §8.3's planted
defects survive extraction rather than being sanitised by their own detector's producer. See
[plan/stage-0-decisions.md](plan/stage-0-decisions.md) §27 for the alternatives and their
measured failure modes. Two consequences are deliberate and are the honest limit: a book with
**no imported snapshot has nothing to read back and extracts nothing**, which is Book Zero
(Stage 3); and `render_prompt` now asks generators to emit system voice for any book whose
canon already holds a status snapshot.

**That change landed, and the gain is the gate rather than the extraction.** A generated
litrpg scene used to carry no game state at all, so `state.contradiction.v0` had nothing to
read and every generated scene passed the integrity gate **vacuously** — a scene claiming Rook
had forty gold where canon says forty-five was accepted, because it never said so on the page.
It says so now and is refused, measured through the loop. That is §8.3's fourth promotion
clause and this stage's "validation on model-written rather than templated chapters", closed by
making the prose speak rather than by adding a detector. What it is **not**: a redraft agreeing
with canon still extracts nothing new (`_already_canon` suppresses a fact already accepted at
that position), and a book with no imported snapshot still extracts nothing at all, because
`attested_position` has no evidence to place it by — Book Zero will write system voice that
nothing can yet position, and asking for the line is a precondition for solving that rather
than a solution to it.

**That is now closed, and the correction to what stood here is worth keeping.** It read: the
story position of an authored scene has to come from the plan, which does not state one, so
this is a Stage 3 *design* item rather than an engineering gap. The first half was right and
the conclusion was not — the plan states it now, in eleven lines.

The tempting fix really is the refuted scheme: let extraction derive a position from the
scene's ordinal for a book with no imported vocabulary. §27 measured that and rejected it, and
moving it to the one book where the measurement cannot be run makes it worse rather than
safer — reading order is not story order, the mystery's scene 5 is an analepsis attested at
`s1`, and on Book Zero the error would be invisible because the system would be checking its
own invention. What was missed is that **the refutation is about *deriving* an order for an
arbitrary book, not about a template *stating* that the story it lays out runs forwards.**
`SIX_BEAT` is setup, inciting, rising, turn, crisis, resolution: a chronological progression
with no flashback beat, so a book planned from it cannot contain one — not by assumption, but
because there is no beat to hold it. `BeatTemplate.chronological` is that statement, defaulting
to **False** so a future template that forgets loses extraction coverage instead of minting an
order nothing could detect as wrong.

Three guards keep it narrow. The book always wins: an attested position is read first and a
stated one only fills silence. A stated position is refused outright for a book that has story
positions **somebody else** chose, so the mystery's scene-2 gap is never filled and no record is
inserted into a numbering another author owns. And every record placed this way says so in its
`note`, because "the book said where this sits" and "the sheet we planned said so" are different
provenance.

**One defect, found by running Book Zero rather than by reasoning about it.** The vocabulary
guard first counted *any* canon record with an order key — including the ones this extractor
had just written. So scene 1 was placed, its own record made the book look like it had a
vocabulary, and every later scene abstained: a six-scene book extracting exactly one fact,
indistinguishable at every layer from a book whose other five scenes established nothing.
`REGISTRY_VERSION` already existed to tell this extractor's records from authored ones.
Measured after the fix: a book with no snapshot drafts six scenes and reads back all six
balances, `s1` through `s6`.

What still has to be supplied is the **seed**: a book with no status record at all is never
asked for system voice, so it writes none and there is nothing to place. One starting sheet —
the initial condition a LitRPG book has anyway, carrying no story position because it is true
before the book begins — closes the circle, and it is authored input rather than a genre this
system guessed. The instruction is the book's own current status line, held to the parser by
a round-trip test, because a prompt asking for a form the parser rejects yields zero records
and reads exactly like a scene that established nothing.

**And it was measured rather than reasoned about, which is the only reason it works.** The
first version showed the extractor's template with its `{subject}` slot intact. Asked to draft
against it, two of three local models substituted the character's name and one wrote
`[STATUS] {subject} — Level 3 | ...` verbatim: a line that *matches* the parser, names a
subject canon has never heard of, and extracts nothing — the silence no gate catches, produced
by the instruction meant to prevent it. Showing the book's own line instead is three of three.
The whole suite runs on a provider that ignores the prompt, so **nothing but a live model can
check this**, and `tests/test_planner.py` carries that check as an opt-in test against local
Ollama, which spends no quota. It is off for the mystery, whose canon
holds no status snapshot: a stat block in a locked-room mystery is not a smaller error than a
missing one.

The **game-system replay validation** is built where §8.4 says it belongs and now reaches the
gate. Stage 2 adds the optional live subprocess adapter: a tick can stream the current shared
manuscript/state/plan bundle through that pack without coupling either sibling at import time.

### Stage 2 — Detect and scoped repair
Repairs triggered by findings, applied to a located span, verified by re-detection,
bounded by vetoes.

**The exit clause below replaces one that could not be run, and the replacement is
narrower on purpose.** The original read: *"detect-then-repair beats revise-then-gate
on affected-span precision and preservation on held-out material (RevisionBench's own
promotion gate)."* Four of its terms were checked against the code and three do not
exist:

- **"Affected-span precision" is not computable.** `GoldImpactExpectation` is
  `(target, label, note)` — **no character offsets anywhere**. The gold also never
  labels the node the change edits (`e1-lantern-price` edits scene-2 and labels scenes
  1, 3, 4, 5, 6), so it cannot grade the repair site either. What it encodes is *blast
  radius at node granularity*: which other nodes a change must reach, and which it must
  not touch. Real, useful, and not span precision.
- **"Preservation" is already a guarantee, not a measurement.** `patch.py`'s
  `_verify_preservation` refuses any patch whose text outside the licensed spans is not
  byte-identical, checked by walking the result independently. There is nothing to score:
  a patch that fails it does not exist. Scoring it would report 1.000 forever.
- **"RevisionBench's own promotion gate" does not exist.** Four prose hits for "promot"
  in that repo; its one standing rule is a *blocker* — no threshold ships until
  replicated on a second model family. And it cannot be imported anyway: §13, plus
  `requires-python >=3.13` against this project's `>=3.11`. What transfers is the loop
  *shape* — one complaint and one span per call, best-of-N ranked by edit distance, a
  screen rejecting empty or oversized or form-changed output, acceptance only if the
  complaint count strictly falls — re-derived against this project's `PatchOp` vocabulary.
- **"Held-out material" does not exist either**, and this is the one the replacement does
  not solve. Both gold impact suites are generated from the same `def.json` that authors
  the prose they grade, and ship inside the contracts package, which six test modules
  already read. 37 expectations against this project's own `MIN_HOLDOUT = 50`.

**Exit, as it can actually be run:**

1. A finding with a `primary_span` triggers a bounded repair that changes only that span,
   verified by re-detection over the repaired prose — and a re-detection that *errored* is
   not a pass (`adapters/evaluation_artifact.py`).
2. **Node-level propagation scope on the dev suites**, scored by `domain/impact.py` and
   reported with its caveat attached, beating both baselines it ships with: precision
   above `predict_everything`'s **0.481** at comparable recall, and `e3-typography-only`
   — eight `safe_preserve` targets, no `must_update` — left **untouched**. Measured
   already: the obvious positional heuristic scores **0.333**, worse than guessing
   everything, so "downstream of the edit" is refuted before it is built.
3. The number is labelled **dev-set** wherever it appears. Held-out material is Stage 3's
   to supply — Book Zero's own output is the first genuinely unseen prose this project
   will have — and until it exists, no claim from this stage generalises.

**All three met.** Item 1 is `test_accepted_draft_is_evaluated_repaired_and_verified` for the
chain, `test_incomplete_verification_never_marks_a_finding_fixed` for the errored-run half, and
`test_preservation_holds_for_arbitrary_single_span_edits` for "only that span" — a property
test, because the guarantee is checked by walking the result rather than trusted. Item 2,
re-measured: the engine scores **precision 1.000 at recall 1.000** with zero false touches,
against `predict_everything`'s 0.481 and the positional heuristic's 0.333, and
`e3-typography-only` reaches nothing at all. Item 3 is `impact.CAVEAT`, defined once, asserted
by `test_every_score_carries_what_it_is_not`, and printed by `litharness propagate` under every
result so the number cannot travel without it.

**What "Stage 2 complete" does not mean, in the order a reader is most likely to get it
wrong.**

- **The propagation number does not generalise, and item 3 exists to say so.** Four cases, 37
  expectations, both suites generated from the same `def.json` that authors the prose they
  grade, and the rules were written after reading them. A perfect score on material of that
  size and provenance rules out an engine that is obviously wrong and rules in nothing.
  `tests/test_propagation.py` is the other half — each rule against a book built for it, plus
  the cases the gold has none of — and it is evidence about the rules, not about books.
- **Propagation routes re-checks; it does not detect.** Walked end to end, the four evaluations
  a gold-price repair queues all complete and report nothing, because `state.contradiction.v0`
  compares values at a *single* story position and the broken thing is arithmetic across them.
  That belongs to ContinuityEvaluation's pack, which is optional. The stage's title is "detect
  and scoped repair" and the *scope* is what these numbers are about.
- **The in-repo change producer reads `fact_changed` only.** Renames and moved events are
  reachable through `litharness propagate` over a `ChangeSet` and have no producer here, which
  is §13's boundary rather than an omission.
- **The original exit clause was not met, because it could not be run.** Three of its four
  terms do not exist, as the paragraphs above record. Nobody should read this stage as
  "detect-then-repair beats revise-then-gate on held-out material"; held-out material is Stage
  3's to supply and this measured node-granular scope on dev fixtures.

`domain/impact.py` and `tests/test_impact.py` are this clause, executable. The first exit item
is now wired as durable `evaluate_revision` and `repair_finding` work: accepted drafts enqueue
evaluation, one deterministic located complaint licenses one bounded replacement, and only a
complete re-detection that explicitly checked the rule can mark it fixed. The chain is serial
and capped, so content-derived job ids cannot turn a persistent complaint into a spin loop.
The live-book producer contract and subprocess adapter are now wired. Frozen fixture plans and
live bundles use the same ContinuityEvaluation runner, and transport/schema failures become an
incomplete evaluation rather than a false clean.

**Exit item 2 is now met on the dev suites, and for a while it was a scorer with nothing to
score.** `impact.py` graded blast-radius predictions and shipped three baselines to beat, and
no code in `src/` produced a prediction — the clause was executable and had no subject.
`domain/propagation.py` is the engine: four rules, one per semantic change kind the contract
names and this project can honestly read. A **rename** reaches wherever the old name is
spelled, forwards and backwards, minus the aliases the change preserves — a name is not
carried forward, it is written, and every place it is written is wrong the moment it changes.
A **changed fact** reaches forward only, to the later scenes carrying both its subject and its
predicate and to the records asserting it from that story position on; a balance before the
purchase was true before and stays true. A **moved event** reaches the window strictly between
the two edited nodes, plus the records at the origin sharing its subject. **Surface-only**
reaches nothing, which is `e3-typography-only`. Measured over both gold suites: **precision
1.000, recall 1.000, thirteen hits and zero false touches**, against `predict_everything`'s
0.481 and the positional heuristic's 0.333, with `e3` untouched.

**That number is a dev-set number and the third exit item is the one that governs it.** Four
cases, 37 expectations, both suites generated from the same `def.json` that authors the prose
they grade, and the rules were written after reading them. A perfect score over material of
that size and provenance rules out an engine that is obviously wrong and rules in nothing;
`tests/test_propagation.py` exists to test each rule against books built for it, including the
cases the gold has none of, and `litharness propagate` prints `impact.CAVEAT` under every
result so the number cannot travel without it. Held-out material remains Stage 3's to supply.

**What abstains, and why that is the load-bearing part.** `event_added`, `event_removed`,
`plan_changed`, `pov_changed`, `rule_changed` and `unknown` have no rule. They come back as
`unhandled`, leave the analysis incomplete, and exit non-zero — because "nothing propagates"
and "nobody looked" are the same empty result otherwise, which is precisely the defect
`litharness ingest` was corrected for one stage earlier.

**The loop now closes inside a tick, and the defect it closes was invisible to every gate the
system has.** The evaluation a repair schedules re-checks the repaired node and only that one,
so correcting the lantern's price in scene 2 left four downstream balances wrong while the
book reported clean — detect-then-repair with no propagation is detect-then-repair-then-lie.
The producer is the one this repo can honestly build: an accepted repair already runs
`extract_state` over its result, and `propagation.changes_between` reads the difference against
the canon being retracted. Matched on `(subject, predicate, order_key)`, because a running
balance differs at every position by design and matching without the position would report the
ledger advancing as a contradiction; and a mapping value is diffed **to the field**, because
`status_snapshot` is not a word any book contains while `gold` is both the changed field and
the token the prose carries. The reached scenes are queued for evaluation in the acceptance's
own transaction, under an `ImpactAnalyzed` event carrying the reached set beside the enqueued
set so a cap that bit is visible rather than reading as coverage. Bounded twice: a propagated
evaluation costs a `repair_depth` level, so repair→propagate→repair terminates at
`MAX_AUTO_REPAIRS` hops, and the fan-out per acceptance is capped.

**What closing the loop does and does not buy, walked rather than assumed.** Driving the
cascade end to end — repair, propagate, then *run* the four propagated evaluations — they all
complete and report nothing. That is correct and it is not a fix: `state.contradiction.v0`
checks disagreement **at one position**, and scene 3 stating fifteen gold agrees perfectly with
the record saying fifteen gold. What is broken is the arithmetic *across* positions, and
§8.4 gives that vocabulary to ContinuityEvaluation, whose pack is optional. So the honest
statement is that **propagation routes re-checks to the detectors; whether anything is found is
a fact about detector coverage, not about the book.** With the CE pack configured the ledger
rules see the four scenes; without it the re-checks are real work that finds nothing. Stated
here because "the loop closes" is exactly the sentence that would be read as "the ledger now
repairs itself", and this project's §19.1 is a record of that kind of drift.

The engine deliberately does not fill the gap by minting a finding of its own. It knows scene 3
was *reached*; it does not know scene 3 is *wrong* — that it states fifteen because of the
number that changed is an inference, and the one detector that could settle it belongs to a
sibling. A propagation engine asserting staleness would be guessing in exactly the register
§27 refuses.

**What it does instead is make the ledger legible, which is the §4.3 answer rather than the
§4.2 one.** `litharness state` prints the book's canon in story order, so a balance that stops
adding up is visible to a human in one column even where no configured detector can see it.
That is directing rather than operating: the system routes the re-checks it can justify, and
the place a director looks when it finds nothing is a view that did not exist until now.

The remaining Stage 2 work is **the other two producers, and richer live state/facts
production**. `changes_between` reads `fact_changed` and nothing else: renames and moved events
have no in-repo producer and are reached only through `litharness propagate` over a `ChangeSet`
file, which is §13's boundary and honest about where that half lives. Stale future evidence is
deliberately omitted.

### Stage 3 — Book Zero (the pivot)

**Startable, and it was not before.** A book this system wrote entirely itself used to extract
nothing: `attested_position` reads a scene's story position out of the book's own evidence and
a fresh book has none, so §12 step 5 was inert on exactly the book Stage 3 produces. Three
things closed that, and the preconditions are worth stating because they are what a Book Zero
run needs on day one rather than what it discovers on day three:

1. **A seed sheet.** One canon status record — the starting condition a LitRPG book has anyway
   — carrying no story position, because it is true before the book begins. Without it the book
   is never asked for system voice, writes none, and has nothing to place. Authored input, not
   a genre this system guessed.
2. **A chronological template.** `SIX_BEAT` declares that the story it lays out runs forwards,
   so its beats can state where they sit; the flag defaults to False so a future non-linear
   sheet loses coverage rather than minting a false order.
3. **The instruction, measured.** The generator is shown the book's own current status line
   rather than a template with placeholders — three of three local models produce an
   extractable line, where the placeholder version was two of three.

Measured end to end: a seeded book with no snapshot drafts six scenes, reads back all six
balances at `s1`–`s6`, and seven revisions rebuild cleanly.

**Two more walls fell, and both were structural rather than qualitative.** `SIX_BEAT` is
exactly six functions and `beats_for` refuses any book that is not exactly six scenes, so a
50-80k word book could not be *planned*; and every revision came from `import`, which needs a
manuscript file, so a book could not be *created* from a premise at all. `arc_template(n)`
and `litharness new` close both. The arc reproduces `SIX_BEAT` function-for-function at six —
the property that keeps it from silently relabelling both golden fixtures — and keeps singular
beats singular at length, because a story has one inciting incident whether it is six scenes
or sixty and spreading the six functions proportionally would give a sixty-scene book twelve
of them.

**And it runs free.** `--prefer ollama --no-billing`, or the environment variables behind
them, put a local model in front; measured on `llama3.2:3b`, a seeded six-scene book drafts in
42 seconds at no cost. That matters for this stage specifically: §1a is suspended here because
Book Zero is instrumentation, so the cheapest generator that clears the gates is the right one
to gather a taxonomy with.

**The first run's taxonomy is in
[plan/stage-0-decisions.md](plan/stage-0-decisions.md) §44 and §45**, and its headline is that
**so is progression** — the frozen ledger §44 recorded turned out to be a property of
llama3.2 rather than of this system, and a second model moves it every time (and collapses it
instead, straight to zero in scene one). Scale is a property of the generator rather than of
the loop: 24 scenes came to 3,800 words
because a 3B model writes ~160-word scenes and nothing had asked for more.
*(Struck: "asking helps a capable model (phi4 +47%) and does nothing for a small one". The
instruction was never sent — `render_prompt` took `target_words` and never read it, so both
arms of that measurement were the same request. Re-measured with it wired, three draws per
arm: `llama3.2` 279 -> 384 (+38%) and `phi4` 324 -> 611 (+89%, 68% of target). The small
model follows the instruction; it had not been given one. See
[plan/stage-0-decisions.md](plan/stage-0-decisions.md) §51.1.)*
**The gap is smaller than this paragraph assumed and is not closed**: at 611 words a scene,
50,000 words needs about 82 scenes rather than the 291 the 19% rate implied.

**Pooled across every stored run, and now carried in the record rather than only here.** Six
books, 45 scenes: mean **172 words against a 900-word target — 19%**, ranging 14% (`bz`) to
40% (`run2/local-llama3.2`). At that rate Stage 3's low end of 50,000 words needs **291
scenes**, against the 24 the largest run has managed. **Every one of those runs was drafted
against a prompt that never carried the target**, and no shipped command could select a model
either, so the 19% is a measurement of `qwen3:4b`-or-whatever-was-default writing with no
length instruction — read it as a floor rather than as this system's rate (§51.1). That single ratio is what the stage turns
on, and until now it lived only in this paragraph: `policy_config_digest` cited `target_words`,
the instruction, and nothing anywhere recorded what arrived. `DraftOutcome` now carries `words`
and `target_words`, and an accepted shape gate's `detail` reads "172 words against a target of
900 (19%)" — so the shortfall accumulates per scene and a change to the prompt can be measured
against history instead of guessed at. **It is still not a gate**, and §1a.1 is why: a 900-word
floor would pass a scene that rambles to 900 and refuse a taut one, which measures nothing
about whether the scene lands. The 170-word draft in the test that pins this is *accepted*.

What none of that supplies is the stage itself. 50-80k words is still an order of magnitude
beyond what has been run, the context packet's 6,000-token budget **now has a measured binding point** — scene 24 at the
160 words a 3B model writes, and scene 5 at the 900-word target, holding three prior scenes
(§47). It still drops the oldest prose rather than the least relevant, which is §12's work for
LongRangeContext; what changed is that the budget is settable (`--context-budget`) and a book
being written blind bumps a digest counter instead of recording it where nothing reads it, the budget governor has never met a real bill, and the failure taxonomy is the output
rather than the input.

One complete 50k–80k word LitRPG draft, end-to-end, 24/7 unattended: Narrative
Planner v0 (arc template + beat generation + foreshadow ledger + progression
schedule), simple context, full gate ladder, craft instrumentation logging,
budget governor live. The draft is *expected to be mediocre*; producing it is the
point. **This is the one stage where §1a is deliberately suspended, and only
because Book Zero is instrumentation rather than a product** — its output is a
failure taxonomy, not a book anyone is asked to read. Do not let the exemption
leak: a "Book Zero is allowed to be bad" habit applied to Stage 4 onward would
quietly become the project's quality standard.
**Exit:** the draft exists, produced without inline human action; a written failure
taxonomy (what broke: distant context? pacing? payoff? repetition? cost?) with
frequencies; instrumentation and cost data. **Book Zero's taxonomy reprioritizes
Stages 4–6 — the plan commits to following the evidence, not this document.**

**Run, and the taxonomy is in [plan/stage-0-decisions.md](plan/stage-0-decisions.md) §52.**
Thirty scenes, **26,266 words**, `phi4:14b` local, no inline human action, 400 ticks, zero
exceptions, zero parked units, **10,108 tokens per accepted scene** — which lands at the
bottom of §15's 10-20k hypothesis and makes that estimate measured. Mean scene 875.5 words
against the 900-word target (97%), so the 291-scene figure above becomes **57** and a 50k
draft is about two hours on one local GPU. The stated length is 50-80k and this run was 30
scenes by choice, so the stage is **evidenced at 26k rather than met at 50k**; ~~nothing in
the run suggests the remaining scenes are a different problem~~ — §56.4 measured that they
are: at this stage's own 57-scene target the shipped context budget leaves 32–67 prior scenes
present in the packet in no form at all, a regime a 30-scene run never enters — and §52 is
the output the stage exists for.

**Its headline is not what this section expected.** The dominant failure was **whole-scene
duplication that no gate refuses**: five of thirty scenes are near-copies of an earlier scene,
the longest verbatim run is **872 words** against this project's previous machine worst of 59
and a published-human maximum of 93, and all 31 decisions were ACCEPT with zero findings.
`repeated_span` measured it and reported it in the annotation; §10.4 correctly forbids an
uncalibrated craft gate from blocking, and it has no calibration.

**Closed, by moving the check rather than by calibrating it** — see
[plan/stage-0-decisions.md](plan/stage-0-decisions.md) §53. §10.4's bar governs claims about
*quality*; "these 872 words appear in scene 6 and again in scene 11" is arithmetic over two
strings, and `craft.py`'s own defence of the metric already said so. It is now
`integrity.duplicate_scene.v0`, a deterministic detector in `IN_PROCESS`, blocking without a
calibration exactly as `state.contradiction.v0` does. Replayed over the thirty accepted
scenes it refuses those five and no others, agreeing exactly with an independent whole-scene
similarity measure, and the golden fixtures produce nothing. The threshold sits above the
93-word published-human maximum and inside a gap in the run's own distribution — nothing
between 48 and 352 words — so it is placed rather than fitted and the choice is not delicate.

**And the mechanism is upstream of generation.** `arc_template(30)` yields **25 `rising` beats
of 30**, and the beat's title plus that one word is the entire plan-side instruction — so
twenty-five scenes are asked the same question, and the book re-issues its own errand. The
frozen ledger has the same root: 31 extracted status records, **two** distinct states. So the
taxonomy's first entry is **Narrative Planning v0**, not the sampler and not the context
packet, ~~and §17 Stage 5's "in the order Book Zero's taxonomy demands" now has its
order~~. **Generator-scoped, per §57 (2026-08-17):** the duplication this ordering rests on
is a property of `phi4:14b` — two frontier books in the same no-outline condition put the
longest verbatim repeat at **17 and 12 words** against phi4's 872 — so on the generator
§1a.5 actually requires, the taxonomy's first entry does not reproduce and Stage 5's order
has to be re-argued on other measured ground; §57 names the settling run.

**Narrative Planning v0 shipped, and §54 has what it moved.** One model call per book produces
one statement per scene, stored as scoped `SCENE_PLAN` plan items through the existing
`PlanProposal` path and rendered last in the drafting prompt. Same premise, same model, 30
scenes: near-copies **5/30 → 0/30**, longest verbatim span **872 → 55 words** — below the
93-word published-human maximum — with the duplicate gate refusing nothing, so the gate is not
the explanation. **Measured at five books per arm** (§54.1), and the metric had to change to get there: with
the duplicate gate live a copy is refused rather than accepted, so `copies_accepted` is 0 in
all ten books and the accepted text says nothing. On the gate's own finding count, duplicate
findings per book run **11, 8, 1, 2, 6 without an outline against 0, 0, 0, 1, 1 with one** —
mean 5.6 against 0.4, exact two-sided permutation p = **0.0238**. The arms **overlap**, so the
claim is that outlining substantially reduces whole-scene duplication rather than eliminating
it, and the control arm's 1-to-11 spread is why two books misled in both directions. **The
ledger did not move** (2 distinct states), which is expected and leaves taxonomy entry 3 where
it was — blocked on the level curve the game-mechanics pack owns.

### Stage 4 — Calibrated quality gate
~~Stand up the weekly calibration program (RevisionJudge protocol) over Book Zero
output~~ *(struck, §67/§69: the weekly-session design's measured throughput was 2
verdicts per 104 pairs; the instrument is now the pairwise preference engine —
paid external genre readers, blinded, position-swapped, operated per
[plan/preference-runbook.md](plan/preference-runbook.md))*; validate/discard craft
metrics against human judgment; promote the first calibrated thresholds under §59's
bound; the reference corpus is the preference engine's comparison corpus, selected
under a declared comparator frame rather than authored (§10.6's demand, §61's form);
regenerate or repair the worst chapters under the new gates → **Book One**.
Target per §1a.5 as refounded by §61: the superiority bar (the CI lower bound on
blinded pairwise win rate against matched published-human prose exceeds 0.5), with
"I would keep reading" as subsidiary evidence and flawless system math throughout.
**Exit:** a promotable calibration row exists under §59's bound and a selection
mechanism consumes preference evidence (§61 Add 3); Book One produced under them.

### Stage 5 — Scale the weak subsystem
Integrate LongRangeContext / ContinuityEvaluation prose detectors /
RevisionPropagation slices, each through its own incubator gates.
~~**in the order Book Zero's taxonomy demands**~~ *(struck, §65: Book Zero's taxonomy
was measured on `phi4:14b` and its first entry does not reproduce on the pinned
generator — §57. The ordering source is now the frontier arm's own defect taxonomy,
which does not exist yet and is collected by the pairwise preference engine (§61
Add 1) and the structural instrumentation (§61 Add 2): the defects that predict
pairwise losses order this stage. Until that data exists, no Stage 5 slice is
scheduled on taxonomy grounds. §56.4's dark-scene arithmetic remains the one
frontier-measured candidate — the context packet stops representing the book at
about forty scenes — and overdue-payoff detection ships with Add 2 rather than
waiting here.)*
**Exit:** the dominant *frontier-arm* failure class — as ranked by prediction of
blinded pairwise losses — measurably reduced in a later draft at equal budget.

### Stage 6 — ~~Serial operation~~ *(retired, §62)*
~~Publication pipeline (§16), chapter cadence, recaps, publication policies;
multi-book direction (a second book started while the first serializes); operator
playbook (backup/restore drills, budget reviews, calibration cadence).~~
~~**Exit:** one book serializing on schedule under a queued-or-scheduled policy;
a second in drafting; a month of unattended operation with only directive/exception
/calibration touches.~~
*Retired by §62: serializing-on-schedule and unattended-months are the old goals.
What survives moves elsewhere — backup/restore drills and budget reviews into the
operator playbook (§19); calibration cadence into the preference engine's operation
(§61 Add 1).*

### Stage 7 — Series and steady state
Series continuity (cross-book canon via BookWorldState branches), genre profile
variation, ~~provider failover~~ *(struck, §64 — fallback is a quality defect now)*,
cost optimization. Production claims per v1's reproducibility levels.

## 18. Deferred / cut (explicitly)

Deferred until a human-editing product is wanted: full editor UI, branch-merge UI,
context-inspection panels, real-time collaboration. Deferred until distribution
demands: DOCX/EPUB polish (Markdown/HTML first), plugin sandbox/permissions and
third-party plugin surface, any provider beyond the pinned frontier adapter and the
deterministic fake (§64; [plan/provider-adapters.md](plan/provider-adapters.md) is
the superseded record). Cut from the
definition of done: v1 §26's commercial-SaaS bar (SLO dashboards, incident
response org, support playbooks, accessibility audits, multi-tenant security).
Kept absolutely: provenance, immutable versioning, deterministic gates, durable
jobs/outbox, crash recovery, backups, budget enforcement — autonomy stands on
these.

## 19. Definition of "operator-grade" (replaces v1 §26 "production grade")

The system is operator-grade when:

- **Integrity:** accepted prose, canon, plans, history, and policy decisions
  survive crashes, retries, upgrades, restore, and rollback; every mutation is
  attributable to a recorded policy decision and reversible.
- **Autonomy:** a directed book makes forward progress for 30 days with human
  input limited to directives, exceptions, and calibration; parked units and
  exceptions are visible and bounded; nothing spins.
- **Trust:** deterministic gates have zero known false-accepts on the fixture
  suites; blocking critics carry current calibration evidence; audit sampling
  runs and disagreements feed back.
- **Genre:** accepted prose contains zero game-system violations by replay;
  progression follows the planned schedule within tolerance.
- **Quality (§1a):** the blinded-reader bar of §1a.5 is measured, currently
  passing, and re-measured as output changes; the craft reference corpus exists and
  promoted craft gates carry held-out evidence that they predict human judgment.
  A system that satisfies every other clause here and fails this one is not
  operator-grade — it is a well-engineered machine for producing books nobody wants,
  and that is the specific failure this definition exists to prevent.
- **Economics:** per-book cost is measured, bounded, and enforced; the operator
  can see spend vs. plan at any tick.
- **Recovery:** restore from backup rebuilds all derived state from canonical
  records and events; a mid-write crash loses at most the in-flight unit.

### 19.1 Scorecard, measured

An audit against the seven clauses above, with what it found and what was closed.
Recorded because "is it production ready" is otherwise answered from impression, and
because four of the seven are structurally blocked in ways worth naming precisely.

| Clause | Status | The binding reason |
|---|---|---|
| **Integrity** | **met, and now checked rather than asserted** | Content-addressed revisions, atomic revision+event+outbox commits, restore-by-rebuild. Reversibility landed with a stored `branch_heads` pointer and a `revert` that moves *forward* — history is immutable, so undo produces a new revision restoring the old content, leaving the mistake and the correction both in the lineage. Undo composes. **The correction this row needed:** it claimed "attribution is enforced at the loop: every accepted revision resolves back through `decision_for_revision`", which was true of the generation path and false of the reversibility feature added under this same clause — `revert` committed a revision and moved the head while writing no decision and no event, so `decision_for_revision` answered `None`. That was the one silent mutation in the shipped system, against a literal §17 Stage 1 exit clause, and no test would have caught it. `revert` now mints its own decision and acceptance event (attribution is not a caller's option), and `store.unattributed_revisions()` — surfaced by `litharness verify`, which exits non-zero — makes the clause a query rather than a claim. A structural constraint on one method would only ever have guarded that method. **Reversibility now covers plans as well as prose**, which it did not: `rollback_proposal` was implemented, tested and documented with no caller in `src/`, so the clause held for the manuscript and not for the plan that produced it. `litharness plans` reads the lineage and `litharness revert-plan` restores one as a forward child, carrying its own acceptance decision like every other plan movement. |
| **Autonomy** | **attemptable; needs 30 days** | Was *not startable*: no entrypoint existed, so §17's week-unattended criterion could be simulated but never run. `litharness tick` closes that. Three spins found and fixed — the outbox retried its head 2,016 times a week while starving entries 51+; an escalated unit was marked SUCCEEDED and discarded; and a provider outage longer than fifteen minutes permanently poisoned every unit it touched, because `ProviderUnavailable` was charged against the attempt budget despite being raised before any work was attempted. The exception queue exists. **"Parked units are visible and revivable" was false on the refusal an operator with real ceilings meets first, and the same lesson had to be learned twice:** a budget refusal settled to POISONED — terminal, unrevivable, idempotency key burned — because `_settle` read the terminal state off the word `PARK` under a comment asserting "`decide` returns this only on attempt exhaustion", a premise the budget gate falsifies on attempt 1. A ceiling that resets at midnight destroyed the unit it refused. `_settle` now derives POISONED from the attempt budget itself, and a refusal reached *in front of* the work gives back the attempt it was charged, exactly as an outage already did. **And the lesson had to be learned a third time in slice 9**: a finding already standing against a node was charged against the unit it refused, so a blocked beat poisoned after twelve model calls and the operator's own remedy — dismiss the finding — arrived to find nothing revivable. The gate now runs a pre-flight pass in front of the spend. `replan` shipped in the same fix, because the recovery path it completes was named by `handlers._stale_base` and by migration 011 and did not exist. **And the outbox delivered nothing to anyone for nine slices** — send-then-mark, derived idempotency keys, backoff, a FAILED terminal state and the spin fix above, all draining into a null dispatcher that no caller ever replaced, because no caller ever passed `dispatch=` at all. So `tick`'s printed `dispatched=` count was *structurally* zero, and the fix for the 2,016-attempt spin was a fix to a loop that could not deliver. A JSON Lines sink (`--notify-file`, one `EventEnvelope` per line, fsynced before delivery is claimed) is now selectable, the null dispatcher stays the default when none is configured, and a write that fails refuses rather than raising — because the drain runs *before* work selection, so a mistyped path would otherwise stop the book being written at all. **What remains is elapsed time, which nothing but time supplies.** |
| **Trust** | **no longer vacuous; partly met** | Was: "the deterministic ladder is one gate, `shape.draft.v0`; zero false-accepts over a suite that does not exist is trivially true". The ladder is now shape *then* integrity, and the clause has a suite to be measured against — both fixtures' planted defects, injected from their own `findings.json`. Measured: every planted defect that reaches the gate is refused, the beat's node stays empty, and both fixture books still reach six accepted scenes with the gate live, so there are no false *rejects* either. Two invariants are enforced rather than asserted — a finding's status overrides its severity, so a negative control cannot block forever; and an uncalibrated critic cannot block at all (§10.4). The six-rule pack can now run from each durable evaluation through an explicit live subprocess contract, with transport/schema failures reported as incomplete instead of clean. **What keeps this short of met, re-stated because one of the two reasons went away:** the pack is still optional, but "real-book sensitivity depends on live state/facts the narrow extractor cannot yet produce" is no longer true of the extractor — it produces state for books this system wrote, and the deterministic ladder now runs against that state rather than only against imported snapshots. What replaces it as the honest limit is *coverage*: the in-process detector reads system voice and checks one position, so the violations it cannot see are the ones that need the optional pack. The second half of the clause — "blocking critics carry current calibration evidence" — is untouched and correctly so: there are no critics, only rules. |
| **Genre** | **started; the score is unchanged and both of its stated gaps are not** | The six game-system rules run in LitHarness when the ContinuityEvaluation executable is configured. This row named two remaining gaps — *forward game-state production* and *validation on model-written chapters* — and both closed, without the clause moving. Forward production: `render_prompt` asks for the status line, `extract_state` reads it back, and a chronological template places it, so a book with no imported snapshot now drafts six scenes and reads back all six balances. Validation on model-written prose: before the prompt change a generated litrpg scene carried no game state, so `state.contradiction.v0` had nothing to read and **every generated scene passed the integrity gate vacuously**; a scene now claiming forty gold where canon says forty-five is refused, measured through the loop. **What keeps the clause at *started* is the word §19 uses: "zero game-system violations by replay".** Replay is the CE pack's ledger arithmetic, the pack is optional, and this system's own detector checks disagreement at one position rather than arithmetic across them — so an unconfigured installation routes re-checks to detectors that cannot see the violation. Progression-within-tolerance has no schedule to be within. Two named gaps closing is not the clause being met, and recording them as closed is how the next reader knows which ones are left. |
| **Quality (§1a)** | **not met; the machinery is built and the evidence is not** | Still blocked on §10.6's craft reference corpus, which is human authoring work — and the refutation ledger in [research/quality-measurement/BRIEF.md](research/quality-measurement/BRIEF.md) §2, canonical for the count, now stands at twenty dead, four of them measured against 13,000 chapters of published LitRPG and seven against compression. What changed is that the *path* exists where before there was none. §10.5's standing audit routes a content-derived sample of accepted scenes to a queue and `litharness audit --next` prints the prose blind; a verdict is recorded once and never overwritten; §10.4's promotion bar is a function (`promoted_gate`) that refuses without held-out precision, a minimum holdout, unexpired evidence and a matching verdicts digest, and it is the only way to construct a blocking craft gate. Craft metrics are logged per accepted scene from now on, so a future calibration has held-out history to be measured against rather than starting from zero on promotion day. **The missing input is human judgment and nothing here substitutes for it**: RevisionJudge holds 104 exported pairs and two collected verdicts. The clause is met when readers have answered, not when the schema exists. |
| **Economics** | **met for enforcement; per-book still per-day** | Ceilings on tokens *and* invocations, checked **before** the provider call rather than after — a check that runs afterwards records an overrun, it does not prevent one. Invocations are a ceiling in their own right because §15's per-call harness tax (~24k tokens for `claude -p`) is invisible to token accounting. Dollars are never the sole ceiling, since `claude -p` on a subscription reports none. `cost_usd` was parsed and then dropped; migration 008 stores it. `status` prints spend against plan. **Enforcement that destroys the unit it refuses is not what this clause describes, and that is what it did** — see Autonomy above; a refusal now parks revivably and costs the day rather than the work. **Honest gap: ceilings are per-day and per-operation, not per-book** — that needs a book-scoped job, which arrives with the planner. |
| **Recovery** | **met** | Mid-write crash loses at most the in-flight unit (WAL, `synchronous=FULL`, `BEGIN IMMEDIATE`, lease reclaim). Backups existed nowhere and now use SQLite's online API — a file copy is invalid under WAL and would silently omit everything since the last checkpoint. The drill asserts prose, the accepting decision, and the undelivered outbox all survive. |

**Two of the seven are met outright** — Integrity and Recovery. Economics is met for
enforcement and unmet as §19 words it, because the clause says *per-book* cost and the
ceilings are per-day. Autonomy is attemptable and needs elapsed time. Trust is partly
met and no longer vacuous: the ladder refuses every planted defect the fixtures supply,
and what keeps it short of met is that the pack is optional and there are no calibrated
critics. Genre is started — the six rules run live when configured, and the two gaps this
table used to name under it (forward game-state production, validation on model-written
chapters) have both closed without the clause moving, because §19 words it as *zero violations
by replay* and replay is the optional pack's. Quality is not met, and stays blocked on the one
input engineering cannot supply: human judgment against a human-authored corpus.

An earlier revision of this paragraph said "four of the seven now met" while the table four
lines above it said otherwise, which is worth leaving on the record: the readiness number
this project reports about itself had drifted from the evidence directly above it, in the
one section written specifically to stop that happening. It then happened a second time in
the opposite direction: the table was re-scored for Stage 2 (Trust partly met, Genre
started) while this paragraph went on calling Trust vacuous and Genre not started — the
prose lagging the evidence instead of outrunning it. The direction changes; the defect —
restating the table instead of reading it — does not.

Eleven defects worth remembering, because each failed *silently* and none would have surfaced
without being looked for: migrations resolved to nowhere under a wheel while `migrate`
reported success, so a restored host would have come up with an empty schema that reads as
data loss; a full disk reported "cannot rollback" because the rollback in the transaction's
exit path replaced the real exception; a failed `open` leaked the file handle, which on
Windows blocks replacing a corrupt database with its backup; the outbox spun and starved
simultaneously; an escalated unit was counted as a success; an infrastructure outage
was charged against the unit of work it had prevented; a **budget** refusal was charged the
same way *and* made terminal, so a ceiling that resets at midnight destroyed the work it
declined; `revert` — the feature added to satisfy §19's reversibility clause — violated
the attribution clause in the same sentence, committing a revision that no policy decision
explained; slice 9's integrity gate charged a standing finding against the unit it
refused, so the operator's own remedy arrived to find the work already destroyed; and the
outbox delivered to nobody for nine slices, because the only dispatcher was the null one
and no caller ever passed another — so the audit trail's whole outward half was absent
while every test of it passed; and the deterministic fake backstopped *generation*, so when
every real provider went down the loop kept drafting canned 80-character text, failed the
200-character shape gate three times per beat, and poisoned six beats with five exceptions
for what was an outage.

**That last one is the fourth instance of the rule two paragraphs down, and it hid best.**
`ProviderUnavailable` and a budget ceiling at least *look* like refusals. Here nothing looked
refused at all: a healthy provider answered every call. It simply could not write, and the
attempt budget was spent on discovering that three times over. Found by running a book on a
local model and having the daemon stop mid-session — the failure mode is invisible from any
test that supplies its own registry, which is every test that existed. The fake is out of the
default *generation* order now and stays in the cheap one; `LITHARNESS_FAKE_PAD_CHARS` puts it
back, because setting the pad is the statement "I am deliberately running on the fake".

*(The two counts below read "eight" for three revisions after the ninth defect was added,
which is the same drift the paragraph above the table exists to catch, one paragraph lower
down. Corrected with the tenth.)*

Two of those eleven are the same defect at different layers, and that is the more useful
observation. `ProviderUnavailable` and a budget ceiling are both refusals raised *in front
of* the work; both were charged against the attempt budget of a unit that never ran; the
first was found and fixed, and the second survived that fix by three commits because the
lesson was recorded as a patch rather than as a rule. The rule, stated so the third instance
is caught by reading: **a refusal reached before the work must cost time, never the unit.**

**The third instance arrived with slice 9's integrity gate, and it is worth recording that
the rule above did not prevent it — walking the operator's recovery path did.** A finding
already standing against a node cannot be caused or cleared by the candidate, so all three
attempts met the identical refusal and the unit poisoned: twelve model calls to discover a
fact known before the first one, and then a terminal state with its idempotency key burned.
The operator's correct response is to dismiss the finding, and at the plan's cadence it
arrived roughly fifteen minutes too late to have anything left to resume. The gate now runs
in two places — a pre-flight pass over standing findings that parks revivably and charges
nothing, and a post-generation pass over what the candidate itself produced, which is about
the work and is charged like it. Measured on the litrpg fixture with its six planted defects
ingested: 12 calls and 8,599 tokens before, 3 calls and 1,912 tokens after, with three units
parked-and-revivable instead of poisoned.

**What actually caught it is the transferable part.** The rule was in the document and the
code was written by someone who had just read it. What surfaced the defect was running the
recovery journey end to end through the CLI — ingest, tick, dismiss, revive — and finding
that the documented next verb refused. **A gate is not finished when it refuses correctly; it
is finished when the operator can get past it.** Two further gaps fell out of the same walk:
`replan` was named by `handlers._stale_base` and by migration 011 and did not exist
(`bump_plan_epoch` had one caller and it was a test — the `reset_health` shape again), and
`revive` alone cannot clear a unit whose head has moved on, which is correct behaviour that
nothing had written down.
Three of the eleven were also *pinned by passing tests* — the budget refusal's POISONED
status was asserted by name, and `revert`'s attribution was never asserted at all. A suite
that encodes the defect is worse than no suite, because it converts a bug into a
requirement. **The silent outbox is the subtler version of the same thing:** nothing
asserted the wrong behaviour, but the suite tested the *machinery* exhaustively — backoff,
starvation, redelivery, the FAILED terminal state — and never once tested that a real sink
existed to run it. Green, thorough, and about a component that had no consumer. The
`reset_health` shape for the fourth time (`bump_plan_epoch`/`replan` was the third), and
the pattern is specific enough to search for: **a documented promise whose only caller is a
test.** `domain/plan_refinement.py`'s `rollback_proposal` was the next one on that list, and it was
closed in the same session by `litharness plans` / `litharness revert-plan`.

**The sentence that stood here said the list was then empty, and it survived exactly one
commit.** It also said to read that as "nobody has searched since" rather than "there are
none", which is the only reason it is not simply wrong — searching again immediately found
two more, of a shape the earlier phrasing had missed. `domain/impact.py` was not an uncalled
function: it was a *complete measuring instrument with nothing to measure*, grading
blast-radius predictions against a gold suite while no code in `src/` produced one, so §17
Stage 2's second exit item read as satisfied by the scorer that could only ever report on an
engine that did not exist. And `EventType.IMPACT_ANALYZED` had been in the contract since 1.0
with no producer anywhere. Both are closed by `domain/propagation.py` and `litharness
propagate`. The lesson to carry is that the search term is wrong: it is not "a function whose
only caller is a test" but **anything the project can point at when asked whether something is
done, that nothing in production touches** — a scorer, an event type, a schema, a baseline.

## 20. Immediate next actions

Ordered as of the **2026-08-12 evening (v2.2) re-inspection**. The v2.1 list
struck two already-complete actions and congratulated itself on the correction;
this pass found that **three more had completed and a fourth had been answered**
in the hours since. The pattern is now the plan's most reliable property, so treat
every unstruck action below as a claim to re-verify rather than a task to start.

1. ~~**`git init` and commit litharness-contracts**~~ — **DONE.** Branch `main`,
   3 commits, clean tree. The commit landed at 17:36 on 2026-08-12; the v2.1 edit
   that called this "the actual cheapest unblock" was written at 17:45.
   ~~**Remaining and real: it still has no LICENSE** (README says "License: TBD"),
   which is the follow-up the original action deferred to the owner.~~ —
   **Closed. Apache-2.0 landed 2026-08-13 in `32d9728`, which is the commit this
   plan's CI was already pinning**, so the claim was false in the same file that
   recorded its own contradiction. Only the contracts README still carried the
   "License: TBD" line, and it is corrected as of contracts 0.2.0 (§7's row,
   re-verified 2026-08-17). The owner's decision was made; the documents lagged it
   by four days, which is this action's own recorded pattern applied to itself.
   **Superseded by a bigger instance of the same defect, now also done:** LitHarness
   *itself* was untracked while carrying 15 modules and 119 passing tests, and §7's
   inventory audited every sibling's VCS status without having a row for the product
   repo. Now committed, with a `.gitattributes` that matters — `core.autocrlf=true`
   is global on this machine and plan/stage-0-decisions.md §1 records the near-miss
   it already caused in contracts.
   **Still outstanding:** RevisionPropagation is the last untracked project, and it is
   one file. ContinuityEvaluation (60 tests, Apache-2.0, live and frozen runner surfaces) and
   LongRangeContext (5 commits) are both git repositories — this action claimed otherwise for
   two revisions while §7 four hundred lines above said the opposite, which is the
   contradiction-in-place this document keeps producing about its own progress.
   *(Struck: "commit, license and tag BookWorldState" — done. 13 commits, clean
   tree, tag `v0.1.0`, Apache-2.0 LICENSE, pushed. The v1 plan carried this
   forward for a release cycle after it stopped being true.)*
2. ~~**Build the LitRPG deterministic rules pack in ContinuityEvaluation**~~ —
   **DONE.** Six checks green against the litrpg golden fixture with span-level exact
   set equality, mutation-tested for sensitivity, byte-identical across runs; CE 20 →
   42 tests. See [plan/litrpg-rules-pack.md](plan/litrpg-rules-pack.md) §0 for what
   was built and the two places the spec was wrong. Original scope, for the record:
   change the `contract_fixture_id` const gate to an enum, replace the
   three-branch predicate translator with a table-driven one that carries
   `world_rule`, `event` and `thread` records through, add the six checks under
   the reserved `detectors/rules/`, and parameterize the slice-gate test off its
   hardcoded 5/3/5 counts. Apply every correction in §8.2 and §8.3 — resync
   semantics, gold-and-level only, exact-set equality, mutation testing, and
   `note` stripping — or the gate goes green while proving nothing. While in
   there, fix the machine-bound `samefile("C:/DEV/litharness-contracts/schemas")`
   in the contract test.
3. **Extend litharness-contracts with 1.x minors** — **SCHEMA 1.1.0 SHIPPED; one
   item deferred.** Landed: `lease_holder`/`lease_expires_at`/`payload`/`priority` on
   `JobRecord`; `lock_kind`/`block_kind`/`block_payload`/`tombstoned`/
   `tombstone_reason` on `ManuscriptNode`; eight Conductor `EventType` members; and
   a new `conductor` module carrying `Directive`, `PolicyDecisionRecord`,
   `ExceptionRecord`, `DigestEntry` and `GateResult`. 25 → 30 schemas, 113 → 124
   tests. LitHarness's IR now projects losslessly instead of smuggling five fields
   through `metadata`, and LongRangeContext's exact `==0.1.0` pin is relaxed.

   **The rule the whole change obeys, learned by getting it wrong first:** a 1.1
   field defaults to `None`, never to a natural default. The serializer omits `None`
   and only `None`, so a field defaulting to `LockKind.NONE` or `{}` or `0` appends a
   key to *every artifact ever written* — changing the bytes of existing payloads and
   every content address derived from them. Four golden-fixture tests caught it. It is
   now a pinned, mutation-tested property, and any future minor must obey it.

   **Two things worth knowing before the next minor.** The `EventType` asymmetry is
   why this was blocking rather than cosmetic: unknown values *decode* to `UNKNOWN`,
   so adding a member is additive for readers — but construction goes through
   `EventType(value)` and raises, so a producer cannot emit a type the enum lacks.
   `DirectiveIngested` was unrepresentable, not merely unnamed. And bumping the wire
   version rebuilds the golden fixtures, which changes their SHA-256 and therefore
   every digest a consumer records — a 21-line, version-stamp-only diff this time,
   but budget for the consumer sweep.

   **Still open: the game-system schemas** (`CharacterSheet`, ledger event, quest
   state, status-block payload). Deliberately deferred rather than forgotten — §20.3
   says to shape `CharacterSheet` from action 2's working code, and that code is
   ContinuityEvaluation's rules pack, which is an *evaluator*: it replays a ledger
   backwards over a fixture and never constructs a sheet to hand forward. §8.4 makes
   the same point — the forward interface has no consumer until a generator exists to
   constrain. Shaping the sheet now would be the exact guess this action's own
   sequencing rule forbids.
4. **Scaffold LitHarness Stage 0** — **slices 1–6 done** (271 collected, 268 passing
   + 3 opt-in live, ruff clean,
   mypy strict clean). Slice 1, the model-free manuscript spine: canonical text and
   hashing, the IR with lock taxonomy and block payloads, immutable
   content-addressed revisions, bounded patch application with the mechanical veto
   list and a checked preservation guarantee, SQLite persistence with atomic
   revision+event commits, the transactional outbox, durable jobs with leases,
   restore-by-rebuild. Slice 2, the Conductor skeleton: idempotent tick, instance
   lease with single-leader enforcement, pluggable work selection, one bounded unit
   per tick, crash recovery, bounded retry, digest, and send-then-mark outbox
   dispatch. Ten open invariants settled and recorded in
   [plan/stage-0-decisions.md](plan/stage-0-decisions.md) rather than silently
   invented. **Not blocked on action 3 after all** — building the consumer first is
   what turned the lease, block-payload and event-type shapes from guesses into
   requirements. Slice 3, the provider adapters: all four built behind one contract,
   with a shared conformance suite, parsing verified against real captured CLI
   envelopes, and `LITHARNESS_ENV=test` enforced suite-wide so a test run provably
   cannot reach a paid provider.

   **Remaining, re-premised — the v2.2 pass found the blocker diagnosis wrong.**
   The claim was "directive ingestion, a real work-selection policy, and wiring the
   registry into a job handler — all three need subsystems that do not exist yet."
   That is true of one and a half of the three:

   - ~~**Wiring the registry into a job handler**~~ — **DONE (slice 4).** It was not
     blocked at all, and the thing actually standing in the way was a column no
     planning document named: `Job` and the `jobs` table carried `input_digest` — *a
     hash* — and no input, so a handler satisfying the `JobHandler` protocol received a
     job it could not reconstruct a prompt from. Migration 003 adds `payload`;
     `make_scene_draft_handler` is a closure satisfying `JobHandler` with zero
     Conductor changes. Generated text now passes a shape gate and becomes an accepted
     revision, with provenance recorded on both the accepted and the refused path.
     What *is* still a Stage 1 concern is where the prompt comes from — today the
     caller supplies it in the payload, because no planner derives it from a beat and
     no context packet grounds it. *(Both halves closed since: the template planner
     derives the prompt from a beat in slice 7, and slice 8 grounds it in an assembled
     context packet. `enqueue --prompt` remains for drafting one node by hand and is now
     the exception. See §17 Stage 1 for what the packet does and does not do.)*
   - **A real work-selection policy** is blocked on the plan graph and findings store
     as stated — but there was a second, purely local blocker the plan never named:
     `claim_next` hardcoded `ORDER BY rowid LIMIT 1`, so *no* ordering other than FIFO
     was expressible regardless of which subsystems exist. The `priority` column landed
     with slice 4 and is deliberately inert; a severity policy waits on a findings
     store, or it is a selector over a column with one value.
     **Both stated blockers are now gone** — the plan graph landed with slice 7 and the
     findings store with slice 9 (migration 013, severity indexed) — so `jobs.priority`
     can stop being inert whenever a policy wants it. Deliberately *not* done in slice 9:
     nothing yet generates repair work for a finding to prioritise, so a severity ordering
     would sort a queue whose entries all came from the same beat template. The column stays
     inert for one more reason rather than for the two it had.
     *(Struck: "the column stays inert". It has not been inert since the deterministic
     directive lane, and Stage 2's repair chain added two more bands — explicit direction at
     1000 + precedence, interpretive at 500 + precedence, repair at 100, evaluation at 80,
     scene drafts at 0. Three docstrings went on saying otherwise, including the one on the
     field itself and the one over `claim_next`, so a reader deriving claim order from the
     code's own prose got it wrong for any book with direction or repairs in flight. **What is
     genuinely still unused is the severity half**: a finding's severity does not reach the
     repair job it produces, so two repairs of very different urgency are claimed in insertion
     order. That is the accurate remaining gap, and it is smaller than the one recorded here.)*
   - ~~**Directive ingestion**~~ — **capture, atomic acceptance, deterministic explicit
     constraints, and bounded model interpretation DONE.** Contracts
     1.1.0 made `DirectiveIngested` representable, so directives are captured durably and
     drained as step 1 of the tick. An accepted `PlanProposal` can now record the immutable
     original words, their interpretation, the locked constraints produced, the new plan
     revision, and `PlanChanged` event in one transaction. The first producer is deliberately
     mechanical: a `constraint` or `veto` becomes a locked plan item
     with no model call (constraint text exact; veto words under an explicit veto label), and
     its high-priority unit runs before queued scene work. Scope is resolved only when one
     branch matches. A second producer now sends arc, tone, chapter, and premise notes through
     a strict, budgeted model proposal capped at 12 edits, then applies the same immutable-plan
     locks, target scope, current-head check, and atomic decision/event transaction. Invalid
     output leaves the directive in `RECEIVED`; control directives remain operator state.

   *(Also fixed in slice 4: `ProviderRegistry.reset_health()` documented "called at the
   start of a tick" and had no non-test caller, so a provider that recovered stayed
   marked dead for the process's life.)*

   **Slice 5 then closed §4.2's audit gap and §20.8.** Acceptance is now a recorded
   `PolicyDecision` — persisted, queryable by job and by resulting revision, carrying
   every gate that ran including the passing ones — which makes §19's "every mutation is
   attributable to a recorded policy decision" checkable rather than asserted. Two
   invariants are enforced at construction rather than documented: a blocking gate may
   not source its verdict from the model that produced the candidate (MirrorBench, and
   the substance of §20.8), and an uncalibrated craft gate may not block (§10.4). A veto
   no retry can fix escalates *before* the attempt budget is consulted, so a locked node
   reports as locked on the first try rather than as "attempts exhausted" on the fourth.

   **Slice 6 opened the loop, which had no entry.** Stage 1 is graded on "the mystery and
   litrpg fixture books regenerate from premise to accepted six-scene draft autonomously",
   and there was no code path anywhere — not in `src`, not in the CLI, not in the suite —
   that put either book into a store. Fifteen subcommands and none minted a revision;
   `enqueue` requires `--revision`; a revision id came only from committing a revision; and
   the only caller of `commit_revision` outside the store was the draft handler, which needs
   a job, which needs the id. Every operator verb in §4.3 acted on a book no command could
   create. Two things were in the way, and neither was a missing subsystem:

   - `Revision.from_contract` **cannot load a contracts-authored manuscript, by
     construction, and that is correct.** Contracts mints revision ids as UUID5; this
     package computes a sha256 content address; the classmethod asserts they match. Both
     fixtures fail it (`ef55d5adf2d9 != 1462725a-b14`, `907d923e5cd7 != cfb8482a-e84`). The
     assertion is the round-trip corruption check for artifacts *this system wrote*, so
     relaxing it to admit foreign ones would have deleted the check for the artifacts it
     exists to protect. `import_manuscript` rebuilds the id instead and keeps the source id
     as provenance; a test pins that `from_contract` still refuses the fixtures, because the
     cheap fix was the wrong one and would look identical from the outside.
   - **An imported book must have its scene prose cleared, and this is not a convenience.**
     `gate_draft` refuses any node that already carries content (§12: rewriting routes
     through a licensed complaint), so a fixture imported intact is a book with zero
     draftable scenes — it looks like a book and can take no work. Clearing is what
     "regenerate from premise" means mechanically. `--keep-content` exists for inspection
     and says on stdout that nothing is draftable.

   The import records a `PolicyDecision` and a `ManuscriptRevisionAccepted` event, so §19's
   attribution clause holds on the one path that creates a book. It carries **no gate
   results**: the only checks that run (a root-revision requirement, the per-node content
   hash) raise before a decision exists, and recording them as passed would be a gate that
   cannot fail — §8.3's own objection. **What this does not do:** it does not make Stage 1
   attemptable. The prompt still comes from the operator's `--enqueue --prompt`, there is
   still no planner, and the only blocking gate in the wired path is `shape.draft.v0`, so
   "accepted" still means "a string of plausible length". It removes the precondition; it
   closes no exit criterion.
   *(All three were closed later and are left standing as written, because the sequence is
   the point: slice 7 derived the prompt from a beat, slice 8 grounded it in a context
   packet, and slice 9 put a second blocking gate in the ladder so "accepted" now also means
   "nothing unresolved stands against it". See §17 Stage 1.)*

   **On the exit criterion, precisely:** the endurance property is *evidenced, not
   met.* `test_a_week_of_no_op_ticks_changes_nothing` runs the 2,016 ticks a week
   produces at the 5-minute cadence with injected time and proves state growth is
   bounded and accumulation idempotent. It does not prove a long-lived process
   survives a real week of scheduling, sleep, clock changes and file growth. Do not
   let "Stage 0 green" be reported as the stage being complete.
5. **Unblock the Game-System Engine's real dependency, then keep it at arm's
   length.** §8.1's "predicate registry extensions on BookWorldState" cannot begin
   as the code stands: `validate_record_references` takes no registry and calls
   `record.validate_predicate()` bare, defaulting to the closed 5-predicate
   `DEFAULT_PREDICATES`, and neither persistence adapter constructor accepts a
   registry — so a `game.*` assertion validates at the domain layer and is then
   rejected at commit time. The dependency-injection pattern is already idiomatic
   elsewhere in that codebase, making `validation.py` the single break in an
   otherwise complete chain — verified still true, and it is ~10 lines across 3 files
   with every new parameter defaulted, so no existing construction site changes.
   `PredicateDefinition` rejecting any predicate name without a dot, while every
   fixture predicate is bare (`status_snapshot`, `purchased`, `rule_hp_ceiling`), is
   also still true. *(Struck: "so a namespacing/mapping layer is required and someone
   must own that vocabulary" — §8.4 assigned that ownership to the game-mechanics
   pack, and ContinuityEvaluation now ships it. The mapping layer exists; it just
   does not live here.)*
   Hours of work, and **not** on the critical path — §8.4 routes around it, and this
   action advances no Stage exit criterion in §17. Do it when BookWorldState is being
   worked on for its own sake, not as LitHarness progress.
6. **Extend Narrative Planning beyond its bounded directive producer.** The safe
   provider-to-proposal lane now exists in LitHarness (§9.3); the remaining incubator work is
   a beat-sheet schema, template arc planner v0, foreshadow-payoff ledger, progression
   schedule, and gold outlines plus adversarial directive cases as its first benchmark.
   Note the ordering trap: the
   progression schedule references a level curve that only exists once the
   game-mechanics pack defines the sheet, and the litrpg fixture contains **no XP
   figure, no level curve and no milestones** (Rook reaches Level 4 because the
   System announces it), so cadence has nothing to attach to yet.
7. ~~**In RevisionBench, proceed with A3d and the M5 metric decomposition**~~ —
   **DONE, AND THE ANSWER IS IN. This is the most consequential correction in the
   v2.2 pass, because it is not a status update — it is the redirect this plan
   promised to obey.**
   A3d is built (it shipped under the name *A2d*; `docs/literature.md:220` titles the
   section "Detect-repair-verify (A3d)"), and the last unbuilt element — best-of-N
   repair ranked by minimal intervention — landed in `22a228d`. The M5 decomposition
   is done for the LitRPG stratum: `scripts/litrpg_eval.py` measures detection alone
   with no model calls, `scripts/litrpg_repair_run.py` measures repair given
   detection. Numbers are on disk: detection recall 0.987 / precision 0.883 with zero
   clean-chapter false positives; **recall 1.0 / precision 0.902 on model-written
   prose**, which also closes §8.3's "known gap" clause about templated-only
   validation. Repair resolved 61/63 and restored 55/63 with zero collateral chapters.

   **The verdict, verbatim from `docs/literature.md:215` — "Detection *was* the
   bottleneck… The 0.22 that looked like a repair problem was a detection problem."**
   This action's own stated rule was: *if the bottleneck is detection rather than
   repair, effort belongs in ContinuityEvaluation instead of the revision loop.* The
   condition is met. §17 Stage 2 and §6's priority order should be read through it —
   detector coverage outranks further work on the repair loop.

   **Acted on.** The first pass into CE built `repetition.exact.v1` plus the structural
   advisory/blocking partition described in §10.6, and — more usefully — established that
   eight of nine candidate craft proxies are not buildable on defect fixtures, with the
   reasons recorded there. The redirect is followed; what it found is that the next step
   is not another detector.
   *(Struck: "export current pairs to RevisionJudge" — done, 104 pairs on disk.
   The missing half is the verdict consumer; nothing reads `verdicts.jsonl`. Size
   the session before spending human attention: the 92-pair subjective set already
   gave a chance-spanning CI, and order-consistency filtering discards ~⅔ of panel
   coverage.)*
8. Keep MirrorBench independent; adopt its invariants (no self-report trust,
   order-randomization, frozen configs) in the Conductor's policy records. Verified
   zero coupling in both directions — MirrorBench work advances LitHarness by exactly
   nothing otherwise.
   **DONE as of slice 5a, and the re-premise is worth keeping visible.** This action
   said "doc-only until Stage 0 exists". Stage 0 existed and it was still not
   actionable, because the *target* did not — acting on it then meant inventing the
   record shape, the exact failure action 4 avoided by building the consumer first. It
   was gated by action 3, not by Stage 0. Contracts 1.1.0 shipped
   `PolicyDecisionRecord` with `GateResult.verdict_source`, and LitHarness now **refuses
   at construction** to build a blocking gate whose verdict comes from the generating
   model's report on its own output. The invariant is a raised exception, not a
   paragraph. Still outstanding from MirrorBench's set, and genuinely blocked until
   critics exist: the recorded pairing/order key for judge and panel comparisons.
   `policy_config_digest` covers the frozen-config half.
9. **Provider adapters** — see [plan/provider-adapters.md](plan/provider-adapters.md).
   Local Claude Code session by default, Codex as fallback, Ollama for iterative
   testing, plus the deterministic fake. Measured, with amendments this plan owes
   §2, §4.2, §15 and Stage 0's exit.
10. **Calibrate a craft proxy against revealed preference — ~~the new critical path for
    §1a~~ run at probe scale, and the label failed its own control (§56.3, 2026-08-17).**
    Replaces "author the §10.6 corpus", which is withdrawn as the gating item (see §10.6 —
    whose selected replacement is now also refused, so the corpus question is open again).
    Two pieces of engineering, in dependency order, both detailed in
    [plan/craft-corpus.md](plan/craft-corpus.md) §4:

    - **Build the labelled study set.** Full-corpus pass (all 47 shards, offline, behind the
      `corpus` extra), LitRPG-tagged, story-complete so chapter counts are real — the 2-shard
      probe truncates them because a story's chapters span shards. Label was to be
      `followers / total_views` — ~~measured at 9× spread p10→p90 and ρ = 0.44 against raw
      followers, so it discriminates without being popularity restated~~ **refuted at decile
      grain by its own control (§56.3)**: the deciles are recoverable from `followers` alone
      at AUC 0.814, and the denominator counts staying as well as discovery, so the label
      carries story size. A full-corpus successor is not forbidden, but it states its
      prose-blind covariate control before it runs (craft-corpus §4.1) — and until one
      survives that, this action is not a critical path, it is a refuted probe with a named
      successor design. Strata: tag set, era, length, cadence (computable from
      `release_datetime`), and author where possible — only 23 of 590 authors had ≥2 LitRPG
      stories in the probe, so within-author matching needs the full pass.
    - **Then test proxies against it, era control in the same pass.** Non-negotiable after
      `tricolon_rate`: a headline AUC without its control is meaningless, and that one would
      have shipped as this project's first working AI-tell detector.

    **The two highest-value additions are data acquisition, not modelling.** Per-chapter view
    counts give §1a.5's retention bar directly and move the label from story-level to
    chapter-level, which is the main validity weakness of everything above. Reader reviews are
    voluntary written judgments with scores — solicited judgment already collected at scale.
    Both are visible on RoyalRoad and neither is in this dataset.

    **A crawler for them was proposed and refused; do not re-propose it.** RoyalRoad's Terms
    of Service explicitly forbid automated access — "scrape, crawl, cache, spider" — unless
    expressly permitted, and the site sits behind bot protection that returns 403 to a plain
    `robots.txt` request, so a crawler that worked would be one that defeated that check.
    The open routes are, in order: ask RoyalRoad (permission is the sanctioned path the ToS
    itself names); ask whoever compiled `RoyalRoad-1.61M`, since that collection exists and is
    MIT-licensed; other platforms with per-chapter engagement, each needing its own ToS check
    and a genre-transfer argument; and §16's own serialization, which yields our retention
    curve with nobody's permission required. Reasoning in
    [plan/craft-corpus.md](plan/craft-corpus.md) §4.6.

    **Neither absence blocks this action.** §4.1 runs on the corpus already in hand under a
    licence that permits it. Chapter-level retention is a granularity improvement, and
    treating it as a prerequisite would reintroduce exactly the blocker §10.6's amendment
    removed.

    **And one standing constraint, recorded here because it is the way this direction fails.**
    §4.2's discriminator is a Goodhart magnet of exactly the kind §10.6 catalogues: it must
    never be exposed to the generation loop as an optimisation target or a prompt, must be
    retrained on a fresh held-out slice each cycle, and a passing score is
    necessary-and-insufficient. §1a.2 already measured what happens when a model optimises
    prose against a signal — it gets worse, and order-consistent judges preferred the human
    originals ~80% of the time.

11. **Give the writer an identity: a roster of named professionals, and a Director that casts
    one** — see [plan/writer-roster.md](plan/writer-roster.md), written 2026-08-20 before any
    code. **Operator directive:** directors select from writers they have access to; each writer
    carries a deep backstory; all are professionals; their interests are deep and spread across
    many subjects. **What is true today:** the drafter has no identity whatsoever — three
    sentences of system prompt (`application/planner.py:354`), no name, no career, no genre —
    and everything topical it knows arrives through the context packet. The Director's brief
    never reaches it.

    **The order to build it in, cheapest-first, and each step can kill the next.** (i)
    `domain/writers.py` plus `--writer`, off by default with no-writer as the control, the
    dossier landing in the drafting **system message** and never in the packet — the boundary
    `feedback` already observes, because a novelist's career is not a fact about the story.
    (ii) G0, the fake-provider wiring pilot: does the dossier reach the request and change its
    bytes, and what does it cost in tokens re-sent on every scene call. (iii) G1,
    `writer_distinctness.py` on a real local model — the prose-side twin of
    `director_distinctness.py`, five readings and all — because §89.1 measured four personas
    returning one byte-identical answer vector and an unchecked roster is that failure in a
    fourth costume. **If G1 reads `INDISTINCT`, that finding is the deliverable and the rest is
    not built.** (iv) G2, whether the *interest* binds rather than the name, via E6 "name the
    difference" plus the dossier-shuffle control `persona-reader-validity.md` §6 already
    specifies. (v) Director casting, which needs a fifth `DIRECTOR_KIND` and its own containment
    argument, and is deliberately last.

    **Two things to have read before starting.** The backstory is **deep in domain and shallow
    in demography** — `research/quality-measurement/personas.py` records that demographic
    persona description elicits stereotype performance, so a dossier says what a writer knows
    and has done professionally, never their age or hometown. And **a roster multiplies §61's α
    divisor**: `director-role.md` §4 divides confidence by N directors, and N directors × M
    writers is N×M candidate books. Fix the casting before the book is measured; do not pick the
    best of M afterwards.
