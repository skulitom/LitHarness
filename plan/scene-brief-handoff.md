# Scene planning and prose handoff

Implemented on operator direction, 2026-09-08 (stage-0 §248). This changes ownership and
context routing. It does not establish an improvement in literary quality.

## Production contract

Discovery proposes story material in planning language. The existing concept and world stages
retain that material, with the original author brief stored separately in new concepts. Model
development cannot replace the author brief, and precision edits cannot change it.

The existing outline call receives the concept's story foundations, author direction, accepted
history and world context. Its projection omits `discovery.opening`, the duplicate
`first_arc.opens`, `first_use` and `threat.first_reach`. Background, pursuit, world/growth
possibilities, system conditions, turn, later arc shape and debts remain. The complete stored
concept is unchanged. For a concept-backed book, it returns a structured brief for each scene:

- `situation`: the starting place, relevant relationships, and the viewpoint character's
  understanding and concerns.
- `pursuit`: what the viewpoint character is trying to accomplish.
- `changes`: developments in the character's circumstances, understanding or pursuit,
  connected through what they can notice, infer or misunderstand at consequential choices.
- `future_dependencies`: later-story commitments this scene must leave possible, or an empty
  list. These are kept separate from events to enact now.

The planner may revise provisional obstacles, props and choreography while preserving the
premise's pursuit and magical promise, author choices and established facts. It receives a
planning contract rather than the prose writer's house-style rules. The structured fields
constrain the handoff's shape; code does not certify that their language is factual or good.

The outline receives the actual configured scene word target, separately from any length for
the brief itself. Planning and drafting share this value; the outline decision's configuration
digest records it. Planning may move optional developments later to leave room for experiencing
the scene and developing choices. The writer's length instruction makes room for action and
viewpoint experience without requiring additional events to fill the allowance.

Generated opening and first-use chapter labels are proposals, and their detailed sequences
are no longer passed to the outline. It constructs events while preserving meaningful early
magic, original author instructions, author locks and established world rules. An unchanged
world condition remains a constraint rather than requiring its own demonstration episode.
Actual costs, prerequisites and activation conditions still precede dependent gains.

Planning receives relevant locked plan items with their exact text and resource scope, mapped
to the scene ordinals used in the request. The
writer receives only constraints/promises applicable to its scene; future or foreign scopes
consume no context budget. Book, part and chapter boundaries follow the actual manuscript tree.
Unsupported local scopes produce a diagnostic rather than being widened into global directions.

Briefs are versioned text inside the existing unlocked, scoped scene-plan records. The normal
policy decision and transaction accept them. Invalid structured responses cannot fall back to
an unstructured statement. There is no new model call, critic, ranking or narrative template.

Once a scene plan exists, its writer receives the plan, public premise, original author brief
when available, and the normal established-story packet. The complete concept, treatment and
distant arc summaries are no longer supplied again in the intentions section. Raw proposal
wording therefore cannot enter through that duplicate channel. Established world material and
the scene brief can still contain generated wording; this is not a complete contamination cure.

## Compatibility and transport

Historical concepts without an author brief remain readable. Existing ordinary scene plans
remain readable and are not silently rewritten. They also use the restricted writer view.
An author/directive edit that replaces a structured brief with ordinary text does not restore
the duplicate concept block. With no scene plan, the explicit no-outline control also keeps
only the original author brief from an unlocked concept; an explicitly locked concept retains
its full source. The stored concept remains available to subsequent planning.
Accepted manuscript, world canon, locks and existing plan revisions are
unchanged; future outline calls use the new handoff.

Tool-free Claude calls now run in fresh empty temporary directories. Tool-using world agents
retain the caller's workspace. Safe mode, replacement system prompts, disabled tools/MCP and
subscription authentication settings remain. Tests verify directory selection and cleanup,
including failures. They do not establish the complete model-visible context, and no live
isolation or prose comparison was run for this implementation.

## Verification and remaining question

[test_scene_brief.py](../tests/test_scene_brief.py) exercises the real outline-to-draft path,
checks that discarded treatment changes leave writer context unchanged, and verifies retained
author instructions, world rules, plan authority, legacy edits and rejected malformed outputs.
[test_providers.py](../tests/test_providers.py) covers transport lifecycle without model calls.
Check logs are retained locally under `runs/diagnostics/scene-brief-pipeline-20260908/`.

The initial implementation had not yet been compared in a fresh generation. The follow-up
below examines whether the handoff preserves necessary causal information or relocates the
same prose habits into the scene briefs. Structural checks do not establish prose quality.

## 2026-09-09 orientation revision

The operator's reading of *The Mechanics of Impossible Stairs* identified unclear geography,
relationships, emotional response and reasons for consequential actions. The shared writer
guidance now permits necessary context and explanation; it no longer dismisses passages that
establish people without advancing an external event. The existing scene-brief fields carry
the viewpoint information described above. No extra model role or output schema was added.

The bounded comparison is recorded locally under `runs/luke-chapter-orientation-20260909/`.
Successive arms isolate shared writer guidance, revise the scene handoff, release generated
opening deadlines, and test selective narrative attention against the same accepted plan.
They preserve the source concept, initial world and cover. First outputs, requests, source
hashes, usage and editorial readings are retained. These readings describe individual artifacts,
not validated quality labels or evidence of parity with published novels.

The production handoff test now follows a nondefault word target through CLI composition,
outline input, its recorded decision digest and the writer request. Representative prompt
inspection honors the same target. Old tests that froze retired craft wording and exact clause
counts were removed; prompt ceilings and scope, transport and persistence checks remain.
The containment checks now perform real accepted plan edits, rather than attempting to update
existing immutable IDs through an import that ignores them. Scoped author-lock coverage checks
both planning visibility and exclusion from unrelated writer scenes.

The four complete chapters and located readings are available in that run's `comparison.html`.
The later outline distributes the original learning sequence across more chapters, and the
new prose makes several relationships and action connections explicit. Mechanical exercises
still receive much of the narration's attention; the latest attempt also introduces an unclear
cage-gate judgment. No edition is certified against the named novels or promoted to the main
shelf. The next source audit concerns the difference between required capability facts and
which learning steps must be narrated. The present comparison does not establish that answer.

## 2026-09-09 source and chapter-configuration follow-up

Registered attempts, first outputs, frozen requests, failures and complete readings are local
under `runs/luke-story-developments-20260909/`. The original generated opening was a direct
source of repeated training episodes. Removing its four choreography fields from planning
changes that input without mutating the stored concept, accepted world or author locks.
World rules now constrain events without requiring demonstrations of unchanged conditions.

The one-unit chapter trial exposed two configuration defects: its 1,800-word answer exceeded
the fixed 8,000-character ceiling, and the valid grouping of one suppressed chapter context.
CLI targets above the default now scale the runaway allowance; explicit domain caps and the
stub floor remain binding. Configured positions reach both planning and drafting, including
one-unit chapters. `None` remains the unconfigured non-serial selector control. The actual
corrected request, acceptance decision and export verify those paths.

[test_cli_draft_length.py](../tests/test_cli_draft_length.py) checks the composed handler and
recorded effective policy. The production handoff test exercises one-unit mapping through
the CLI, planner and writer; [test_serials.py](../tests/test_serials.py) checks release grouping.
Chapter shape and target remain invocation settings. Continuation tooling must preserve them;
changing global defaults would regroup existing library output.

A fresh-world comparison permits useful entry capabilities without separately acquired
handling or perception, while preserving author mechanics and later depth. Its chapter still
filled the opening with instruction. Replacing the early-magic planning rule then connected
one spell to the existing pursuit in one chapter. An unchanged repeat, with byte-identical
planning messages, returned to general preparation and escape from a self-created hazard.
The rule is therefore an instruction, not an established solution. Both results remain in
the comparison; no quality score selects a manuscript or licenses volume expansion.

The existing no-outline path now also projects an unlocked concept to its foundation;
explicit author locks preserve the full treatment. Its first chapter makes the surroundings
and Luke's uncertainty legible, but again postpones the search for training. Removing the
outline alone did not resolve this case. The remaining lead is the coexistence of an urgent
personal pursuit and a gradual introductory progression in the retained story foundation.
The no-outline status requirement also differs, so this is not a single-variable comparison.

## 2026-09-09 three-chapter progression handoff

The first continuation under `runs/luke-three-chapters-20260909/` retained every prior chapter
in its writer requests, but separate free-form gain announcements did not reach the compact
status extractor. Chapter 3 consequently received Grade 0 beside Chapter 2's prose gains.
The no-outline path still required an exactly-once opening sheet and did not expose the
declared update columns. This was a located contract defect, not evidence of missing prose.

Concept-backed drafting now uses conditional result updates with or without an outline.
The declared sheet supplies exact labels and value types separately from current holdings;
a uniquely matching numeric system supplies its existing rung mapping. The grammar is
available before the first snapshot as well. Later partial updates retain omitted fields,
and unchanged scenes need no update or invented gain. Existing extraction and acceptance
rules remain in place. [test_status_handoff.py](../tests/test_status_handoff.py) follows
selection, ordinary draft acceptance, extracted state and the next writer request, including
first gains, existing holdings, unchanged scenes and legacy behavior.

The registered `status-handoff` arm under `runs/luke-three-chapter-repairs-20260909/` kept the
original Chapter 1 fixed and generated both continuations. Chapter 2's Initiate, Sight and
Ember updates reached Chapter 3 as current state; Chapter 3's Current update retained those
earlier gains. The complete first outputs, requests, read-only verification and readings are
retained. The concrete handoff works in this run. Repeated training still dominates the
opening, and no parity with published novels or permission to expand the volume is inferred.
Regression to an unranked graph standing is a separate existing limitation; this forward-gain
repair does not claim to fix it.

A further continuation cue distinguishes the currently requested piece from earlier chapter
or output requests in the unchanged original author brief. It appears only when an earlier
accepted scene and a concept author brief exist. Ongoing story/style direction and applicable
author locks remain binding. [test_continuation_scope.py](../tests/test_continuation_scope.py)
checks planned and no-outline continuation, unchanged first-chapter controls, raw source
preservation and later-chapter locks. Compact updates also identify themselves as the result
announcement, preserving distinct warnings, choices and explicitly required notices. These
clarifications address input scope and duplicate display instructions, not a validated pacing
mechanism; the separate `continuation-contract` arm records their first generated outputs.

## 2026-09-09 planning after an accepted opening

The continuation audit under `runs/luke-story-momentum-20260909/` found that enabling the
existing planner after an accepted opening still requested the whole arc, omitted that
same-arc prose and anchored state before it. Planning now requests the contiguous unwritten
suffix and supplies bounded history tied to accepted content hashes. Its response ordinals
map to original story keys and chapter coordinates; original concept references remain in
their original coordinates. Accepted prose and its plans are preserved. Gaps, conflicting
locks and stale queued bases refuse before a call. Acceptance also checks the manuscript
head in the same transaction as the plan change; replay preserves recorded acceptance.

[test_continuation_outline.py](../tests/test_continuation_outline.py) exercises the actual
accepted-opening, outline and subsequent writer handoffs, along with history, scope and
concurrent-change boundaries. The existing plan stage is reused; no narrative role is added.

Planning world briefs now classify explicit operating records as rules individually.
Ordinary character facts keep their cast grouping even when that character also has a
world rule. Existing rule meanings, consequences and complete constraints are preserved;
no accepted personality record is silently reclassified. The regression coverage lives in
[test_world_brief.py](../tests/test_world_brief.py). These are input-contract repairs, not a
demonstrated literary mechanism; the registered generation retains first outputs and full
readings to assess the resulting continuation.

The first live outline stopped before drafting: the ordinary summary handler had minted
new promises with book-template positions while serial planning used stable serial positions.
CLI composition now passes the same serial shape into summary production. The continuation
regression includes the actual summary handler rather than manually seeding all promise
positions. The failed output remains in the run, and `continuation-positions` starts from
the original checkpoint under the corrected producer. Existing mixed-coordinate promise
rows are not silently rewritten by this producer fix.

The `plain-writer` arm exposed a separate extraction defect: accepted updates such as
`Grade: 1 | Sight: 1` and `Ember: 1` left stored progression unchanged. Declared-label readers
now accept an optional colon while preserving exact labels, typed values, paired columns
and omitted holdings. [test_status_delimiters.py](../tests/test_status_delimiters.py) covers
parser boundaries, and [test_status_handoff.py](../tests/test_status_handoff.py) follows
separate gains through acceptance into the next request. The stopped manuscript and failed
handoff remain preserved; `plain-status` starts from the original Chapter 1 checkpoint.

The no-outline writer now uses the same original-author-brief projection as the planned
writer for an unlocked concept. The stored concept, accepted canon, premise, prior prose,
status contract and independent author locks remain intact. The existing locked-source
exception remains. [test_scene_brief.py](../tests/test_scene_brief.py) covers these boundaries.
This removes a generated treatment from the writer's input, including unaccepted background
and possible future events; existing concept debts still appear independently as threads.
The isolated `brief-only` registration records this scope and its remaining inputs. It is
not a claim that future directions are absent or that omission improves prose reliably.
