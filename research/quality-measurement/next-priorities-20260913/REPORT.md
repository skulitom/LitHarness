# Four priority tests: a goal contrast, six chapters, and two remaining boundaries

## Results

**State: OBSERVED.** All four goal assignments and the fixed continuation through
Chapter 6 completed. The scoped clarification avoided the homeward goal proposal
in the conditional case while preserving it when explicitly adopted. The book
earned and spent two points on different upgrades. A separate deterministic
diagnostic confirms that the current ceiling prevents a second investment in Load.
The payoff-deletion construction produced no verified semantic test pairs.

This is isolated evidence. The candidate clarification was not installed in
production, and the continuation used the unchanged baseline instructions. No
reader mechanism was called, qualified, or allowed to steer a book.

Registration was committed and pushed as `fa58c9e` before any model call. The
baseline is the earlier frozen `b774e6c` production source. The live run took
1,227.5 seconds, used fourteen distinct native sessions and 1,542,801 reported
input-plus-output tokens, and completed within the registered ceilings. Exact
controls and identities are in [evidence.json](evidence.json); all its provenance
controls pass, including original-input preservation, containment, attribution,
whole-scene hashes for construction inputs, and preservation of earlier chapters.

## Goal boundary

Each case began with the same Chapter 1 world readout, reconstructed from its
accepted record identities and original declaration times. The fixtures contain
empty manuscript placeholders; they do not reconstruct the original drafting jobs
or manuscript history. The model received the recorded Chapter 2 grow request.
The adopted variant replaces only the two located possibility paragraphs; the
clarified variant appends one general instruction about established desires and
adopted pursuits. Exact experimental prose remains under ignored `runs/`.

| Instructions | Passage | Observed new Wren goal proposal |
| --- | --- | --- |
| Current | Original conditional thought | Includes seeking a possible way home |
| Clarified | Explicitly adopted homeward pursuit | Retains returning to Earth and seeking the other arrival |
| Current | Explicitly adopted homeward pursuit | Retains returning to Earth and seeking the other arrival |
| Clarified | Original conditional thought | Continues along the ledge and records observations; no homeward pursuit |

All four resulting world checks pass with no unplaceable records. These new goals
remain proposals in the fixtures; there was no acceptance step. The earlier
production run separately records the original promotion into accepted canon.
The positive cases matter: the clarification did not merely suppress every new
goal. With one observation per cell on one chapter, this does not establish a
general accuracy rate or transfer to other kinds of thought and desire.

The new goal identities and exact declaration locators are in
`evidence.json.goal_cases` and `calls[].goal_declaration_locators`. Full values,
requests and receipts are under the four named case directories in
`runs/next-priorities-20260913/`. The general clarification is in that root's
`goal-input.json`; production source is unchanged.

## Continuation and numerical investment

The original three-chapter store was copied with SQLite's read-only backup API.
The existing plan continued through ordinary tick, extraction, reconciliation,
check and acceptance. Every new chapter was read in full. Earlier chapter files
retain their hashes at all checkpoints, and final revisions are attributable.

| Boundary | Accepted progression state | Located continuation behavior |
| --- | --- | --- |
| Chapter 4 | Rank 1, Load 1, Point 0 | New tests earn a point; it is spent on Load. The next writer's actual request carries these values. |
| Chapter 5 | Rank and investment retained | Load suffices for the attempt, but the seam expires before the paste sets; the catch limits the failure. |
| Chapter 6 | Rank 2, Load 1, Duration 1, Point 0 | A new point buys Duration. The display gives a longer holding window, and the chapter uses it in the restoration. |

The visible mana sequence also continues: Chapter 4 ends at 20, Chapter 5 at 15,
and Chapter 6 at 5 after two further casts. This is a located reading of these
chapters, not a claim that every magical constraint has been independently tested.
The rank, holdings and spent-point values above are present in accepted world
snapshots and edges, rather than only in the prose.

**Two different purchases do not exercise repeated deepening of one capability.**
The separate [ceiling diagnostic](progression-probe.json) was designed after
observing Chapter 4 and is explicitly not a preregistered live outcome. It reads
the real Chapter 4 sheet, then makes only immutable in-memory counterfactuals:

| In-memory condition | Point balance | Second Load investment | Duration acquisition |
| --- | ---: | --- | --- |
| Actual Chapter 4, maximum 1 | 0 | Unavailable | Unavailable |
| Next rank granted, same maximum 1 | 1 | Unavailable | Available |
| Same funded sheet, maximum changed to 2 | 1 | Available; gives Load 2 and Point 0 | Available |

This isolates the ceiling as sufficient to block the second Load investment even
when funds are available. It does not establish maximum two as the right production
representation. Ownership-only capabilities and declared repeatable investments
still need compatible semantics. No store, accepted event or production scale was
changed by this diagnostic.

## Reader-test construction

The frozen earlier admission cohort supplies 54 promise/payoff relations across
five book IDs. The construction probe removes each exact payoff quotation and
searches for a non-overlapping sentence deletion with the same shallow fingerprint,
including edit position. Only two relations supply any match, with three matching
sentence deletions between them. Candidate texts stay private; identifiers and
counts are in [probes.json](probes.json).

None of these mechanical matches has independently verified semantic damage or
harmlessness. The focused adversarial regression constructs a uniquely located
payoff plus a differently worded realization. Deleting the keyed quotation leaves
the payoff realized, even with a matched shallow edit beside it. Unique quotation
and matching edit dose therefore do not certify that the payoff was removed.

This rejects exact-quotation deletion as a sufficient construction rule. It does
not refute promise/payoff testing as a family or measure reader sensitivity. The
next construction needs an independently checkable semantic relation and a
verified harmless control, plus the registered book and transformation holdouts.
No reader calls or quality qualification follow from these candidate counts.

## Architect cost

Keep the goal fixtures separate from production continuation when interpreting
cost. The four fixture reconciliations and their initial health call used 689,656
tokens. The three new production chapters used 853,145:

| Continuation profile | Calls | Reported tokens |
| --- | ---: | ---: |
| Drafting | 3 | 99,136 |
| Mechanical extraction | 3 | 23,278 |
| Architect reconciliation | 3 | 730,731 |

Reconciliation accounts for about 86% of continuation tokens. Its 45 queries
(44 scoped and one unscoped first page) returned 228,993 UTF-8 bytes and 617
record payloads. Within individual
calls, 57 returned payloads repeat exactly; their canonical serialized size is
17,125 bytes out of 177,290 record bytes. No complete query/result pair repeats
exactly. Vocabulary replies add 43,341 bytes across the three grow calls;
declaration-batch replies add 41,229 bytes.

The native envelopes report 605,952 cached input tokens across continuation.
Reported tokens, cached input tokens, tool bytes and dollar cost are distinct;
these measurements do not establish savings from a particular optimization.
They locate reconciliation and its sequence of scoped reads as the next place to
measure. Exact-query caching alone has no repeated query/result pair to remove in
this sample. Per-call data and all earlier baseline reads remain in `probes.json`;
the live auditor records per-tool payload sizes in `evidence.json`.

## Validation and reproduction

Eight focused experiment regressions pass, including controlled request changes,
pre-call ceilings, usage-envelope validation, the semantic-deletion counterexample,
and import isolation from other experiments. The initial full suite exposed the
helper's generic `run` import collision. It was corrected before registration;
preflight manifests and failed-check logs are preserved locally. The final
registration handoff passed 5,040 tests, with 20 skips and 89.86% branch-aware
coverage, plus lint, types, lock/diff validation, wheel build and corpus-history
audit. The operator's unrelated precision changes remain outside the experiment.
The result handoff also passed; its complete log is
`runs/next-priorities-20260913/handoff-final.log`.

Rebuild the derived results after live completion:

```powershell
runs/world-fixed-continuation-20260913/runtime/Scripts/python.exe research/quality-measurement/next-priorities-20260913/audit.py
runs/world-fixed-continuation-20260913/runtime/Scripts/python.exe research/quality-measurement/next-priorities-20260913/probe.py
runs/world-fixed-continuation-20260913/runtime/Scripts/python.exe research/quality-measurement/next-priorities-20260913/progression_probe.py
uv run python research/quality-measurement/epistemic_governance.py research/quality-measurement/next-priorities-20260913/claim.json
```

The complete six-chapter reading copy is
`runs/next-priorities-20260913/continuation/library/world-boundary-probe-1/world-boundary-probe-1.md`.
The registration and frozen inputs remain unchanged. The post-observation
auditors carry their own hashes in their outputs; they did not influence live
generation or change the registered assignments.
