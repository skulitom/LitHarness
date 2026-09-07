# Disclosure record inspection

Read CONTRIBUTING.md and the shared research RUNBOOK.md before sustained validation.
This is model-free implementation and provenance inspection, not a prose-quality experiment.
No model invocation, database repair, reveal authorization or candidate selection is part
of it. Exact source text and retained views stay under ignored runs/ab/prose-disclosure-debug-20260907.

1. Use a read-only database connection and retain before/after identities for the database
   and existing WAL/SHM sidecars. Identify the scene's attributed job and frozen request.
2. Read `scene_trace.request.story_order`. A recorded story key is the disclosure comparison
   key; a manuscript reading-order key is not interchangeable. Preserve absent/null cases.
3. Use `world(view=threads, subject=CLAIM_ID, at=STORY_KEY)` and the equivalent CLI
   `world threads --subject CLAIM_ID --at STORY_KEY`. Compare their JSON. Inspect reader
   and other-audience records separately, without converting ordinal intentions into events.
4. Join the claim to its original seed and job-bound plan by recorded identities. State
   whether the observation came from captured input, current reconstruction, or inspection
   of a retained seed. Never silently substitute today's state for historical context.
5. Keep source-free results and hashes here. Test the diagnostic against the existing hidden
   consumer and actual context assembly, including false claims, future/incomparable keys,
   missing cutoff, other audiences and proposals. No automated semantic plan matching.
6. Run the repository handoff before committing. Record any change in generation behavior
   separately; no such change is authorized by this diagnostic's own outputs.

## Verification amendment, 2026-09-07

The first `verify_tools.py` run failed its unchanged-file-family assertion: the CLI opened
the retained database through writable startup. Preserve that script and the earlier
`state-audit.md`; do not regenerate either to replace the failed result. The separate
`storage-side-effect-audit.md` records which surviving logical subsets were checked after
the incident and why full pre/post logical equivalence cannot be established.

Use the corrected CLI and `verify_tools_v2.py` for subsequent verification. It starts from
the post-incident database and writes partial results even on failure. Record exact main,
WAL and SHM identities at each stage. A read-only connection may create an empty WAL and
SHM; distinguish those files from changed database pages without calling the whole family
unchanged. Do not delete sidecars, restore an incomplete family, or open a live WAL database
with SQLite's immutable option. The follow-up audit used immutable reads only after
confirming both sidecars were absent.

Local inspection scripts live in the ignored run directory. Invoke them with
`uv run python -X utf8 SCRIPT`; output files intentionally refuse replacement. The original
inspection is historical evidence, not a command to rerun against a changed baseline.
`record_execution.py` derives the source-free manifest from preserved artifacts. No artifact
from this inspection becomes generation input.
