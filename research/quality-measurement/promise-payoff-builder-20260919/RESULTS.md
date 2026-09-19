# Promise/payment builder: construction result

The first builder is implemented and exercised against the completed **The Last Anchorage**
snapshot. It produces actual manuscript windows and separate reference keys, with explicit
refusals. It certifies removal or retention of a recorded payment quotation, not loss of the
story's payoff. No reader or model was run, and the original manuscript was not changed.

## What the completed book supplies

[construction.json](construction.json) is the owning numeric record. Of 52 ledger rows,
48 are marked paid with located opening/payment evidence. The fixed constructor yielded:

| Disposition | Promises |
|---|---:|
| Constructed with matched controls | 3 |
| No matched, unprotected control paragraph | 40 |
| Payment paragraph overlaps other located evidence | 5 |
| Not marked paid | 4 |

Each constructed item has four packets: unchanged, payment paragraph withheld, matched other
paragraph withheld, and whitespace-only. The three items cover adjacent scenes/chapters, a local
arc, and half a volume. Their full windows contain 2, 7 and 19 scenes respectively, ranging from
26,069 to 253,260 characters. All intervening scenes are retained; there is no cropped-context
claim of long-context coverage and no tokenizer-specific fit claim.

The original 48-candidate census is preserved in the
[book readout](../full-book-trial-20260919/readout.json). This result neither overwrites that
historical artifact nor retroactively admits its empty ecological battery.

## Why construction is separate from a reader test

The ledger's summary model supplied the opening/payment association. Unique exact spans verify
where it pointed, not whether its interpretation is right, whether another passage pays the same
promise, or whether deleting a paragraph changes only that promise. In one constructed case the
payment quote sits inside a longer paragraph, so more than the quote is deliberately withheld.
The private key records that full paragraph and its exact offsets.

The matched deletion preserves the registered payment quote and avoids every current, located
state or promise reference. It matches token, sentence, punctuation and whitespace deltas,
position decile and scene distance. This does not establish semantic harmlessness. Character
lengths differ in all three pairs, and their exact deltas are reported, so even the surface
shortcut audit is unfinished. The whitespace-only condition preserves the content.

For these reasons `construction_ready` is true and `eligible_for_model_run` remains false.
No claim about reader accuracy, literary quality, unpaid promises or release readiness follows.
This book was inspected during development and must not become a supposedly unseen holdout.

The next dependency is an independent semantic admission contract for a narrow payoff
transformation, including alternative evidence and collateral effects, followed by shortcut
controls and held-out books/implementations. Increasing the item count by relaxing the current
checks would not meet that dependency. This implementation provides inspectable material and
precise refusal reasons for that work; it does not claim to complete it.

## Reproduction and provenance

The [runbook](RUNBOOK.md) gives the command and exact construction contract. Source snapshot:
`runs/full-book-trial-20260919/readout-frozen/book.db`, revision
`0c1b306d3d401eda38cec60067d131ec6ab4a313367fdcf95c719baf303892a8`.
The source was opened using SQLite `mode=ro`; a consistent backup supplied all reads. The
snapshot SHA-256 matches the frozen full-book readout. Builder and salience-helper hashes,
packet hashes, reference identities, source-group digest and every refusal are in the report.

Manuscript-bearing outputs stay local:

- `runs/promise-payoff-builder-20260919/book/packets.public.json`
- `runs/promise-payoff-builder-20260919/book/keys.private.json`
- `runs/promise-payoff-builder-20260919/book/source.db`

The public file is a flat packet collection without condition labels or sibling groupings;
it is not a model prompt. A future registered experiment must send one packet per isolated
request, enforce token budgets and keep the private keys out of all reader inputs.

The [regression suite](../../../tests/test_promise_payoff_builder.py) exercises source
integrity, ambiguity, context retention, matched edits, protected references, public/private
separation, deterministic identities, read-only WAL snapshots and failure on pending migrations.
