# Brief: the unsolved quality-measurement problem in LitHarness

Read this before proposing or building anything. It is the ground truth about what has
already been tried and why each attempt died. **Every single failure below died to a
*control*, not to a bug.** That is the pattern to internalise.

## 1. The problem, stated exactly

LitHarness is an autonomous book-production system (LitRPG genre). Its gate ladder blocks on
*shape* (a draft exists, right size, did not overwrite) and *integrity* (no contradictions).
**Nothing blocks on whether the prose is any good.** PLAN.md §1a.3 orders what "quality" means:

1. **Dramatic function** — every scene changes something; scenes that only *convey
   information* are the most common failure of generated prose.
2. **Progression as drama, not bookkeeping** — the LitRPG system must cost the protagonist
   something.
3. **Escalation and payoff** — promises planted get paid, on a cadence a reader feels.
4. **Voice** — a particular consistent narrator; dialogue that distinguishes characters.
5. **Line-level craft** — concrete specificity, varied rhythm, no filler.
6. **Absence of AI tells** — register drift, summarising instead of dramatising, tidy
   emotional resolution, the tricolon habit, the same three sentence shapes.

Items 1–4 are the ones that move a reader, and **nothing in the project has ever touched
them.** All instrumented metrics are items 5–6, and all four are refuted (§3 below).

The gate that could refuse a scene is wired end to end (`domain/calibration.py::promoted_gate`)
and **cannot be constructed**, because it demands held-out precision ≥0.80 on ≥50 judgments
with ≥17 flags, and no calibration exists. `litharness calibrations` prints nothing. That
emptiness is the honest measure of the gap.

## 2. The refutation ledger — 20 proxies dead

**This section is canonical for the count.** It was carried in two places for a while and
drifted within a single session; `PLAN.md` and `plan/stage-0-decisions.md` now point here
rather than restating a number.

**Pass 1: nine candidate proxies against the golden defect fixtures. One promoted, eight dead.**

| proxy | how it died |
|---|---|
| `progression_cost` | Satisfied by inserting a token gold decrement beside each level-up. The cheapest repair that satisfies the metric *is the disease* — it rewards the failure it was built to catch. |
| `silent_ledger` | Fires on the fixture's **best** prose. The fixture renders HP qualitatively ("warmth climbed his ribs like a tide coming in"); the only repair pushes prose toward machine register, degrading items 5–6 to satisfy an item-2 proxy. |
| `state_change_prose_trace` | Same failure as `silent_ledger`. |
| `scene_change_profile` | **Falsified outright.** Assumes ledger delta tracks dramatic change. Mystery scene 6 — the confession and arrest — carries **zero** state records; scene 1, pure exposition, carries the most. It ranks the book upside down. Record density measures annotation coverage, not scene function. |
| Burrows Delta (voice consistency) | Separates within-book from between-book by **0.6%** at ~120 prose tokens per scene. |
| dialogue distinctiveness | The entire golden program contains **77 words of dialogue**. Needs a corpus, not a better method. |
| (three others in the same pass) | — |

**Pass 2: the four instrumented metrics against ~13,000 published LitRPG chapters.** All four
dead. Rank AUC, declared-AI-2025 vs undeclared-2025 (era held fixed):

| proxy | declared-AI vs undeclared 2025 | vs pre-2023 | **control: undeclared vs pre-2023** |
|---|---|---|---|
| `dialogue_ratio` | 0.445 | 0.481 | 0.531 |
| `opening_shape_repetition` | 0.455 | 0.404 | 0.450 |
| `sentence_length_cv` | 0.461 | 0.500 | 0.534 |
| `tricolon_rate` | **0.528** | **0.629** | **0.606** |

**The `tricolon_rate` row is the transferable lesson.** 0.629 against pre-LLM prose looks like
the project's first working AI-tell detector, and it survives exactly as long as it takes to
read the control beside it: *undeclared* 2025 chapters separate from the same baseline at
0.606. **The metric detects the year, not the machine.** Any future proxy measured against this
corpus must compute its control in the same pass or its headline number means nothing.

**Pass 3: per-chapter comment counts via the Wayback Machine.** Recovered 108/108 chapters,
8,849 comments — the project's first complete chapter-granular human-response measurement.
Dead on the control: rho(comments, chapter position) = +0.16, but rho(comments, **capture
date**) = +0.43, and the partial correlation of position given capture date is **−0.045**. The
number measures *when the archive looked*, not what readers did. The exposure-adjusted rescue
(comments per day) looked like a finding at rho=+0.26 until its mechanical null was computed:
dividing by exposure injects position by construction, and a *constant* comment count would
produce +0.567. Observed was **below its own null**.

**Pass 4: raw model-judge verdicts (RevisionBench).** 43–65% positional artifacts;
order-consistent survivors preferred the *human originals* ~80% of the time. Models asked to
improve prose made it worse — which is why the architecture is `detect → scoped repair →
verify`, never open-ended "improve this".

**Pass 5: compression. Seven more dead, two kept — and the two kept are not quality proxies.**
Detail in [plan/stage-0-decisions.md](../../plan/stage-0-decisions.md) §48–§50; this is the
ledger row. All seven were measured against the RoyalRoad books in `corpus_io.by_story`, with
the era control computed in the same pass as §2 demands.

| proxy | how it died |
|---|---|
| whole-book gzip joint/parts ratio | Tracked **scene count**, not authorship. A machine six-scene book scored 0.704 against human books at 0.625 and 0.757; only *n* differed, because gzip's dictionary amortises. |
| minimum cross-paragraph NCD | A **coverage** artifact. Minimum-over-pairs is a lottery, so equalising the *number* of comparisons while one book is sampled at 100% and another at 2% measures the sampling. Same text, same book: 0.473 at 8.5% coverage, 0.078 at 100%. Forcing the large human books to exhaustion reverses the ranking. |
| paragraph NCD dendrogram (UPGMA) | Clean null, declared-vs-undeclared 0.412, and its **seed-to-seed swing (0.228–0.545) exceeded its distance from chance**. Note for anyone retrying: 50.6% of NCD cells at paragraph scale are exact ties, because NCD is a ratio of small integer gzip sizes. |
| nearest-predecessor lag | Null that **inverts on the target defect**. It awards the looping book the best score in the corpus, because duplicated scenes are adjacent and lag 1 cannot distinguish "continues" from "is being rewritten". |
| marginal novelty-decay exponent | AUC 1.000 against the machine cohort, and `Counter(trigrams)` reproduces it outright. Word-shuffle inside the window took it to 0.521. |
| compression order asymmetry `A_C` | An **LZ77 match-distance readout**. Reversing paragraph order *inside* each unit while units keep their book positions inverts the sign (t = +6.72). The control originally specified — reverse the book, check the sign flips — **cannot fail**: `A_C` is algebraically antisymmetric, measured at 0.000e+00 over 34 books. It passes on pure noise. |
| tree-Haar scale energy | Null (0.56), and 73% measurement-window noise: across 158 disjoint windows the within-book sd equals the between-book sd, ICC(1) = 0.270. |

**Kept: `scene_echo` and `repeated_span`, and they claim repetition rather than quality.**
"These 28 words appear in scene 5 and again in scene 6" is mechanically checkable and needs no
human judgment, which is the only reason they are not in the table above. They are **not AI
tells and the code says so**: published human serials repeat verbatim spans up to 93 words,
longer than this project's own worst generated book at 59.

**Three method rules earned in this pass, all cheap and all general.** Ask whether a control
*can fail* before running it. Simulate the null at your own *n* — the log-log slope estimator
is biased low, 0.436 at n=32 against 0.482 at n=1024, so comparing to a theoretical 0.5
manufactures 0.03 of effect from nothing. And check within-book reliability (ICC) before
believing any per-book statistic; this project had never run one.

## 3. The structural diagnosis (this is the opening for a novel approach)

Every one of the 20 refuted proxies shares three properties:

- **Static** — a scalar computed on one text in isolation, with no model of what the text does.
- **Absolute** — the number is compared *across* texts that differ in era, author, story
  maturity, length, tags, cadence. Every confound that killed a proxy entered through this door.
- **Correlational** — a property is measured and correlated with a label. Nothing has ever
  *intervened* on the text and measured the difference.

And the labels available are all contaminated: engagement tracks cover art and launch timing;
comment counts track archive capture date; declared-AI tracks the year.

**Nothing model-based has been tried.** No proxy in the ledger uses a language model's
predictive distribution over the text. Zero.

**Nothing causal has been tried.** No proxy perturbs the text and measures what changes.

> **Status, and read it before treating the two paragraphs above as an open invitation.** That
> was true when this section was written and is no longer. [feasibility.md](feasibility.md)
> probed the direction on 2026-08-14 and **two of its designs are already closed**, both by
> controls computed in the same pass. §4.3: the interventional effect does not survive
> distance — with the placebo beside it, a gap of 0 gives real − placebo of +0.2615 at 12/12
> draws (sign-test p = 0.0005), 256 tokens gives +0.0608 at 11/12 (p = 0.0063), and by 512
> tokens it is +0.0102 at 8/12 (**p = 0.388**), which is nothing. §5.3: the RoyalRoad
> within-story design has no outcome variable and the within-author one is n=23. `surprisal.py`
> implements what survived — Context Dependency Gain, scoring a block against its own prefix
> versus a foreign one — and `results/` holds no CDG numbers yet, so it is **built and not yet
> evidenced**. The opening is narrower than these paragraphs make it sound: short-range only,
> and still short of a label.

## 4. What is available to experiment with, verified present on this machine

- **RTX 4090, 24GB.** `C:/DEV/MirrorBench/.venv/Scripts/python.exe` has torch 2.13+cu130
  (CUDA available), transformers 5.15, numpy, scipy, sklearn. `google/gemma-3-4b-it` and
  `gemma-3-4b-pt` are in the HF cache. Ollama has qwen3:4b, gemma3:4b, gpt-oss:20b, phi4,
  llama3.2.
- **RoyalRoad corpus, 2 shards cached locally** (~68,676 chapters, ~19% LitRPG-tagged):
  `C:/Users/artem/.cache/huggingface/hub/datasets--OmniAICreator--RoyalRoad-1.61M/snapshots/*/data/train-00003-of-00047.parquet`
  (2025 cohort) and `train-00030-of-00047.parquet` (2021–22 pre-LLM cohort). Columns that are
  populated: `text`, `tags`, `warnings`, `release_datetime`, `fiction_id`, `followers`,
  `favorites`, `total_views`, `ratings` (a count). **All five score columns are 100% null**
  despite the dataset card. Measured label available: `conversion = followers / total_views`,
  9× spread p10→p90, Spearman ρ=0.44 vs raw followers (so not popularity restated).
- **Mother of Learning, complete**: `C:/DEV/BookCrawler/data/mother-of-learning-20220313/` —
  108 full chapter texts, 806,157 words total, plus `chapters.csv` and `reviews.csv`.

  **The reviews are measured, and they are close to useless as a label — check this yourself
  before building on them.** `wc -l` says 387 and that is wrong: review bodies contain
  newlines, and a real CSV parse yields **116 rows**. Of those:

  | column | populated | distribution |
  |---|---|---|
  | `overall_score` | 116/116 | **96 are 5.0**; 7 at 4.5; 11 below 4.0 |
  | `style_score` | **34**/116 | 25 of 34 are 5.0 |
  | `story_score` | 34/116 | 30 of 34 are 5.0 |
  | `grammar_score` | 34/116 | 24 of 34 are 5.0 |
  | `character_score` | 34/116 | 25 of 34 are 5.0 |
  | `reviewed_at_chapter_id` | 76/116, over **20 distinct chapters** | — |

  So: one book, one author, one quality tier, a self-selected fan population, and a ceiling
  at 5.0. There is no usable variance to calibrate against, and the sub-scores that would
  supply *attribution* exist on 34 rows spread across 20 chapters. Treat this as a source of
  review **text** (a vocabulary of located complaints) and as a within-book prose corpus of
  806k human-written words — not as a score label. Any proposal resting on these scores as
  ground truth is refuted before it starts.
- **Golden fixtures**: `C:/DEV/litharness-contracts/fixtures/golden/{mystery,litrpg}/` —
  6 scenes each, ~130 words per scene. Mystery scene 6 (confession and arrest) is the dramatic
  peak, scene 1 (pure exposition) is the flattest; `scene_change_profile` ranked these upside
  down.

  **Measured caveat, and it demotes this test hard — read it before relying on the fixture.**
  The mystery's scene lengths run 166, 148, 128, 124, 131, **103** words. The dramatic floor
  is the *longest* scene and the dramatic peak is the *shortest*, nearly monotonically. So the
  anchor ordering is confounded with both length and position, and **any statistic that is
  noisier or larger on short text ranks the anchors "correctly" for free**. Measured on the
  incumbents (`research/quality-measurement/baseline.py`):

  | incumbent | order high→low | scene 6 | scene 1 | "separates anchors" |
  |---|---|---|---|---|
  | `sentence_length_cv` | 6,2,3,1,4,5 | #1 | #4 | yes |
  | `tricolon_rate` | 6,4,2,1,3,5 | #1 | #4 | yes |
  | `opening_shape_repetition` | 5,6,4,3,1,2 | #2 | #5 | yes |
  | `dialogue_ratio` | 5,3,2,1,4,6 | #6 | #4 | no |
  | **raw word count** | 1,2,5,3,4,6 | #6 | #1 | yes (inverted) |

  Two already-refuted metrics pass the anchor test. So passing it shows **nothing**; only
  *failing* it is informative. Treat the fixture as a smoke test that can refute and cannot
  confirm, and never report "it ranked the fixture right way up" as evidence. At n=6 scenes
  and ~800 words total there is no version of this that becomes decisive.
- LitHarness source: `src/litharness/domain/craft.py` (the four metrics),
  `domain/calibration.py` (the promotion bar), `tools/build_craft_profile.py` (the corpus
  harness, including a working rank-AUC implementation and the cohort logic).

## 5. Rules any proposal must obey (these are the project's, not negotiable)

- **Compute the control in the same pass.** A headline number without its control is not a
  result. Name the confound your measure is most likely to be detecting, and measure it.
- **A metric reports a number, never a judgment.** Thresholds are properties of a
  *calibration*, which is a claim about human judgment that has to be earned.
- **Necessary and insufficient.** Passing a deterministic gate means the draft is not broken.
- **Never expose a discriminator/critic to the generation loop as an optimisation target.**
  Goodhart is the failure mode that would wreck the project. `PolicyDecision.__post_init__`
  already refuses a blocking gate whose verdict came from the generating model.
- **Beware the metric that is easy because it is shallow.** Word count, scenes/day, findings
  closed, tokens spent — all trivially instrumentable, none of them quality.
- **The cheapest repair that satisfies the metric must not be the disease.** State, for your
  proposal, what the cheapest way to game it is and whether that gaming would be a *real*
  improvement.
- **Refuting is worth as much as confirming.** Four proxies were refuted in an afternoon and
  the project counts that as its best day of quality work. A proposal that fails fast and
  cheaply beats one that might work but takes a month to find out.
