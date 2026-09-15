# Carrying an intended experience through planning

Status: registered design, no established enjoyment or quality effect.

The operator asked to work on the next experiment after the experience-first pilot.
Read the parent [RUNBOOK](../RUNBOOK.md), [BRIEF](../BRIEF.md), and
[epistemic governance](../EPISTEMIC_GOVERNANCE.md) before execution.

## Question and design

Does supplying an original experience specification at the outline handoff change where
its specified events appear in a two-chapter episode? This is a transmission feasibility
study. It fixes planning-language representation; prose versus planning is a separate,
unrun question. Prior pilot interpretations motivate the design, not a supported premise
that the current planner harms enjoyment.

Four independently authored inputs cover combat, tactical combination, repeated mastery,
and comic companionship. Each fixes people, mechanics, initial state, personal desire,
concrete use, experienced consequence, next desire, chapter boundaries, and unresolved
material. These are original prospective creative instructions, not reader labels or
corpus summaries. No published text, titles, reviews, digest, earlier generated story,
reading notes, or pilot report enters a generation request.

Per block, generate ONE discovery from premise plus specification, then ONE concept from
that discovery and the short premise. Both outline arms share these exact parent bytes:

- A: the frozen production outline request and its existing concept projection.
- B: the identical request, with the original specification added as one JSON field.

The B field states prospective requested events, not accepted history. It preserves the
existing locked premise and cannot override it. The specification is offered to discovery
and restored to the B planner; it is not separately supplied to the writer. Thus the
contrast bundles availability, repetition, explicit timing, and extra input length.
It does not identify a pure representation, attention, or compactness effect. Shared
upstream semantics do not guarantee that either model preserves the input semantics.

Both planners outline exactly two chapters at 1,400 target words each. Both use the same
research beat functions: an initial local episode, then a subsequent local episode; these
replace the six-beat pilot schedule and do not request particular events in A. Both use
the unchanged structured production renderer/schema, with no world store or Architect.
The writer receives the short premise and its current structured scene. Chapter two also
receives its own exact chapter-one prose as prior narrative. All eight outlined chapters
pairs advance without ranking or selection. The complete two-chapter episode is read.

The four blocks have AB, BA, AB, BA order, reversed at the next arm-bearing stage.
Stages: all discovery, all concept, all outline, all chapter one, all chapter two.
Use one independent 2048-bit opaque prefix per block. This prefix is not a deterministic
sampling seed. One draw per block/arm provides descriptive cases, not population estimates.

## Freeze, limits, and execution

Source is archived from committed 01deb0c, excluding unrelated working-tree changes.
Freeze source modules, lockfile, executable, driver, tests, runbook, inputs, seeds, and
static requests before dispatch. Commit and push registration before native calls.
Native settings: gpt-6-astra / medium, isolated ephemeral tool-free subscription sessions,
project instructions/user config/memory disabled; no model switch, fallback, reset, or
billed API. Backend resolution is reported only if the transport independently exposes it.

Maximum 32 application calls: 4 discovery + 4 concept + 8 outline + 16 chapters.
Sequential under runs/box.lock. Admit no new call after 1,000,000 recorded tokens or
120 minutes from dispatch start. An admitted call may exceed an admission ceiling.
Keep frozen production timeouts; drafts use 600 seconds, 4,200 output-token allowance,
and requested 1,200–1,600 words. No word-length rejection or aesthetic repair.

Preparation and dispatch refuse existing state. No implicit retries or redraws.
Malformed parents skip descendants, including both arms for a malformed shared parent.
Transport, containment, missing usage, or frozen-file errors stop all new calls.
Preserve every attempted receipt, including failures and unknown interrupted usage.
An interrupted run requires an explicit, preregistered continuation before another call.

```powershell
uv run python research/quality-measurement/experience-handoff-20260915/run.py prepare
uv run python research/quality-measurement/epistemic_governance.py research/quality-measurement/experience-handoff-20260915/claim.json
# Run offline focused tests and tools/check.py handoff, commit, then push registration.
uv run python research/quality-measurement/experience-handoff-20260915/run.py run
uv run python research/quality-measurement/experience-handoff-20260915/run.py audit
```

Only this task releases its machine lock. Coordinate sustained checks as required by the
parent runbook; use one pytest worker. Never set LITHARNESS_LIVE_PROVIDERS for checks.

## Controls, analysis, and stopping rules

Do not inspect generated content until dispatch finishes or stops. Audit exact requests,
shared parent receipt hashes, one-field outline difference, no direct specification in
writer context, exact chapter-one lineage for chapter two, schema validity, source freeze,
transport containment, distinct session IDs, and resource/attempt counts. The audit models
the frozen provider's dynamic-schema fallback: an outline can intentionally omit native
output-schema enforcement while retaining the original schema and downstream validation.

An audit failure voids the affected causal contrast; report it, never quietly repair a
generation input or replace an output. Mechanical format validity is not literary validity.
If upstream generation already changes a requested event, locate that divergence and
interpret B as restoring original instructions, not merely preserving the shared concept.

Read every reached output and make a located account for every block and both arms:

1. What does the specification request in each chapter, and what is left unresolved?
2. Where does discovery/concept retain, transform, omit, or postpone it? Distinguish raw
   concept opening fields from the actual projected fields the planner sees.
3. What does each outline schedule? What does each chapter actually enact?
4. Does a later use follow the supplied starting mechanics and the preceding prose, or
   treat a proposed event as already completed? Note contrary evidence and ambiguity.
5. Do tone and interaction change even when the same broad event occurs? Use located
   observations; do not call a keyword, notification, or narrator assertion enjoyment.
6. What does the control preserve, and what does the added specification fail to preserve?
   Identify alternative explanations, including short episode constraints, input length,
   repetition, explicit author instruction, and the full previous chapter in context.

This is descriptive analysis with no quality score, winner, preference judge, significance
test, or target rate. Do not count interpretive event coding as a validated measurement.
No outcome can qualify editorial feedback or certify popularity/enjoyment. A single later
reuse with full preceding prose tests this narrow handoff only, not long-serial retention.
If both arms preserve the specification, report the ceiling within this setting rather
than inventing a new criterion. If neither does, report it without adapting the task.

Raw outputs, reading copies, interpretive notes and report stay under ignored
runs/experience-handoff-20260915. Commit identifiers, hashes, derived volume/control
numbers and methodological conclusions. Claim status may become observed; this run has
no rule licensing supported quality or reader-experience claims. Production stays untouched.
