# Correction to prose-diagnostic token terminology

Codex CLI output_tokens includes reasoning_output_tokens. The installed version is 0.153.4.
In the matching official source, the Responses usage mapper copies output unchanged and
takes reasoning from output_tokens_details. Its test gives input 100, output 10, reasoning 5
and total 110. The exec JSONL processor preserves those fields in turn.completed. See the
[version-matched conversion test](https://github.com/openai/codex/blob/3d2ee51ca2d5db578f328aa75e20aa22c0197c9a/codex-rs/codex-api/src/sse/responses.rs#L890-L915)
and [JSONL mapping](https://github.com/openai/codex/blob/3d2ee51ca2d5db578f328aa75e20aa22c0197c9a/codex-rs/exec/src/event_processor_with_jsonl_output.rs#L117-L127).

Earlier prose diagnostics sometimes described input + output + reasoning as accounted
tokens. That sum double-counts the reported reasoning component. It is a conservative
dispatch counter, not a non-duplicated usage aggregate. Preserve historical registrations,
counters and raw usage; this is a visible correction to their interpretation, not a change
to past dispatch rules. Cached input is likewise already included in input.

For this run, reported input + output is 82788; reasoning is a 2772-token component of output.
The frozen counter remains 85560 against its registered 125000 ceiling. Neither number is
verified account-level consumption or subscription-window percentage. One internal sampling
retry further limits any claim about complete consumption. A missing reasoning detail may
also become zero in the mapper, so zero alone does not prove absence of internal reasoning.

The full local version/source audit and raw retry evidence are identified by hashes in
execution.json. No current or historical frozen runner was changed after dispatch.
