# Fixed-pipeline baseline: bounded attempt stopped

The registered three-book, three-chapter baseline did not complete. The frozen pipeline
produced three accepted chapters across two books before its stopping rules ended the batch.
No book was rerolled or revived, no prompts were changed, and no failed book was replaced.
The registration remains unchanged. [results.json](results.json) owns the derived counts,
artifact hashes, transport diagnostics, and verification outcomes.

| Slot | Book | Accepted chapters | First stop |
| --- | --- | ---: | --- |
| 1 | The Sea Needs Mending | 2 of 3 | Daily token ceiling before the third drafting attempt |
| 2 | Where the Water Hangs | 1 of 3 | Provider containment rejection during the first reconciliation |
| 3 | Not started | 0 of 3 | Registered global stop after the provider failure |

The run lasted 2,164.2 seconds. Its 40 native attempts include 39 returned results and one
rejected response. The frozen progress ledger records 1,157,033 tokens from returned results.
The rejected response's retained native trace reports another 149,736, for 1,306,769 observed
native tokens in total. These totals include cached input and are not dollar charges or counts
of newly generated manuscript tokens. Failed-response usage is reported separately rather
than silently rewriting the frozen ledger.

## Located engineering findings

Book 1's parked `scene_draft` job had zero attempts. Its stored budget error reports 855,327
application-ledger tokens already spent, against a 700,000 daily ceiling, before a projected
47,500-token call. The runner's broader total includes discovery/health work outside that
ledger. World seed and reconciliation consumed 732,514 of its 874,276 returned tokens.
An in-flight reconciliation exceeded the registered bound, as the registration anticipated.
The pilot budget was too small to establish three-chapter continuation for this book.

Book 2's rejected trace is
`book-2/transport/attempt-902d98e3f0914431b637a91cd86b6d85.json` under the ignored run root.
The native model called `codex/list_mcp_resources` and `codex/list_mcp_resource_templates`;
both completed with empty inventories. The bridge contract permits only
`litharness/litharness_command`, so this is a real boundary violation, not evidence of a
false-positive guard. Validation rejected the response after native execution. Earlier world
declarations in that attempt remain proposed; the runner did not accept them or continue.

The retained traces also locate a cost question without proving an optimization: Book 1's
two reconciliation calls made 26 and 50 individual `world declare` calls, respectively,
although `declare-batch` is available. Batching and narrower returned context are candidates
for a separately tested engineering change; this pilot does not establish their savings or
equivalence. Containment should stay strict.

## What the manuscript records establish

The accepted texts contain 3,847 and 1,982 words respectively. Final revision verification
reported no unattributed revisions in either book. Book 1's earlier chapter hash stayed
unchanged through its second checkpoint. Frozen source and registered file hashes still match.
Book 2 has only one accepted chapter, so it supplies no between-chapter preservation test.

The two default-brief draws share a protagonist name and conspicuous water-repair material.
That is a located observation about these outputs, not an estimated diversity rate. The first
book's second chapter continues its station investigation and uses the previously acquired
capability; the second book's opening keeps its rescue goal active. These readings supply
neither quality labels nor production feedback. Short accepted continuations do not establish
long-serial endurance or improvement over another pipeline.

## Related work and next decision

The [historical screen audit](../volume-screen-audit-20260910/REPORT.md) reconciles saved
feasibility records but leaves historical provenance incomplete. The
[causal admission census](../causal-reader-admission-20260910/REPORT.md) found no usable
state-continuity manipulation items, so no subtler reader-validity arm was bought.

The next engineering work should address unnecessary native tool exposure and profile world
declaration/context costs, then register a newly budgeted continuation attempt. A reader arm
still needs a valid, non-empty manipulation substrate and its own attainable held-out design.

Rebuild the numeric report from the retained local artifacts with:

```powershell
.venv/Scripts/python.exe research/quality-measurement/continuation-baseline-20260910/report.py
```

Complete requests, responses, book databases, reading copies, and failure records remain in
`runs/continuation-baseline-20260910/`. They are not reconstructible from this committed report
alone. No production code changed in this experiment; the pre-existing precision edit was
excluded from its frozen runtime and remains another session's work.

Final validation passed the repository's `handoff` check and separate helper lint/format checks.
Offline replay reproduced the containment rejection. Injected raw-budget, raw-action, and
ledger-usage errors were each detected by the screen audit. Validation logs and the machine
readable check receipt remain beside the run; no live-provider tests were enabled.
