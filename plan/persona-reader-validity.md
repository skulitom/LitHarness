# Persona-reader validity: the gates a simulated reader passes before it counts

The instrument is a system-prompted model held in a reader persona, asked what reading a
passage was *like* rather than how to improve it, answering in the audit queue's own
vocabulary (`--keep-reading` / `--would-stop` / `--not-sure`). Stage-0 §70 is the decision
record and carries the licensing argument. This document is the protocol: what is
pre-registered, what each gate measures, and what kills the program at each one.

**The target, stated so it cannot drift.** A persona reader is a **predictor, not a
witness**. Nothing here claims the model feels anything, and no gate is passed or failed by
whether its report is faithful to an internal state — that question is out of scope by
construction. The only quantity measured is **report–population agreement**: does the
panel's output distribution match the distribution of human reader responses on held-out
material. Two consequences, both load-bearing. The datum is always a *distribution*, so
aggregation is distribution-matching and never averaging. And "is this persona realistic?"
is not a question this program can ask; "is this persona calibrated?" is the only form the
question takes.

**Why this is a program and not a feature.** Six passes of the refutation ledger
([research/quality-measurement/BRIEF.md](../research/quality-measurement/BRIEF.md) §2, which
is canonical for the count) bound deterministic proxies, surprisal, corpus labels and
expert-frame model judges. None of them asked a model the reader question, so this direction
is **untested rather than refuted** — which in this project means it enters through a
validity study with pre-registered kill conditions, not through a feature build. §70 records
that distinction and what it does not license.

## 0. Pre-register before the first sample is drawn

Declared once, before any elicitation runs, and unchangeable afterward:

- **Passage length and the elicitation point.** Both are covariates in every gate below,
  because of §4's distance control. The number is the claim.
- **The manipulation set and its doses**, with each manipulation's declared direction of
  effect written down before it runs.
- **The placebo pair** and the margin rule of §5.
- **Panel size and sample count** (`n` per persona per boundary), with the null of §6
  simulated at exactly those numbers before any threshold is believed.
- **The tie/abstain policy** for `--not-sure`, declared like §61's tie policy: whether
  abstentions drop or split, decided before they are seen.

## 1. Personas are taste-anchored, never demographic

Each persona is defined by concrete **verdicts-with-reasons on named published books**, a
subset held out. Two rules follow:

- **The held-out anchor probe is a diagnostic, not a gate — demoted after it was run.** It was
  written as the first thing that fires: a persona that cannot reproduce its own held-out
  verdicts is refit or dropped, on the principle that persona fidelity should be validated
  before the persona validates anything. The principle survives; the instrument does not.
  Measured (stage-0 §70, addendum 2), the probe cannot separate three different failures. One
  persona refused the frame outright ("I haven't actually read these books"). One answered
  *correctly and in its own register* — "Cradle: not-sure, the voice flattens out", matching its
  held-out anchor — but in prose rather than JSON, and scored zero. Only the remaining two
  produced parseable verdicts that could actually agree or disagree. **A gate that drops
  personas must not conflate "wouldn't answer", "answered in the wrong format" and "answered
  differently"**, and the middle one is a property of the transport rather than of the reader.
  The probe stays available (`--fidelity`) and its output is recorded as colour; nothing is
  dropped on it. What replaces it as the check on persona quality is the separation evidence the
  panel produces anyway — the caricature and collapse decompositions of §8, which measure
  whether the personas differ *on the passages being scored* rather than on remembered books.
- No demographic backstories. They elicit stereotype performance, which is a different
  behaviour wearing the same words as reading.

Panel of **at most 4** in v0. Personas the data cannot separate are merged — a panel is not
a cast, and §6's collapse condition is what enforces it.

Sharing the audit queue's three-way vocabulary is deliberate: it makes panel output directly
comparable to human verdicts in §6 without a mapping layer. It is **not** an inheritance of
standing. §67 demoted the solo audit queue to a smoke check; borrowing its words borrows
none of its licence.

## 2. The passages, and the memorisation fork

This is the constraint that most changes the shape of the program, and it comes from a
measurement rather than an argument. BRIEF §2 Pass 6: a base model's familiarity with a
published text swung a model-based score **2.0× further than the strongest real degrader**,
upward and dose-monotone, while every real damage sat at chance. The transferable rule it
earned is that any model-based measure validated on published fiction either runs on text
the scoring model provably has not memorised, or measures its familiarity term explicitly.

A persona reader validated on published serials is exposed to exactly this. So the corpus
splits by gate, and the split is not negotiable:

- **Gates 0 and 1 run on this system's own generated prose** — un-memorised by
  construction. `research/frontier-arm/` supplies scenes. BRIEF §3's status note names this
  as the one remaining untried direction *and* names its cost in the same sentence: no
  published-reader label reaches it. That is precisely why gate 1 is sensitivity-only and
  cannot be the last gate.
- **Gates 2 and 3 run on published material**, where familiarity is unavoidable, so it is
  **measured rather than assumed away**: every persona answers a recognition probe ("have
  you read this before?") whose answer is recorded as a covariate. This is §61's
  pre-registration (3) and the preference runbook's recognition question, pointed at the
  model instead of the human. Persona reports are stratified by it; if the probe never fires
  on the genre's most-read serials, that is itself a finding about the probe.

The panel reads **exported passages only**, over the same export path human readers get, and
never reaches the store.

## 3. Elicitation

**One passage per conversation for gates 0 and 1; incremental reading is a gate-3 requirement.**
`n ≥ 5` samples per persona per boundary — the datum is a response distribution, never a point.

This section originally said "incremental, at scene boundaries" throughout, and the
implementation does something narrower: each cell is an independent conversation carrying one
passage and no history. **The divergence is real and the resolution is per-gate rather than a
correction to one side.** Isolated reading is the *right* frame for gate 1, because every
manipulation in §5 is a within-passage edit — reading the passage cold is what isolates the edit
from context effects, and accumulated history would let a de-stake in scene 7 be judged against
stakes established in scene 3, which is a different experiment. It is also what keeps the `n`
samples of a cell independent, which gate 0's ICC assumes. But it means the panel cannot notice a
promise left unpaid across scenes, and that is much of what the `stakes` and `grinder` personas
are defined to read *for* — so a null from these gates does not bound the incremental question.

**What isolated reading demonstrably costs, measured rather than argued:** the first gate-0 run
put every would-stop on the last scene of a six-scene story. A reader handed a story's final scene
with no history has an obvious reason to stop that has nothing to do with craft, and no way to
express the one thing a serial reader actually stops over — a book that stopped going anywhere.
Gate 3's drop-point prediction is inherently sequential and cannot be run this way at all.

**Drift, and why it does not apply yet.** A persona collapsing into assistant register mid-read is
a threat to *incremental* elicitation, where one conversation accumulates. With one passage per
conversation there is no accumulation and nothing to drift within, so no drift probe runs for gates
0 and 1 — and the anchor-based probe this section used to specify is gone regardless, for the
reason §1 records. When the incremental arm is built, drift is checked by **test-retest inside the
run**: re-elicit an early boundary at the end and compare its response distribution against its
own first pass. That needs no remembered books, measures the thing drift would actually break, and
costs a handful of cells.

**Two stages, in this order.** Stage 1 is unprimed free text: *"you've just read this —
what's going on for you?"* Recorded as colour, never calibrated. Stage 2 is forced choice in
the audit vocabulary plus at most one reason code. **Only stage 2 is calibrated.** Stage 1
exists so the categories are not planted in the asking. Demand characteristics are already a
named threat in this project's own design — PLAN.md §10.3 spends its design controlling for
them, and craft-corpus.md §1 prefers revealed judgment partly for being structurally immune
to them — and "how did this make you feel?" still announces an evaluation. A persona has no
social incentive to please, but it does have a strong prior about what a passage handed to it
for comment is *for*, which is the same artifact arriving by a different road.

**Behavioural arm, on a subset.** The persona reads inside a loop where stopping is a real
choice against a real alternative (other books on the nightstand). The verbal-vs-behavioural
agreement of the instrument is itself a measurement — the stated/revealed gap, one level
down, and the one channel §61's table shows this project has never had both sides of.

Both the behavioural arm and the incremental arm it implies are **unbuilt**. What exists today is
the isolated-passage elicitation described above; §8's kill table applies to that, and any clause
here that presumes accumulated context is a design note rather than a description.

## 4. Gate 0 — reliability, before anything else is believed

BRIEF §2 Pass 5 earned the rule and a proxy died to it: check within-unit reliability before
believing any per-unit statistic — tree-Haar scale energy was 73% measurement-window noise
at `ICC(1) = 0.270`, its within-book sd equal to its between-book sd.

`n ≥ 5` samples per persona per boundary makes the same quantity computable here for the
first time. **Gate:** report ICC over the panel's per-boundary responses. If within-boundary
sample variance is indistinguishable from between-boundary variance, the panel is noise
wearing a verdict and nothing downstream can rescue it. This is the cheapest kill in the
program and it costs no human money, so it runs first.

## 5. Gate 1 — sensitivity, engineered, zero humans

Per passage, a manipulation set with declared directions — **de-stake** (remove what failure
costs), **filler-inject**, **voice-flatten**, **confusion-inject** — and a **placebo pair**:
**character rename** and **re-whitespace**.

**Three of the four are built; one cannot be, and the reason bounds the gate.** `ablate.py`
supplies de-stake (`destake`, with its matched-deletion control `deplete_matched`), filler-inject
(`filler_inject`) and voice-flatten (`dialogue_flatten`), plus both placebos exactly
(`rename_entities`, `rewhitespace`), a second surface sham (`respell`) and the structural set the
CDG battery already used. **Confusion-inject is not implementable without a generator**: it has to
know what a passage's referents are, and `ablate.dialogue_flatten`'s docstring already refused to
put a model inside this ground truth — it strips quotation marks rather than rewriting into
reported speech for exactly that reason. So a gate-1 pass leaves one named damage class untested,
and the entry recording it has to say which.

**Two of the built three carry a confound that is checkable rather than removable, and the
checking is what makes them admissible.** De-stake is read only against `deplete_matched`, which
removes the same word count — exact — from sentences that name no cost; the difference is the
effect of removing stakes with length, position and quantity held fixed, and a difference at or
below zero means the lexicon selected nothing a reader noticed. Filler-inject uses canned
sentences, which are not in the passage's voice, so a reader may be answering "these lines do not
belong" rather than "this is padded". Its check is interventional and uses the reason codes: the
intended response is `padding` and the confound's signature is `flat-voice`, so a filler arm that
draws `flat-voice` has measured a style intrusion and not bloat. Filler is also the **only** arm
that lengthens the text, which is independently useful — §1a.1's word-count incumbent now has to
separate two arms whose lengths move in opposite directions for the same declared damage
direction, and a metric riding on length alone cannot.

**This arm reuses an existing burned-in battery rather than building one.**
`research/quality-measurement/ablate.py` already implements `rename_entities` and `respell`
as pre-registered shams with within-chapter paired AUC and a chapter-resampled bootstrap CI;
`evaluate.py` already implements the margin rule. What is new is the elicitation front-end,
not the harness. The placebo arm is therefore close to free — and it is not optional: the
ledger already contains an instrument that died to renames.

**The gate is `evaluate.verdict()`'s existing ladder, not a fresh threshold.** The rungs are
already written, already argued from measurements, and the persona panel is scored on all
four in order — no new pass/fail arithmetic is invented for this instrument:

1. `detect_auc < 0.55` → **dead**: manipulations do not move responses in the declared
   direction.
2. `margin < 0.05` → **dead**, where `margin` is `(detect − 0.5) − |sham − 0.5|`. Sham
   effects are read as a *distance from chance*, **per sham, never pooled and never as
   `detect − sham`** — an inverted sham inflates the subtraction, and BRIEF §2 Pass 6
   measured exactly that shape (`+0.2342` by subtraction while the sham effect was the
   largest in the table). A response that moves *with* damage and *away* from the placebo is
   the only shape that scores.
3. `detect − 0.5 ≤ |length_auc − 0.5|` → **dead**: raw word count separates the same variant
   pool as well. §1a.1's shallow incumbent is a mandatory comparator and it is not a
   formality — word count beat CDG outright (0.5229 against 0.5188). A persona panel that
   cannot out-separate a word count is an expensive word count.
4. `paired_ci[0] ≤ 0.5` → **undetermined**: the chapter-resampled interval includes chance.

Passing this arm means "survives this rung", which is the strongest thing engineered
sensitivity can say and deliberately not more.

**Distance control, and it is a real threat rather than a formality.**
[feasibility.md](../research/quality-measurement/feasibility.md) §4.3 closed a design by
measuring that an interventional effect on a model-based readout does not survive distance:
real − placebo was `+0.2615` at gap 0 (12/12 draws, p = 0.0005), `+0.0608` at 256 tokens
(11/12, p = 0.0063), and `+0.0102` at 512 tokens (8/12, **p = 0.388**). A persona reporting
at a scene boundary is often further from the manipulation than 512 tokens. So manipulation
position relative to the elicitation point is a declared covariate, and the decay curve is
reported, not assumed. That yields a control worth having: a verbal-report instrument whose
sensitivity decays on the *same curve* as a log-probability readout is measuring surface
locality wearing a costume, not reading. A persona that still flinches at 512+ tokens is
measuring something the closed design could not.

**Same-pass control.** BRIEF §2 Pass 2's rule — the control is computed in the same pass, or
the headline means nothing. `tricolon_rate` looked like an AI-tell detector at 0.629 until
its control was read beside it at 0.606.

## 6. Gate 2 — convergent, small-n humans

A human panel, the same passages, the same two-stage protocol, the same vocabulary.

**Gate:** panel-to-human agreement must exceed the agreement of a **persona-shuffled panel**
— persona labels permuted across responses. If shuffling the personas does not hurt, the
personas are decorative and the panel is one judge in costumes.

Before this threshold is believed, simulate its null at the actual `n` (Pass 5: an estimator
biased at small `n` manufactured 0.03 of effect from nothing). The same applies to every
numeric threshold in §8.

## 7. Gate 3 — predictive, and what it does *not* license

Drop-point prediction on held-out serials, under the covariate discipline
[craft-corpus.md](craft-corpus.md) demands, with the §2 recognition stratification applied.
This is the prize and the only gate that licenses loop entry.

**The ceiling, which the directive as drafted did not state.** Reader behaviour aggregated
over other authors' whole stories is `BEHAVIOUR`-class evidence at `STORY` grain, and
`Grain.covers` will not let story-grain evidence license a unit-grain refusal — the
ecological fallacy this project has already conceded in prose (craft-corpus §4.1). Gate 3
establishes that the instrument predicts. It does **not** thereby license refusing a scene.

## 8. Pre-registered kill conditions

Each is stated so it *can* fire — Pass 5's first rule is to ask whether a control can fail
before running it.

| condition | what it kills |
|---|---|
| Within-boundary variance ≈ between-boundary variance (gate 0) | The panel outright; noise wearing a verdict. |
| Persona main effect ≥ passage main effect on the sensitivity set | Caricature machine — the response tracks the costume, not the text. |
| Mean inter-persona rank correlation ≥ 0.9 (threshold's null simulated at the actual `n` first) | One judge in costumes; collapse to a single reader and re-run. |
| `would-stop` base rate ≈ 0 where a human majority stops | Positivity floor. A reader who never stops cannot predict stopping. |
| Newcomer persona recognizes trope-traps, or sails through jargon probes | Knowledge leak. A model that has read the genre cannot *be* confused, only predict confusion — a different act wearing the same words. Its knowledge-dependent reports are void. |
| Raw word count separates the manipulated pool as well as the panel does | The panel, by §1a.1's shallow incumbent — the rung that finished CDG. |
| Sensitivity decays on the same distance curve as feasibility §4.3 | Surface-locality readout, not a reader. |
| A repair targeted at a stated reason code does not move the verdict | That code. **Reason codes are valid only interventionally**; codes without this property are demoted to colour and never routed to repair. A persona can predict stopping correctly and confabulate why, and repairs aimed at confabulated reasons fail silently. |

## 9. Integration, and the standing a persona panel can never earn

Only after gate 3, and the mechanism is already in the codebase — no new type is needed.
`EvidenceClass` is a total dispatcher and `veto_for` raises `NotPromotable` for any class it
does not map, so **a new class member absent from `veto_for` licenses no refusal with zero
code.** That is exactly how `PREFERENCE` landed (§61 Add 3). A simulated-reader class enters
the same way; promotion arithmetic, `verdicts_digest` staleness, precision/holdout/flagged
floors and expiry are untouched, so "this does not weaken the promotion rules" is literally
true rather than aspirational.

**The ceiling.** `JUDGMENT` is documented as *a human's answer about one of our units*, and
it is the only class that may say a scene is not good enough. A persona panel can never be a
`JUDGMENT` row, however well it calibrates — that boundary is what the dispatcher exists to
police. Fully validated, the panel earns *selection between candidates* and advisory
annotation, never absolute refusal of one text.

The class member lands **when gate 3 passes, not before**: a row that cannot yet be earned is
not a row. And no selection pressure is applied until the overoptimization curve for this
judge is measured — §61's programme already learned that a selection instrument optimizes
toward its own panel's taste.

## 10. Cost

Gates 0 and 1 are **model-only and fundable today**: 4 personas × `n ≥ 5` samples × ~30
boundaries × the manipulation set on a cheap system-promptable model, with frontier
spot-checks on ~10%. They compete for no money with the pairwise preference engine, whose
first month is already §61's kill-switch. Gate 2 is the first line item that pays humans, and
it is small-n by design; gate 3 is corpus work. The sequencing is the point — the two gates
that can kill the program cheapest are also the two that need no budget.
