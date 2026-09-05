# Transport framing and scene-context diagnostic, 2026-09-05

The operator asked to continue searching after the full-context, reconstruction and deletion
trials. Status: CONJECTURE, not literary qualification or candidate selection. Read the parent
BRIEF.md and EPISTEMIC_GOVERNANCE.md. The prior located readings are defect harvest and do not
establish the efficacy of the mechanisms below. No published prose or preferred opening enters
this trial. No result may automatically steer or replace a production manuscript.

## Fixed request and conditions

Use `runs/ab/prose-inputs-reviewed-20260905/plain_factual-1.request.json`, the same previously
fixed control request. Keep the approximately 900-word instruction in every arm. Use
claude-opus-5 throughout. Compare four packages, twice each, forward then reverse order:

1. `control`: the saved request through the current provider after its explicit no-tools fix.
2. `isolated`: identical request, but replace `--append-system-prompt` with `--system-prompt`
   and enable `--safe-mode`. This changes default framing and user customization together;
   it does not isolate those two components.
3. `neutral`: same isolated transport, deleting only the initial writer-persona paragraph.
4. `focused`: same neutral system, with source-selected context in the user prompt.

All arms disable built-in tools through `--tools ""`, isolate MCP servers, retain manual
permission mode and the existing CLAUDE.md exclusions, and use no session continuation.
Nonempty agent allowances are outside this trial. No permission bypass, fallback, health
probe or retry is permitted. Record complete argv alongside each request and freeze the
installed CLI version and code. The tool-availability correction is a separate implementation
fact; this trial's control is after that correction, not a byte-identical historical transport.

The installed Claude Code 2.1.261 help and
[CLI reference](https://code.claude.com/docs/en/cli-reference), accessed 2026-09-05, distinguish
approval (`--allowed-tools`) from availability (`--tools`). They also advertise system-prompt
replacement and safe mode without suppressing authentication. The documented flag behavior
motivates a transport comparison; it is not evidence of prose improvement or a verified exact
model-visible prompt. Record token usage and actual response envelopes without claiming that
lower token counts measure literary quality.

## Context selection before drafting

One isolated call receives source IDs and selects keep/drop for each optional unit. It cannot
write replacement context. Grouped character descriptions retain their owner; section headings
stay with retained lines. The entire system message (all rules, costs and author locks), private
information block and current scene plan are protected. The persona manipulation remains its
own independent step; future milestone instructions in the system stay in every arm.

The selector may omit future plot summaries, actors not needed now, distant progression facts
and duplicates. There is no size or selection quota. Validate complete ID coverage and boolean
decisions; render original text only, never selection reasons. Read every selection against the
source before drafting. Source-only corrections may restore missing context, remove irrelevant
future facts or repair selection identity errors. Record every correction and rationale, retain
the raw result and freeze the reviewed decisions before any draft. This tests source-reviewed
selection, not autonomous selector reliability. A later output cannot tune this input.

## Execution and interpretation

Nine calls maximum: one selector and eight drafts, sequential. Stop before the next call once
recorded equivalent cost reaches $6.00 or is missing; an in-flight call can exceed it. An
interrupted request without a result cannot replay silently. Ordinary tests structurally block
fresh calls through `LITHARNESS_ENV=test` and never enable live-provider tests.

Read all eight complete outputs in their fixed order. Locate surviving mannerisms, changed
events or knowledge, omitted necessities and any transport failures; do not rank, choose a
winner, redraw, or declare better prose from length or token count. One story and two samples
per condition do not establish transfer, literary validity or production qualification.
Retain all prose locally under ignored runs; commit code, derived counts, identifiers and
scoped findings. Follow RUNBOOK.md's process and box-lock rules. Commit registration and
call-free controls before the first paid call.
