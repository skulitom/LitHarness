# Audit correction identified before reading story output

During the continuation, static inspection of the frozen provider and outline schema exposed
a mistake in the pilot auditor. The original auditor calls prepare_codex_schema directly for
every request. The outline schema contains a dynamic map at milestones[].state, so that
conversion raises ValueError. The already-frozen provider deliberately catches that exception,
keeps the original schema instruction, and validates the returned payload against the original
schema. The original auditor would therefore stop at the first outline regardless of its result.

This was reproduced using the source schema alone, before any generated story was read. No
generation request, response, retry policy, source snapshot, or original registered file changes.
The independent audit.py retains the original controls and adds explicit checks for the native
schema value, omission reason, schema variant, and presence or absence of --output-schema.
Original JSON-schema and structured-scene validation remain in place. A missing or incorrect
fallback reason fails; a dynamic schema passed as a native schema fails. This is correction of
the expected transport behavior, not a relaxation based on an observed story result.

The continuation run.py and original run.py remain frozen, including their original auditor.
After generation stops, preserve the original auditor's failure log, run the focused audit tests
and repository handoff, then commit this correction before reading story content. Use:

```powershell
uv run python research/quality-measurement/experience-first-recovery-20260915/audit.py
```

Audit output records this correction's identifier and file hashes. All original descriptive
analysis and scope limits still apply. In particular, schema conformance is not reader enjoyment.
