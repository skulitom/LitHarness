# The craft corpus, and calibrating without a human in the loop

> **HISTORICAL DESIGN.** The craft-calibration and solicited-preference paths described here
> were retired under the scope axiom. Current quality-perception work starts at
> `plan/reader-architecture-program.md`; this file remains as the evidence behind rejected
> approaches, not as an implementation plan.

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

The retired profile builder produced `plan/craft-profile.json` over ~13,000 LitRPG chapters.
Its source was removed with the craft-calibration path; the result and decision record remain.

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

~~That is a usable label available today, at a scale no session will ever reach.~~ **Run
against its own control on 2026-08-17 and it did not survive at the grain it was wanted
for** — §4.1 carries the result and [stage-0-decisions.md](stage-0-decisions.md) §56.3 the
full table. The two measured facts above stand as facts; what died is the reading that they
license selecting anything by decile.

**And the division never removed what it claimed to, for a mechanical reason this section
should have stated.** `total_views` is not a discovery counter: it accumulates one view per
chapter-visit, so the denominator counts *staying* too — a reader who reads forty chapters
adds roughly forty views and at most one follow. For a fixed follow propensity, conversion
falls as chapters-read-per-reader rises: the label mechanically penalises the deep-reading
behaviour it was adopted to capture, and rewards stories sampled shallowly and followed
early. The project's own table carries the signature — `chapters_seen`, a column that reads
no prose, separates the conversion deciles at AUC 0.308, the second-strongest separator
after `followers` itself — so part of the 9× spread above is chapter-count spread.

**A survivorship term sits under all of it, unmeasured.** Successful RoyalRoad serials are
routinely *stubbed* — chapters removed when the book moves to Kindle Unlimited — and deleted
stories leave the corpus entirely, while engagement counters freeze at whatever the compiler
last saw. The most-successful tail is therefore systematically truncated or missing, and no
number in this document is corrected for that. Nothing here measures the bias's size; this
paragraph exists so the label is not extended to a use where it would matter without someone
measuring first.

## 4. Research directions, with what each is and is not valid for

### 4.1 Calibrate proxies against revealed preference — ~~*viable now*~~ *run, and the label did not survive its own control*

Score chapters with a candidate proxy; test whether it separates high-conversion from
low-conversion stories on held-out data, stratified by tag set, era, and length, and matched
within author where possible.

**Run 2026-08-17, and the result is a refusal rather than a calibration
([stage-0-decisions.md](stage-0-decisions.md) §56.3).** 354 LitRPG stories, top against
bottom conversion decile, permuted-label null in the same pass: **`followers` alone
separates the deciles at AUC 0.814** while the best prose-reading metric reaches 0.367.
(The first write-up of this paragraph said every prose metric sat *inside* its null band —
the artifact says two sit marginally **below** it: `dialogue_ratio` at 0.3886 against a 5th
percentile of 0.3902, `opening_shape_repetition` at 0.3665 against 0.3935. At nine metrics
against 90% bands, roughly one excursion is chance; both excursions point the same way as
the prose-blind `chapters_seen` at 0.308, which is §3's size coupling wearing a prose
metric's name — a below-band excursion read as a finding would be the label separating on a
metric's *length* loading.) Stratifying within follower bands is the only rescue and it
fails — pooled 0.36–0.59, per-band values swinging 0.41 / 0.76 / 0.55. §3's "ρ = 0.438
against raw followers, so it is not popularity restated" holds across the middle of the
distribution and **does not survive a decile split**, which is precisely where §4.4 proposed
to select the reference corpus. And `tricolon_rate` separates the era (0.644) better than
the reader (0.552): §2's lesson, now against the engagement label.

This refutes the label at story-decile grain *with these five counting instruments*; it does
not prove a §4.3 critic would fail, since a critic reads what counters cannot. What it fixes
is the control, and `results/conversion.json`'s own verdict already words it correctly: a
critic scored against conversion **takes the prose-blind baseline as a covariate from line
one** — scored *conditional on* `followers` (within-band, partialled, or as a regression
covariate), never in a raw-AUC horse race against 0.814. The raw bar this paragraph first
demanded is the wrong shape twice over: `followers` is a component of the label's own
numerator, so its 0.814 is partly arithmetic; and a critic could approach a raw bar by
proxying story size while reading nothing. What stands unchanged: the design says which
control it will be scored against **before it is run**.

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

### 4.4 The reference corpus, selected rather than authored — ~~*dissolves §10.6's blocker*~~ *refused: the deciles select size, not prose (§56.3)*

§10.6 asks for "passages that exemplify each item in §1a.3, paired where possible with a
weaker variant of the same beat", and calls it human work. **Selection from the top and bottom
deciles of conversion rate, matched on tag set, era, length and author, is a paired corpus** —
thousands of pairs rather than dozens, and no one writes a word of it.

**Refused 2026-08-17, before anything was selected** ([stage-0-decisions.md](stage-0-decisions.md)
§56.6 item 4: "do not select §4.4's corpus from conversion deciles"). §4.1's run is the
reason: the deciles are recoverable from `followers` at AUC 0.814 and from `chapters_seen`
at 0.308, so a corpus selected from them is paired on story size and era, and a craft
difference between its halves is whatever residue survives that — unknown, and unknowable
without exactly the attribution work selection was meant to avoid. The "what is lost"
paragraph below was written about attribution; the run showed the loss is larger — the pairs
are not known to differ on prose at all.

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
corpus and judge prose" to "someone must obtain two more columns."

### 4.6 Crawling RoyalRoad for those columns — refused, and why

The obvious move is a crawler subproject to fetch per-chapter view counts and reviews. It was
proposed, checked, and **will not be built.** Recorded here so it is not re-proposed, in the
same spirit as §10.6's refuted proxies.

- **RoyalRoad's Terms of Service prohibit it explicitly.** They forbid using "any manual or
  automated system or software, devices, scripts robots, other means or processes to access,
  'scrape,' 'crawl', 'cache', 'spider' any web page", and separately forbid sending more
  requests than a human could produce with a conventional browser, *unless expressly
  permitted*. This is not a grey area to be managed with a polite rate limit.
- **The site is behind bot protection.** A plain request for `https://www.royalroad.com/
  robots.txt` returns HTTP 403. So a crawler that worked would be one that defeated that
  check, which is a different and worse thing to build than a crawler.
- **There is no official API.** Community requests for one exist (`/ideas/482`, `/ideas/1630`)
  and are unanswered, which is also the evidence that the sanctioned route is *asking*.

**The routes that remain open, in the order they are worth trying:**

1. **Ask.** The ToS bars scraping "unless expressly permitted", so permission is the
   sanctioned path and a narrow, research-scoped request — two numeric fields over a
   stratified sample, no prose redistribution — is a reasonable thing to send. It is the
   owner's call to make, not an agent's.
2. **Ask the compiler of `RoyalRoad-1.61M`.** The corpus in hand exists because someone
   already did a collection and published it MIT-licensed. Whether they hold permission, and
   whether they would extend the columns, is one message.
3. **Other platforms, each needing its own ToS check before anything is built.** Wattpad
   exposes per-part read counts, which is the retention curve directly; AO3 carries hits,
   kudos and bookmarks per work. Neither is LitRPG-native, so genre transfer would have to be
   argued rather than assumed — but §4.1's method does not depend on the platform.
4. **Publish, and measure our own.** §16's serialization gives per-chapter retention for the
   system's *own* output, from our own analytics, with no permission needed from anyone. It
   is the slowest route and the only one that is unambiguously ours.

**None of this blocks the critical path, and that is the important part.** §4.1 — calibrating
proxies against `followers / total_views` — runs on the corpus already in hand, under a
licence that permits it, today. Per-chapter retention improves the label's granularity from
story-level to chapter-level; it is not a prerequisite for starting, and treating it as one
would be this document reintroducing the blocker it was written to remove.

### 4.7 Per-chapter comments via the Wayback Machine — collected, measured, refuted

§4.5 names per-chapter retention as the single most valuable missing column and §4.6 refuses
a RoyalRoad crawler. A **Wayback** collection is a different act from crawling royalroad.com,
and it was built (`C:/DEV/BookCrawler`) and run against Mother of Learning. This section
records what it produced and why the signal does not survive its own control, so the route is
not re-proposed on the strength of how promising it looks.

**The count is free, exact, and complete.** Royal Road prints each chapter's comment total on
the chapter page (`Comments(226)`), which the crawl already fetches for the prose. Recovered
for **108/108 chapters, 0 failures**: 8,849 comments, median 58, max 883 (the afterword),
then 398 (ch102 "Giants") and 367 (ch106 "I Win (III)"). This is the project's first
complete, uncensored, chapter-granular human-response measurement.

**It is not worth having, and the control is what says so.** Computed in one pass:

| | rho vs comment count | t |
|---|---|---|
| chapter position | +0.1606 | +1.68 |
| **capture date** | **+0.4284** | **+4.88** |
| word count | −0.0333 | −0.34 |
| partial: position \| capture date | **−0.0447** | −0.46 |
| partial: capture date \| position | **+0.4044** | +4.53 |

Position explains nothing once capture date is held; capture date explains plenty once
position is held. The number measures **when the archive looked**, not what readers did — a
page captured in 2024 has accumulated more comments than one captured in 2021, and Wayback
captured this book across 25 distinct dates. It is the `tricolon_rate` lesson in a third
costume, and the permutation null agrees the headline was never there: p = 0.098 at n=108,
and dropping the ten largest chapters turns it *negative* (−0.0511).

**Both rescues fail.** Within-capture-date strata: 5 strata with n≥8, pooled rho = +0.2228
(t=+1.69, n=62) against a minimum detectable effect of 0.3494 — undetermined, not answered,
and three of the five strata span only 8–10 chapter positions so they could not have detected
a position effect anyway. Exposure-adjusted rate (comments per day from publication to
capture) looks like the finding: rho = +0.2641, and +0.3151 partialling capture date,
t=+3.40. **Its mechanical null refutes it.** Exposure is `capture − published`, and
rho(exposure, position) = −0.5668, so dividing by exposure injects position by construction:
a *constant* comment count would produce rho(rate, position) = **+0.5668**. Observed is
+0.2641 — below its own null. There is no positive position effect on the rate.

**What the route did establish, and it is a correction rather than a finding.** The paginated
comment crawl that preceded this recovered 60 pages of 422 and exported 48 chapters as having
**zero** comments. Those 48 chapters hold **39.1% of all comments** in the book (median 56,
max 367); 42 of them were lost to the crawler's own TLS throttling rather than to archive
gaps, and a CDX probe found captures for 14 of 14 checked. Coverage is 105/108, not 60/108.
Two further measurements from that pass are worth keeping: comment-page archival coverage by
follower band is 0/16, 1/16, 1/16, 4/16, 9/14 (AUC 0.889) against a general-archival control
of AUC 0.969 — so a multi-story comment corpus below ~1,500 followers is not obtainable — and
`comments_unique` carries no volume information at all, being exactly 10 top-level comments
for all 60 covered chapters by pagination.

**The comment *text* is the part still worth reading.** Hand-coding a 209-comment stratified
sample: 14.4% [10.2–19.8] carry craft judgment attributable to something in that chapter, and
7.7% [4.8–12.1] both name a dimension and evaluate it. Sign is recoverable in 29 of 30 cases,
and the self-selected-fan worry is refuted — negatives are 30% of located craft judgments,
not a missing class. But the absolute volume is ~18 hand-confirmed negative craft judgments
across 15 chapters, against `MIN_HOLDOUT = 50`, and the block is doubled in code:
`promoted_gate` demands a `verdicts_digest` content-addressed over `store.audit_samples()`,
keyed `sha256(revision_id, logical_id)`, so reader comments on someone else's published book
cannot enter the calibration set at **any** volume. Collecting ten more stories fixes the
first block and not the second. Its use is **vocabulary** for a located-complaint producer,
which is §4.1's neighbour rather than its substitute.

## 5. Consequence for the plan

- §1a.4's "human judgment is the only ground truth" **stands**, with the solicited/revealed
  distinction made explicit.
- §10.3's weekly sessions are **demoted from the primary instrument to a cheap confirmation
  sample**. §10.5's standing audit (built, `litharness audit`) is the right size for that:
  it collects judgment as a by-product of operation rather than as a scheduled event.
- ~~§10.6's hand-authored corpus is no longer the gating item; §4.4 supplies a selected
  one.~~ §4.4 is refused (§56.3, §56.6 item 4): conversion deciles select story size, not
  prose. §10.6's corpus question is open again.
- ~~The new critical path is §4.1 and §4.2, both of which are engineering.~~ §4.1 ran and
  refuted its own label at the decile grain. What remains live from this document: §4.2
  under its stated Goodhart constraints, §4.7's comment-text vocabulary, the §4.6
  acquisition routes — and any future §4.3 critic inherits §4.1's covariate control as a
  precondition, stated before it runs.
