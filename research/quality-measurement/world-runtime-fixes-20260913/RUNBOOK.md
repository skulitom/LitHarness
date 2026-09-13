# Bounded world retrieval and usable reconciliation timing

The preceding [fixed boundary run](../world-boundary-fixes-20260913/REPORT.md) preserved
its tested source conditions but reconciliation still repeated whole-world reads and
produced twenty accepted facts at unusable schedule-space keys. This run tests the
engineering response on fresh stores. All earlier stores and manuscripts remain frozen.

## Changes and fixed cases

The Architect receives `world query` in place of the unrestricted `world show` allowance.
Query returns twenty records by default, at most fifty, with total/next_offset and a
selection hash. It uses in-force records, retains provenance/proposals, and omits the
duplicated `says` rendering. Full history remains available to the operator and diagnostic
MCP surface. Existing containment guards remain strict.

Reconciliation receives the actual story key in the same coordinate space as planning
and summaries. New world declarations refuse non-scene keys before their immutable
identity is persisted. The vocabulary no longer instructs agents to use numeric schedule
keys for world declarations. Existing stored records are neither moved nor removed.

Repeat the two assignments from the preceding run in the same order: the fixed original
Wren treatment through development, seed, one chapter and reconciliation; then the opposing
Mara treatment through development and seed only. The original source receipt and the
constructed opposing source are unchanged and hashed. Retain all first results; these are
new versioned attempts, not replacements for the earlier outputs or selected candidates.
No diagnostic text or prior chapter is supplied to generation.

## Execution and bounds

The small runner reuses the prior capture driver without editing it. Preparation freezes
that driver and its base auditor beside the committed production snapshot; their hashes
become part of the source inventory checked before every call. The wrapper supplies the
new output root and registration, preserving the prior workflow and safeguards. Both
prior experiment databases and chapter exports are added to protected-file checks.

Use the prior RUNBOOK's exact command workflow: one ordinary development per source,
`new --concept` with fixed neutral premise/title, six scenes, one scene per chapter,
six chapters per arc and 1,800 target words. Wren gets seed/check/accept, normal ticks to
one accepted chapter, follow-up drain, grow/check/accept and saved checkpoints. The
opposing case gets seed/check/accept and no chapter. No listing, fresh invention,
precision edit, name redraw, manual repair or manuscript import occurs.

Use one sustained job under this task's existing box-lock prefix. Retain the same ceilings:
40 native attempts / 1,600,000 reported tokens in aggregate, 25 attempts / 1,000,000 tokens
per book, and a two-hour new-call bound. Checks are pre-call, so an in-flight call can
overshoot. The existing individual timeouts remain. Unknown usage, transport/containment
failure, source/binary/dependency drift, attribution failure, wrong chapter count or twelve
ticks without progress stop the entire run. Preserve failures; do not implicitly resume.

The frozen native CLI is `0.154.0-alpha.6.2`, ChatGPT subscription authentication, with the
repository-default Codex model/reasoning. No API-key transport or provider fallback.
Commit and push the prepared registration before the first call.

## Readout

Rebuild all provenance controls with the base audit and additionally record every query's
arguments, result size, record count, total, continuation and selection hash. Retain all
query failures and denied full-dump attempts. A query exceeding the declared record cap,
an executed full `world show` by the Architect, or any newly accepted unplaceable record
prevents a claim that the relevant engineering fault is fixed. Correct pagination must
remain possible; avoiding data by returning empty results is not success.

Read the new Wren chapter in full and inspect both sources' developed concepts and seeds
for the preceding acquisition/access/motive conditions and future-event leakage. Inspect
the actual grow request's story key and resulting positioned declarations. Attribute every
accepted manuscript revision and verify all protected prior hashes.

Report native usage separately from tool bytes. This sequential version comparison cannot
isolate causal token savings, and preserving the selected source boundaries does not
establish creativity, reader enjoyment or general reliability. No scoring, candidate
ranking, reader feedback or editorial intervention follows from these observations.

## Commands

Run `tools/check.py handoff` before the engineering commit. Then:

```powershell
uv run python research/quality-measurement/world-runtime-fixes-20260913/run.py prepare
# Inspect, commit and push registration before generation.
runs/world-runtime-fixes-20260913/runtime/Scripts/python.exe research/quality-measurement/world-runtime-fixes-20260913/run.py run
```

After completion, run this directory's `audit.py` with the frozen interpreter and validate
its content-addressed result record. Release only this task's own lock at final handoff.
