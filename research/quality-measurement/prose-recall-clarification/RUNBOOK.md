# Recall clarification runbook

Read [PREREG.md](PREREG.md), [CONTRIBUTING.md](../../../CONTRIBUTING.md),
[BRIEF.md](../BRIEF.md) and [EPISTEMIC_GOVERNANCE.md](../EPISTEMIC_GOVERNANCE.md).
Use the shared [box-lock procedure](../RUNBOOK.md#guard-and-go-how-several-sessions-share-one-box);
the older experiment commands elsewhere in that historical runbook are not this arm's setup.

1. Run the ignored `prepare_source.py`, then read its `input-audit.md`. Verify the single
   relative-clause edit, unchanged system/first scene, canonical cost and exact inverse.
2. Run focused tests and `uv run python tools/check.py handoff`. Commit registration,
   runner/helper and tests before prepare/dispatch.
3. Prepare once and draft the four slots individually, inspecting transport after each:

```powershell
uv run python research/quality-measurement/prose_recall_clarification.py prepare --out runs/ab/prose-recall-clarification-20260907 --source runs/ab/prose-recall-clarification-tools/source.json
uv run python research/quality-measurement/prose_recall_clarification.py draft --out runs/ab/prose-recall-clarification-20260907 --slot control-1
```

Continue only with `clarified-1`, `clarified-2`, then `control-2`, subject to the registered
stops. Do not change frozen files or replace any failed slot.

4. Read every complete raw scene. Assemble it with the same retained first scene for
   inspection, labelled as a fixed-prefix continuation. Expose all slots and failures.
5. Retain source-free request/transformation checks, usage, paragraph spans, outputs and
   reading-artifact hashes. Complete results/deviations even if stopped, validate the claim,
   update the index, run final handoff and commit/push.

Only archive this task's owned lock after calls and validation finish. Do not open or modify
the original book database. Repository-documentation cleanup may proceed independently but
must not change files frozen by this arm or enter its isolated generation context.
