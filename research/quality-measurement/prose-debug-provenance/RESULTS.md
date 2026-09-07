# Historical plan and prompt provenance tooling — 2026-09-07

This is an implementation and inspection record, not a generation experiment. No model
calls, prose revisions, quality judgments or disclosure-policy changes ran.

## Delivered behavior

The scene dossier retains its existing current `plan_item` and labels its scope explicitly.
`job_plan` reads only the plan revision recorded by the attributed drafting job. Missing,
invalid, unavailable and mismatched history remain explicit. A stored plan item is not
assumed to equal the delivered instruction, which may include renderer transformations.

New drafting jobs retain a source map alongside their unchanged system/prompt strings.
Context rendering records each inserted item body during composition, preserving distinct
locations for identical text. The map includes source IDs, authority, visibility, source
spans where supplied, hashes, and rendered section roles. Rules and locks map to the system
message; prepended shelf material shifts prompt offsets. Renderer fragments identify their
producer, including additional system duties and the transformed scene-plan argument.

The map is a description of selected packet items and renderer fragments. A cast item or
projected world fact can aggregate several records; complete upstream lineage is not claimed.
The scene-plan argument hash is taken before the existing whitespace stripping and wrapper;
the entry hash describes the actual rendered fragment. Recorded section membership describes
disclosure handling, without interpreting a scene plan or authorizing a reveal.

`scene_trace.source_map` exposes a summary and bounded, optionally source-filtered pages.
The full job digest and all stage/span hashes must match before source metadata is exposed.
Invalid hashes/metadata are withheld as an explicit error state. Shelf exposure withholds
entries and context. Older jobs report missing provenance; revision calls do not inherit the
drafting map. No historical map is reconstructed from current state.

The full job digest still covers the metadata. For a recognized, integrity-matching scene
job, the sampler derives its material with only the diagnostic sidecar excluded, preserving
the seed that the same pre-instrumentation payload would have used. No stored or supplied
seed is trusted. Legacy and other job kinds retain their existing behavior.

## Chapter-one inspection

The original chapter-one database was copied with its available WAL/shared-memory family
into an isolated ignored directory, checking all source/copy hashes. The new agent tools
inspected scenes one and two on that copy. Original file-family hashes matched before and
after. No connection to the original database was opened by this check.

Both historical plan lookups were available, bound to revision
`ff4f728305543d9901d9d26d2839becb52968881fa3f540204063bfba55e2eeb`.
Both current plan items matched their job-bound items. Both old jobs reported
`source_map.status = not_recorded`. This check therefore does not establish a plan-drift
cause for the prose or retroactively provide the missing source map. Frozen system/prompt
identities remain in [inspection.json](inspection.json), with the local raw-artifact hashes.

## Validation and limits

Regression tests cover plan changes after enqueue, unavailable/foreign history, exact
rendered offsets under duplicate and multiline text, empty items, system routing, shelf
prefixes, malformed maps, bounded filtering, revision/shelf withholding, actual queued
payloads and sampling isolation. Fixed pre-change hashes pin maximal writer requests with
and without a shelf; they match the instrumented renderer byte for byte.

During implementation, focused tests caught fixture setup errors, an incorrect contracts
serialization method and a documentation value mistaken for a field by the guide checker.
These were corrected. Review caught and corrected metadata-induced seed drift and source-map
schema mismatches before handoff. These were local development failures, not model outputs.

Raw inspection and verification material is under ignored
`runs/debugging-provenance-20260907`. Final repository handoff passed: 4,557 tests, 19 skipped,
89.12% coverage, lint/types, lock/diff checks, wheel build and a clean history
audit. The retained log and tested source hashes are in [validation.json](validation.json). The tools establish what input was recorded and where it
was inserted. Controlled comparisons are still needed to investigate prose causes.
