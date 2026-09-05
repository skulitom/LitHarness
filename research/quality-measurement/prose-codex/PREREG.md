# Subscription Codex drafting diagnostic, 2026-09-05

The operator asks to continue the method search and explicitly permits Codex CLI, with
subscription quota only and no direct API. This is a four-invocation diagnostic of a model
and transport package, not a quality measure, ranking, production provider migration, or
reader qualification. The hypothesis that a different drafting model changes the surviving
prose habits is CONJECTURE. Located agent readings cannot establish efficacy.

## Frozen source and invocation order

Use the exact system and prompt strings from the prior framing trial's
`runs/ab/prose-framing-20260905/neutral-1.request.json` (full) and
`runs/ab/prose-framing-20260905/focused-1.request.json` (focused). These packets share the
same system, scene plan, world rules, private information, state instructions and approximately
900-word target. The previously frozen selection is reused without further review or tuning.
No generated draft, example opening, corpus text or reading note enters either request.

Request `gpt-6-astra`, reasoning effort `high`, in order `full-1`, `focused-1`, `focused-2`,
`full-2`, sequentially. The installed Codex model cache lists this model and effort. Preserve
all four outputs or failures. Compare them by located full-text reading with the prior
`neutral-1`, `focused-1`, `focused-2`, `neutral-2` Claude outputs; these are historical controls,
not randomized contemporaneous controls. The model, provider, reasoning implementation and
residual CLI context change together. No attribution to model alone or winner selection is
licensed. Four opening scenes from one story are not four independent books.

## Subscription and context containment

Before preparation, require the installed CLI's login status to report ChatGPT. Invoke only
the installed Codex CLI through its npm entry point. Set `forced_login_method="chatgpt"` and
the built-in `openai` provider; remove API-key and endpoint override environment variables
from the child environment. Do not read or copy credentials, call a direct API, redeem quota
resets, change account settings, or fall back to another model or transport.

Use `--ignore-user-config`, `--ephemeral`, a dedicated empty work directory, read-only sandbox,
zero project-document bytes, no personality, disabled web search, and the source system text
as `model_instructions_file`. Disable shell/exec, apps, plugins, hooks, host skill discovery,
browser/computer/image tools, and multi-agent features as enumerated in the frozen runner.
Record actual argv, CLI version and raw event stream. Fail a sample if any tool item starts or
completes, or if there is not exactly one nonempty agent message and one completed turn.
This does not assert that all model-visible CLI context is known or absent.

These settings are grounded in the installed `codex-cli 0.153.0` help/features list and the
[official CLI reference](https://learn.chatgpt.com/docs/developer-commands?surface=cli) and
[configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference), read
2026-09-05. The references describe forced authentication, instruction replacement, project
document limits and relevant toggles; they do not establish literary consequences.

## Stop and readout

At most four fresh CLI invocations, no wrapper retries, health-generation probes, or fallback.
Disable unbounded connection retries; retain any internal retry/error events the CLI emits.
Stop on a failed invocation or missing/invalid usage. Also stop before the next invocation
once reported input plus output tokens reach 120000; cached input is already included in
Codex's input total and must not be added again. An in-flight call can exceed this stop. Each
invocation has a 900-second transport timeout. A request without a result cannot replay.
Report subscription token usage, with dollar cost unavailable rather than invented or zero.

Read every complete output in fixed order for repeated explanations, invented comparisons,
retrospective knowledge, current-world consistency, causal gaps and endpoint preservation.
Record locations rather than scores. A changed habit does not establish overall improvement;
no candidate is selected or accepted and no automatic editorial feedback is produced. Save
raw prose under ignored runs; commit only code, derived counts, identities and scoped findings.
Ordinary tests structurally block fresh invocations. Commit registration and passing call-free
controls before preparation and generation. Follow RUNBOOK.md's box-lock requirements.
