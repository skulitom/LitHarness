# Attention trace: stopped before chapter drafting

**OBSERVED; unqualified diagnostic.** The single source-only proposal completed and passed
structural checks. Its temporal review was not accepted for use as operative attention.
All four chapter calls were skipped under the registered stop rule. This batch contains no
chapter comparison and no observation of an attention intervention's effect on prose.

## What failed

The representation requests a current concern, an event that interrupts or redirects it, and
something still unresolved. Several proposed concerns already incorporate understanding reached
after their listed interruption. They summarize the interval retrospectively instead of defining
the attention state that can precede and respond to the event.

| Interval | Source anchors | Located temporal problem |
|---|---|---|
| P1 | F03a, F05, F06c | Current concern includes the later interpretation at F06c; the shift to interpreting the list is earlier at F05. No earlier state or activation time is supplied. |
| P2 | F10, F13b, F14a | Concern presupposes disappearance and later self-assessment; disappearance itself is the listed interruption. |
| P3 | F16, F17, F19-F20 | Concern combines an early response with later knowledge of what the awards leave unspecified; the door obstruction precedes that later knowledge. |
| P4 | F21-F24 | Current concern already centers the boy and his resistance; noticing the boy is presented as the shift, and resistance is recorded later still. |
| P5 | F25a, F25c, F26 | The concern about reachability can precede the closing interruption. Its end question remains provisional and does not add a mechanism. |
| P6 | F27-F29 | Concern bundles purchases with survivors' scrutiny and persistent perception; the latter details follow the listed recall-price interruption. |

All six rows were read against the source. Foreground/peripheral IDs are valid, distinct and in
their intervals. Evidence IDs use the registered current-or-earlier interval allowance. Text
lengths and phase coverage pass. The content is broadly compatible as retrospective character
understanding, with no new identity, biography or established supernatural rule. That does not
make it a usable live trajectory: the schema lacks distinct before/after states and activation
times, and the structural guard permits evidence from anywhere in the current interval.

The natural-language instruction against using later knowledge did not resolve that ambiguity.
The operative direction to carry a current concern until its listed interruption therefore has
no coherent temporal reading in several rows without additional interpretation or repair.

This is a representation and delivery failure. It does **not** prove that a writer would leak
future knowledge: the shared writer system separately requires source timing and might delay
or reinterpret the concern. No writer was run. It also does not establish that this behavior
causes the earlier chapters' explanatory prose, or that attention guidance cannot help.

## Gate and disposition

The source review records static compatibility and no new canon, but does not certify absence
of future knowledge for the proposed operative use. The runner refused to freeze writer inputs
with `trace needs complete source review`. The retained rejection confirms zero writer requests
and no draft manifest. The proposal was not patched, regenerated or promoted into character
canon. There was no alternate model, retry, quality ranking or candidate selection.

The two-draw background/operative comparison remains unexecuted. It must not be entered into
history as a null prose result. The comparison page displays the unchanged proposal and each
temporal review, prominently stating that no chapters were generated.

## Next representation question, not yet tested

A subsequent version should distinguish attention **before** an event from the update caused
by that event, and give each concern an explicit activation point. The evidence allowed for the
earlier state must precede that point; phase-wide evidence is insufficient. Prefix-limited
inputs could provide stronger containment, while already-known context would need explicit
availability handling. This can be derived from each scene rather than prescribing a narrative.

Those are unrun design conjectures, not a qualified mechanism or a repaired result. A fresh
registration and temporal controls are required before spending on that changed representation.
Do not silently repair this trace or count a later run as one of its missing chapter draws.

## Reproduction and accounting

Registration commit: `72b37028f1700f59325f0009702acf7287e5dc1a`. CLI 0.153.4, requested
gpt-6-astra/high, ChatGPT subscription authentication; resolved model not separately exposed.
One call completed in 58.542 seconds, with zero tool use. Usage: **8354 input + 1491 output +
516 separately reported reasoning = 10361 tokens**. Cached input 2688 is included in input.
The 95000 token stop was not reached; the temporal review stopped the batch. No direct API,
provider fallback, probe, reset or purchase was used.

Local root: `runs/ab/prose-attention-20260907`. `trace-1/full-1.*` retains exact request, actual
argv, raw events, parsed result and text. `trace-review.json` records all six source reviews;
`freeze-rejection.json` records the gate. Rebuild derived results and presentation with
`uv run python -X utf8 runs/ab/prose-attention-tools/build_stopped_review.py`. It verifies frozen
inputs, raw/result/text identity, review hashes, structural validation and zero writer requests.
The unused four-chapter review scaffold remains ignored and did not produce readings or drafts.

Final handoff: **4088 passed, 19 skipped, 88.76% coverage**, with clean lint, types, diff/lock
checks, wheel build and corpus-history audit. Browser review confirmed all six intervals,
expanded source/request/review sections, zero console messages and no horizontal overflow at
1280/740 pixels; both screenshots were inspected. Six snapshots were archived with hashes.
Explicit claim validation also corrected artifact-kind labels to the allowed derived_result
kind in this and the preceding constraint record; prior evidence bytes and hashes did not change.
