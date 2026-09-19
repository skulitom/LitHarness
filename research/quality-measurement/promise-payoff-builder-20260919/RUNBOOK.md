# Promise/payment test construction

This is call-free engineering authorized by the operator on 2026-09-19. It builds research
materials from immutable manuscript snapshots. It does not change a book or run a reader.

## What the builder certifies

The existing promise census establishes uniquely located opening and payment quotations.
It does not establish that the summarizer's relation is correct or that the payment quotation
is the only evidence of fulfilment. Automatically treating a removed quote as an unpaid promise
would silently promote a model-sourced annotation to an independent semantic answer key.

This first implementation therefore certifies **registered evidence availability**, with four
conditions: unchanged passage, payment paragraph withheld, a matched other paragraph withheld,
and a whitespace-only placebo. The only Boolean key is whether the registered payment quotation
is present. No construction labels a book's promise unpaid or its prose worse.

The other-paragraph deletion is a matched withholding control, not a claim that deleting that
paragraph is semantically harmless. The whitespace condition is the genuinely content-preserving
control. Both distinctions are explicit in the report and private keys. Construction readiness
and eligibility for a model experiment are separate; the latter remains false.

## Admission and controls

- Read only an existing schema-current store. Take a consistent SQLite backup, including WAL
  state, then read that snapshot. Refuse absent stores, pending migrations and existing outputs.
- Require a paid ledger row, uniquely located current opening/payment hashes, live scene anchors,
  consistent story positions and opening before payment.
- Retain every complete scene from the opening scene through the payment scene. Missing scenes
  and contexts above the character ceiling are rejected, never silently cropped. A future model
  arm must separately preflight its actual tokenizer and context limit.
- Require each reference quotation to occur exactly once in that complete window.
- Remove the complete paragraph containing the payment, leaving every other character unchanged.
  Reject a payment that crosses paragraphs, or a target paragraph overlapping another stored
  opening, payment or located state reference. Single anchors of otherwise incomplete promises
  are protected too.
- Choose a donor paragraph in the same payment scene, outside all located references. Match the
  six existing edit fields: token, sentence, punctuation and whitespace deltas, position decile
  and anchor distance. Choose the nearest match, breaking ties by source position. No match means
  refusal, not weaker matching. Report character-length differences; these are not yet controlled.
- Preserve the opening quotation in every condition. Preserve the payment quotation exactly once
  in three conditions and zero times after its withdrawal. Reflow paragraph separators for the
  whitespace placebo and verify unchanged token sequence.
- Derive identities from inputs and edits. Emit a flat, deterministically shuffled-by-hash set of
  public packets containing only opaque presentation ID, opening quotation and passage. A future
  reader receives one packet at a time, never the sibling set or private file.
- Keep the full reference spans, condition labels, source map and paragraph offsets in a separate
  private file. The committed report contains numbers, IDs, hashes and refusal reasons only.
- Carry an explicit whole-book/world group. Branches and scenes from the same world must never
  be treated as independent holdouts. Only one transformation implementation exists in this pass.

## Reproduction

Coordinate checks and construction with `runs/box.lock` as the parent research runbook requires.
No provider, API key or GPU is needed. Keep snapshots and manuscript-bearing packets under
ignored `runs/`. The default context ceiling is 400,000 characters; it is not a model capability.

```powershell
uv run pytest tests/test_promise_payoff_builder.py -n 0
uv run python research/quality-measurement/promise_payoff_builder.py --database runs/full-book-trial-20260919/readout-frozen/book.db --source-group full-book-trial-20260919-A1 --out runs/promise-payoff-builder-20260919/book
uv run python tools/check.py handoff
```

The completed book is development material: its evidence has been inspected while designing
the builder. Do not later relabel it a held-out book. No model experiment or quality bar is
registered here. A later arm needs independent semantic validity and alternative-evidence checks,
edit-shortcut controls, held-out books and transformations, and a frozen task and scoring rule.
