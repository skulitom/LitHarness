# Opening-chapter pilot — frozen before generation and before reading either chapter

Date: 2026-09-27. Question: does a fresh two-call drafting tool produce a promising
opening chapter at much lower orchestration cost than the existing LitHarness lane?
This is one exploratory matched-brief comparison, not a general quality estimate.

## Fixed sample and inputs

- Heavy: `C:/DEV/LitHarness/runs/chapter-one/read-21/draw-6/chapter-one.md`.
  This was the only completed `chapter-one.md` found under the chapter-one lane.
  It was selected by file availability before its prose was read, not by its quality.
  Source revision `07b077f2ce64375d47df2dc2d7f32425432247b3`, writer `marsh`, draw 6.
  It completed the chapter stage, but has no recorded chapter gate pass. Its concept,
  listing and world had passed earlier checkpoints. It is not an accepted-quality anchor.
- Lite: exactly one new plan and one new chapter; no selection among drafts, edits,
  repair, feedback, extra style dossier, or supplied heavyweight plan/world/chapter.
  The only creative input is the byte-preserved original brief.
- Both: Codex `gpt-6-astra`, medium effort; close third person; aim at 3,962 words.
  Model identifiers and effort match; service snapshots across dates cannot be proven identical.
- Native CLI binary is bound by hash in the Lite manifest and historical settings.
  Generation and judge calls disable tools/config/skills and run from empty directories.

## Procedure and ceiling

1. Snapshot baseline brief, chapter, settings, stage metadata and all 33 raw call traces.
2. Freeze the Lite source, benchmark runner, protocol and baseline hashes; commit locally.
3. Generate once with `python lite.py --brief experiments/2026-09-27-opening/baseline/brief.txt
   --out experiments/2026-09-27-opening/lite --words 3962`.
4. Run `python benchmark.py evaluate`. Exactly four fresh model calls in this fixed order:
   Heavy/Lite; Lite/Heavy; Lite/Lite; paragraph-damaged Lite/intact Lite.
   Identities, costs, plan, source paths and this protocol are absent from judge requests.
   Model/effort match generation; sessions are isolated, not epistemically independent models.
5. Read the outputs and save a report with quoted examples, operational measurements,
   diagnostic results, limitations and a provisional engineering recommendation.

Maximum six successful provider invocations, 900 seconds per call. No automatic retries.
If transport fails before any answer is read, preserve it and record a failure note
before at most two operational retries of the identical request. A content change,
reroll after reading, extra candidate, or different model requires a visible amendment
before proceeding. No dollars are inferred from subscription tokens.

## Diagnostic rubric and controls

Six ordered dimensions, each 1–5: brief fidelity, dramatic causality, character/dialogue,
prose control, progression as drama, continuation pull. Anchors are serious failure,
weak, competent, strong, exceptional. Every score requires a short exact quotation
from both chapters and a rationale. These are uncalibrated ordinal editorial labels,
not measurements of reader enjoyment. No statistical significance or population claim.

Controls must all pass before reporting an order-stable diagnostic preference:

- Quote validation: every cited passage is a substring of its assigned chapter.
- Order: both main reads map their holistic preference to the same underlying output,
  including an order-stable tie. Per-dimension disagreement is still reported.
- Identity null: two identical copies receive a tie and equal scores on every dimension.
- Severe damage: the same Lite text reordered as even-indexed paragraphs then odd-indexed
  paragraphs loses to the intact copy overall and on dramatic causality. Wording and length
  are held constant. Detection of this loud damage is necessary, not sufficient for craft validity.

Failure of any control makes the preference inconclusive. Do not quietly repair quotations,
drop criteria, change controls or rerun judges. Preserve the failure as a result.

## Decision scope, confounds and evidence boundary

Generation input fidelity and located continuity defects will also be described directly.
Word count, runtime, token totals, cache use, call count and code size are operational facts,
never quality proxies. Report chapter-stage costs and full-pipeline costs separately;
heavyweight listing/world/state work serves capabilities the prototype does not implement.

The heavy artifact is historical and draw 6 after earlier attempts; their full cost is not
in its 33-call subtotal. It uses a recruited writer dossier, additional authoring directions,
world seeding, per-scene generation and bookkeeping. Lite invents its own characters and
plot. This comparison tests two complete approaches on one brief, not orchestration alone.

If controls pass and Lite wins or ties without a clear premise violation, recommend continuing
the clean prototype for the next bounded test. If Heavy wins, recommend retaining Heavy for
current production while identifying the missing capability. If controls fail, base the next
step on transparent qualitative inspection and engineering cost, labeled provisional, without
claiming a measured winner. A single chapter never licenses deleting the incumbent or claiming
long-serial equivalence. No judge feedback is fed to either generation system.

The recommendation is an engineering choice about the next experiment, not a qualified
production gate. All raw observations and hashes are retained locally. Nothing is published
or introduced into LitHarness production or its research claim ledger.
