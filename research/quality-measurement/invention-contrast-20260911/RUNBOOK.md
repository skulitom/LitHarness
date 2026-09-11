# Contrasting premise batches and representative-sample wording

The operator authorized a contrasting-premise batch followed by random selection and
provided a video transcript proposing the sentence "Use a representative sample."
This is an isolated invention experiment. No premise is ranked by a model, accepted into
a book, or used as reader feedback. The production default remains the opaque Base64 prefix.

## Registered conjectures

Generating alternatives together may avoid the repeated first-choice family. An explicit
contrast instruction may add to the effect of requesting several alternatives. The video's
representative-sample wording may add an effect beyond an additional neutral sentence.
These are untested interventions, not claims about access to training distributions.
The literature source and its limits are recorded separately in SOURCES.md and sources.json;
none of its story text, names, theme lists or the transcript enters any model request.

## First-response arms

Draw two fresh 2,048-bit integers once. Retain their decimal representations and production
v3 Base64 prefixes. Use one prefix in every arm within each block. Keep requested model
gpt-6-astra, medium effort, no tools, user text, native JSON schema and transport constant.
All arms request 80-120 words per premise identifying protagonist, setting, conflict,
first consequential power use and how power growth drives further events. The schema is
the same object containing an array of strings; count is checked offline.

- single: exactly one premise.
- batch: exactly six premises, no added contrast instruction.
- contrast: six plus an explicit instruction to differ in protagonist, setting, conflict
  and the way power growth drives the plot.
- representative: contrast plus exactly "Use a representative sample."
- placebo: contrast plus exactly "Return the requested output."

The last two sentences each contain four whitespace-delimited words and 28 characters
including their period. Tokenization need not match and the placebo need not be inert.
The plain batch is the count control; the placebo is the added-wording control.
Order: single-1, batch-1, contrast-1, representative-1, placebo-1,
placebo-2, representative-2, contrast-2, batch-2, single-2.

Before dispatch, derive and retain one slot per block with
random.Random("invention-contrast.v1:" + decimal_integer).randrange(6).
Reuse that slot for all four batches in the block; the single's slot is zero.
This is deterministic pseudorandom selection independent of output content. It is not a
native model seed or a quality choice. A malformed response has no replacement selection.

## Prespecified expansion

After all ten generation attempts, expand single-1, contrast-1, contrast-2, single-2 in that
order. Use only the retained selected premise as the author brief of the unchanged production
discovery renderer, with no writer, previous concepts or second Base64 prefix. Capture the
source receipt hash, exact selected-text hash and index outside the prompt. Freeze the
renderer and selection code beforehand; record and hash each dependent request before its
call. If a parent has invalid shape, skip its expansion and retain the failure, without
substituting a sibling. No deeper book operation is authorized by this experiment.

## Inspection and inference

Inspect no story prose until all attempted generation and expansion slots finish or an
operational stop fires. Read every premise, including unselected ones, and every expansion.
Report names, setting, initiating power use and continuing plot purpose with per-item hashes.
Inspect recurrence within and across the two batches per arm; six correlated alternatives
are not six independent trials. Literal searches are passage locators, never semantic scores.
Record output lengths because a shorter premise may omit a motif rather than remove it.

If single does not reproduce the earlier cluster, this baseline has failed to reproduce it;
do not claim the treatments cured that cluster. If batch and contrast exhibit the same
variety, the explicit contrast wording adds no visible benefit in these draws. If the same
story families recur across batches or return during expansion, the batch method has not
solved that recurrence. If representative resembles placebo or contrast, do not credit the
phrase with a distinct improvement. A different name alone is not a different story family.
Preserve counterexamples. With two blocks there is no general effect estimate, novelty rate,
quality conclusion, training-distance estimate or proof of a hidden provider mechanism.

## Execution and bounds

Use a frozen copy of committed src, excluding unrelated checkout edits. Freeze runner,
protocol, dependency lock, trace debugger, binary, seed receipts, prepared requests and source
record. Commit registration and run the repository handoff checks before model dispatch.
Hold runs/box.lock after checking processes. Run one sustained job at a time.

Use the existing subscription-only Codex transport and fresh isolated sessions. No API keys,
reset credits, provider fallback, live-provider tests, redraws, retries or implicit resume.
Stop before a call if 100,000 recorded tokens or fourteen attempts have been reached; an
in-flight call may exceed the token ceiling. Per-call timeout is 600 seconds; requested
output limit is 3,200 for the premise arrays and the normal 2,400 for expansion. Unknown
usage, transport/auth/quota failure or frozen-file drift stops the whole batch. Invalid
output shape is retained and prevents only that parent's expansion.

Raw prose stays under runs/invention-contrast-20260911. Commit registrations, code, hashes,
bounded paraphrases and observational controls. Run the final handoff checker and release
only this task's lock. Rebuild results without model calls using audit.py.
