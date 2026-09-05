# Prose-input trial, 2026-09-05

The operator requested trials of plain writing instructions, factual scene planning and
paragraph-level editing after identifying mannered prose in a generated opening. This is a
small diagnostic with status CONJECTURE, not a qualified reader mechanism, literary metric,
candidate-selection procedure or production change. Read BRIEF.md and EPISTEMIC_GOVERNANCE.md.

## Fixed source and conditions

Use the saved first-scene request from `runs/ab/chapter-rule-context-20260905/request-4.json`.
The same book concept, world, writer, scene events, output length and model are held fixed.
Apply a332c50's world-truth/character-knowledge label correction equally in all conditions.
Freeze both original and corrected requests with hashes. No published prose, exemplars, reading
notes or illustrative rewrite from the conversation enter drafting.

Two factors form four conditions: current versus plain house guidance, crossed with the
original scene statement versus factual planning notes. Only the house-guidance substring and
the final scene-plan slot may change. The writer dossier, complete concept, world facts,
protected operating rules, author locks and transport settings remain fixed.

The plain-guidance treatment removes the global craft/genre lecture and substitutes four
literal instructions. This changes instruction content and length as well as rhetoric; it
cannot isolate imitation of rhetorical form. Other context still contains generated prose.

Make one model call to convert the original statement into starting situation, ordered actions,
ending state and constraints. Each note has an exact quote from the original plan, checked
locally; only neutral note text reaches the writer. Quote matching checks provenance, not
semantic equivalence. Inspect the conversion against the original before drafting. If it
changes material story decisions, stop the factual-plan trial rather than interpreting its
output as a style-only intervention. Do not tune a plan after seeing its drafts.

Generate two first scenes per condition. First replicate order: current/original,
plain/original, current/factual, plain/factual. Reverse that order for replicate two. These are
eight samples of one story, not eight independent books or a powered efficacy experiment.
Retain every output, including malformed, weak or failed ones; no winning candidate is selected.

## Paragraph editing

After drafting, make one editor call on the existing criticized Chapter 1 and one on the
preselected plain/factual replicate 1. Give the editor the full respective text, but permit
changes only to paragraphs 1–6. The fixed instruction addresses strained comparisons,
redundant commentary and fragmented incidental detail, preserving events, causality, quantities,
negation, uncertainty, character knowledge and printed system text. No word-pattern quotas.
Unchanged paragraphs are allowed. Return exact-source paragraph replacements, retaining raw
responses and a diff. Code verifies edit locations and source identity, not semantic fidelity.
No edited artifact replaces an accepted manuscript, even if structural checks pass.

## Reading and limits

Read every generated scene and both edits. Record located examples of the habits under
discussion, story omissions or changes, unsupported knowledge and losses caused by editing.
Compare each edit with its exact input. Observations are defect harvest, not reader labels or
quality scores. No model rates, ranks, chooses a winner or generates feedback for another draft.
Word totals, request hashes, cost and paragraph changes describe execution only.

The untouched existing chapter is the editing control. Current/original repeats are the
concurrent drafting control. Scope, source-identity and billing-guard tests are code controls.
Sampling noise, one-book specificity, plan-conversion drift, instruction-length changes and
different histories between editor substrates limit interpretation. No literary pass bar,
statistical superiority claim or automatic default switch will be made from this diagnostic.

## Stops and provenance

Eleven provider calls maximum: one conversion, eight drafts, two edits. Use the current
repository Claude CLI provider and explicitly request claude-opus-5, with its resolved model
and raw usage recorded. No automatic retries or refusals-triggered redraws. A missing response
after a recorded request requires inspection rather than another paid call. Stop before any new
call when recorded equivalent cost reaches $12 or cost is unavailable; the last in-flight call
can exceed that boundary. No billing calls in tests. All generated text and state stay under
an ignored `runs/ab/` directory. Commit this registration and call-free tests before live calls.
