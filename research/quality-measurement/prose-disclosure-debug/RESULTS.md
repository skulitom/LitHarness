# Disclosure conflict and diagnostic tooling — 2026-09-07

This follow-up locates an input-contract conflict in the retained original scene-one
request. It establishes how that conflict was assembled, not its effect on prose quality.
No generation, model judging, candidate selection or direct model API call ran. No story
state or production generation prompt was intentionally changed.

## Located record and producer chain

The source is `runs/ab/chapter-rule-context-20260905/request-4.json`, SHA-256
`4cb3c1292b764ed9087a43fbbd903f9848688a16e1ec3bf15b2d23802722b13f`, job
`beat-2c70980362f0426bfd63cb30`. Its bound plan revision is
`ff4f728305543d9901d9d26d2839becb52968881fa3f540204063bfba55e2eeb`.
The exact source text remains in ignored inspection artifacts.

- Claim `claim_edge`, record `rec-w13845db145c6b8c17716178d`, is accepted canon,
  unpositioned and unretracted, with no manuscript evidence or source revision.
- The claim's literal content occurs in the captured prompt both as a character belief
  at characters [20875, 20965) and under the hidden-truth prohibition at [31695, 31785).
  The hidden block spans [31037, 32821). The job-bound scene plan requires the same event.
- The retained database has zero reader-valued `disclosed_to` records. Five records
  targeting this claim address characters; their blank values do not identify the reader.
  Four have order key `0300`, one `0600`. The frozen job lists all five as omitted because
  their keys are incomparable with its drafting cutoff, `s1`.
- There is no `asks`, `reveal_scene` or `claim.false` record for this claim. A separate
  unpositioned belief edge does not satisfy reader disclosure. Planned reveal metadata
  on other subjects is a schedule, not an accomplished disclosure event.
- The 334-row imported seed matches the retained Architect-origin world in
  `runs/ab/pilot25/draw3/serial.db`. The import preserves claim identities while creating
  a new book. The seed decision `dec-ae4b290b641e0be096daefc4`, policy `architect.seed.v0`,
  supports operation-level provenance. No retained per-declaration event or raw authoring
  tool call establishes the exact original command arguments.

These checks separate three facts: the reader has not been recorded as told, a character
has knowledge, and the current scene is intended to disclose something. The existing hidden
consumer uses the first; scene-plan text is appended independently. There is no implemented
semantic reconciliation of those instructions in this path. The numerical scene reading
position `0000010` is also not the frozen story key `s1`; substituting it would change the
question asked of the state records.

## Tooling delivered

`scene_trace.request.story_order` now exposes the job's recorded drafting key, its source,
and separate recorded/unpositioned/missing/invalid/unavailable statuses. It does not infer
the key from the current manuscript order or copy drafting metadata onto a revision request.

`world(view=threads, subject=..., at=...)` and CLI `world threads --subject ... --at ...`
now explain each claim's existing disclosure classification. They return source record IDs,
canon labels, supporting reader and other-audience records, position comparisons, false
flags and separate planned reveal metadata. Filtering happens after supporting records
are joined, since their subjects can differ from the claim. No existing reveal rule changes.

The response explicitly describes current in-force declarations, including proposals.
It does not claim to reconstruct a historical writer packet, check scene-plan prose or
authorize disclosure. The agent guide and MCP debugging workflow document the frozen-key
to current-state inspection sequence. No new agent or independent narrative planner was added.

## Failed first verification and read-path fix

The first live `verify_tools.py` run obtained equal CLI/MCP JSON but failed its final
`before == after` file-family assertion, exiting 1 before writing its planned JSON report.
The script and original successful read-only `state-audit.md` are preserved. Its in-process
hash dictionaries were not persisted; the identities below come from the earlier audit
and the separate follow-up, not a fabricated record of those lost variables.

Before that CLI run, the audit recorded main database SHA-256
`148e4db05d28e7acd1213bec0e417cf55e810a29109a08e9bba8cfb60e3bc1fd`, WAL
`0d992db6f3994faecc09400d0644f448878a9ae119519f9fba1be41b2b4b5b23` and SHM
`8a180a05838a24cce7e7a089f531e29f07008fb26094365cd69ae3dab5c0f821`.
Afterward the main hash was
`f11823ca25791ccc5278deca2dbdd8fb41c42537cccb2d17e83840fbd8516969`, with both
sidecars absent. This is a real physical change, consistent with checkpoint/cleanup; the
precise sequence was not instrumented. `cmd_world` had used writable `SqliteStore.open`,
which sets WAL mode and runs migrations, while the MCP equivalent used `open_read_only`.

CLI world read views now use `open_read_only`. Existing write commands retain their write
path. Regression tests verify refusal of missing databases and pending migrations, without
file creation or migration, and preservation of a non-WAL database's journal mode and hash.

The follow-up audit verified all 334 seed rows, all six specifically audited claim/disclosure
rows and their saved metadata, the frozen system and prompt, raw draft, accepted scene,
selected policy fields and exact job-bound scene plan against surviving artifacts. All 39
migration timestamps remain September 5 with none pending. No complete pre-incident logical
dump survives, so this does **not** establish full logical database equivalence.

The corrected `verify_tools_v2.py` completed with identical CLI/MCP results and an unchanged
main database hash. MCP's read created a zero-byte WAL and a 32,768-byte SHM; the subsequent
CLI read preserved both exactly. The entire before/after family therefore differs. The v2
JSON records each stage and would preserve partial results on failure. It verifies the
corrected path against the post-incident database, not against the lost physical baseline.

## Validation, limits and next bounded test

Focused diagnostic, scene-trace, MCP and CLI regression tests passed. Independent static
review found no actionable issue; that review is not empirical prose evidence. Full handoff
outcomes and artifact identities are recorded in [execution.json](execution.json).

The remaining design question is how to represent permission to reveal in the scene being
written, separately from a record that the reader has already been told. A bounded next
comparison can vary that instruction for the located conflict while retaining unrelated
future embargoes and the same scene requirements. That comparison is not run here. Do not
repair the seed by fabricating reader-disclosure history, reinterpret ordinal reveal plans
as completed events, or normalize unrelated order-key spaces by guesswork.

This work supplies a reproducible diagnostic and fixes an unsafe inspection path. It does
not establish that the conflict caused the explanatory prose, that resolving it will improve
the chapter, or that a model can reliably infer disclosure permissions from free-text plans.
Exact source and rebuild scripts remain local under ignored
`runs/ab/prose-disclosure-debug-20260907`; a fresh clone has the code/tests and source-free
record, but not those retained manuscripts/databases.
