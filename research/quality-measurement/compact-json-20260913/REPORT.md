# Compact replies preserve data; the fixed token comparisons disagree

**State: OBSERVED.** All four registered grow calls completed and retained the
conditional/adopted goal distinction. Every native-visible tool result matches its
expected receipt. Compact stdout is smaller, but reported token usage falls in one
pair and rises in the other. The implementation remains opt-in, with the production
default verbatim. This study does not establish a general cost saving or literary
quality result.

The [registration](RUNBOOK.md), scripts and tests were committed and pushed in
`254d7ae` before calls. Both formats used frozen production `991ff2c`, the same
pinned native executable and dependency inventory, identical initial world
readouts, and byte-identical requests within each pair. The fixed order was
verbatim conditional, compact adopted, compact conditional, verbatim adopted.
There was one first output per cell and no reroll or acceptance step.

## Native usage and reply size

These are reported input-plus-output tokens, including cached input, not dollars.
The [registered audit](evidence.json) retains each native usage envelope, session,
receipt hash and individual command's original and visible byte counts.

| Source | Format | Total tokens | Cached input | Output | Seconds | Tool results | Visible stdout bytes |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Conditional | Verbatim | 175,484 | 143,488 | 1,817 | 79.43 | 12 | 56,852 |
| Conditional | Compact | 164,606 | 133,120 | 2,008 | 81.76 | 15 | 47,177 |
| Adopted | Verbatim | 166,939 | 130,176 | 1,999 | 85.80 | 10 | 59,253 |
| Adopted | Compact | 184,029 | 153,728 | 1,515 | 72.95 | 10 | 51,070 |

Compact minus verbatim is **-10,878 tokens (-6.2%)** for conditional and
**+17,090 (+10.2%)** for adopted. Across these four observations, compact totals
348,635 against verbatim 342,423: 6,212 more reported tokens. Neither elapsed time
nor reported tokens improves in both pairs.

Within the compact calls themselves, lexical compaction reduces original stdout
from 55,980 to 47,177 bytes for conditional and 60,231 to 51,070 for adopted.
That is an exact byte effect on those receipts, independent of the different
command sequences. It is not a token estimate. Uncached input is 30,179/29,478
for verbatim/compact conditional and 34,764/28,786 for verbatim/compact adopted;
those differences also cannot establish subscription cost or a causal saving.

Fresh native session identities do not eliminate server-side cache effects.
Query selection, declaration volume, command errors, output length and cache
state differ, with only one observation per cell. The fixed paired requests and
counterbalanced order do not remove those limits. Keep both directions; do not
promote the opt-in implementation on the smaller-byte result alone.

## Retained behavior and failures

All four world checks pass without complaints or unplaceable records. Every
fixture verifies without unattributed revisions, and each new positioned record
uses `s000002`. The two cells that add growth declarations also produce timeless
records, as required for that predicate. The fixtures contain restored world
evidence and empty manuscript placeholders; no new chapter was drafted.

| Cell | New Wren goal identity | Located goal content |
| --- | --- | --- |
| Verbatim conditional | `rec-wfa67ceace59c4ec0bee740a7` | Accurate inspection, safe work and continued questions; water fulfilled; no homeward pursuit |
| Compact conditional | `rec-w90a477d86fa943179bed032e` | Accurate defect recording and safe work; water fulfilled; no homeward pursuit |
| Verbatim adopted | `rec-wa1a323b226848035be9b4342` | Return to Earth, find the other arrival and ask how; retain accurate, safe work; water fulfilled |
| Compact adopted | `rec-w3120c2a53e9839014f7743fb` | Return to Earth, find the other arrival and ask how; retain accurate, safe observations |

The verbatim conditional cell also adds a stair-repairer goal update
(`rec-w3d90e3994fcfe9d61858aac3`) reflecting the voluntarily transferred chit.
The other cells do not. These summaries locate the retained assertions; they
do not establish complete semantic equivalence between outputs. Full values
remain in the ignored case stores and `wants.private.json` files, with value
hashes and identities in the registered audit.

The [post-observation trace summary](trace-summary.json) retains all command
counts and new-record differences. Verbatim conditional, compact adopted,
compact conditional and verbatim adopted add 31, 25, 47 and 40 records,
respectively. Compact conditional proposes six growth declarations: Load,
Duration and Length open; Loadstitch, Split and Articulated one. Verbatim adopted
proposes only Loadstitch one. The other two propose none. These proposals were
not accepted and do not migrate any original book.

**Two malformed tool requests are retained in compact conditional.** They use
`args` where the tool requires `arguments`, before any successful compact reply.
Both are refused as `invalid_arguments`; the model then uses the declared
schema within the same native call. Their complete failure receipts reach the
model unchanged. There are 45 successful tool executions and two rejected tool
requests across the study, with no transport fallback or repeated native cell.
All 47 actual visible replies match the registered transformation, including
those two failures. This observation does not attribute the schema mistakes to
compaction, and it does not relax the tool contract to accept them.

## Provenance, bounds and reproduction

Five distinct native sessions, including health, used 694,822 reported tokens
over 329.59 seconds. The health call used 3,764 tokens. This is within the fixed
8-attempt, 1,200,000-token and 60-minute start ceilings. The final progress ledger
and native usage agree. Source, executable, dependencies, registered scripts,
paired requests and protected original inputs retain their frozen hashes. All
tool executions remain inside the bound LitHarness bridge. Read-only analysis
preserves each final fixture database hash.

The registration handoff passed 5,105 tests with 20 skips and 89.91% branch-aware
coverage, plus lint, types, lock/diff checks, wheel build and corpus-history audit.
The final result check is retained at
`runs/compact-json-20260913/handoff-final.log`. Unrelated precision and reader
research work is outside this change.

With the study's shared-machine lock held, rebuild:

```powershell
runs/compact-json-20260913/runtime/Scripts/python.exe research/quality-measurement/compact-json-20260913/audit.py
runs/compact-json-20260913/runtime/Scripts/python.exe research/quality-measurement/compact-json-20260913/describe.py
uv run python research/quality-measurement/epistemic_governance.py research/quality-measurement/compact-json-20260913/claim.json
```

`describe.py` was added after observation to describe world and command
differences; its output records its own hash and the registered audit's hash.
It did not influence generation or change the registered analysis. The frozen
runner and audit remain unchanged. Raw evidence stays under ignored
`runs/compact-json-20260913/`; committed results contain identifiers, hashes,
derived measurements and these scoped conclusions.
