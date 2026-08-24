# Anticipation-probe validity — does a reader's described future sharpen with the text's grip?

**Status: REGISTRATION, 2026-08-24.** Written before any call. The operator's directive:
stop the reader mid-chapter and have it **describe — never rate** — what could happen next and
which outcomes it finds itself hoping for or dreading. The hypothesis: flat text yields vague,
low-specificity hypotheses and no preference over outcomes; gripping text yields sharp,
concrete predictions with a hope/dread gap. Stage-0 §124 is the intended ledger entry;
`research/quality-measurement/anticipation.py` carries the frozen bytes and the arithmetic.

## 0. Why this can live where verdicts died

Every verdict channel in this project is dead (§70, §86.6, §89.4); the one surviving frame is
the **report channel** — a model describing content, not grading it (§89's E6; §120's
inheritance). The anticipation probe is report-channel by construction: the persona describes
concrete futures and marks its own stance toward each. The stance mark ("hoping" / "dreading" /
"neither") is a self-report of reading experience in behavioural terms, not a quality verdict,
and the schema is closed so no verdict vocabulary can arrive.

One ledger landmine, defused by naming: **"valence" in stage-0 §90–§97 means reader
preference** and may not be reused. The hope/dread measurable is therefore registered as
**stance spread**, and the word "valence" appears nowhere in the instrument.

## 1. The instrument

At the **stop point** — the paragraph boundary nearest 60% of the passage's words — the
passage-so-far is shown to each of the four `personas.GENRE_PANEL` readers (§120.5's panel,
untouched, so its prior numbers stay reproducible). One byte-frozen probe asks for exactly
three concrete things that could happen next, each marked hope / dread / neither. **K = 4
draws** per (passage, arm, persona) cell — the comic-beat census measured a one-draw locator
at 0.54 reliability, and four draws is that lesson applied.

## 2. The measurables, all scored by code

- **Specificity** = grounding: the fraction of an outcome's content tokens (casefolded,
  punctuation stripped, a frozen stopword list removed) that appear in the passage-so-far.
  "Something bad might happen" grounds near zero; "Marrow's forged seal fails at the gate"
  grounds high. Outcomes are scored on their first 50 words. No sentiment lexicon anywhere —
  the machine-taste programme's lexicon-redundancy gauntlet is dodged structurally, not
  survived.
- **Distinctness**: mean pairwise Jaccard distance between the three outcomes' content-token
  sets — three near-duplicate vague guesses score low.
- **Stance spread**: `engagement` = 1 − (neither share over the cell's 12 stance marks), and
  `bipolarity` = whether hope and dread are both present in the cell. Flat text is predicted
  to raise neither-share and kill bipolarity.
- Exploratory, reported and never gated: cross-draw recurrence (the maximum outcome-pair
  Jaccard similarity across independent draws — a gripping text's futures should recur).

## 3. Arms

`ablate` at strength 1.0, nothing invented: `original`; **`destake`** (the stakes-establishing
sentences deleted — the operator's named damage arm); **`deplete_matched`** (the same number of
words from zero-stake sentences — the mandatory control; *the difference between the two rows
is the entire claim*, per `ablate.destake`'s own docstring and the persona-battery rule);
`rename_entities` and `rewhitespace` (the standing sham pair — both reach prose, and rename
leaves grounding intact by design because the outcomes ground against the renamed passage).
Transforms apply before the stop point is computed, so every arm is probed at its own 60%.

## 4. Kill conditions, pre-registered

- **K1 — constancy.** If the five arms' mean specificity spans less than 0.05, the probe is a
  constant function and every statistic below is undefined.
- **K2 — the sham floor**, per sham and never pooled: the destake effect (absolute distance
  from the original's mean) must clear the largest sham's absolute distance by +0.05, on
  specificity or on engagement. A probe that moves as much for whitespace as for stakes is
  measuring edited-ness.
- **K3 — the matched control.** `destake` must sit further from the original than
  `deplete_matched` on the same measurable, or the deletion did the work and the stake reading
  is unsupported.
- **K4 — draw reliability.** Within-cell (across-draw) standard deviation of specificity is
  reported against between-passage standard deviation; a probe whose draws disagree with each
  other as much as passages differ is noise wearing a description, and no direction may be
  read from it (the gate-0 discipline).

No bar over any rate; distributions before bars; a null on every kill is a result.

## 5. Substrate, cost, and what is not run here

Substrate: the toll book's drafted scenes (`corpora/toll-scenes.json`, un-memorised own
prose), passages of at least 500 words. Shape: 10 passages x 5 arms x 4 personas x 4 draws =
800 single-call cells on the standing panel model — inside `CALL_GUARD`, refused without
`--yes`, replay-cached. The paid run is not part of this registration's build; the free legs
(`--selftest`, `--dry-run`) prove the arithmetic and the plumbing first, in the house order.

## 6. What a pass licenses, and what it does not

A pass licenses **a diagnostic**: a located report that a chapter's stop point yields flat
anticipation, printed on the operator's side of the loop (§97.1 — nothing here feeds a
prompt). It ranks nothing, selects nothing, gates nothing, and says nothing about reader
preference — the distance between detecting manufactured flatness and reading taste is three
ledger entries long (§87–§89) and this instrument does not cross it.
