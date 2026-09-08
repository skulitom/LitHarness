# Scene planning and prose handoff

Implemented on operator direction, 2026-09-08 (stage-0 §248). This changes ownership and
context routing. It does not establish an improvement in literary quality.

## Production contract

Discovery proposes story material in planning language. The existing concept and world stages
retain that material, with the original author brief stored separately in new concepts. Model
development cannot replace the author brief, and precision edits cannot change it.

The existing outline call receives the complete concept, author direction, accepted history
and world context. For a concept-backed book, it returns a structured brief for each scene:

- `situation`: the scene's starting circumstance.
- `pursuit`: what the viewpoint character is trying to accomplish.
- `changes`: intended actions and consequences in causal order.
- `future_dependencies`: later-story commitments this scene must leave possible, or an empty
  list. These are kept separate from events to enact now.

The planner may revise provisional obstacles, props and choreography while preserving the
premise's pursuit and magical promise, author choices and established facts. It receives a
planning contract rather than the prose writer's house-style rules. The structured fields
constrain the handoff's shape; code does not certify that their language is factual or good.

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

A fresh registered generation comparison is still needed to determine whether the narrower
handoff improves Chapter 1, preserves necessary causal information, or merely relocates the
same prose habits into the scene briefs. No quality gate or automatic adoption follows from
these structural checks.
