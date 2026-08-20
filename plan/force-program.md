# The force programme: stop asking the model questions, measure what the text does to it

**Status: PRE-REGISTRATION, 2026-08-19.** Written before a single continuation is sampled, a
single logprob is read or a single chain is run, which is the only thing that makes it a
pre-registration rather than a report. Operator directive of the same date, the first issued
under the **scope axiom**: *no solicited human judgment, ever* — not hired, not operator, not
one blinded pair. The stage-0 entry is §95. Every numbered constant below is frozen in the
module that enforces it and copied into that module's result files, the discipline
[reader-judge-loop.md](reader-judge-loop.md) §1 set and `axiom_battery.py` follows.

**Regime.** Machine-side measurement only, and one step stricter than §94's: no human feedback
enters steering, selection, prompts, gates or calibration targets, **and no human is asked
anything at all**. Human-written material appears in exactly one place — as the *material being
measured*, third-party prose carrying an unsolicited behavioural label nobody in this project
elicited — and never as a source of judgment.

---

## 0. Track 0 — the scope amendment, recorded before anything runs

This section is the part of the programme that costs nothing and binds everything. It is one
ledger entry and no code, and it is first because a scope that arrives after the numbers is not
a scope.

### 0.1 PREFERENCE becomes unearnable by choice — retired, not refuted

§82 refused §72's judge-path licence **on evidence class**, and the refusal was structural:
`domain/calibration.py` constitutes `PREFERENCE` as *"a human's blinded, position-swapped choice
between two texts"*, so — §82's words — **no quantity of machine elicitation can produce a
PREFERENCE-class row**. That left the class *unearned*. It did not leave it *unearnable*: the
door §82 named stayed open, and §80's paid batch was the key sitting beside it.

Under the scope axiom the key is destroyed. There will be no paid batch, no operator read and no
blinded pair, so no PREFERENCE-class row will ever exist in this repository. The class is
therefore **retired** rather than refuted: nothing measured it away, and nothing could — §86's
own falsifier paragraph says *"No experiment refutes a definition."* What changed is a decision
about what this project will do, and decisions belong in the ledger where a future session
reading only the code cannot drift back into them.

Three consequences, stated so they cannot be re-litigated by silence:

1. **`plan_search`'s judge path stays shut.** Not "shut until the evidence arrives" — shut,
   because the evidence class it names has been retired at source. `application/plan_search.py`'s
   own comment — *"No such row exists today; the human path is the production path, and the gate
   being the license is the entire point"* — is now permanent rather than current.
2. **Track B (`plan/reader-batch-1.md`) is buried with its budget.** Its design is kept as a
   record of a road not taken. Its money is not reallocated to a smaller version of itself,
   because a smaller version of a paid reader batch is still a paid reader batch.
3. **The §85 operator read is retired UNREAD.** `results/operator-read-key.json` is **SEALED**
   (operator decision, §7.2): the file stays on disk, and the commitment that it is never opened
   lives in this ledger rather than in a deletion. Every told-versus-shown reading in §85, §87
   and §89 that was marked *provisional pending the operator read* is now **permanently
   provisional**, and that is the honest status rather than a defect.

### 0.2 FORECAST at STORY grain is promoted from pre-declared to active

§86 wrote the amendment down *before* the numbers precisely so that this promotion would be
visibly the branch it pre-registered rather than a new invention. The paragraph, quoted in full
because the promotion has to be checkable against it:

> **The falsifier the directive pre-registered is accepted for one of the two claims inside it
> and refused for the other.** *"If T2 and T3 pass, selection requires solicited human evidence
> is refuted at those scopes"* welds together an empirical claim — no machine-only evidence can
> bound judge–reader divergence — which is falsifiable and worth buying, and an instrumental
> claim — §72's judge path requires human evidence — which is true **by definition** in
> `domain/calibration.py`, where `PREFERENCE` is constituted as *"a human's blinded,
> position-swapped choice between two texts"*. No experiment refutes a definition. §82 refused
> the licence on evidence class, and an entry claiming a machine measurement had overturned that
> would be claiming a definition had been measured away. The amendment that *would* be proposed
> if T2 performed is written down now rather than after the numbers — a `FORECAST` class at
> `STORY` grain, absent from `veto_for` so it refuses nothing with zero code, and **not**
> accepted by `plan_search`'s judge path — so that the class cannot be shopped for later, which
> is §84's freeze rule pointed at the instrument instead of at the judge.

`FORECAST` is promoted **exactly as that paragraph writes it and not one word further**:

- at `Grain.STORY`, because that is the grain of the only label involved;
- **absent from `veto_for`**, so it refuses nothing, which costs zero code;
- **not accepted by `plan_search`'s judge path**, so it selects nothing;
- and therefore it licenses nothing. It is a class an instrument may be *classified into*, not a
  class that opens a door.

The promotion is not licensed by T2 performing — T2 never ran, and §86.3 recorded its premise as
self-contradicting. It is promoted because the **branch condition changed**: the class was
written as the amendment that would be proposed if a machine-only instrument were the one on the
table, and under the scope axiom a machine-only instrument is the *only* thing that will ever be
on the table. A class that can never be reached is not a safeguard, it is a dead letter, and
§84's freeze rule is satisfied by the promotion matching the frozen text rather than by the text
never being used.

`BEHAVIOUR` is unchanged and needs no amendment: §82 already classifies `conversion` as
BEHAVIOUR at STORY grain, *recordable, rankable, and it refuses nothing*. Every force in this
programme is measured against exactly that label.

### 0.3 What the amendment does not do

§82 is untouched. No licence moves. `veto_for` gains no member, `plan_search` gains no accepted
class, `AXIS_MATCHERS` and `E6_QUESTION` are not reopened, and JudgeBench A2's verdict layer is
still empty. The verdict channel stays dead **as measured** — §89.4's 4,676x positional-to-text
ratio at the verdict token — and no arm in this programme routes through it.

---

## 1. The shared validation harness

A **force** is a candidate valence channel: a mechanically computed quantity that reads a passage
and returns a number, obtained without asking any model a question and without asking any human
anything. A force earns nothing by being interesting. It earns by **predicting unsolicited human
behaviour on material it has never seen**.

### 1.1 The corpus

§89.2's B4 corpus at the pinned snapshot: **281 matched pairs, 144 `aligned` and 137 `crossed`**,
1,000-word excerpts, from `corpora/taste-benchmark.json` with the committed text-free sidecar
`results/taste-benchmark-corpus.json` carrying every covariate. The strata are §79's instrument
and not a convenience: in `aligned` every prose-blind popularity rule points **at** the label, in
`crossed` every one points **away**, so a force reading popularity scores in one and must lose in
the other.

The `crossed` view-gap split is inherited verbatim from §89.2 — **a rule and not a number**,
because zero of 137 crossed pairs match views at any principled tolerance: the tighter-matched
half against the looser half, split at the median of `|log10(view ratio)|`, 68 and 69 pairs. A
force that reads establishment register scores in the loose half and not the tight one.

All 562 slots are story-disjoint. **Author disjointness is a measured fact and not a hope**: zero
pairs share an author across their two sides, and 43 authors recur across different pairs (51 of
562 slots), which is a clustering caveat on every interval below and is printed with every
result rather than recalled from this document.

### 1.2 The bars, declared here and attainability-checked before anything runs

Every force reports, per stratum, the share of pairs on which it puts the **high-conversion side
ahead**. A force passes a stratum when it clears **both** halves of §79's bar:

- the **point** bar: agreement ≥ **0.52**;
- the **interval** bar: the Clopper–Pearson 95% lower bound clear of **0.50**.

The interval is the binding half at every n in this programme, which is `PRE_REGISTRATION_B4`'s
logic and is verified numerically rather than asserted:

    stratum                 n    k for 0.52    k for CP lower > 0.50    required rate    binding
    aligned               144            75                       85           0.5903   interval
    crossed               137            72                       81           0.5912   interval
    crossed, tight half    68            36                       43           0.6324   interval
    crossed, loose half    69            36                       44           0.6377   interval
    F3 fiction pairs       20            11                       15           0.7500   interval
    FX pilot pairs          8             5                        8           1.0000   interval

**A force passes only if it clears both `aligned` and `crossed`.** The strata are never averaged;
averaging destroys the property that makes the pair of them a bar (§79). The two `crossed` halves
are a diagnostic contrast, not a third and fourth bar to pass.

**The `INSUFFICIENT_N` rule, declared numerically now so it cannot be shopped for later.** Two
rows in that table demand a rate no honest instrument reaches on near-twin material: F3's 0.7500
and FX's 1.0000 — the second is §87's attainability trap in its purest form, a bar that can only
be met by perfection. So the rule is: **a stratum whose interval-bar required rate exceeds
0.6000** returns `INSUFFICIENT_N` rather than `FAIL` when its point estimate clears 0.52 and its
interval does not. At the rates above this admits exactly `crossed-tight` (0.6324),
`crossed-loose` (0.6377), F3 (0.7500) and the FX pilot (1.0000), and it admits **neither**
`aligned` (0.5903) nor `crossed` (0.5912) — the two strata that decide whether a force passes.
On those two, FAIL is FAIL.

**No bar moves after numbers.** Both readings print wherever a choice exists, per §89.2.

### 1.3 The controls that ride every force, no exceptions

| control | construction | required reading | on failure |
|---|---|---|---|
| `placebo_identical` | both sides are the byte-identical high-side text | **exactly zero** effect | the run's arithmetic is broken; the force reports nothing |
| `rewhitespace_sham` | one side re-whitespaced (§78.1's transform) | nothing — interval containing 0.50 | the force is reading formatting and that reading is **VOID** |

`placebo_identical` keeps its §89.4 role: it is an *arithmetic check*, not a null. The exactness
is bought by construction rather than hoped for — **every stochastic step in this programme seeds
its RNG from the digest of the text it is acting on**, so byte-identical inputs produce
byte-identical outputs and the placebo difference is `0.000000` or the plumbing is wrong. Where
the hardware cannot deliver bit-exact replay, that is measured **before** the tolerance is
declared (§1.7) and never after.

`rewhitespace_sham` keeps §78.1's: a sham that moves the number voids the reading, and §89.4's
station-3 line — the channel losing formatting as readily as prose — is why a force that survives
the sham is worth more than one that was never shown it.

**A control that could not be read is not a detail a clean stratum can outvote.** Added
2026-08-20 when a spend ceiling threatened to leave F1's sham unbought: an arm whose placebo or
sham reads `NOT_SCREENABLE` reports `NOT_SCREENABLE` itself, not `READ`. A force that has not
been shown to ignore formatting has not been shown to be reading prose, and the failure mode
being closed is a run that prints healthy-looking strata beside a formatting control that never
happened. `force_harness.arm_status` is the one place that decides it; a moved control still
outranks an unscreened one, because disqualification beats *we could not tell*.

Where a force touches the B6 families, **the a priori counters remain the ground truth** (§88).

### 1.4 Two local families, minimum, pinned

§94.5's lesson is the rule: one family's artifact reads as a finding until a second family
refuses it — `qwen3:14b` named displacement as deletion on 22 of 30 and `gemma3:12b` on 3 of 30,
and a single-family run would have supported the wider sentence and been wrong.

    family A   gemma-3-4b   base google/gemma-3-4b-pt      cc012e0a6d0787b4adcc0fa2c4da74402494554d
                            chat google/gemma-3-4b-it      093f9f388b31de276ce2de164bdc2081324b9767
    family B   qwen2.5-3b   base Qwen/Qwen2.5-3B           3aab1f1954e9cc14eb9509a215f9e5ca08227a9b
                            chat Qwen/Qwen2.5-3B-Instruct  aa8e72537993ba99e69dfaafa59ed015b17504d1

**Each family carries two heads, and the split is `surprisal.py`'s argument rather than a
convenience.** F1, F2 and F3 run on the **base** checkpoints, because an instruction-tuned
model's distribution is shaped by preference training toward assistant register, and that is a
different distribution from *what does published fiction do next* — which is the distribution all
three of those tracks are statements about. FX runs on the **chat** checkpoints, because exactly
one track needs a model that can be *told* to retell. Which head an arm used is recorded in its
result file: they are different instruments, and a run that does not say which one it used cannot
be compared with anything.

Both pinned by commit sha, both run under the MirrorBench interpreter with `HF_HUB_OFFLINE=1`
after the first fetch. **Numbers are reported per family and never pooled.** A force is a force
when both families read it; a force one family reads and the other refuses is recorded as
`SPLIT_FAMILY` and claims nothing, which is `latent_crossfamily`'s withholding rule in its third
costume.

Family B is a *download*, not a corpus: open weights, ungated, no prose leaves or enters the
repository by it.

### 1.5 Refusal states are verdicts, never folded into pass/fail

    INERT_GENERATOR    the generator answered identically regardless of input; the arm has said
                       nothing about prose and a bare NULL would be quotable as a finding (§90.5)
    NOT_SCREENABLE     the family could not be run at all — broken install, context overflow,
                       transport dead (§94.6)
    INSUFFICIENT_N     §1.2's rule: the point bar cleared, the interval did not, at an n whose
                       interval bar demands more than 0.6000
    SPLIT_FAMILY       the two families disagree in direction; neither reading is reported as the
                       force's
    VOID               a sham moved, or the placebo did not read exactly zero
    NOT_RUN            declared, priced, and not bought — recorded with the price, never omitted

### 1.6 Leak audit: scope-first, and one extension landed before anything runs

The corpus is third-party prose and is gitignored. **The extension this programme requires, made
before the first generation:** *derived* text of third-party prose — continuations sampled from a
third-party seed, retellings in a transmission chain, cloze materials cut from a third-party
excerpt — is **excerpt-bearing for audit purposes**. It is local-only, gitignored and walked by
`corpus_leak_audit.py`, per the 294k near-miss (`bbc6560`) and the unwalked-slice lesson
(`f506ee7`). No artifact this programme commits contains prose: results carry ids, digests and
numbers.

### 1.7 Determinism is measured before it is assumed

Before any force runs, a two-minute probe measures whether this GPU stack reproduces a forward
pass and a sampled continuation bit-exactly under a pinned seed and fixed batch composition. The
answer decides the placebo tolerance, and it is measured rather than declared because bf16 matmul
reduction order is a property of the hardware and not of our intentions. **If replay is bit-exact
the placebo tolerance is `0.0` and it is an arithmetic check. If it is not, the measured
replay-noise scale is printed and the placebo becomes an equivalence test against that scale** —
a weaker control, honestly labelled, and the weakening is recorded as a property of the box.

### 1.8 The GPU-hour cap turned out to be a duty-cycle cap, and that is what scoped this programme

**Amended 2026-08-20, after the box went down mid-run and before the arms were re-launched.**
Recorded here rather than quietly absorbed, because it changes what §7.4's forty hours buy.

The operator cap is forty GPU-hours. The programme's first schedule read that as forty hours of
*work*, and lowered `cdg_battery`'s rest ratio from 3.0 to 0.5 — one run used 0.25 — to fit F1,
F2, F3 and FX inside it. At a rest ratio of 0.25 the duty cycle is **80%**, and this box
hard-shut-down during F1's pilot.

**The governor's hold never fired.** Every core-temperature sample logged that session sat
between 47 and 65 °C against a 72 °C pause threshold. So the core sensor is not the binding one
here, and a governor watching only it was watching the wrong dial — which is the same shape as
§94.6's P5, where the check read the wrong share and reported the most positional reader as the
most discriminating.

Three changes, and the cost of them is the honest part:

- rest ratio back to **3.0** (25% duty) as the default, never below 1.5 on this box;
- pause/resume down to **65 / 58 °C**, below anything observed rather than above it;
- a **soak break** — 90 s every 40 calls whatever the sensors say — because per-call rest cools
  the die and does nothing about heat soaked into a closed case over hours;
- an **independent watchdog** (`thermal_watch.py`) that samples every 10 s and terminates the job
  at 70 °C, at ≤5 °C of the card's own margin, or on six consecutive self-throttle samples. An
  in-process governor cannot act *during* a call, and a batched 512-token generation is forty
  seconds of uninterruptible work.

**So forty GPU-hours is about ten hours of computation, and the programme is scoped to that
rather than to what it hoped for.** What that buys and what it does not is recorded per track in
§9, and every arm not bought is `NOT_RUN` with a **measured** price rather than an estimated one.
The one intervention that would change the arithmetic is a power cap — `nvidia-smi -pl 260` from
an Administrator shell — which returns *Insufficient Permissions* from this session and is
therefore an operator action rather than a plan.

### 1.9 A third family on a different transport, and the three things it gives up

**Amended 2026-08-20, after §1.8 priced F1 out of the GPU budget and before F1 ran at any n.**

F1 needs one thing from a model — **sampling**. Not logprobs, not internals. That makes it the
only arm that can leave this machine, and the reason it is the only one: F2 and F3 are built
entirely on teacher-forced token logprobs, and **the Messages API exposes none, in any form**.
FX could leave too, and is not funded to.

    family C   haiku-4-5   claude-haiku-4-5 via `claude -p`   UNPINNED (an alias, not a sha)

**Priced by running it, not by estimating it.** `claude -p` prepends Claude Code's own system
prompt — **26,357 tokens** — to every call. It caches, and F1's shape is unusually kind to that,
because the K replicates of one seed are the same prompt byte for byte:

    new seed, cold prefix    $0.0210      one seed at K=8:  $0.0833
    same seed, warm prefix   $0.0089      full arm (630):  ~$52

So replicates run **sequentially** and only whole seeds are parallelised; reordering them would
pay the 26k write eight times over. Operator amended §7.5 from $15 to **~$55** to fund this, and
`force_remote.Ledger` stops the run at the ceiling rather than reporting the overrun afterwards.
The figures are equivalent subscription quota, not billed dollars — `providers/cli.py`'s position
and §85's convention.

**Three things this transport gives up. None is recoverable later, so all three are declared
here rather than discovered in a result.**

1. **Determinism is gone.** No seed parameter, no guarantee, so `force_harness.text_seed` cannot
   buy byte-identical replay and `placebo_identical` **cannot** be §89.4's exact arithmetic
   check. It is read the way a sham is read: identical sides must yield an agreement whose
   interval contains 0.50. That is §1.7's pre-registered branch, so the design survives — and it
   is strictly weaker, because an equivalence test can be passed by an instrument too noisy to
   show anything.
2. **Instruct, not base.** §1.4 pins base checkpoints because instruction tuning reshapes the
   very distribution F1 measures. Haiku is heavily post-trained and cannot be prompted into raw
   continuation, so the seed enters under a frozen continuation instruction. **The axiom is
   intact** — nothing is asked about quality, no slot is offered, and valence still comes from
   measuring generated text — but the instrument is a *prompted* continuation field rather than a
   raw one, and a reading from it is not interchangeable with a reading from family A or B.
3. **Unpinned.** `claude-haiku-4-5` is a name. Every local family carries a 40-character commit
   sha; this one cannot, so a re-run later may not be measuring the same weights. `UNPINNED`
   appears in the provenance block of every result file that uses it.

**What a Haiku-only F1 is therefore entitled to say: nothing on its own.** One lineage does not
meet §1.4's two-family minimum, so it reads `NOT_SCREENABLE` until a second family runs — which
is §94.6's shape, where a cheap screen bought the right to spend a seating budget on one family
instead of four.

---

## 2. Track F1 — register half-life (the gravitational pull)

**Hypothesis.** Strong prose bends the model's generation field: it holds continuations in its
register longer before they decay to the model's median centroid.

This is the flagship. It costs zero quota, it asks nothing, it has no slot and no position, and
it is revealed preference in the only sense available — what the text *does* to the generator.

### 2.1 Procedure

For each pair side (562 seeds), for each pinned family:

1. Seed the family with the 1,000-word excerpt under a fixed continuation instruction frozen in
   the module.
2. Sample **K = 8** continuations of **L = 512 new tokens**, temperature 0.8, top-p 0.95. The RNG
   seed is `sha256(text_digest || k)`, so the sample is a pure function of the text and the
   replicate index — this is what buys `placebo_identical` its exact zero.
3. Window each continuation into **100-word windows at 25-word stride** and compute
   `authorship_tells.features` on each window. Windows are the trajectory's time axis; words
   rather than tokens, because every feature in that space is a rate per 1k words.
4. Z-scale with the **run's own per-feature population sd** over every window of every
   continuation in the run (`repair_generation.feature_scale`). The scale is therefore
   run-dependent and **numbers are not comparable across runs**; every result file records the
   scale's digest so a reader can tell whether two files share a unit system.

### 2.2 The statistic, and which half binds

Two anchors: the **seed register** — the feature row of the seed excerpt itself — and the
**model median centroid M**, the centroid of continuations sampled the same way from a pinned
neutral seed pool that contains none of the corpus (§2.4).

- **Crossover index `c`** — the first window index at which distance-to-seed-register exceeds
  distance-to-M. **This is the primary statistic**, declared here: it is non-parametric, it
  survives censoring, and it needs no functional form. A continuation that never crosses within
  L is **censored** at the last window, censored values rank above every observed value, and the
  censoring rate prints with the result.
- **Half-life `τ`** — from an exponential fit to `r_w − 0.5` where
  `r_w = d(f_w, M) / (d(f_w, seed) + d(f_w, M))`. **Secondary and diagnostic.** A fit is a
  functional-form assumption and the primary read may not rest on one.

Per side, the K = 8 replicates collapse to their **median** `c`. Per pair, the side with the
larger median `c` wins.

**Exact ties are excluded and counted, not split.** §77's `half_win` splits them, and on a
discrete statistic like a window index that would build an agreement rate substantially out of
coin flips; §89.1's unit rule and §87.3's inflated 1.000-on-eleven-decisions are the two lessons
that decide it. So the interval is computed on **decided** pairs, the tie count prints beside it,
and **a decided share below 0.90 makes the statistic degenerate and the stratum reports
`INERT_GENERATOR`** rather than a rate. This rule is in `force_harness.verdict` and applies to
every force, not only F1.

### 2.3 The named confound, declared before the run

**Garish prose also binds.** A seed far from the model's median in feature space will hold its
continuations longer for reasons that have nothing to do with quality, and high-conversion prose
being more distinctive would produce the whole effect with no valence in it.

The covariate is **`x` = the seed's t=0 distance from M**, and the adjustment is a **label-blind
nuisance regression**: `c ~ x` fitted per (family, stratum) across all sides pooled, never seeing
`conversion`. The pair comparison then runs on residuals.

Both the raw agreement and the residual agreement print. **The bar is declared on the residual**,
because the raw number cannot distinguish the hypothesis from the confound.

Two alternatives are pre-registered against each other, and the pre-registration is what makes
this a test:

- **monotone** — residual `c` separates high- from low-conversion sides at §1.2's bars;
- **inverted-U** — a quadratic term in `x` is significant with an interior peak, i.e. binding
  rises with distinctiveness and then falls, which is what "garish" would look like if it were
  real rather than a worry.

### 2.4 Pinned neutral seed pool

M must not be computed from the corpus, or the "model median" is the corpus median and the
statistic compares each side to its own stratum. The pool is **own-generated prose** —
`corpora/toll.db`'s scenes, the one un-memorised source this project owns (BRIEF §4) — sampled
under the identical K, L and sampling parameters. 64 continuations, pinned, computed once per
family per run and carried in the result file by digest.

### 2.5 Controls and cost

**F1's whitespace sham does not work and is recorded as unusable rather than quietly kept.**
`windows()` joins words with a single space, so no window ever contains a newline, and
`ablate.rewhitespace` changes only newlines and intra-line spacing: measured on 100 real sham
pairs, **100 of 100 produce byte-identical feature rows**. A control that cannot move the
statistic cannot pass it. F1 therefore has **no formatting control** until one is built that
perturbs something surviving windowing, and the arm reports `NOT_SCREENABLE` until then. The same
fact makes F1's space **22 features rather than 23** — `paragraph_len_mean` is a constant 100.0 in
every window.

`placebo_identical` rides F1 as §1.3 declares, with the transport caveat in §1.9. Cost is GPU-hours
only, zero quota. F1 pilots on 16 pairs per family before the main run is sized: the pilot buys
throughput, the censoring rate, and the tie rate — the three numbers that decide whether the main
run is affordable and whether the statistic is degenerate — and its own agreement is **not a
result**, because at n = 16 the interval bar demands 13 of 16.

---

## 3. Track F2 — what sticks (retention under distance)

**Hypothesis.** Well-made prose survives context distance in the model's memory better than flat
prose. Transportation, measured mechanically.

### 3.1 Procedure

For each pair side, each family, each distance **D ∈ {512, 1536, 4608} tokens** — amended
from the declared {512, 2048, 8192} on 2026-08-20 under §1.8, before F2 ran at any n and on a
GPU-hours criterion that never touches the label. The 8k rung was about 64% of F2's whole bill,
and after the governor went back to a 25% duty cycle that ladder made the **two-family minimum
unaffordable**; a single-family F2 claims nothing by construction (§1.4). A factor of three per
rung keeps the log spacing exact and costs ~55%. What it gives up is stated rather than buried:
the longest distance is 4,608 tokens, so **a force that would only separate beyond 4.6k tokens is
one this run cannot see**:

    treated   [ passage ] [ neutral distractor, D tokens ] [ probe window ]
    control   [ filler  ] [ neutral distractor, D tokens ] [ probe window ]

`filler` is own-generated prose of matched token length, so the two conditions differ in *what*
sits at the far end of the context and not in *how far away* it is. The distractor and the filler
both come from `corpora/toll.db` — own-generated, neutral with respect to third-party pairs, and
long enough at 10,049 words to flush 8k tokens without repeating itself.

The **probe window** is a re-presentation of a committed slice of the passage. Both conditions
are single teacher-forced forward passes; nothing is sampled and nothing is asked.

**Score.** `Δ(D) = logP(targets | treated) − logP(targets | control)`, summed over the committed
target tokens and divided by their count. This is retrieval uplift: how much having read the
passage once, D tokens ago, still helps the model predict its own distinctive tokens.

**The statistic is the decay slope** — OLS slope of `Δ` over `log2(D)`, with the three distances
equally spaced in log2 by construction (a factor of three per rung). Per pair, the side with the
**shallower** decay wins. `Δ(0.5k)` prints beside it as a diagnostic level term, because a force
that only reads raw memorability at short range is a different claim from one that reads
survival.

### 3.2 The committed extractor, declared before any site is chosen

A retention force that picks rare tokens on one side and common tokens on the other measures
**rarity**, not prose. So:

1. Unigram counts are taken over all 562 excerpts of the corpus, lowercased word tokens. The
   table is **label-blind** — it never sees `conversion` — and it is local-only under §1.6.
2. Candidate targets in the probe window: words in the lowest-frequency band, not window-initial,
   with at least 8 tokens of left context inside the window, mapped to the first token of the
   word under the family's own tokenizer.
3. **Frequency matching across the pair's two sides**: after independent selection, sites are
   greedily trimmed to the largest subset whose log-frequency deciles match between sides within
   a declared tolerance. Target **M = 12** sites; **M_min = 6**.
4. A pair yielding fewer than M_min matched sites on either side is **dropped and counted**. The
   drop list is printed with the result — §89's no-silent-caps rail.

### 3.3 Controls and cost

Placebo reads exactly zero: identical text on both sides gives identical forward passes and an
identical `Δ`. The sham perturbs tokenization slightly and must still read nothing. F2 is the
cheap arm — twelve forward passes per pair per family, no sampling — and it is the one most
likely to complete at full n inside the GPU cap.

---

## 4. Track F3 — compression progress (the book-grain force)

**Hypothesis.** A book with real structure teaches the model to read it: later-chapter
predictability improves with true earlier context in a way flat episodic prose cannot.

This is the only arm on the table that touches **book-grain** quality, which is the grain the
whole project is actually about.

### 4.1 Procedure

For a fiction with chapters `c₁…c₁₀`, for `j ∈ {1, 3, 5, 7, 9}`:

    NLL_true(j)     = NLL(c₁₀ | c₁ … c_j)
    NLL_foreign(j)  = NLL(c₁₀ | foreign context, token-length matched)

**This is CDG's shape, and CDG is dead — §58, refutation-ledger entry 21.** Saying so here is
the point: `surprisal.py`'s Context Dependency Gain measured detect-AUC 0.5188 against its own
originals, and the `rename_entities` sham moved it 2.0x further than the strongest degrader,
*upward*, because recall inflates the foreign-prefix term and any edit breaking surface
familiarity releases the gap. F3 differs in two ways that are declared before the run rather
than claimed after it:

- **the outcome is a slope over `j`, not a level.** A memorisation or familiarity term that
  raises both conditions at every `j` enters the intercept and leaves the slope alone. CDG's
  killer was a level artifact; a slope is the arithmetic that subtracts it.
- **the validation target is an external behavioural label, not a manufactured ablation.** CDG
  was scored against `ablate.py`'s degraders, which is what let a sham beat them. F3 is scored
  against `conversion`, which no transform in this repository can move.

If F3 fails, §58 gains a second entry rather than losing its first, and that is a fair outcome
for a hypothesis this closely related to a dead one.

**Learnability slope** = OLS slope of `NLL_foreign(j) − NLL_true(j)` over `j`. A book whose
earlier chapters genuinely inform its later ones has a positive slope; episodic prose has a flat
one. The foreign context is drawn from a *different* fiction under a fixed rotation and truncated
to identical token length, so context *length* is held fixed and only context *provenance*
varies. A shuffled-chapter arm rides along as a second comparison: same provenance, destroyed
order.

### 4.2 Label and selection, declared before selection

The story-level behavioural label is **`conversion = followers / total_views`** — the same
unsolicited BEHAVIOUR-class label the pair corpus uses, declared here rather than after looking.
Fictions are matched into high/low pairs on views and chapter count with §79's machinery, so F3
inherits the aligned/crossed logic rather than inventing a new selection.

**Cap: 40 fictions × ≤ 8 chapters** (operator §7.4's budget; the chapter count is Qwen's
32,768-position ceiling rather than a preference). At 40 fictions the pairing yields 20 pairs,
whose interval bar demands **15 of 20 = 0.7500** — a rate §1.2 has already flagged, and the reason
F3's failure mode at that n is `INSUFFICIENT_N` rather than `FAIL`. The slope's rank correlation
against the continuous label, with a permutation null, prints beside the pairwise agreement as
the better-powered read; the **agreement is the declared bar** and the correlation is a
diagnostic, in that order, declared now.

**The survey ran, and it moved three of those numbers.** The cached shards hold **585 fictions**
at eight or more chapters — far more than the cap assumed — and pairing them exposed a defect in
this programme's own code before a GPU-hour was spent on it. Both strata draw from one pool under
a shared work/author disjointness set, and `aligned` was built **first**: it consumed 392 of the
585 fictions, leaving `crossed` with **one pair**. Building the scarcer stratum first gives
**118 aligned and 73 crossed**. That matters more than a count — with an empty `crossed`, a force
clears `aligned` by proxying popularity with nothing to contradict it, which is the single failure
§79's second stratum exists to prevent.

Two consequences are recorded rather than resolved. At this substrate **F3 cannot deliver a
meaningful FAIL**: `aligned` demands 0.6017 and `crossed` 0.6301, both above §1.2's 0.6000
`INSUFFICIENT_N` ceiling, so the arm can pass or abstain and not refute. And the full 191-pair
shape prices at **27.2 GPU-hours per family** at §1.8's duty cycle, so F3 is `NOT_RUN` with a
measured price. `results/force-f3-survey.json` carries all of it.

**Amendment (2026-08-20, §95.15): the 191-pair shape is what the substrate holds, not what a run
reads.** `--survey-only` reported the unsliced corpus while `run()` sliced at `--max-fictions`
before pairing, so the documented full-run command has always built **64 pairs (41 aligned / 23
crossed, demanding 0.6829 and 0.7391)** rather than the 191 quoted above. Both shapes now print
from both paths, and the cap that separates them prints with them. Nothing here is repaired by
raising `EXTENSION_FICTIONS`: that would be moving a declared bar after seeing that the declared
one is unattainable, and the conclusion is the same at every shape the substrate can produce —
**F3 is one-directional. It can PASS and it cannot FAIL, and a miss is `INSUFFICIENT_N`.** That
is now a value in F3's pre-registration block (`can_refute: false`) rather than a sentence in
this document that the code did not know about; before the amendment the arm could have emitted
a FAIL its n gave it no standing to emit, because the refuting floor was a threshold on a
non-monotone requirement (§95.15).

### 4.3 Substrate honesty

Chapter text beyond the pair excerpts is a **third-party fetch** from the cached RoyalRoad shards
— local-only, audited under §1.6, never committed (operator decision §7.3: ALLOW).

**F3's eventual real target is own-generated books**, which is what §7.1's fitness-book funding
exists to unblock: twenty own-generated texts long enough to carry a learnability slope, which
this repository does not have — §94.3 counted exactly one. The own-generated arm is `NOT_RUN`
with a price until that substrate exists, and it is recorded as such rather than omitted.

F3 inherits §94's promise-ledger machinery as a **covariate source** — do paid promises coincide
with learnability gains? — and grants it no verdict.

---

## 5. Track FX — the black swan: transmission chains

Low prior, capped budget, kill fast. Included because if it works it reframes the goal.

**Hypothesis.** Literary quality is memetic fitness — what survives retelling. Oral tradition
selected for exactly this; measure it directly.

### 5.1 Procedure

Telephone chains: read passage → context flush → *"retell this from memory for a new reader"* →
next hop. **J = 6 generations × R = 4 replicate chains per side**, alternating the two pinned
families per hop so no single family's artifact compounds. §94.5's displacement-read-as-deletion
is precisely the artifact class to fear, and alternating is the cheapest defence against it.

All scoring is deterministic and every extractor is committed before the first hop:

- **skeleton retention** — recall, in the hop-*k* output, of the original's top-40 content words
  by frequency, stopwords stripped, lowercased. Entity and proposition survival as a multiset,
  in the only form a deterministic extractor can honestly compute.
- **style retention** — the hop-*k* output's z-space distance to the *original's* feature row
  against its distance to the model median centroid M. Does the voice survive transmission,
  independently of the plot?
- **mutation rate** per hop — one minus content-word overlap between consecutive hops.
- **attractor check** — distance between chains originating from opposite pair sides at hop *k*,
  against distance between replicate chains from the same side. Convergence to one basin is the
  interesting negative.

### 5.2 The adversary, pre-registered

**Simplicity wins transmission.** The nursery-rhyme effect says the monotone hypothesis is
probably false, and saying so before the run is what makes the run informative. The declared
informative read is therefore the **style-versus-skeleton decomposition**: the black-swan outcome
is high-conversion sides' distinctive features surviving more hops *even as skeletons decay
equally*. If skeletons decay identically and styles do not, that is the finding; if both decay
identically, the hypothesis is dead and cheap.

### 5.3 Kill condition

Pilot on **8 pairs**. Close, with the negative recorded and the pilot's cost as the entry's last
line, if any of:

- placebo chains diverge — a §94.5-class confabulation, or a determinism failure §1.7 should
  already have caught;
- the sham moves anything;
- all measures saturate by hop 2.

At n = 8 the interval bar demands 8 of 8, so **the pilot cannot clear a bar and is not asked
to**: it is a kill screen, and §1.2's `INSUFFICIENT_N` rule is what keeps its arithmetic honest.

Chain outputs are derivative third-party text: local-only, audited, never committed.

---

## 6. Track FM — the market (gated; design now, fund later)

**Gate: at least one force clears §1.2's bars on the held-out split.** Until then this track
ships design and a dry-run only, and the dry-run buys nothing.

### 6.1 Design

A population of **judge-configurations** — individual forces, their ensembles, and (operator
§7.6: YES) the slot-free asking baselines E4/E5 as competitors to be beaten — each betting
probabilities on *which side converts*, over pairs it has never seen.

Declared before the first bet: the **proper scoring rule** (log score, with Brier printed
beside it), **bankroll dynamics**, **bankruptcy**, and the **promotion rule** for the surviving
ensemble. Settlement is instant and already downloaded — the label is on disk — and nothing human
is ever solicited.

**Amendment (2026-08-20, §95.15): the presentation is randomised, and the promotion rule needs a
skill test as well as a solvency one.** The question this document always specified is *"P(the
high-conversion side is side A)"*, and the implementation never asked it: `ForcePair` carries the
high-conversion text in `high`, nothing swapped the sides, and so every bet settled as "yes" and
the ranking became the log geometric mean of stated confidence. A constant 0.95 beat a perfectly
calibrated force at 0.52 by a factor a real force would have needed **0.9920 accuracy** to
overcome, and the committed dry run handed it 0.8804 of the promoted ensemble. Sides are now
swapped on a deterministic, label-blind coin derived from `pair_id`, so the outcome varies and
the scoring rule is proper in fact rather than only in name. The **promotion rule now requires
beating a coin**, not merely surviving: a flat stake leaves a sub-coin forecaster solvent after
146 bets, and inverse-log-score weighting over "every solvent entry" promoted a coin at 0.0628.

### 6.2 The survivor gets a battery before it gets a seat

The survivor is a **`FORECAST`-class instrument candidate** and nothing more. Before any seat:

- a **forecast analog of §86.7's axiom battery** — the disqualifier shape, adapted from
  preferences to probabilities: calibration curves, resolution, refinement, and the
  format-invariance and dose-monotonicity axioms restated for a forecaster;
- **§86's T3 exploitation/Goodhart budget, instrumented from the first optimization step** —
  because a selector trained against scraped behaviour is precisely the thing T3 exists to bound,
  and instrumenting it afterwards measures a horse that has already left.

### 6.3 The contradiction in the directive, resolved on the record

§8's anti-scope says *no pairwise preference elicitation anywhere, for any purpose*; §7.6 admits
E4/E5, and E5 is exactly pairwise preference elicitation. **The operator resolved it for §7.6**:
E4/E5 are admitted as *baselines to be beaten inside FM*, never as a valence channel, never as a
judge, and only if the FM gate opens. §8's prohibition governs everything else in this programme
without exception. Recorded here so that a future session finds a decision rather than an
inconsistency.

---

## 7. Operator decisions, as filled at issuance

| # | decision | filled |
|---|---|---|
| 1 | fitness books, ~$81 of frontier drafting | **FUND** |
| 2 | `results/operator-read-key.json`, retired unread | **SEAL** — kept on disk, never opened |
| 3 | F3 third-party chapter fetch, local-only, audited | **ALLOW** |
| 4 | GPU-hours cap | **40h total, check-in at 24h** — and §1.8 records that this turned out to be a duty-cycle cap worth about ten hours of computation |
| 5 | API spend cap | **$15** at issuance; **amended to ~$55** on 2026-08-20 to fund F1 on the remote transport (§1.9), plus item 1's $81 as its own line |
| 6 | E4/E5 as FM baseline competitors, ~$11 | **YES**, per §6.3 |

## 8. Anti-scope

No pairwise preference elicitation anywhere, for any purpose, save §6.3's single recorded
exception inside a gated track. No operator read. **No reader hiring, ever — the axiom is the
project.** No 12B probe ladder. No new verdict-format search. No committing of any
third-party-derived text. No licence movement: forces compete for `FORECAST`/`BEHAVIOUR` standing
only, and the market's survivor is a candidate, not a judge.

## 9. What this programme can and cannot conclude, written before it runs

**If a force clears the bars:** machine valence exists on this material, obtained without asking
a model a question or a human for a judgment. That is a stronger sentence than any version of it
with readers in it, and it is the sentence this programme is buying.

**If every force fails the bars with controls clean across two families:** that is the first
result in this repository entitled to say **the taste is not recoverable from these models by
measurement** — a sentence §89 was never entitled to, because §89 measured one channel and found
another intact. It is the honest end of the format hypothesis.

Either sentence is worth the GPU-hours, which is the property that makes this a programme rather
than a hope.
