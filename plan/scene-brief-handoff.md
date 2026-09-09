# Scene planning and prose handoff

Implemented on operator direction, 2026-09-08 (stage-0 §248). This changes ownership and
context routing. It does not establish an improvement in literary quality.

## Production contract

Discovery proposes story material in planning language. The existing concept and world stages
retain that material, with the original author brief stored separately in new concepts. Model
development cannot replace the author brief, and precision edits cannot change it.

The existing outline call receives the complete concept, author direction, accepted history
and world context. For a concept-backed book, it returns a structured brief for each scene:

- `situation`: the starting place, relevant relationships, and the viewpoint character's
  understanding and concerns.
- `pursuit`: what the viewpoint character is trying to accomplish.
- `changes`: intended actions and consequences connected through what the character can
  notice, infer or misunderstand at consequential choices.
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

Generated opening and first-use chapter labels are proposals. The planner can distribute that
material across chapters while preserving meaningful early magic, original author instructions,
author locks and established world rules. Concept development and inspection labels use the
same distinction; they no longer assign an automatic Chapter 1 deadline to the full sequence.

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
the duplicate concept block. With no scene plan, the explicit no-outline control retains its
full-concept source. Accepted manuscript, world canon, locks and existing plan revisions are
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
