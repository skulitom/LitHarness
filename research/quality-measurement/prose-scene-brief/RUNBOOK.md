# Scene brief runbook

Read PREREG.md and the shared ../RUNBOOK.md guard-and-go rules. Check processes and acquire
runs/box.lock. Freeze the fresh source and source review under ignored runs. Run handoff and
commit this registration before the planner call.

```powershell
uv run python research/quality-measurement/prose_scene_brief.py prepare --out runs/ab/prose-scene-brief-20260906 --source runs/ab/prose-scene-brief-tools/source.json --note runs/ab/prose-scene-brief-tools/source-review.md
uv run python research/quality-measurement/prose_scene_brief.py plan --out runs/ab/prose-scene-brief-20260906
```

Read the entire plan against the source. Record any source-only corrections and preserve the
raw proposal. Stop if it needs narrative redesign or contains unresolved source conflicts.

```powershell
uv run python research/quality-measurement/prose_scene_brief.py freeze --out runs/ab/prose-scene-brief-20260906 --reviewed runs/ab/prose-scene-brief-20260906/plan.reviewed.json --note runs/ab/prose-scene-brief-20260906/plan-review.md
uv run python research/quality-measurement/prose_scene_brief.py draft --out runs/ab/prose-scene-brief-20260906
```

Read all eight drafts without selecting a winner. Verify actual dispatched inputs against
the frozen conditions, build and inspect the comparison, run handoff, commit results and
push main as previously authorized. Release only this session's lock after its jobs finish.
