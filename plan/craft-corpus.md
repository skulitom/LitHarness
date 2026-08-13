# The craft corpus, and calibrating without a human in the loop

Companion to PLAN.md §1a, §10 and §17 Stage 4. Records what the RoyalRoad corpus is, what
was measured against it, and — the reason this document exists — **how the craft programme
can be calibrated without requiring anyone to sit down and judge prose.**

## 0. The objection this document answers

§10 as written routes craft validation through "weekly bounded RevisionJudge sessions", and
§10.6 makes a hand-authored reference corpus the gating item. §1a.4 justifies both: *human
judgment is the only ground truth for items 1–6.*

That is epistemically right and operationally self-defeating. **The product is a system that
makes books without a human in the loop.** A quality programme whose measuring instrument
requires scheduled human sessions is a programme that will not be run — and the evidence is
already in: RevisionJudge has 104 exported pairs and **two** collected verdicts. The
instrument was built, it works, and in practice it has produced 1.9% of one session's worth
of data. Planning for more of that is planning for the same result.

**The amendment is narrow and it is not a retreat from §1a.4.** Human judgment remains the
only ground truth. What §1a.4 conflates is two ways of getting it:

- **Solicited** judgment — sessions, rubrics, pairwise forms. Expensive, slow, needs
  blinding and order-randomization precisely because the asking distorts the answer, and
  it does not scale.
- **Revealed** judgment — readers who chose to keep reading, follow, favourite or abandon,
  for their own reasons, with nobody asking them anything. Free, enormous, already
  collected, and structurally immune to the demand characteristics and positional artifacts
  §10.3 spends its design controlling for.

§1a.5 already words the project's own bars in revealed terms — *"a majority of sampled
chapters earn 'I would keep reading'"*, *"retention across consecutive chapters is measured
and does not decay faster than a comparable human-written serial"*. Those are statements
about reader behaviour. Revealed preference measures them directly; a rubric measures a
proxy for them.

## 1. What the corpus is

`OmniAICreator/RoyalRoad-1.61M` — 1,613,875 chapters, 12.5 GB, MIT-licensed compilation of
publicly posted RoyalRoad fiction. Roughly 19% carry the `LitRPG` tag, which is the genre
this system is being built to write.

**Verified against the data rather than the card, and the card is wrong in one important
way.** Two full shards (68,676 chapters) were checked column by column:

| Column | State |
|---|---|
| `overall_score`, `style_score`, `story_score`, `grammar_score`, `character_score` | **100% null.** Advertised on the dataset card; absent from the data. |
| `pages` | 100% null |
| `followers`, `favorites`, `total_views` | 100% populated. Followers 0–14,287; views 25–10.4M |
| `ratings` (a *count*, not a score) | 82–100% populated, 0–4,103 |
| `tags`, `warnings`, `release_datetime`, `text` | populated |
| `status` | ~19% populated |

So the corpus supplies **engagement, not ratings**. That is the whole design problem, and
§1a.1 is the reason it cannot be waved away: *"beware the metric that is easy because it is
shallow"*. Raw popularity tracks cover art, blurb, tags, launch timing, update cadence and an
author's existing audience at least as much as it tracks prose.

**Two structural handles the corpus has that are worth more than the missing scores:**

- **`AI-Assisted Content`** — a RoyalRoad warning authors set themselves. A labelled
  human/machine split, under-reported but real.
- **Release dates spanning 2021–2025** — chapters before 2023 predate general LLM
  availability. A temporal control that confounds *differently* from the declaration, which
  is what makes the pair useful.

## 2. What has been measured so far

`tools/build_craft_profile.py` → `plan/craft-profile.json`, over ~13,000 LitRPG chapters.

**All four instrumented craft metrics are refuted as AI-tell detectors.** Holding the era
fixed — declared-AI 2025 against undeclared 2025 — every rank AUC lands within 0.06 of chance:

| proxy | declared-AI vs undeclared (2025) | vs pre-2023 | control: undeclared vs pre-2023 |
|---|---|---|---|
| `dialogue_ratio` | 0.445 | 0.481 | 0.531 |
| `opening_shape_repetition` | 0.455 | 0.404 | 0.450 |
| `sentence_length_cv` | 0.461 | 0.500 | 0.534 |
| `tricolon_rate` | **0.528** | 0.629 | 0.606 |

**The `tricolon_rate` row is the transferable lesson.** 0.629 against pre-LLM prose is the
only number here that looks like a finding, and it survives exactly as long as it takes to
read the control beside it: undeclared 2025 chapters separate from the same baseline at 0.606.
The metric detects **the year, not the machine**. Reported without the control it would have
been this project's first working AI-tell detector. **Every future proxy measured against this
corpus must compute the era control in the same pass.**

Three confounds hold this at *no separation detected* rather than *no signal exists*: 55
stories in the declared-AI cohort, self-declaration certainly under-reported, and cohorts
differing enormously in maturity (median followers 16 / 88 / 314).

## 3. The label that makes revealed preference usable

Raw follower count is popularity. The refinement is a **conversion rate**:

```
conversion = followers / total_views
```

Discovery — cover, blurb, tags, promotion, timing — drives the *denominator*. Whether readers
stayed drives the *numerator*. Dividing one by the other removes most of what §1a.1 warns
about, and leaves the part that is closest to being about the prose.

**Measured, not assumed** (365 LitRPG stories with ≥1,000 views):

- spread p10→p90 is **9×** (0.00112 → 0.01045), so the label discriminates
- Spearman ρ against raw followers is **0.438**, so it is *not* popularity restated — it
  carries information beyond story size

That is a usable label available today, at a scale no session will ever reach.

## 4. Research directions, with what each is and is not valid for

### 4.1 Calibrate proxies against revealed preference — *viable now*

Score chapters with a candidate proxy; test whether it separates high-conversion from
low-conversion stories on held-out data, stratified by tag set, era, and length, and matched
within author where possible.

- **Validity:** this is §1a.4's ground truth, revealed rather than solicited. It supplies
  exactly the evidence `domain/calibration.py::promoted_gate` refuses to promote without —
  held-out precision on a named verdict set — with no session.
- **Limits:** the label is *story-level* and a scene metric is chapter-level, so a per-scene
  proxy is validated against an outcome one level up. That is real label noise and an
  ecological-fallacy risk; it argues for chapter-aggregated metrics per story rather than
  per-scene claims.
- **Uncontrolled confounds:** update cadence (computable from `release_datetime` — control
  it), cover and blurb (partly divided out by conversion), and author reputation (control by
  matching within author; only 23 of 590 authors had ≥2 LitRPG stories in a 2-shard sample,
  so this needs the full corpus).

### 4.2 Indistinguishability as an adversarial objective — *the most direct removal of the human*

§1a.5's **first bar is literally a discrimination task**: "blinded genre readers cannot
reliably distinguish accepted chapters from published human LitRPG at the same tier". Train a
discriminator to separate this system's accepted chapters from tier-matched published LitRPG.
If it succeeds easily, the bar is failed and no reader was needed to find that out.

- **Validity:** high for that specific bar, because it is the bar the plan already wrote.
  A machine that cannot tell them apart is weak evidence a human could not; a machine that
  *can* is strong evidence the bar is failed. Asymmetric, and useful in the direction that
  matters — it is a cheap way to *fail fast*.
- **The danger, stated loudly because it is the one that would wreck the project:** this is a
  Goodhart magnet of the exact kind §10.6 catalogues and §1a.2 measures. If the generator is
  ever optimised against the discriminator, the result is prose that fools the discriminator —
  not prose anyone wants. Non-negotiable constraints if this is built: the discriminator is
  **never** exposed to the generation loop as an optimisation target or a prompt; it is
  retrained on a fresh held-out slice each cycle; and passing it is treated as
  necessary-and-insufficient, never as a quality claim.

### 4.3 Model critics calibrated against revealed preference — *unblocks a refuted instrument*

RevisionBench refuted **raw** model-judge verdicts: 43–65% positional artifacts, order-
consistent survivors preferring human originals ~80% of the time. What a critic lacked was not
a better prompt but a **calibration target**. Revealed preference is one, at scale.

- **Validity:** inherits §4.1's limits. MirrorBench's invariants remain mandatory and are
  already enforced in code — `PolicyDecision.__post_init__` refuses a blocking gate sourcing
  its verdict from the generating model, and `promoted_gate` refuses without measured
  held-out precision.
- **Why it matters:** a calibrated critic is the only instrument on this list that could reach
  §1a.3 items 1–4 — dramatic function, progression as drama, escalation, voice — which §10.6
  established are unreachable from defect fixtures and which no counting proxy has touched.

### 4.4 The reference corpus, selected rather than authored — *dissolves §10.6's blocker*

§10.6 asks for "passages that exemplify each item in §1a.3, paired where possible with a
weaker variant of the same beat", and calls it human work. **Selection from the top and bottom
deciles of conversion rate, matched on tag set, era, length and author, is a paired corpus** —
thousands of pairs rather than dozens, and no one writes a word of it.

- **What is lost:** the pairs are not *attributed*. A hand-authored pair says "these differ in
  dramatic function"; a selected pair says "readers converted on one and not the other" and is
  silent about why. Item-by-item validation of §1a.3's ordering still needs attribution.
- **What is gained:** the thing §10.6 says is missing — something for craft work to be
  measured against — exists immediately.

### 4.5 What remains genuinely blocked

Stated so this document does not read as claiming more than it does:

- **Attribution.** Revealed preference gives one scalar per story. It cannot say whether a
  pair differs on dramatic function or on voice, so §1a.3's *ordering* stays unvalidated.
- **Per-chapter retention.** The single most valuable missing column. RoyalRoad exposes
  per-chapter view counts publicly; this dataset does not carry them. With them, §1a.5's
  third bar — retention decay against a human-written serial — becomes directly measurable,
  and the label stops being story-level, which removes §4.1's main weakness.
- **Reader reviews.** RoyalRoad reviews are voluntary written judgments with scores, which is
  solicited judgment *already collected at scale* — the best of both. Not in this dataset.

Both gaps are **data acquisition**, not human authoring. That is the substantive change in
this document's conclusion: the craft programme's blocker moves from "someone must write a
corpus and judge prose" to "someone must collect two more public columns."

## 5. Consequence for the plan

- §1a.4's "human judgment is the only ground truth" **stands**, with the solicited/revealed
  distinction made explicit.
- §10.3's weekly sessions are **demoted from the primary instrument to a cheap confirmation
  sample**. §10.5's standing audit (built, `litharness audit`) is the right size for that:
  it collects judgment as a by-product of operation rather than as a scheduled event.
- §10.6's hand-authored corpus is **no longer the gating item**; §4.4 supplies a selected one.
- The new critical path is §4.1 and §4.2, both of which are engineering.
