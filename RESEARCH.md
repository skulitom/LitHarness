# LitHarness research overview

<!-- research-overview: ledger through §239; checked 2026-09-05 -->

This page is for someone opening the repository who wants to know what the research has
established, why each line of work was opened, and what matters now. It is a map of the
record, not the record: every result below points at the document that owns it (a decision
ledger entry, a `FINDINGS.md`, a committed results artifact), and when this page and that home
disagree, the home wins and this page is corrected. Nothing here is evidence
([EPISTEMIC_GOVERNANCE.md](research/quality-measurement/EPISTEMIC_GOVERNANCE.md)): a sentence
on this page can cite an artifact but cannot promote a claim, and no count is restated here
that another document owns (the refutation count is
[BRIEF.md](research/quality-measurement/BRIEF.md) §2's, the decision count is the ledger's, the
test count is the suite's).

`§N` is entry N of [plan/stage-0-decisions.md](plan/stage-0-decisions.md), the append-only
decision ledger; a section of any other document is written with that document's file name in
front of it (`BRIEF.md §2`, `PLAN.md §1a.3`). The **state** column uses the six research
states defined in EPISTEMIC_GOVERNANCE.md: `CONJECTURE`, `REGISTERED`, `OBSERVED`,
`SUPPORTED`, `REFUTED`, `QUALIFIED`. `SUPPORTED` means supported by the registered test and
nothing wider; nothing in this repository is `QUALIFIED`. A row marked `—` records a decision,
a census or an instrument defect rather than a claim.

Section 6 says how to update this page. `uv run python tools/research_overview.py` checks
every pointer on it and lists what has landed in the record since the marker above.

## 1. The question, and why it is hard

**The product objective** is fiction a defined audience voluntarily continues and recommends,
with no human in the production loop (§126; [PLAN.md](PLAN.md) §1a). The audience inside the
loop is simulated and only simulated (§97); real readers may never enter it, and
real-population data has one admissible role, grading the simulation rather than a book (§123).
Superhuman literary quality is the long-term goal, made falsifiable by §61 and demoted from the
daily objective by §126.

**The gap** is that every gate in the production loop is deterministic (shape, integrity,
contradiction, duplication, progression arithmetic) and none of them measures whether a scene
lands. PLAN.md §1a.3 lists the six things believed to keep a reader reading, dramatic function
first and line-level craft last, and PLAN.md §1a.1 names the hazard: the plan's incentive
gradient points at whatever is gateable. A book with flawless ledger arithmetic can still be
dead on the page.

**The search is for a reader architecture, not a metric** (§144): an LLM-based cognitive
system that perceives quality well enough to behave as a readership, validated by manipulation
and control rather than by agreement. A prompt is one interface to that capacity; multi-agent
mechanisms, costed readers and representation probes are others.
[plan/reader-architecture-program.md](plan/reader-architecture-program.md) owns the mechanism
families and the qualification boundary.

**Status line.** The production loop is real and drafts books end to end. No simulated reader
mechanism has earned the right to certify or steer prose. One mechanism, a reader whose
continuing costs it something, has moved under a story-level manipulation and held under
replication (§230); it satisfies, arguably, one of the ten evidence fields qualification
requires. That sentence is the whole of what the research has bought on the central question so far.

## 2. The constraints every experiment runs under

These are decisions, not findings, but they explain the shape of every result below. Each was
bought by a measurement recorded at its pointer.

- **No solicited human judgment, ever** (the scope axiom, §95): not hired readers, not the
  operator, not one blinded pair. Measurement is LLM-only. The operator's reads are defect
  harvests, never labels (§97.1, §148). Unpaid solicited judgment had measured out at two
  verdicts against 104 exported pairs before the axiom closed the channel (§61).
- **No corpus text crosses to the generation side** (RS1, §97.3), with one operator exception:
  openings placed by hand on a gitignored shelf may be shown to the writer as register, and are
  then out of measurement for any book that saw them (§196).
- **The verdict channel is shut** (§89, §97.4): no model rates, ranks or prefers anywhere a
  claim depends on it. Scores come from what a system does, computed in code; a reader's
  vocabulary is behavioural (continue, abandon, return).
- **No model ranks or selects among candidates** unless the log holds its containment (§61(5),
  §105.1, §107.5). Roles that generate need containment; roles that judge need a validity
  licence (§90).
- **No bar without the four attainability checks**: range at the real n, direction, an
  independent unit, a non-empty subgroup. §81, §85, §87 and §89 each record a bar declared over
  a quantity that could not do what it said. Distributions before bars; a pre-registered null is
  a result (§61).
- **Registration before spend.** The claim, controls, kill conditions and analysis rule are
  committed before the relevant result is observed, and every paid arm reads its transport
  failures before any verdict (§145, §222, §224). BRIEF.md §5 holds the rules a proposal must
  obey and BRIEF.md §6 the six questions asked before a number may refuse anything.
- **Raw reader answers never reach drafting or planning.** The live path is the editorial
  control plane in `src/litharness/application/editorial.py`: observations stay inert until
  their mechanism is qualified (§128, §129).
- **Agent prose is not evidence.** Plans, summaries and repeated agreement can point at an
  artifact and cannot add to it (EPISTEMIC_GOVERNANCE.md).

## 3. Where the record lives

| document | owns |
| --- | --- |
| [plan/stage-0-decisions.md](plan/stage-0-decisions.md) | every load-bearing decision and measurement, append-only, corrected in place with strikethrough; the `§N` pointers on this page |
| [research/quality-measurement/BRIEF.md](research/quality-measurement/BRIEF.md) | the refutation ledger and its count, the structural diagnosis, the substrates, and the rules a proposal must obey |
| [research/quality-measurement/EPISTEMIC_GOVERNANCE.md](research/quality-measurement/EPISTEMIC_GOVERNANCE.md) | the claim states, the evidence boundary, and claim records |
| [research/quality-measurement/RUNBOOK.md](research/quality-measurement/RUNBOOK.md) | the commands behind recorded runs and the operating constraints of the box |
| [plan/reader-architecture-program.md](plan/reader-architecture-program.md) | the mechanism families, where each stands, the production control boundary and the qualification contract |
| [plan/reader-architecture-proposal.md](plan/reader-architecture-proposal.md) | what the one moved mechanism would need to qualify, what it would feed, and what would withdraw it |
| `PREREG.md` and `FINDINGS.md` pairs under `research/` | one registered arm each: the design fixed before spend, and the reading in house form (the claim, the number beside it, the caveat travelling with it); raw records and results beside them |
| [research/quality-measurement/results/](research/quality-measurement/results/) | committed text-free result artifacts, keyed by registration digest |
| the `reader-read-*.md` and `serial-pilot-*.md` notes under `plan/` | the operator's reads (defect harvests) and the pilot records they were made on |
| [PLAN.md](PLAN.md) §1a, §17 and §19 | the objective, the roadmap by gates, and the operator-grade scorecard |

## 4. Results, by question

### 4.1 Can a statistic computed on the text measure its quality? No.

**Why it was opened.** The cheapest imaginable gate is a number computed on the prose. The
project tried seven passes of them, from surface counts to compression to a base model's
log-probabilities, each against a control computed in the same pass. Every one died to a
control, not to a bug.

| result | state | home |
| --- | --- | --- |
| Surface proxies against the golden defect fixtures: the cheapest repair that satisfies `progression_cost` is the disease it was built to catch; `scene_change_profile` ranks the fixture upside down, because record density measures annotation coverage and not scene function; voice and dialogue measures have no corpus to stand on | `REFUTED` | BRIEF.md §2 Pass 1 |
| Four instrumented metrics against thousands of published LitRPG chapters: `tricolon_rate` separates declared-AI 2025 chapters from pre-2023 prose, and undeclared 2025 chapters separate from the same baseline just as well. The metric detects the year, not the machine | `REFUTED` | BRIEF.md §2 Pass 2; §66 |
| Per-chapter comment counts recovered from the Wayback Machine track archive capture date, not reader response; the exposure-adjusted rescue sits below its own mechanical null | `REFUTED` | BRIEF.md §2 Pass 3 |
| Compression: seven gzip-family measures die to scene count, sampling coverage, seed swing, an LZ77 match-distance readout whose reversal control cannot fail, and window noise. Two repetition detectors survive because they claim repetition and not quality | `REFUTED` | §48, §49, §50; BRIEF.md §2 Pass 5 |
| Context Dependency Gain, a base model's own-prefix against foreign-prefix log-probability gain: detection at chance, and its pre-registered entity-rename sham moved it twice as far as the strongest damage, upward. Over published fiction it is a memorisation-release detector | `REFUTED` | §58; BRIEF.md §2 Pass 6; `research/quality-measurement/results/cdg.json` |

**What it changed.** The four instrumented metrics left the production page (§66), and the
calibration path that would have promoted them was found to admit a row whose true lower bound
was 0.566 (§59), then cut. The structural diagnosis (BRIEF.md §3) names what every dead proxy
shared: static, absolute and correlational, with every available label contaminated. The
method rules earned here are collected in section 4.9.

### 4.2 Can a model's verdict rank prose? The verdict channel is dead; the report channel is alive.

**Why it was opened.** If a model cannot be trusted to rate a passage, perhaps it can be
trusted to choose between two. Every design that asked for a preference was measured against
position, edited-ness and a placebo, and the question of *where* discrimination dies was asked
directly.

| result | state | home |
| --- | --- | --- |
| Raw model judges (RevisionBench): positional artifacts on roughly half the verdicts, and the order-consistent survivors preferred the human originals about four times in five. Asked to improve prose, models made it worse | `REFUTED` | BRIEF.md §2 Pass 4; PLAN.md §1a.2 |
| A persona held in a reader role and asked whether it would keep reading said yes on 195 of 196 un-memorised mid-book scenes. The absolute verdict has no variance; the pairwise form separates edited from unedited text, and its de-stake arm ran backwards | `REFUTED` | §70; BRIEF.md §3; [plan/persona-reader-validity.md](plan/persona-reader-validity.md) |
| The panel appeared to order human prose on an external label; the arm was void on its own positional precondition and its two sides differed 255x in views | `REFUTED` | §77, §77.1 |
| The panel weakly prefers a scene that kept its interiority over one that lost it (the interval spans indifference) and strongly prefers one that gained it, with length as the named confound; it is blind to a stat flatten | `OBSERVED` | §81, §85 |
| Simulated writer states (drunk, tripping, a tea placebo) do not move the register; the panel voided itself on all three arms | `REFUTED` | §83 |
| The incumbent judge is disqualified on three axioms of a pre-registered battery, and the battery as first written would have disqualified a genuinely good stochastic judge most of the time | `REFUTED` | §86.7 |
| A layer probe on a small model's internals adds nothing a surface counter does not already have; the report failure is real and the probe is not what shows it | `REFUTED` | §87 |
| Where discrimination dies: at the verdict token the answer distribution is 0.9998 position against 0.000214 text. The same model asked to name the single most salient difference clears every damage family while calling the placebo identical | `SUPPORTED` | §89, §89.4 |
| The readership prefers our listings to the market's best 15 pairs of 16, and 24 of 24 against the operator's own favourites, while reading a follower gradient off published blurbs at H = 0.935. It reads a stable signal and attends to the wrong one; six model-based instruments were blind to the defect the operator named and a corpus n-gram counter was not. §142's claim that the market was wrong is withdrawn | `OBSERVED` | §140, §141, §142, §143; [plan/reader-calibration.md](plan/reader-calibration.md) |
| The adversarial span tribunal measured the market cleanly (its gradient leg separated 8 of 8) and never read our listings: every call on that leg hit one weekly-limit error | `OBSERVED` | §145; [plan/blurb-tribunal-validity.md](plan/blurb-tribunal-validity.md) |
| An opening-parity panel took a paragraph-shuffled copy of our chapter over an anchor at the ordered copy's rate, so every ours-against-summit share it reported was surface | `REFUTED` | §195.5; [research/opening-parity/FINDINGS.md](research/opening-parity/FINDINGS.md) |

**What it changed.** Reader and Judge became two roles split by valence against location, and
neither is a signal alone (§90); a Director role was added that measures nothing (§91). The
only elicitation frame that survived is E6, name the difference, which reports a difference
and never a preference. The operator's redirection followed: the unit of search is the
mechanism, not the question wording (§144), and every mechanism validates on the follower
gradient before its reading of our text is believed.

### 4.3 Can a base model's probabilities read structure or taste? Structure yes, taste no.

**Why it was opened.** The force programme (§95;
[plan/force-program.md](plan/force-program.md)) stopped asking the model questions and measured
what a text does to a base model's predictive distribution, on local GPUs, under the scope
axiom.

| result | state | home |
| --- | --- | --- |
| Before any force had a number, the programme found more than a dozen defects in its own instrument: harness arithmetic, the inference layer, the transport, the thermal governor, and a length confound the corpus had carried since §79 | `—` | §95, §95.3 to §95.15 |
| F1's controls were vacuous and it returned a reading about the instrument; F2 scored the wrong token every time and its numbers are withdrawn | `—` | §95.11, §95.14; `research/quality-measurement/derived/README-f2-withdrawn.txt` |
| F3: a fiction's own earlier chapters make its later chapter more predictable than length-matched foreign prose, the advantage grows with more of the book, and it grows more in the real chapter order than reversed, on three checkpoints across two lineages. The most replicated positive finding in the repository, and it predicts nothing about the conversion label at the n the corpus can supply (the registered reading is insufficient n, not a refutation) | `SUPPORTED` | §98, §102 |
| F4, the surprisal field, is registered as a shape statistic with an external reading-time validation target, and has not run | `REGISTERED` | §99 |
| The interventional effect does not survive distance: a perturbation's log-probability signature is gone by 512 tokens | `OBSERVED` | [research/quality-measurement/feasibility.md](research/quality-measurement/feasibility.md) §4.3 |

**What it changed.** Representation-level readers are parked deliberately in the programme
table: F1, F2 and FX died in ways that will look like a working lens from the inside, and the
Messages API exposes no log-probabilities, so the family is GPU-only.

### 4.4 Can a simulated readership behave like one? This is the central track.

**Why it was opened.** The objective is measured on a simulated audience (§97, §126), so the
project needs a reader whose behaviour moves when the story changes and holds still when only
the surface does. Every instrument here is validated by manipulation: a damage arm read
against a matched control and a placebo, registered before spend.

| result | state | home |
| --- | --- | --- |
| A budgeted continuation reader needs a shelf of twenty own-generated books and the repository held one long enough; seated on a local model, every equivalence control failed, because the sizing table simulated twelve independent coins per session and the real reader committed to one allocation for a whole session. The correction was the unit, not the count | `OBSERVED` | §94, §94.3, §94.7; [plan/llm-reader-engagement.md](plan/llm-reader-engagement.md) |
| A reader put in front of a premise: the panel is not constant and position is real but smaller than the largest effect; the one arm that cleared the sham floor damaged sense as well as vocabulary and was withdrawn, leaving a null | `REFUTED` | §120; [plan/pitch-reader-validity.md](plan/pitch-reader-validity.md) |
| Feed continuation (`fcr.v0`): continuing costs a finite attention budget spent against a feed of rival books, with a cheaper skim. Three of its sizing numbers were replaced by measured ones before any call; its arms are the two costed-reader rows below | `REGISTERED` | §122 |
| The `readers` lanes in the production loop carry on four of four on every chapter and on every shuffled copy of it: both lanes read content, not order | `OBSERVED` | §198.2, §199.1; [research/quality-measurement/readers-order-control/FINDINGS.md](research/quality-measurement/readers-order-control/FINDINGS.md) |
| The reassembly instrument reads a chapter's order by rank correlation: the shelf anchors reassemble far above chance and our chapters sit inside the market's range | `OBSERVED` | §199.2; [research/quality-measurement/reassembly/FINDINGS.md](research/quality-measurement/reassembly/FINDINGS.md) |
| Order recovery does not separate the chapters the operator could not follow from the ones where he only named sentences | `OBSERVED` | §225; [research/quality-measurement/reassembly-reads/FINDINGS.md](research/quality-measurement/reassembly-reads/FINDINGS.md) |
| The anticipation probe (describe three futures, mark hope or dread) returns the same answer whatever is done to the passage: the arms' mean specificity spans 0.008 against a registered floor of 0.05, and the whitespace placebo moved it further than deleting the stakes did | `REFUTED` | §124, §227; [research/quality-measurement/anticipation-run/FINDINGS.md](research/quality-measurement/anticipation-run/FINDINGS.md); BRIEF.md §2 Pass 7 |
| The first costed-reader arm came back unreadable, one session below its scorable floor after a contiguous transport stop the instrument could not classify; what it did measure is that the reader's positional lean eats three quarters of the design | `OBSERVED` | §222, §224; [research/quality-measurement/cost-that-bites/FINDINGS.md](research/quality-measurement/cost-that-bites/FINDINGS.md) |
| A reader whose continuing costs it something reads a book less when that book's paragraph order is destroyed, and further than a whitespace placebo moves it; replicated with the permutation redrawn, inside the band the registration fixed. The first mechanism in this house to move with a story-level manipulation and hold under replication | `SUPPORTED` | §230; [research/quality-measurement/cost-that-bites/FINDINGS-v2.md](research/quality-measurement/cost-that-bites/FINDINGS-v2.md) and [FINDINGS-v3.md](research/quality-measurement/cost-that-bites/FINDINGS-v3.md) |
| The sim-readership backtest asks whether the readership, blind and stopped part-way, can post-dict which of two real Royal Road books the real readership stayed with. Every free slot is filled (thousands of divergent pairs, a conditional primary with calibrated type-I, a cutoff-clean set that is empty so recognition probes carry the whole memorisation defence); no paid call has been made | `REGISTERED` | §123; [research/sim-readership-backtest/FINDINGS.md](research/sim-readership-backtest/FINDINGS.md) |
| Correcting the simulated readership against what a real population did (the SYN-DIGITS reading): the distributional half is admissible and gated on a decision not yet taken; individual-level calibration is closed twice | `REGISTERED` | §106; [plan/sim-readership-calibration.md](plan/sim-readership-calibration.md) |
| Whether the sim predicts the real readership's continuation on a book it has never had readers for is registered against the release queue and waits for a posted chapter | `REGISTERED` | [research/launch-outsample/PREREG.md](research/launch-outsample/PREREG.md); §221 |

**What it means, and what it does not.** Three instruments designed to avoid the verdict channel
inherited saturation instead: a cooperative reader that can answer for free answers the same way
every time (BRIEF.md §2 Pass 7). The one that moved is the one whose reader had to give
something up to keep reading. What it established is deliberately narrow: one faculty, on the
loudest stimulus available, a whole-book shuffle. Qualification needs ten fields of evidence
and these arms satisfy one; the proposal that says what the rest would take is
[plan/reader-architecture-proposal.md](plan/reader-architecture-proposal.md), and it asks for
nothing that spends. The finding that outlasts the track is about substrate: the twenty-book
shelf caps the costed reader's power, nineteen operator reads cap order recovery, and the
instrument needs longer members than the pipeline drafts (BRIEF.md §3).

### 4.5 Does simulated-reader direction improve the writing? Nothing measurable yet.

**Why it was opened.** The point of a readership inside the loop is to steer the next chapter.
The channel was opened (§128) and ranked above every craft rule (§129) before its first number.

| result | state | home |
| --- | --- | --- |
| One steered redraft against one blind redraft: the whole range the treatment could have moved was spanned by drafting the same prompt twice. The draft is the unit of variance | `OBSERVED` | §133 |
| Four drafts a side: no effect of reader direction on continuation in either direction, and six of the eight drafts scored four of four. Continuation at its ceiling cannot rank candidates drawn from the same prompt, which is exactly where selection lives | `OBSERVED` | §134 |
| An agentic repair session against the fixed retry path: the same feasible commits at more than twice the calls; its higher gate-pass rate is an artifact of double-gating | `OBSERVED` | §105.5; [plan/variation-session.md](plan/variation-session.md) |
| Whether ten writers are one writer in ten hats: every pair reads distinct and the shuffle control does not clear, so the statistic cannot answer | `OBSERVED` | §137 |
| Instruction text was the thing nobody measured: two words of brief outweighed every rule in the prompt, a rule's affirmative half is what gets obeyed, and clauses added against the operator's named register defects moved one shape while the register stayed | `OBSERVED` | §135, §136, §138, §176 to §181, §187; [plan/agent-impact/REPORT.md](plan/agent-impact/REPORT.md) |
| A prose-input trial: plain house guidance crossed with factual scene-planning notes, four conditions over one frozen scene request, written up as a diagnostic; a single draw and an editorial reading can establish no treatment effect | `CONJECTURE` | [research/quality-measurement/prose-inputs/PREREG.md](research/quality-measurement/prose-inputs/PREREG.md) |

**What it changed.** The editorial control plane exists and is inert: a chapter-boundary panel
freezes versioned observations, one controller reduces a qualified panel to one of five
decisions, and only two of those may submit a scoped directive; the bundled mechanism is
`experimental` and cannot steer (the production control boundary in
plan/reader-architecture-program.md). On the writing side, the levers that did move register
were code at the seat rather than clauses: the exemplar shelf shown to the writer with the
reviser dropped (§196), the tells counter and the located rewrite pass (§199), and the concept
stage drawn before the listing (§197).

### 4.6 What is our prose like next to the market's? Code-only censuses, no model, no bar.

**Why it was opened.** The operator's reads named defects; each was turned into a counter run
over our shelf and the cached RoyalRoad shards in the same pass, with the genre split and the
era control as the validity arm. These are defect instruments and distributions, never readers
and never bars; any admission to a gate is the operator's.

| result | state | home |
| --- | --- | --- |
| Our scenes are separable from human chapters at AUC 1.0 by 24 surface counts, against a permuted null; the question answered is "is this ours", the one label the project owns with certainty | `OBSERVED` | §75; `research/quality-measurement/results/authorship-tells-controlled.json` |
| The first human read of a generated book: stats monotone with unresolved values, a body-part to interiority ratio of 4.56 to 1, the em dash carrying the AI signature almost alone. The em-dash ablation arm was later found to be a formatting artifact and withdrawn | `OBSERVED` | §74, §78 |
| Two of the operator's three register complaints belong to the genre and one is ours: the narrating-the-inference tell runs at roughly five times the LitRPG rate in our text; the institutional lean is not in our text; vocabulary friction is the genre's | `OBSERVED` | §156; `research/quality-measurement/results/register-census.json` |
| Our shelf writes twice the market's numbers and none of them are a quantity; the excess is on the calendar | `OBSERVED` | §162; [research/quality-measurement/number-context-results.md](research/quality-measurement/number-context-results.md) |
| Five regular tells run three to ten times the shelf's rate on every chapter. A located rewrite pass moved three families to the shelf's rate on its first draw; the long sentence (the shelf never writes past thirty-five words, ours run to ninety) is the residue | `OBSERVED` | §199 to §199.8; `src/litharness/domain/tells.py` |
| Chapter endings: our units never end on a question against the market's one in fifteen, and at chapter grain our last line is a system line every time against almost never | `OBSERVED` | §108.5; [research/quality-measurement/chapter-endings-census.md](research/quality-measurement/chapter-endings-census.md) |
| Levity beats: our chapters sit near the genre's 61st percentile, and a one-draw model locator over a chapter is only 0.54 reliable, so four draws per unit or population statistics only | `OBSERVED` | [research/quality-measurement/comic-beats-results.md](research/quality-measurement/comic-beats-results.md) |
| The market's progression cadence is late, bursty and half empty: a median of zero located events per thousand words, half the genre's chapters carrying none, and gaps essentially Poisson. "Constant and regular" is not what the market does | `OBSERVED` | §155.1; [research/quality-measurement/progression-cadence-results.md](research/quality-measurement/progression-cadence-results.md) |
| Two census instruments scored our own page contract at zero because they could not read our furniture; a second version of each reads it, and the shelf still writes no advancement, named capability or moving number | `OBSERVED` | §189, §190 |
| The summits open the same way and ours did none of it: who the person was before, the system arriving inside that, the chapter ending on a thing read or offered and unanswered. The anchors are close third with a reported mind | `OBSERVED` | §195.1; [research/opening-parity/FINDINGS.md](research/opening-parity/FINDINGS.md) |
| Status windows in the market's early chapters: two fields to a window, one field in fifteen at zero, no choice screens, and two thirds of the earliest chapters print nothing; ours printed eight fields twice with six at zero | `OBSERVED` | §201, §202; [research/quality-measurement/system-displays/FINDINGS.md](research/quality-measurement/system-displays/FINDINGS.md) |
| The fit census: declared shape by shape, the house vocabulary expresses about seven in ten of the market's furniture features and three of sixty whole stories; the gaps rank with the System's own voice first | `OBSERVED` | §217; [research/quality-measurement/system-fit/FINDINGS.md](research/quality-measurement/system-fit/FINDINGS.md) |
| Listing coordinator density: three of our listings sit above the market's maximum, and the a-priori fix (fewer demands) is refuted by arms already on disk | `OBSERVED` | §147.1 |
| Every code-only instrument runs over one book in one command and prints a scorecard whose honest column says why a row has no market number | `—` | §190; `plan/agent-impact/scorecards/` |

### 4.7 What breaks when the system writes at length? Measured on its own books.

**Why it was opened.** Book Zero (PLAN.md §17 Stage 3) was scheduled as a deliberately ugly
end-to-end draft whose failures would order the research. Every pilot since has been read the
same way: the store the run wrote is the measurement.

| result | state | home |
| --- | --- | --- |
| The first Book Zero on a small local model: scenes an order of magnitude too short, a ledger that never moves, a story-order bug past nine scenes | `OBSERVED` | §44 |
| On a model that can write, the dominant failure is whole-scene duplication, unrefused; the outline call is what removes it, and on the frontier provider the longest cross-scene repeat without an outline is seventeen words against 872 | `OBSERVED` | §52, §54, §57 |
| Forty-nine draws of one scene reproduced whichever status line was nearest to hand and computed no number; the progression clause was never the variable | `OBSERVED` | §56 |
| The context packet stops representing the book at about forty scenes: the fact list crowds out the story and the horizon shrinks as the book grows | `OBSERVED` | §56.4, §132 |
| A forged world reached the writer and neither planner, so the plan named nothing the page names; plan-first uptake went from none to complete once the planners were shown the world | `OBSERVED` | §107, §111; [research/quality-measurement/world-uptake.md](research/quality-measurement/world-uptake.md) |
| The one call that can settle a debt was never shown the promise ledger; shown it, the ledger began to settle | `OBSERVED` | §110; [research/quality-measurement/promise-ledger-settlement.md](research/quality-measurement/promise-ledger-settlement.md) |
| Every packet the system had ever built was built for no one: the world now says whose book it is, and the exception it grants that person survives the gate | `—` | §112; [research/quality-measurement/protagonist-results.md](research/quality-measurement/protagonist-results.md) |
| The genre's one unbreakable rule (the numbers go up, and the power is personal) was a declared fact nobody stood on: two of four worlds declared a ladder and no cast member stood on any | `OBSERVED` | §113, §114; [research/quality-measurement/numbers-go-up-results.md](research/quality-measurement/numbers-go-up-results.md) |
| Thirty worlds in a row were about paperwork and the instruction that made them was ours: every forged world carried the administrative word family and most named one in the premise; thirty-two worlds held no power anybody would want | `OBSERVED` | §116, §118 |
| Four entries aimed the progression beat and none asked whether it landed: seven scheduled beats existed on the whole shelf, and a scene told a quantity moves could return it unmoved and clear the ladder. The gate now asks for the change and never a direction | `OBSERVED` | §184 |
| Past chapter one for the first time under the general system, the economy moved on the page across a chapter boundary and the second chapter's second scene would not commit; the drafting loop had never written the page's gains and rises back as canon edges, so the sheet reader only ever saw the seed | `OBSERVED` | §232, §234, §236 |
| Concept-backed books now require narrative plans, wait for missing predecessor prose, and carry declared operating rules as protected context; each is an implementation control, not a quality claim | `—` | §237, §238, §239 |

**What it changed.** Almost everything under `src/litharness/` that is not plumbing: the
outline, the world Architect, the promise ledger, the protagonist and its exception, the
declared ladder, the general system layer (§203 to §213), the progression gate, the concept
stage. The pattern the ledger records is that the defect was in what a call was shown, not in
the model, and the measurement that licensed each build was a count taken before a line was
written.

### 4.8 What can the instruments be calibrated against? Less than it looks.

| result | state | home |
| --- | --- | --- |
| Unpaid solicited judgment: two verdicts against 104 exported pairs; then the scope axiom closed the channel for good | `—` | §61, §95; PLAN.md §1a.4 |
| The revealed-preference label (followers over views) does not separate prose: its top decile is recoverable from follower count alone, and matching the covariates is arithmetically impossible, since matching the denominator makes the numerator a perfect predictor | `REFUTED` | §56.3, §79 |
| The declared-AI label tracks the year; comment counts track archive capture date; Mother of Learning's reviews sit at a ceiling with no usable variance | `REFUTED` | BRIEF.md §2 Pass 2, Pass 3; BRIEF.md §4 |
| The only un-memorised substrate is this system's own generated prose, and it carries no reader label of any kind; that trade is the design constraint on every reader instrument | `—` | BRIEF.md §4 |
| The estimator behind the retired pairwise bar over-rejects when one cluster dimension is small and heterogeneous, dividing alpha by the candidate count lets the bootstrap seed decide certification, and a marginally better system cannot be demonstrated at any budget tested | `OBSERVED` | [research/preference-power/FINDINGS.md](research/preference-power/FINDINGS.md) |
| The register the market's professional selectors reward, read from publishers' catalogues rather than from prose | `—` | [research/market/publisher-taste-profile.md](research/market/publisher-taste-profile.md) |

### 4.9 Method rules the record earned

Each of these was paid for by an instrument that died to it, and each is cheap to apply before
the next one is designed.

- **Compute the control in the same pass**, and name the confound the measure is most likely
  detecting. The era control is what killed `tricolon_rate` (BRIEF.md §2; BRIEF.md §5).
- **Ask whether a control can fail** before running it: the compression asymmetry's reversal
  control was algebraically antisymmetric and passed on noise (§49); the surprisal field's
  formatting control went vacuous under the directive's own default (§99.1).
- **Simulate the null at your own n**, and check within-book reliability before believing any
  per-book statistic (§49, §73).
- **Read sham effects per sham** as distance from chance, never pooled and never as detect
  minus sham; an inverted sham inflates the margin (§58).
- **Position is measured, never assumed away**: both presentations of every pair, a declared
  band, and a void verdict outside it (§69, §77.1, §89, §120.3).
- **Store the integers, put the floor on the bound, and divide the confidence by the candidates
  tried** (§59, §61(5); BRIEF.md §6).
- **Size the batch against the reader actually seated**: simulate the positional lean you have
  measured, or say you have not measured one (§94.7, §222).
- **Read transport failures before any verdict**, and never buy a cell after seeing which way a
  number points (§145, §222, §224, §226).
- **Ask whether a cooperative reader can answer well every time**; if it can, the instrument has
  no variance in it, whatever it is about (§70, §199.1, §227).
- **Show that an instrument reads our own furniture** before its zero means anything (§189); a
  scorecard made of counts cannot be damage-tested at all (§193.1).
- **A metric reports a number, never a judgment; the cheapest repair that satisfies it must not
  be the disease; every deterministic gate is necessary and insufficient** (BRIEF.md §5).

## 5. Where things stand

**Established, narrowly.** A costed allocation reader moves under a whole-book shuffle and
holds under replication (§230). A base model's predictive distribution reads a book's structure
(§98, §102). The readership reads market performance off a listing (§141). Our prose is
separable from the market's by surface counts (§75) and differs from it on named, counted
defect families (section 4.6). Everything else on the central question is a registered null, a
refutation, or a decision.

**Registered and unspent.** The sim-readership backtest (§123) and the launch out-of-sample
prediction ([research/launch-outsample/PREREG.md](research/launch-outsample/PREREG.md)) both
wait on the operator's go; the surprisal field (§99) and the dossier-voice arm (§150.6) are
registered and unscheduled; the reader-sims brief
([plan/handoff-reader-sims.md](plan/handoff-reader-sims.md)) lists what the costed reader owes
next.

**Closed, and closed for a reason.** Solicited human judgment at every grain (§95); the verdict
channel (§89); individual-level sim calibration (§106); the anticipation probe (§227); every
static proxy in BRIEF.md §2. Representation-level readers are parked, not closed.

**The operator's open decisions** are recorded where they sit: the evaluator boundary's three
questions ([plan/handoff-evaluator-boundary.md](plan/handoff-evaluator-boundary.md)), the
status line's unheld columns (§201), and the ability magnitude (§114.6).

**What would change this page.** A mechanism reaching `QUALIFIED` through the
`reader-mechanism qualify` command; the costed reader moving under a manipulation quieter than
a whole-book shuffle; the backtest running; a chapter posted through the release queue and the
out-of-sample registration answering.

## 6. How to update this page

The page is meant to be updated whenever a result lands, and the checker is what keeps that
cheap:

```bash
uv run python tools/research_overview.py
```

It verifies that every `§N` on this page is a heading in the ledger, that every path exists in
the repository, and that every state is one of the six; then it lists the ledger entries
numbered above the marker at the top of this file and the `FINDINGS.md` and `PREREG.md` files
under `research/` this page does not mention. Those two lists are the update queue.
`tests/test_research_overview.py` runs the same pointer checks in the suite, so a stale pointer
fails the build rather than surviving as a claim with its evidence removed.

Rules for an edit:

1. **One row per result**, in the section whose question it answers, with the state, one
   sentence of finding, and the pointer to the home that owns the numbers. Write the why and
   the consequence in that section's prose, not in the row.
2. **Point, do not restate.** A headline figure may appear when it is the finding itself and
   the run is complete; a count another document owns never appears here.
3. **Correct in place** the way the ledger does: strike the sentence, write the correction
   beside it, and point to the entry that corrects it. A withdrawn result stays visible.
4. **State the smallest claim the artifacts warrant**, in the governance vocabulary. A result
   that survived its registered controls is `SUPPORTED` by that test and nothing wider; a
   registered kill firing is `REFUTED`; a census or a decision is `—`.
5. **Move the marker** at the top to the highest ledger entry triaged and today's date, then run
   the checker and the test.
