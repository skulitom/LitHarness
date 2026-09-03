# Pre-registration addendum — the anticipation probe's paid run

**Registered 2026-09-03, before any call**, as the fourth experiment of
`plan/handoff-reader-sims.md`. The instrument and its kills are already registered:
`plan/anticipation-probe-validity.md` (stage-0 §124) and the frozen bytes in
`research/quality-measurement/anticipation.py`, whose `registration_digest()` is printed
into the result. Nothing there is edited. This file adds only what a paid run owes under the
handoff's rules — the model, the ceilings in dollars and calls, the abstention rules, what a
null looks like — and records one plumbing defect the free legs found and fixed before spend.

## The run

- **Reader:** `claude-haiku-4-5`, the module's default and the house's panel tier, through
  the `claude -p` transport with the two hardening flags (§109). Four personas
  (`personas.GENRE_PANEL`: `climber`, `stranger`, `regular`, `mechanism`), untouched.
- **Substrate:** the ten drafted toll scenes in `corpora/toll-scenes.json` (own prose,
  un-memorised, at least 500 words), the committed export and not the gitignored store.
- **Shape:** 10 passages x 5 arms x 4 personas x 4 draws = **800 calls**, the registered
  shape, inside the module's 1,000-call guard.
- **Ceiling:** **$30** subscription-equivalent, read from the replay cache's own usage
  between cells and stopped there, every cell bought kept, a stopped run stamped partial
  (`stopped_at_ceiling`). The module had a call guard and no dollar ceiling; the ceiling is
  added to the driver's loop and to nothing registered.
- **Cache:** `research/quality-measurement/results/anticipation-raw.jsonl`, digest-keyed with
  the draw index beside the digest, so a rerun replays free.
- **Result:** `research/quality-measurement/results/anticipation.json`, carrying the
  registration verbatim, its digest, the spend and the kill table.

## Abstention rules

- A draw that does not parse as exactly three `{outcome, stance}` objects is unanswered; a
  cell with fewer than two answered draws is unscorable (the one-draw trap the module names)
  and is reported, never filled.
- `transport_failures` is read before the kill table; a run whose failures are more than one
  in twenty planned calls is reported as under-run, with the count, before any verdict.
- The kill table is computed over scorable cells only, as the module does.

## What null looks like, and it is a result

K1 KILL: the five arms' mean specificity spans less than 0.05 — the probe is a constant
function. K2 KILL: the destake effect does not clear the largest sham's by 0.05 on either
measurable — the probe reads edited-ness. K3 KILL: matched deletion moved the probe as far as
destake did — the deletion did the work. K4: reported, never gated. Any KILL closes the probe
as registered; a run with every kill passing licenses a located diagnostic on the operator's
side of the loop and nothing else (`plan/anticipation-probe-validity.md` §6).

## The defect the dry run found, fixed before any call

`--dry-run` raised on its second cell: `ablate`'s sentence-level transforms (`destake`,
`deplete_matched`) rebuild a passage with single newlines between paragraphs, and
`stop_point` splits on blank lines, so every damaged arm arrived as one paragraph and the
registered cut had no future to leave. `_arm_text` now puts the paragraph separator back to
the convention the original carries — the same paragraphs, the same words, the stop rule
unchanged (`tests/test_anticipation.py::test_a_damaged_arm_keeps_the_paragraph_convention_the_stop_point_reads`).
The registered constants and the measurables are untouched; the dry run now prints every arm's
stop point at its own 60%.

## What may not follow

Nothing here feeds a prompt (§97.1). No bar over any rate. No reader is retuned. A pass makes
the probe a candidate for the reader-architecture proposal the handoff's fifth item asks for,
and a candidate only.

## Addendum, 2026-09-03: a second plumbing defect found before spend

`--out` was resolved under `results/` at the write and `--cache` was handed to `Path()` bare,
so the replay cache of an 800-call run would have landed in whatever directory the run was
launched from while its result file landed under `results/`. Nothing would have failed; the
substrate of a paid run would simply have been somewhere nobody would look for it, which is
the `toll.db` shape `RUNBOOK.md` opens with. The default is now the absolute
`DEFAULT_CACHE = results/anticipation-raw.jsonl`, an explicitly passed `--cache` is taken as
typed, and `tests/test_anticipation.py` pins it. No cache existed when this was found, so no
record was invalidated and no measurable moved.
