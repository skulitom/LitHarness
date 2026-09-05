# Prose-input diagnostic, 2026-09-05

Status: completed diagnostic; no production adoption or qualified quality claim. The located
reading observations below are agent defect harvest, not reader labels or candidate rankings.
The procedure and pre-draft amendment are in [PREREG.md](PREREG.md). Derived execution metadata
and output hashes are in [execution.json](execution.json). No generated prose is committed.

## Execution

Eleven calls completed on claude-opus-5: one plan conversion, eight first-scene drafts and two
paragraph edits. Total reported equivalent cost was $3.8945345. Draft lengths ranged from 960
to 1077 whitespace-delimited words; these are execution descriptions, not quality measures.
All outputs were retained and read, with no retries, replacement draws or chosen winner.

The conversion changed private access to floating scheme text into private access to
overwritten papers. Its exact-source quotation check passed despite this scope error. That run
stopped before drafting. The visibly amended continuation used source-checked notes frozen
before any draft. It therefore tests supplied factual inputs, not automatic planner reliability.

## Located observations

The house-guidance and scene-plan treatments did not remove the habits being investigated in
the inspected samples. Examples include invented sensory comparisons in `current_factual-1`
P1 and `plain_factual-1` P1, repeated explanatory commentary in `plain_original-1` P10 and
`plain_original-2` P7, and unsupported precise rule knowledge in `current_original-1` P19,
`plain_original-1` P22 and `plain_factual-1` P20. Other drafts avoid the precise interval; this
small trial does not establish a treatment effect.

Inspection of the actual `current_factual-2` request found the full Chaperone walking
comparison in the unchanged world-form description, at prompt character 19405. Removing the
scene-plan instance had left this other instance in place. The teeth-felt bell and distinctive
lighting also occur repeatedly in the world context. The trial cannot isolate plain wording
across the whole request or attribute recurring phrasing solely to the model's default style.

The editor changed P1 and P5 of the criticized chapter, and P1, P3, P4 and P6 of the fixed
plain/factual draft. It removed some comparisons and joined some fragments, but preserved the
main opening-sentence problem in both inputs. Every paragraph after P6 remained identical.
Source-identity and location checks passed; these checks do not certify semantic preservation.
No new action or quantity was located in the edits, but one sensory aside was removed.

## Consequences and limits

No production prompt, plan or manuscript was changed. The trial does not justify automatic
paragraph rewriting or claim that a new narrative agent will solve the problem. Its controls
also do not establish literary superiority, reader response or generalization to other books.

Two possible next tests remain conjectures: a literal representation of the entire drafting
context with source-mapped rules and preserved author locks; and paragraph reconstruction from
explicit meaning constraints instead of light polishing. The observed conversion scope error
requires attention before treating an LLM context rewrite as a reliable implementation.

Local artifacts are under `runs/ab/prose-inputs-reviewed-20260905`: `comparison.html` contains
every draft and both editing comparisons, `READING.md` records the full located inspection,
and request/result files retain prompts, raw responses and usage. The initial converter
failure and source inspection remain under `runs/ab/prose-inputs-20260905`.
