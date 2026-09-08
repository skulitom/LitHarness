# Subscription Codex comparison — 2026-09-08

The operator requested the clean-start and existing pipelines on Codex, with Claude disabled
if that resolved the reading problems. Both Codex arms use the native CLI 0.153.4, request
`gpt-6-astra` with medium reasoning, and require ChatGPT subscription authentication. Neither
uses API credentials or falls back to another model. The exact short clean-start system and
author brief are unchanged from the [Claude baseline](FIRST_RUN.md).

Recorded requests, available raw responses, failures, hashes and reading notes live under
`runs/codex-pipeline-comparison-20260908/`. Generated chapters are not committed. These are
located readings of individual artifacts, not validated quality scores or reader labels.

## Clean-start result

`clean-first/chapter.md`, **Somewhere Worth Going**, completed in one tool-free turn. Its
SHA-256 is `e12a1e9b31e9a670d5adf695d1f918c8bd495fca1ae89bea215393df5e5049bf`.
It is the unchanged first model response. The preceding `clean/` attempt failed authentication
preflight because an exec-only flag had been placed on login status; no model generation ran
there. That failure remains recorded.

Compared with the Claude baseline's debt and magical accounting, this chapter gives its
protagonist floating islands to explore, a movement skill to learn through failure and
practice, useful discoveries, and progression that changes the next crossing. Her repair
experience helps her operate a hanging carriage. That is much closer to the requested magical
adventure experience in this particular sample.

It still contains the reported defects. Unexplained exact historical durations, an arbitrary
survey percentage and counted background objects remain. Several asides explain a feeling
or decision which the action already communicates. Repeated short setup/reaction/punchline
paragraphs also become conspicuous. One sentence has the boatman leaving with money which is
still sewn inside the protagonist's coat while she is stranded elsewhere. Useful skill costs
and duration improvements should not be conflated with incidental numerical decoration.

Read the entire artifact and `clean-reading-notes.md` for both working passages and located
defects. This is one new story per provider, not a same-story crossover or an estimate of
reliability. Changing provider also changes model and CLI context; this test cannot separate
their individual effects.

## Automatic project instructions

The two-call `document-probe/` used the same greeting request, replacement system, temporary
folder and harmless `AGENTS.md` marker. With `project_doc_max_bytes=32000`, the first response
included the marker. With the generation setting `project_doc_max_bytes=0`, it omitted it.
Both completed. The frozen requests and outputs are in that directory.

This demonstrates suppression of that local AGENTS instruction in this paired test. It does
not capture all effective context, test Claude's loader, or prove a literary cause. Both
Codex generation paths additionally use empty working directories and ignore user config
and rules, with memory, hooks and plugins disabled. The earlier Claude baseline used safe
mode and an empty working directory; its recorded main input was 403 tokens. No evidence
from these runs establishes that this repository's long instruction files entered generation.

At the subsequent read-only inventory, the personal Codex `AGENTS.md` and Claude `CLAUDE.md`
were empty. The checked ancestor instruction paths were absent. The repository's two guides
were present and unchanged; their hashes and the exact paths checked are retained in
`document-probe/instruction-file-inventory.json`. This is a current observation, not proof
of the configuration at an earlier run. The coding assistant does receive repository guidance;
that is separate from what these isolated child writing processes receive. Indirect influence
on assistant-designed application prompts remains possible and was not tested here.

The existing pipeline deliberately passes its writer persona, discovery instructions, scene
plans and established world rules. Those are actual application inputs, independently of
automatic CLAUDE.md or AGENTS.md loading. Removing automatic documents does not remove them.

The subsequent native-feature audit found separately enabled built-ins beyond shell access.
The first Codex chapter made no tool calls, but calling its entire tool inventory disabled
was too strong. Both launchers now record `unused-builtins-disabled.v1`, explicitly disabling
the verified unused built-in and skill controls. Explicit MCP/search roles remain possible.
The audit did not establish a complete inventory or a documented Node-off switch; no Node
execution was observed. Do not equate feature configuration with capture of all context.

`builtins-disabled-probe/` repeats the negative arm's greeting, system and working directory.
Reported input falls from 5,356 to 3,754 tokens; both outputs are the same greeting without
the AGENTS marker. This demonstrates changed request size, not a literary cause. The remaining
tokens are not fully attributed. `BUILTINS-ARM.md` registers one additional clean chapter under
the new controls, preserving the original response instead of substituting a preferred sample.

The additional chapter, **A Thread to Hold On To**, completed in one turn at
`clean-unused-builtins/chapter.md`; SHA-256
`dab530db58fa587b0c0ef8934b08b345f59d53882be6d7c617d6c9fa881fdf4f`.
Its reported input was 3,835 tokens. It turns a small craft skill into a retrieval attempt and
shared escape, then offers a larger adventure. Focus costs are intelligible consequences of
the action. The world has things to discover beyond its interface.

The exact-number problem persists: eleven copper coins with no practical consequence,
precise biographical durations, and counted attempts. Explanatory asides persist as well,
including the narrator qualifying whom the protagonist addressed. The final claim that her
needle lies below the cliff is not supported by the preceding action: it was stitched into
a tree, and the connecting thread was cut. These are located defects, not a claim that all
numbers, whimsical narration or craft-based abilities are unsuitable. See
`clean-unused-builtins-reading.md` for the complete reading notes.

This second sample does not support treating removal of unused built-in context as a
sufficient prose fix. It does not establish that the extra context had no effect.

## Existing-pipeline result and integration failures

The `legacy/` arm retains discovery, concept development, the precision edit, listing, world
seeding, scene planning, drafting and ordinary acceptance. It uses the compiled `halloran`
writer, no exemplars, no title search and two scenes per chapter. Its exact dossier and
source hashes are frozen in registration.json. It is not a matched control against an older
Claude book with a different writer or story.

The first run reached **Climbing the Hanging Sea**, then stopped before drafting. The
Architect's tools required approval in the noninteractive Codex session, so it made no world
declarations. Its final explanatory message was incorrectly accepted as a successful tool
turn. The ordinary first tick then correctly found no usable starting state and no work.
The old Architect command does not save the provider's full raw turn; that transport trace
is an explicit gap. Its final output, zero added records and world-check gaps are retained.

`legacy/AMENDMENT-1.md` records a narrow transport correction and explicit continuation on
the same book. Original concept, title, listing, registration and failure logs remain intact.
No new premise or preferred candidate replaces the failure. The continuation retains the
same quota store and original wall deadline.

That continuation proposed 122 records, then failed the tool-receipt check before accepting
a world. Its raw exchange was lost through the Architect recording gap, so its cause remains
unidentified. One separately recorded read-only world-check call confirmed that ordinary
command validation errors retain receipts and pass the adapter. It did not reproduce the
lost failure. Failed Architect usage was also missing from the old policy totals.

The provider now has optional full-attempt persistence through `LITHARNESS_CODEX_TRACE_DIR`,
including requests before the call and final output files before validation or timeout cleanup.
`legacy/AMENDMENT-2.md` records a second explicit continuation on the same partial world with
that tracing enabled. The original tool guard and generation inputs are unchanged.

That traced continuation exposed recovered input mistakes and exhaustion of the adapter's
128-command cap. The bridge now distinguishes argument refusals from transport/runtime faults,
accepts recovered mistakes only with matching receipts and later execution, and allows up to
512 commands. `AMENDMENT-3.md` records those observed corrections. The next seed completed its
tool turn, but the accumulated partial worlds had incompatible skill-tree links which the
allowed commands could not retract; the resulting system could not be finalized. No chapter
was produced in this store. The failed history is preserved, not classified as a prose result.

`legacy-clean-seed/` registers a single fresh world seed from the byte-identical first concept,
title, listing and author brief with the corrected adapter. It creates no replacement premise
and uses no literary feedback. This explicitly separates the corrected transport attempt from
the damaged partial world, retains the prior known usage floor and has its own bounded stop.

The fresh seed completed at 18:54 UTC and proposed 300 records. Ordinary acceptance took
296, withheld four superseded proposals and derived two system records. Its accepted-world
check still reported a missing usable rank snapshot. The model had consistently used `level`,
matching its declared sheet, while the engine requires the internal key `rank`. The vocabulary
did not expose that requirement; the specific gap appeared only after acceptance. The check
also warned about schedule-space records, some of which are intentional representations;
those warnings alone do not establish an invalid starting state.

The registered run stopped without repair, a second seed or a chapter. The complete provider
exchange, checks and `legacy-clean-seed/failure-notes.md` are retained. This identifies an
existing authoring-contract and feedback defect under Codex, not a prose comparison or evidence
of document leakage. Successful command execution did not establish a usable world.

The vocabulary now exposes the existing `rank` storage key independently of a story's printed
rung label. A focused regression checks that following the documented key clears this gap,
while substituting the printed label does not. No saved world was repaired or rerun, and the
pre-acceptance feedback behavior is unchanged. This is a protocol correction, not a prose rule.

The raw bridge replies also contained replacement characters from a Windows encoding mismatch.
The Python child now uses explicit UTF-8 for stdout and stderr; the original damaged replies
remain unchanged. Offline fixtures additionally exposed stdout-only rate-limit misclassification
and missing usage being reported as zero. Both contracts were corrected without further model
calls. `transport-audit-fixes.md` distinguishes observed run defects from fixture reproductions.

## Subsequent authorized continuation: complete Chapter 1

After the operator asked to continue, `legacy-continuation/` registered a separate allowance
and retained the original concept, listing, title and failed run history. It reconstructed
the accepted world through ordinary declarations in a fresh store, recording seven
`level` → `rank` key corrections, moving the existing first standing to the opening, and
adding an opening snapshot with no learned abilities. It replayed 297 declarations;
ordinary acceptance reproduced the two derived system records. No model reseeded the world
or drew another premise. This is a mechanically repaired continuation, not an autonomous
end-to-end success or a matched comparison against the clean-start stories.

The continuation produced **Climbing the Hanging Sea**, 2,108 words, at 20:17:54 UTC on
2026-09-08. Chapter SHA-256:
`594eb60bf6f5c52f053803ba658fd232f38b432c3c771c567765e2cc501a473e`.
Both scenes were accepted on their first drafting attempt. Eight provider calls, including
four health probes, reported 86,772 input-plus-output tokens. Every usage receipt is
available; there was no model fallback or revision call. The earlier known usage floor
remains separate. Registration, exact repair, all calls, scene dossiers and complete
reading notes are retained under `legacy-continuation/`.

Reading the complete chapter found magical discovery, usable learning and an actively
wanted destination. The earlier decorative exact counts and dialogue-delivery explanations
were not prominent in this artifact; its numerical clutter mainly comes from supplied
game displays. Weaknesses remain: the canvas experiment has little particular motivation,
the long rescue becomes a sequence of magic lessons, harness damage appears after an
earlier soundness check without an intervening event, and dialogue introduces a payment
contrast the protagonist did not raise. These are located readings, not reader labels or
proof of reliable quality. See `reading-notes.md` and `independent-reading.md`.

The frozen writer request identifies an application-context problem independently of
automatic project files: entire future scene plans are stored as accepted world rules
and repeated in the writer's high-priority rule block. The explicit no-payment obligation
also appears in the scene plan. The prompt still says Mara has no assigned opening level
while supplying a current Level 1 display; the mechanical baseline repair did not resolve
that narrative contradiction. The chapter delays the announcement until the first Lean,
but passing world-readiness checks did not certify mutually consistent story instructions.

The first draft copied `[Record] mara Personal level rung_one` directly from the supplied
standing example. That example also ran into the length instruction on the same line.
The subsequent software correction renders an unambiguous declared rung name and resolves
it back to the original stored identifier, retaining exact-ID precedence and refusing
ambiguous aliases. It separates the example from the next instruction. The original chapter
remains unchanged; this correction has not been credited with improving its prose.

`raw-accepted-audit.json` verifies both accepted scene hashes against the original responses
after existing transformations: one em dash becomes a comma in scene one; scene two is
unchanged. The library adds/formats scene breaks. The display leak and narrative defects
were already in the original responses. All three manuscript revisions rebuild cleanly;
ordinary shape and integrity passes did not detect the located reading problems.

## Follow-up: isolate world input and remove obsolete scaffolding

The next software change separates the world-builder's concept projection from the complete
story plan. It omits detailed planned opening actions, future turns, arc outcomes and debts.
Pre-opening history and system definitions remain available, alongside the supplied listing
and original author brief. Chapter
reconciliation no longer receives the original discovery treatment or asks for every declared
name to reach the page. Vocabulary now describes world rules and manifestations as in-world
properties rather than instructions for narration.

An offline replay of the retained continuation concept produced a 5,207-character world
projection instead of its 23,094-character full rendering. None of the complete excluded action
or payoff fields appeared in the projection. Review rejected initially dropping the author
brief and ignoring the supplied listing: explicit constraints and overview overrides must
remain effective. The source digest, final rendered request and checks
are retained in `runs/world-context-cleanup-20260908/input-boundary-report-final.json`. This verifies
input routing, not literary improvement; free-text world fields can still contain intentions,
and previously accepted unkeyed world rules are not automatically reclassified. No new model
call or rewritten chapter is attributed to this change.

The same change fixes a separate structural leak: unkeyed components of a future change
could survive after its positioned occurrence record was excluded. Drafting, planning and
repair now require the occurrence record to be visible at the same boundary. Unknown scene
coordinates cannot admit positioned changes through drafting or repair. An old regression
that explicitly expected future-state leakage was replaced with the conservative boundary
contract, including a check through the actual drafting entry point. Recorded scene evidence
supplies a coordinate when available; the fallback does not invent one for imported scenes. Participant and
capability definitions remain independently available; proposed types cannot hide accepted
facts. Regression fixtures cover time, POV, source evidence and the fallback paths.

The cleanup removes unused exception/protocol exports, an unused fixture helper and orphaned
calibration-test scaffolding that imported a deleted module. Historical essays beside the
changed production prompts are replaced with their current contracts. Experiment artifacts,
saved books and handoffs with unique evidence remain available.

Software validation for this follow-up is recorded under
`runs/world-context-cleanup-20260908/`: focused checks, intermediate failures, the final
repository handoff in `handoff-verified.log`, and the reproducible `verify_inputs.py` replay.

## Provider decision

The Codex chapters demonstrate a promising change in experience, but they do not eliminate
the counts, explanatory narration or continuity errors. Codex is available as an explicit
provider choice; the condition for declaring the problem solved and disabling Claude has
not been established. Keep the independent launcher and all recorded outputs available.
Do not delete the existing system or saved books on the strength of this sample.

Implementation validation: the adapter and subsequent standing-display correction passed
the repository handoff (lint, types, lock/diff checks, full tests with coverage, wheel build
and corpus-history audit). The standalone clean-start tests also passed for the adapter.
The display correction's regressions cover declared-label round trips, ambiguous aliases,
exact-ID precedence, character-kind isolation, unchanged non-standing identities and names
containing an edge phrase. These verify software behavior, not generated prose quality.
The earlier adapter output is `handoff-final.log`; the later correction's complete output
is `legacy-continuation/handoff-final.log` in the local comparison directory.
