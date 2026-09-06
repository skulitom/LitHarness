# Paragraph revision runbook

Read PREREG.md, ../BRIEF.md, ../EPISTEMIC_GOVERNANCE.md and the shared ../RUNBOOK.md guard-and-go
rules. Inspect relevant processes and atomically acquire runs/box.lock before sustained work.
Prepare the reviewed source map in the ignored tools directory. Run handoff and commit the
registration and controls before prepare or live calls.

```powershell
uv run python tools/check.py handoff
uv run python research/quality-measurement/prose_paragraph_revision.py prepare --out runs/ab/prose-paragraph-revision-20260906 --source runs/ab/prose-paragraph-revision-tools/source.json
uv run python research/quality-measurement/prose_paragraph_revision.py run --out runs/ab/prose-paragraph-revision-20260906
```

Read each original-to-patch change and every full reconstruction; record fact preservation
against the frozen map, including omissions not declared by the editor. Compute the frozen
observational counters, build a comparison with original and all four outputs, and inspect it
in a browser. No automatic prose adoption or preferred-candidate selection. Run final handoff,
commit results and push main under the operator's existing authorization. Preserve unrelated
files and archive only this session's lock after its jobs complete.
