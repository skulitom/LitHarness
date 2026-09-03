# Pre-registration — does the sim predict the real readership's continuation on a book it has never had readers for?

**Status: REGISTRATION, 2026-09-03** — no paid call, no post, no fetch. Every slot below is
filled from a free run where a free run can fill it, and named empty where the book does not
yet exist. Nothing here may be edited after the first prediction is committed, and an edit
forced by an error must name the number it had seen (the K1a form, as the sim-readership
backtest keeps it). Stage-0 §221 is the decision this registers; `plan/handoff-evaluator-
boundary.md` is the brief.

**The question.** `research/sim-readership-backtest/` asks whether a simulated readership,
reading blind and stopped part-way, *post-dicts* which of two real Royal Road books the real
readership stayed with, on held-out pairs. This asks whether the same readership *predicts*
the real readership's continuation on a book it has never had readers for — the one this
repository writes and the operator posts by hand. A well-predicted mid-performing serial is a
strong result for the instrument; a badly-predicted hit is a weak one. **The book's rank is
not this programme's success criterion**, and no number below is a claim about the book.

## 1. Unit and the outcome the sim can see

**Unit of analysis: one chapter transition of one serial** — chapter *k* to chapter *k+1*, for
the chapters the release queue records as `posted` (`release_queue`, migration 039), in
chapter order. One serial, one author, one platform account: there is no between-book
variance here and no claim is made across books.

**Outcome: per-chapter continuation, `r_k = views(k+1) / views(k)`**, from the per-chapter
view counts the author dashboard shows and nothing else. It is the platform's own count of
readers who reached the next chapter given they reached this one, which is the behaviour the
sim is asked for (§97.4's *continue*) at the grain the sim answers (a chapter).

**Declared non-outcomes, each because the sim never saw what moves it:** total views,
follower count, favourites, rank, rating, average views per chapter, and any rising-stars
placement. Those measure discovery and the tag filter — the listing, the cover, the title,
the posting time, and the AI-Generated content warning's audience effect (§104 verified the
tag is mandatory policy). **The confound is declared and not fitted.** It enters every
transition as a change in *who* reaches chapter 1, and it does not cancel within a serial if
the audience it selects continues differently; the registration states that and models
nothing.

## 2. The prediction, and the rule that makes it one

For each chapter *k* in the planned release window, the prediction is the evaluator port's
record (`application/instrument.py`, `Readout`) on the approved pastable copy at its fragment
hash (`release_queue.fragment_sha256`), read by the LitRPG pack's declared measurement roster
(`packs/litrpg`, four readers), stopped at the registered fraction (`domain/text.stop_point`,
§124), **K = 4 draws per reader per arm** (the comic-beat census measured a one-draw locator
at 0.54, so four is that lesson applied), two arms:

- **primary arm — a named alternative**: `CurrencySpec(budget_chapters=2, rival_title=…)` with
  the rival drawn from the operator's admitted pool by the content key the pipeline uses
  (`rivals.draw`), one per reader — the instrument as it has stood since 2026-08-26, where
  continuing costs something (§134);
- **control arm — no alternative**: `CurrencySpec(budget_chapters=2)`, the arm every reading
  before 2026-08-26 measured; reported beside the primary, never pooled.

**`p_k` is the share of answered readers whose behaviour was `continue`** over the arm's
sixteen answers, with the record's under-run beside it; a chapter with fewer than twelve
answers in an arm has no prediction in that arm and is counted as missing.

**Commit before chapter 1.** The predictions for the whole window are computed and committed
content-addressed — `predictions-<sha256>.json`, carrying each chapter's `record_id`,
`fragment_sha256`, `p_k` per arm and the transport failures — **before the first
`record-posted`**. A prediction made after a chapter has readers is not a prediction. The
driver that computes them (`driver.py`, owed, see §9) refuses by timestamp: a prediction
whose commit is later than the chapter's `posted_at` on the release queue is excluded from
the primary and counted as `late`. A chapter re-drafted after its prediction (a new fragment
hash on the queue) has no prediction and is counted as `moved`.

## 3. Data collection — operator-exported, hashed on ingest, nothing fetched

Dashboard snapshots are exported by the operator by hand at a **fixed weekly cadence** (every
seven days, tolerance one day) from the first post until four weeks after the window's last
post, saved locally, and ingested by the driver, which records the sha256 of the raw export
and commits **derived numbers only** beside the predictions: `snapshots/<date>.json` with
chapter number, views, the snapshot date, and the raw file's hash. The raw export stays
local. A missed snapshot is recorded as missed. **No live fetch, no scrape, no script against
royalroad.com**: the Terms prohibit it and a banned account ends the test.

`r_k` is read from the **final** snapshot, so every transition has had at least four weeks to
settle; the earlier snapshots are the record of how it settled and feed §6's trend check.

## 4. Attainability at the real n, before any bar

A serial of *W* posted chapters has *W − 1* transitions. Measured by a free permutation run
(`plan/handoff-evaluator-boundary.md` records the script; seeds fixed at 20260903 + n):

    n_transitions  critical |rho| at alpha 0.05   type-I of "bootstrap LB > 0"   power at rho = 0.5
                 (20,000 permutations)           (400 null worlds)               (400 worlds)
               8            0.786                        0.037                        0.255
              10            0.709                        0.022                        0.370
              12            0.650                        0.022                        0.410
              16            0.562                        0.013                        0.593
              20            0.502                        0.022                        0.693
              24            0.454                        0.040                        0.790
              30            0.410                        0.033                        0.885
              40            0.354                        0.035                        0.975

Read it before the window is chosen: at ten transitions the sim has to rank-correlate at
0.71 to be seen at all, and a true 0.5 is seen about a third of the time. **The window is an
empty slot** (§10); whatever length the operator posts, the row above it is what the test can
and cannot detect, and a null at a short window is a statement about power before it is a
statement about the sim.

**Direction:** positive — a higher predicted continuation share goes with a higher observed
retention ratio. **Independent unit:** the transition; adjacent transitions share readers, the
bootstrap resamples transitions and understates that dependence, and the caveat travels with
any number. **Non-empty subgroup:** transitions with `views(k) >= 30`, the exposure floor — at
thirty readers a retention ratio of 0.7 carries a binomial standard error of about 0.08, and
below that the outcome is noise the sim cannot be graded against. If fewer than **ten**
transitions clear the floor (the backtest's `MIN_OUTCOMES` precedent), the registered verdict
is **INSUFFICIENT_EXPOSURE** and it is a result: the serial found too few readers for the
instrument to be tested on it.

## 5. Primary and the decision rule

**Primary:** Spearman rank correlation between `p_k` (primary arm) and `r_k` over the
transitions with a committed, on-time prediction and an observed transition above the
exposure floor, with a **transition-resampled percentile bootstrap interval** (2,000
resamples, seed content-derived from the paired vector, the backtest's discipline), alpha
0.05, one candidate, no division.

**SUPPORTED iff** the interval's lower bound clears 0 AND the exposure floor left at least ten
transitions AND no VOID in §6 fired. **A null — the interval containing 0 — is the result**
"the sim did not predict this serial's continuation at this window", written up in
`FINDINGS.md` in the house form whatever it is. Neither outcome is a claim about the book.

Secondary, exploratory, labelled: the control arm's correlation beside the primary's; the
share of transitions where the two arms disagree on direction; `p_k` against days-since-post.

## 6. Controls, each with its registered condition

- **Constancy (free, before posting).** If the primary arm's `p_k` spans less than **0.05**
  across the window (the anticipation probe's K1 line, §124), the instrument is CONSTANT on
  this serial and the primary is not computable: **VOID**, reported as such. A constant
  prediction cannot correlate with anything and must not be scored.
- **Positional.** Not applicable: one passage in one slot. Recorded as `not_applicable` in
  every record's validity block, never as passed.
- **Recognition.** The passages are this repository's own prose, generated after every
  panel model's documented cutoff, so the readers cannot have read them; recorded as clean by
  construction with that reason, and the record's `recognition` rail says `unprobed` rather
  than `clean` because no probe ran (the pilot's fix, FINDINGS).
- **Label shuffle (free, once the outcome exists).** `r_k` shuffled across transitions 200
  times, seeds content-derived; if the primary's rule clears 0 on more than **3 × alpha / 2 =
  0.075** of draws, the analysis leaks the label and everything is **VOID**.
- **The exposure trend, declared.** `views(k)` falls with *k* on every serial because later
  chapters have had less time; `r_k` is read after four weeks of settling, and the residual
  time-since-post effect is reported as the secondary in §5, **never subtracted**.
- **Sham.** No same-text sham pair is read for the launch; the rail is recorded `not_run`. A
  sham floor for a single-serial design is a second registration, not a line here.

## 7. Cost and staging

The predictions cost *W* chapters × 2 arms × 16 calls on the pinned provider — at most
**1,280 calls for a 40-chapter window**, subscription-equivalent, and none before the
operator's go on the prediction run. **Ceiling: W ≤ 40** for this registration; a longer
serial predicts its first forty and reports the rest as unregistered. No paid call is made by
this registration, and the driver refuses to compute a prediction without a commit citing the
go (the backtest's one-bit gate, in code).

## 8. What a pass licenses, and what it does not

A SUPPORTED result makes the instrument a **candidate** predictor of out-of-sample
continuation on one serial at one window, beside the backtest's number when that exists —
the written result of stage-0 §221's slice 3, in the BRIEF's house form. A null is the same
kind of result with the other sign. **Neither licenses anything about the book**, and
nothing from the launch reaches generation, planning, selection, calibration or any gate
(§126): no real-reader number is ever rendered into a prompt, a plan, a selection or a
threshold, and the driver has no write path into the store.

## 9. The code owed, named so slice 2's sequel builds exactly this

`research/launch-outsample/driver.py`, not built here: compute the two arms' records through
the port for every approved chapter on the queue; write `predictions-<sha256>.json`; refuse
any prediction later than its chapter's `posted_at`; ingest a dashboard export by hash into
`snapshots/`; compute §5 and §6 from the committed files with no live call. Its tests are
hermetic on the fake provider. It runs under `uv run` and touches no corpus.

## 10. Empty slots, named

- **W, the release window**: filled when the queue holds the window (`litharness release show`).
- **The serial**: book id, branch id, and every chapter's fragment hash — filled at the
  prediction commit.
- **The panel provider and model at run time**: recorded in every record's `transport` and
  `model`.
- **The rival pool's digest**: the operator's admitted pool at prediction time.
- **The snapshot dates**: fixed to the first post's date plus seven-day steps once it exists.

## 11. Anti-scope

No review, comment, rating, forum post or message is ever authored by the system — Royal
Road's guidelines confine AI text to chapter pages. The serial's only acquisition loop is the
platform's own (listing, cover, cadence, follows) plus the author-note disclosure that names
the repository. The tool never posts: `record-posted` is the operator saying so afterwards.
No human judgment is solicited anywhere in this programme (§95); real readers' aggregate
behaviour is §126's instrument-grading data and nothing more.
