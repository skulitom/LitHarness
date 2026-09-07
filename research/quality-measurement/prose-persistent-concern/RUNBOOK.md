# Persistent concern diagnostic runbook

Read PREREG.md, shared RUNBOOK.md, BRIEF.md and EPISTEMIC_GOVERNANCE.md. Inspect processes,
acquire runs/box.lock atomically and inspect again. Preserve unrelated checkout work.
Prepare the unchanged source plus four opening-known IDs under the ignored tools directory.
Run handoff and commit this registration, generic runner and tests before model dispatch.

```powershell
uv run python tools/check.py handoff
uv run python research/quality-measurement/prose_persistent_concern.py prepare --out runs/ab/prose-persistent-concern-20260907 --source runs/ab/prose-persistent-concern-tools/source.json
uv run python research/quality-measurement/prose_persistent_concern.py derive --out runs/ab/prose-persistent-concern-20260907
```

Read the whole proposal against the source, including the question's knowledge at opens_after
and every checkpoint. On incompatibility or structural failure, retain and stop without repair
or redraw. A passing temporal-review.json binds text_sha256, reviewed_activations (opening then
all checkpoints in order), source_compatible, knowledge_timing and no_new_canon. The booleans
record compatibility only, not quality. Then freeze and inspect exact inputs before drafting.

```powershell
uv run python research/quality-measurement/prose_persistent_concern.py freeze --out runs/ab/prose-persistent-concern-20260907 --review runs/ab/prose-persistent-concern-20260907/temporal-review.json
uv run python research/quality-measurement/prose_persistent_concern.py draft --out runs/ab/prose-persistent-concern-20260907
```

Read every full chapter, record all source correspondences and attention at/between proposal
checkpoints in both conditions. Preserve unclear and adverse observations. Build and inspect
the comparison in a browser; record evidence hashes and OBSERVED limitations in results/claim
and RESEARCH.md. Run final handoff apart from model calls. Stage only owned files, commit/push
main, verify remote head, and archive only this session's lock.
