# One fixed treatment through three real chapters

The operator chose one fixed story through three chapters on 2026-09-13. Wren is the
first Opus expansion in the prior registered crossed dispatch order, not a new selection
by quality. Its complete treatment is `plan-astra-opus-1.json`, frozen by receipt hash in
the runner. The preceding common-writer chapter is not imported into this book.

## Question and boundary

Can this treatment reach three accepted, attributable chapters through ordinary book
creation, world seeding, planning, drafting and chapter reconciliation while retaining
earlier chapter bytes? Read all resulting chapters after the run to locate pursuit,
capability, cost and continuing-conflict passages. Such readings are descriptive
observations, not reader labels, quality scores or permission to edit this book.

This is one feasibility case, not a controlled estimate of batching savings or a claim
that repetition is solved. No reader mechanism is qualified or promoted. There is no
story-candidate ranking, replacement book, diagnostic feedback, reroll or manual world repair.

## Engineering preparation

The earlier baseline's world calls dominate returned usage. Its two completed first-book
grows made 26 and 50 individual declarations, though batching was already available.
The world instruction now specifies the existing batch command, with no change to
declaration or acceptance semantics. Successful bridge results omit duplicate argument
and executable arrays; complete audit rows and complete failure receipts remain.
`engineering.json` gives original trace hashes and deterministic serialized-byte counts
before and after this projection. Bytes are not token savings; native usage includes
repeated and cached input and will be reported separately.

The earlier rejected native turn used Codex resource-listing builtins. The documented
MCP enabled-tools setting restricts server tools, not those builtins. The official
[configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference)
and its linked JSON schema were inspected on 2026-09-13; no resource-builtin disable
setting was found. This is a limitation of this investigation, not proof no control
exists. The bridge note now explicitly directs reads to its sole command tool and
forbids resource discovery. The native event rejection guard remains strict, including
empty resource-list responses. This mitigation is not structural removal of exposure.

## Frozen inputs and execution

`prepare` archives committed production source and migrations into the ignored run root,
creates an interpreter importing that snapshot, records dependency versions, and hashes
the native executable, runner, this runbook and fixed parent. It refuses overwrite.
The executable must report `codex-cli 0.154.0-alpha.6.2` and use ChatGPT subscription
authentication. No API-key transport, fallback provider or model switch is permitted.
Generation uses the repository's Codex default, gpt-6-astra with medium reasoning.

One preparatory call uses the application's ordinary `render_concept_request` with the
fixed `Discovery`, six first-arc scenes and third person. `Concept.from_development`
retains that discovery and opening. The first shaped response is kept without a name
redraw or precision edit. Failure stops the run. This external concept handoff is
explicit; it is not a fresh invention through `concept` or a claim that every earlier
CLI concept-preparation step ran. All subsequent work uses ordinary CLI commands.

Run `listing --concept` with six scenes, third person, one title attempt and no web title
check, retaining its existing listing workflow and accounting for all its calls. Seed,
check and accept the proposed world. Run ordinary ticks until each successive
chapter is accepted, then drain queued non-draft work, grow, check and accept the world.
Use one scene per chapter, six chapters per arc, and a target of 1,800 words. Stop at
three chapters. No draft import, policy bypass, raw reader-to-writer feedback or accepted
manuscript mutation is introduced by this driver.

The limit is 60 native attempts and 1,800,000 reported tokens, including the health call
and usage from rejected native turns. This leaves headroom above the earlier case's
two-chapter spend for a third chapter and its reconciliation; savings are not assumed.
Both runner and ordinary CLI have these bounds. Token and three-hour wall ceilings
are checked before calls, so an in-flight call may overshoot; existing per-call timeouts
remain. Unknown usage, transport failure, containment failure, source/binary drift,
attribution failure, changing earlier chapter hashes, an unexpected queued draft,
overshooting the chapter boundary, or twelve ticks without progress stops the run.
Retain every started attempt and its failure. Do not implicitly resume a stopped run.

## Commands and handoff

Own `runs/box.lock` with the runner's task prefix and keep one sustained job on the
machine. Run focused tests and `uv run python tools/check.py handoff` before committing
engineering and runner changes. Then prepare, inspect and commit registration before
generation:

```powershell
uv run python research/quality-measurement/distinctive-continuation-20260913/run.py prepare
git diff --check
# Commit this experiment's registration before the following command.
runs/distinctive-continuation-20260913/runtime/Scripts/python.exe research/quality-measurement/distinctive-continuation-20260913/run.py run
```

Inspect saved status, audit, jobs, world and verification views before implementation
diagnosis, following `.claude/skills/debug-book/SKILL.md`. Report accepted chapter hashes,
all native attempts and usage, per-profile totals and tool-call counts, including stopped
results. Distinguish requested model attribution from backend resolution not present in
native receipts. Any new experiment needs a new registration. Release only this task's lock.

A later reader-admission refresh must use read-only backups and its own call-free runbook;
this registration authorizes no new reader-validation calls.
