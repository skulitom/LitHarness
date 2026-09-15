# Completed continuation and descriptive reading

The explicitly registered continuation completed the original two-chapter target in all
eight books: 16 accepted chapters, 25,035 words. All eight first chapters remained
byte-identical. The initial segment's experiment-driver failure is preserved in its
[results](../experience-workflow-20260915/RESULTS.md); this is not an uninterrupted run.

## Resources and operational controls

| Segment | Completed provider calls, including health probes | Recorded Usage.total |
| --- | ---: | ---: |
| Initial | 96 | 2,100,789 |
| Continuation | 48 | 1,458,918 |
| Combined | 144 | 3,559,707 |

The original dispatch clock ran from 2026-09-15 12:44:29 UTC to 14:45:19 UTC, including
continuation preparation. All counts remained within the original aggregate ceilings.
There were no provider failures, unknown-usage calls or continuation stops. Each book has
two accepted chapters and zero pending or terminal jobs. The driver's per-book `status`
field remains `running` after its last phase; aggregate `status: complete`, accepted counts
and empty queues record completion. No native generation process remained at handoff.

[evidence.json](evidence.json) retains continuation receipts, step hashes, chapter hashes,
usage, attribution and controls. Original and continuation usage are separate; copied first
chapters are counted once in the combined volume. All continuation transport controls pass.
The original auditor's false flags remain unchanged; [parent-controls.json](parent-controls.json)
contains the registered supplemental corrections. Every store rebuilds with zero
unattributed revisions. These are operational facts, not prose-quality results.

## Reading and handoff inspection

After generation completed, the reviewing agent read all eight discoveries, concepts,
precision responses and full outlines, then both complete drafts per book and every
accepted-version difference. Truncated tool output was explicitly reread. All 16 scene
dossiers and the relevant frozen requests were inspected. No reading was supplied to
generation, no candidate was selected, and no book was regenerated after reading.

[reading-record.json](reading-record.json) identifies local reading artifacts and hashes.
[handoff-evidence.json](handoff-evidence.json) records the post-run coordinate and exact-string
checks, their inputs and rebuild command. Every original outline scene brief matches its
job-bound and current plan item; every situation, pursuit, change and future dependency
appears in the frozen writer prompt. All accepting attempts are 1, no retained pre-revision
draft is present, and no context item is omitted. Gate passes are not enjoyment labels.

The four updated briefs were retained through concept and outline. Retention did not ensure
consistent timing: B2, B3 and B4 raw concepts group multiple scenes into an opening chapter,
while all outline inputs explicitly map each of six scenes to its own chapter. Their
outlines distribute the corresponding sequence across those separate chapters. B2's
competing grouping remains in projected middle/close fields; B3/B4's opening field is removed,
but scene-indexed debts and later allocations remain. This is an inspected coordinate
discrepancy, not evidence that one particular input caused the model's response.

Discovery received no chapter word budget or layout; concept received the total scene count.
The practical implementation follow-up is to supply actual coordinates and budget upstream
and reconcile proposed coverage before drafting. Generated intentions remain revisable,
and author instructions remain authoritative. No literary effect of that change is claimed.

## Limits and local report

The full reading interpretation and contrary cases are in the ignored local artifact
`runs/experience-workflow-continuation-20260915/REPORT.md`, with detailed notes beside it.
Raw/generated narrative stays under ignored run roots. The report distinguishes proposed,
scheduled and enacted material, and does not demand all later developments inside chapter
one. It includes experiences already delivered by baseline and strengths in the updated
prose, without selecting a winner.

This is one generation per workflow per premise, with different generated stories and an
unblinded descriptive agent reading. Chapters are nested within books. Future planned
chapters were not generated. The trial cannot establish an enjoyment effect, popularity,
an automatic ranking role or an editorial mechanism. The claim remains `observed`.

## Verification

The final repository `tools/check.py handoff` passed, including lint, types, coverage,
lock validation, wheel build and corpus-history audit. Both claim records validate, and a
separate read-only check recomputed every supplemental artifact hash, first-chapter retention,
handoff equality and aggregate count. [reading-record.json](reading-record.json) records the
validation log and its hash. Unrelated checkout changes were present for repository checks
but excluded from both frozen production arms and this results commit.
