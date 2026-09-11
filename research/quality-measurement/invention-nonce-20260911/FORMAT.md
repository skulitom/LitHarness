# Follow-up: retain the Base64 prefix, remove output constraints

The initial eight-call batch completed before this registration. Its complete outputs retain
aquatic repair/support plots, including all six prefixed responses. The same prefix does not
fix the exact output. This follow-up investigates the remaining native JSON and planning-task
constraints while retaining the operator's requested opaque preprompt.

Use the exact short-1 prefix and request from the initial batch. No new random number or
story ingredient is introduced. Prepare three arms:

- **native:** byte-identical to the initial short-1 request.
- **prompt-json:** remove its schema and replace its system with native.effective_system.
  Captured system and user text must match native exactly; the native schema constraint is
  the sole transport manipulation. Validate returned JSON against the original schema offline.
- **free-premise:** no schema, same prefix and user prompt, followed by this system text:
  "Invent an original LitRPG story in portal fantasy, isekai, or system apocalypse. Write
  one concrete story proposal in ordinary paragraphs. Return story material rather than advice."

Keep requested model, medium reasoning, allowance, timeout and other transport controls
constant. Order: native-1, prompt-json-1, free-premise-1, free-premise-2, prompt-json-2,
native-2. Each is a fresh first response, with no retries, replacements or selection.
Do not inspect story outputs until the six-call batch finishes or an operational stop fires.

The native/prompt-json contrast isolates the native constraint while holding submitted text
equal. Free-premise jointly removes JSON instructions and detailed planning content, and
changes prompt length. It can show that those combined requirements are unnecessary on
these draws, but cannot identify an individual sentence or distinguish their separate effects.
If native does not reproduce the prior cluster, report that baseline failure. If prompt-json
retains it, native JSON is not necessary. If free-premise retains it, the detailed production
task and three-field plan are not necessary either. A contrast that breaks the cluster is
a lead, not a general causal proof or a production prompt change.

Read every complete output. Report names, setting, first magical action and further story
purpose where present, preserving counterexamples. Missing detail is not evidence that a
motif is absent. Searches locate passages only. Do not assign quality scores, rank outputs,
infer training-data distance or claim access to hidden backend messages or sampling settings.

Reuse the initial frozen source and binary. Freeze this runner, protocol and new requests,
and inherit the original frozen-file checks. Commit registration before calls. Keep all
receipts under runs/invention-nonce-20260911/format. Use the same shared-machine lock and
subscription-only isolation. Stop after six attempts or 50,000 recorded tokens checked before
dispatch; an in-flight call can exceed that bound. Per-call timeout is 600 seconds, requested
output 2,400 tokens. Stop on unknown usage, drift, transport/auth/quota failure. No API keys,
reset credits, fallback, implicit resume, live-provider tests or downstream book operations.

The native flag distinction is documented in
[OpenAI's non-interactive mode guide](https://learn.chatgpt.com/docs/non-interactive-mode):
JSONL event output and the final-response schema are separate controls. The actual captured
argv, schema and submitted system text are this experiment's manipulation checks.
