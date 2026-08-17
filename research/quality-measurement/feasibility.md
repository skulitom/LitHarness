# Feasibility probe: what this machine can actually do

Companion to `BRIEF.md`. **This document proposes no metric.** It reports what was measured by
running code, so that a later proposal is costed against hardware and data that were checked
rather than assumed. Every number below came from a script that ran; where something failed,
the error is quoted.

Measured 2026-08-14 on the machine described in BRIEF.md §4. Scripts lived in that session's
scratchpad (`p1_load_logprob.py` … `p6_reviews.py`) and are gone with it.

**Provenance note, added 2026-08-17.** This file was first committed with §5.3 and §6 as
placeholder comments while the §0 table cited them as if they existed — two of six headline
results had no in-document evidence, in a document whose charter is the sentence above. The
bodies below were reconstructed by re-measurement on 2026-08-17 (stdlib csv over
`reviews.csv`; pyarrow over both cached shards; definitions stated inline), which also
corrected two numbers the placeholder era let drift: the §0 table said **19** distinct
reviewed-at chapters and "not 386" — measured, it is **20** distinct chapters and **387**
newline-terminated lines. The corrections are in the table; the wrong values are recorded
here so the next reader knows the table was once wrong and why.

---

## 0. Headline results

| # | Question | Answer |
|---|---|---|
| 1 | Does `gemma-3-4b-pt` load on CUDA? | **Yes.** 4.30B params, bf16, 8.60 GB VRAM, loads in 4–15 s |
| 2 | Per-token logprobs over a real MoL chapter | **9,690 tokens in 1.48 s — 6,546 tok/s, 16.5 GB peak** |
| 3 | Context ceiling on 24 GB at bf16 | **~12,288 tokens.** 12,288 OK (21.05 GB); 13,312 OOMs |
| 4 | Interventional pair (score B with / without A) | **0.51 s** @ RoyalRoad scale, **2.60 s** @ MoL scale |
| 4b | Does the intervention survive distance? | **No.** Effect dies by ~1–2k tokens (§4.3) |
| 5 | RoyalRoad within-story / within-author design | **Within-story: no outcome variable. Within-author: n=23, and only 10 cross the era boundary.** Both refuted (§5.3) |
| 6 | MoL `reviews.csv` | **116 rows, not 387 lines.** Sub-scores 29% populated; 20 distinct chapters (§6) |

Two of these are refutations, and they are the load-bearing ones: **§4.3 and §5.3 each kill a
design that BRIEF.md §3 points at as the open direction.**

---

## 1. Model loads and runs on CUDA — confirmed

`google/gemma-3-4b-pt` loads from the HF cache with
`C:/DEV/MirrorBench/.venv/Scripts/python.exe`, offline (`HF_HUB_OFFLINE=1`).

| Property | Value |
|---|---|
| Class instantiated | `Gemma3ForConditionalGeneration` via `AutoModelForCausalLM` |
| Parameters | 4,300,079,472 |
| dtype / device | `torch.bfloat16` / `cuda:0` |
| Weights in VRAM | 8.60 GB |
| Load wall-clock | 13.98 s cold, 2.7–4.7 s warm (OS file cache) |
| GPU | NVIDIA GeForce RTX 4090, 25.76 GB total (24,564 MiB) |
| torch / transformers | 2.13.0+cu130 / 5.15.0, `torch.cuda.is_available() == True` |

Architecture facts that matter later: **34 layers, 8 query heads, 4 KV heads, head_dim 256,
vocab 262,208, `sliding_window = 1024`, `max_position_embeddings = 131072`.** Gemma 3 applies
sliding-window local attention on 5 of every 6 layers; only every 6th layer is global. §4.3
shows that this is not a footnote.

No fallback model was needed. For the record, ollama also holds `gpt-oss:20b` (13 GB),
`phi4` (9.1 GB), `deepseek-r1:8b`, `qwen3:4b`, `gemma3:4b`, `gemma2:2b`, `llama3.2`.

### 1.1 Two environment gotchas that cost real time

- **`AutoTokenizer` returns the slow tokenizer.** Pass `use_fast=True` explicitly. Both report
  `class == GemmaTokenizer`, so the class name does not tell you which you got. Fast path
  tokenises the whole 4.59 MB MoL corpus in **1.81 s (2.54 M chars/s)**.
- **`expandable_segments:True` is silently ignored on Windows** —
  `UserWarning: expandable_segments not supported on this platform`. Fragmentation cannot be
  mitigated that way here.

---

## 2. Per-token log-probabilities over a real Mother of Learning chapter

Input: `C:/DEV/BookCrawler/data/mother-of-learning-20220313/chapters/001-301778.txt`
— 42,998 chars, **7,618 words → 9,690 tokens** (1.272 tokens/word).

| Metric | sdpa | eager |
|---|---|---|
| Wall-clock (warm, best of 3) | **1.480 s** | 1.960 s |
| Throughput | **6,546 tok/s** | 4,944 tok/s |
| Peak VRAM | 16.49 GB | 16.83 GB |
| Mean per-token logprob | −2.1555 | −2.1552 |
| Perplexity | 8.632 | 8.630 |

Scoring all 108 MoL chapters one at a time is therefore roughly **2.7 minutes** of GPU time.

### 2.1 The naive scoring loop does not fit and silently thrashes

The obvious implementation — `log_softmax(model(ids).logits.float())` — materialises a
`[1, 9690, 262208]` float32 tensor. That is **10.2 GB per tensor, twice over**. Measured peak
`memory_allocated` was **44.18 GB on a 24 GB card**: Windows WDDM had spilled to host memory
rather than raising OOM, and the same forward pass took **25.4 s instead of 1.48 s — a 17x
slowdown with no error**.

The fix used throughout: run the base model for hidden states, then stream them through
`lm_head` in chunks, gathering only the target-token logprob. Verified numerically identical
(`torch.allclose(..., atol=1e-3) == True`). This is a correctness-critical detail for anyone
building on this — the slow path produces the right numbers and looks merely sluggish.

---

## 3. Context ceiling on 24 GB at bf16 — **~12,288 tokens**

Each length was run in a **fresh process**, with the torch allocator capped just under actually
free VRAM so the driver raises a clean `OutOfMemoryError` instead of spilling to host RAM.

| Tokens | Result | Wall-clock | Peak VRAM |
|---|---|---|---|
| 8,192 | ok | 1.354 s | 14.32 GB |
| **12,288** | **ok** | 2.810 s | **21.05 GB** |
| 13,312 | **OOM** | — | 21.73 GB before failing |
| 14,336 | OOM (tried to allocate 6.12 GiB) | — | — |
| 16,384 | OOM (tried to allocate 8.00 GiB) | — | — |
| 32,768 | OOM (**tried to allocate 32.00 GiB**) | — | — |

**The ceiling is ~12,288 tokens — about 9,600 words, or 1.3 Mother of Learning chapters.**

### 3.1 Why it is this low, and why it cannot be fixed on this box

The ceiling is not the KV cache and not the weights. It is the attention matrix: the requested
allocation grows as n² (8.00 GiB at 16k → 32.00 GiB at 32k), which is the **math** SDPA
backend materialising `[1, 8, n, n]` in fp32. Diagnosed directly:

```
Warning: Torch was not compiled with flash attention.  (sdp_utils.cpp:923)
Warning: For dense input, both fused kernels require query, key and value to have the
         same num_heads. Query.sizes(): [1, 8, 4096, 256], Key sizes(): [1, 4, 4096, 256]
```

Two independent blockers, both confirmed by running code:

1. **This torch build ships no flash-attention kernel at all.** `can_use_flash_attention`
   returns `False` for every head_dim tested (64, 128, 256), even with no mask.
2. **The memory-efficient kernel refuses Gemma 3's GQA shapes** (8 query heads vs 4 KV heads).
   With heads equalised it returns `True`, so this is the GQA path specifically.

Forcing the kernels raises `RuntimeError: No available kernel. Aborting execution.`
The remaining escape hatch, `attn_implementation="flex_attention"` (O(n) memory, handles
sliding windows natively), fails on this machine too:

```
TritonMissing: Cannot find a working triton installation.
```

Triton is not available on Windows. **So the O(n²) math fallback is unavoidable in this
environment**, and ~12,288 tokens is a real ceiling, not a tuning problem. Lifting it means
installing a flash-attention build or moving to WSL/Linux — an infrastructure decision, not a
research one.

### 3.2 The consequence nobody would guess

MoL chapters, tokenised: **median 9,330, mean 9,544, max 18,294**.

**10 of 108 chapters exceed the 12,288 ceiling** and cannot be scored in a single pass. Six
exceed 13,312. Any design that assumes "one chapter fits in context" is wrong for ~9% of this
book, and the ones it is wrong about are the long chapters — which is unlikely to be random
with respect to what happens in them.

### 3.3 VRAM is shared, and this corrupted a measurement

The 24 GB is not exclusive. During probing, `ollama` had `gemma3:4b` resident (3.0 GB), and
the user's own `gistgap_kill2.py` processes held **up to 15 GB**, leaving 8.4 GB free — less
than the model's own 8.60 GB of weights. Free VRAM observed across the session ranged from
**4.0 GB to 23.7 GB**.

One ladder run silently measured a ceiling against a **9.79 GB** cap instead of 23.32 GB and
produced a meaningless answer. Any harness built on this must **record free VRAM at run start
and refuse to run below a floor**, or it will produce ceiling numbers that are really a
measurement of what else was open.

---

## 4. Cost of the interventional primitive

"Score span B once with span A in context, once with A excised" = 2 forward passes.
Measured with a 500-token B, median of 3 runs.

| Context scale | s / pair | Peak VRAM |
|---|---|---|
| RoyalRoad chapter (2,750 tok) | **0.513** | 15.45 GB |
| MoL chapter (9,200 tok) | **2.604** | 16.50 GB |
| Near ceiling (11,500 tok) | **3.597** | 20.50 GB |

### 4.1 Extrapolations requested

| Design | Pairs | Est. GPU time |
|---|---|---|
| (a) 108 MoL chapters, 1 pair each @ MoL scale | 108 | **4.7 min** |
| (b) 1,000 RoyalRoad chapters, 1 pair each @ RR scale | 1,000 | **8.6 min** |
| (c) 108×108 pairwise matrix @ MoL scale | 11,664 | **8.4 h** |
| (c′) same matrix @ RR-sized excerpts (2,750 tok) | 11,664 | **1.7 h** |

**(a) and (b) are cheap enough to run this afternoon.** Cost is not the obstacle for either.

### 4.2 But the 108×108 matrix does not fit at chapter granularity

Two full MoL chapters concatenated = **19,433 tokens**, well past the §3 ceiling:

```
OutOfMemoryError: CUDA out of memory. Tried to allocate 11.26 GiB.
```

A 108×108 matrix over full chapters is **not runnable on this machine at all**. It is only
possible over truncated excerpts (row c′), which changes what the matrix means: it would
measure the effect of an *excerpt* of chapter i, not of chapter i.

### 4.3 **The interventional effect does not survive distance — this is the important result**

Cost was never going to be the thing that killed an interventional design. This might be.

For each gap distance, 12 independent draws from MoL. `A` is a 512-token span, `B` a 256-token
span, `pre` 1,000 tokens. Per BRIEF.md §5, **the control was computed in the same pass**:
`A_else` is a same-length span drawn from a distant part of the corpus, so the placebo asks
whether the effect is "*this* passage preceded B" or merely "some tokens occupied that slot".

```
delta_real    = LP(B | pre + A      + mid) − LP(B | pre + mid)
delta_placebo = LP(B | pre + A_else + mid) − LP(B | pre + mid)
```

| gap A→B | Δ real (sd) | Δ placebo (sd) | real − placebo | draws real>placebo | sign-test p |
|---|---|---|---|---|---|
| **0** | **0.2771** (0.091) | 0.0156 (0.077) | **+0.2615** | **12 / 12** | **0.0005** |
| **256** | **0.0736** (0.027) | 0.0127 (0.026) | **+0.0608** | 11 / 12 | **0.0063** |
| 512 | 0.0222 (0.021) | 0.0119 (0.029) | +0.0102 | 8 / 12 | 0.388 |
| 1024 | 0.0289 (0.029) | 0.0130 (0.018) | +0.0159 | 10 / 12 | 0.039 |
| 2048 | 0.0076 (0.009) | 0.0065 (0.007) | +0.0011 | 8 / 12 | 0.388 |
| 4096 | 0.0129 (0.033) | 0.0061 (0.009) | +0.0068 | **5 / 12** | 0.774 |

216 forward passes, 69.9 s total, 0.324 s/pass, 11.65 GB peak.

**Read the table this way.** When `A` sits immediately before `B`, excising it is enormously
detectable and unmistakably about *content*: the real effect is 18x the placebo and every one
of 12 draws agrees. By a gap of 512 tokens the real−placebo difference (0.0102) is **smaller
than the standard deviation of either arm** (0.021, 0.029), and the sign test is
indistinguishable from a coin. At 4,096 tokens it is 5/12 — *below* chance.

The 1024 row is the trap. Taken alone, p=0.039 reads as a surviving long-range effect. It is
not one: with six distances tested, Bonferroni α is 0.0083 and it fails; and it is
**non-monotonic** — 512 is null, 1024 "significant", 2048 null again. A real decay curve does
not do that. It is noise that happened to land, and the same discipline BRIEF.md §2 applies to
`tricolon_rate` applies here: read the control and the neighbours before believing the cell.

**Why this is mechanism, not bad luck.** Gemma 3 runs `sliding_window = 1024` local attention
on 5 of every 6 layers (§1). Only **6 of 34 layers** can see a span 2,000 tokens back at all.
The measurement is not failing to find a long-range effect; the model largely lacks the
pathway to carry one.

**What this costs a design.** BRIEF.md §1a.3 ranks dramatic function, progression-as-drama, and
escalation-and-payoff as items 1–3 — and all three are **long-range by definition**. A promise
planted in chapter 2 and paid in chapter 40 is thousands of tokens away. An interventional
proxy built on gemma-3-4b logprobs can measure **local coherence at ≤256 tokens** and, on this
evidence, nothing beyond it. That is item 5 territory — the band BRIEF.md §1 says is already
saturated with refuted metrics.

This does not refute interventional designs as a class. It refutes *this model* as the
instrument for the items that matter, and it does so for a legible architectural reason. A
model with global attention across its full depth (or a design operating on summaries rather
than raw spans, so the "distance" is compressed) is the direction that survives. **The cheap
screening test for any such successor is the table above: run the placebo arm at gap ≥2048
before building anything on top.** It costs 70 seconds.

---

## 5. RoyalRoad parquet shards

Both cached shards read with pyarrow: `train-00003-of-00047.parquet` and
`train-00030-of-00047.parquet`, **34,338 rows each, 68,676 total**. One snapshot in the HF
cache: `0e4df3f22999a7b7fa13b1e7564a09b5f3eb964e` — the revision every number in this
directory was measured against.

### 5.3 The two within-designs, refuted *(re-measured 2026-08-17)*

The point of a within-story or within-author design is to hold the confounds that killed
every between-cohort proxy — era, author, maturity, cadence — fixed by construction. Both
available versions die before the design question is reached:

- **Within-story: there is no outcome variable.** All five advertised score columns
  (`overall_score`, `style_score`, `story_score`, `grammar_score`, `character_score`) are
  **100% null across all 68,676 rows** — re-verified column by column. A within-story design
  compares chapters of one story against a per-chapter outcome, and this corpus has no
  per-chapter outcome of any kind; the engagement counters are story-level stocks. The
  missing column is exactly the per-chapter retention `plan/craft-corpus.md` §4.5 names as
  unobtainable without platform cooperation.
- **Within-author: the cell is too small, twice over.** Definition, stated because the first
  write-up of this number did not state one: an author qualifies with ≥2 LitRPG-tagged
  stories in the cached shards, each with ≥1 chapter passing the corpus filters (cohort
  assigned by `corpus_io.era_cohort`, ≥300 words). Measured: **23 qualifying authors** — and
  the design actually wanted (the same author on both sides of the era boundary, so era
  varies while author holds) is smaller still: **10**. 608 qualifying stories produce ten
  usable author-pairs; nothing calibrates on that, and the ledger's `MIN_HOLDOUT = 50` is
  not in sight.

---

## 6. Mother of Learning `reviews.csv` — the advertised numbers do not survive contact

*(Re-measured 2026-08-17: stdlib `csv` with `utf-8-sig` — the header carries a BOM — over
`C:/DEV/BookCrawler/data/mother-of-learning-20220313/reviews.csv`.)*

The file reports **387** newline-terminated lines, and that is not the row count: review
bodies contain embedded newlines, so a line count overstates the data 3.3×. A real CSV parse
yields **116 rows**.

| column | populated | distribution |
|---|---|---|
| `overall_score` | 116/116 | **96 at 5.0**; 7 at 4.5; 13 at 4.0 or below |
| `style_score` | **34**/116 | 25 of 34 at 5.0 |
| `story_score` | 34/116 | 30 of 34 at 5.0 |
| `grammar_score` | 34/116 | 24 of 34 at 5.0 |
| `character_score` | 34/116 | 25 of 34 at 5.0 |
| `reviewed_at_chapter_id` | 76/116, over **20** distinct chapters | — |
| `content` (review text) | 116/116 | — |
| `upvotes` / `downvotes` | 88/116 | — |

**What this refuses.** One book, one author, one quality tier, a self-selected fan
population, and a ceiling at 5.0: there is no usable variance to calibrate against, and the
sub-scores that would supply *attribution* exist on 34 rows spread across 20 chapters. Treat
this file as a source of review **text** (a vocabulary of located complaints, 116 documents
of it) and as the index to a within-book prose corpus — never as a score label. Any proposal
resting on these scores as ground truth is refuted before it starts. BRIEF.md §4 carries the
same table; this section is the measurement it cites.
