# Phase 3: native instruction-template control

Registered after reading all nine phase-2 treatments. All six Codex treatments named Mara
Venn; the three Claude treatments named different protagonists. Professional expertise also
appeared in Claude's treatments, so the whole pattern is not unique to Codex. This phase
tests the narrower hypothesis that Codex's model-catalog instruction templates cause its
repeated names and repair/restoration premises. No output is a quality label.

Keep the exact phase-1 minimal CompletionRequest. For each of gpt-6-astra and gpt-5.5 at
medium reasoning, compare two frozen native catalogs. Control is the installed current model
catalog copied before calls. Blank differs only by replacing string values inside the two
target models' model_messages objects with empty strings, recursively. Keep model IDs,
transport-route flags, tools, native/application schema, timeout, output allowance, permissions
enforcement, authentication, and the explicit application system unchanged. Both arms select
their catalog with the documented model_catalog_json setting. This removes catalog prose;
it does not remove native fixed messages, environment context, or unknown backend framing.

An offline debug prompt-input preflight, with an empty unauthenticated state directory,
confirmed the catalog shape is accepted and the blank catalog removes substantial template
text. The debug subcommand cannot use exec's isolation flags or output-schema flag, so its
output is a reconstruction, not a captured completion request. No model was called in that
preflight. Capture actual exec argv, stdin, system, schema, settings and raw response for
every real slot, including the injected catalog setting. Do not use transport equality to
assert equality of undisclosed backend inputs.

Fixed order: astra-control-1, gpt55-blank-1, astra-blank-1, gpt55-control-1,
gpt55-control-2, astra-blank-2, gpt55-blank-2, astra-control-2.
These are eight first-response attempts, two per model/catalog cell. No responses are fed
into later requests. Use the same isolated baseline source/interpreter and native binary;
freeze both catalogs, source, this document, runner and request, and commit registration
before dispatch. Existing phase registrations and results remain intact.

Own the shared box lock, dispatch sequentially, and inspect story outputs only after the
entire phase or an operational stop. Stop at eight attempts or 120,000 returned tokens,
checked before dispatch; an in-flight call can exceed the bound. Any auth/transport/quota
failure, unknown usage or frozen-file drift stops remaining calls. Retain failures, with no
redraw, implicit resume, fallback, API-key spend, usage reset, live-provider test flag,
downstream book generation, model ranking or candidate selection. Validate with
Discovery.from_invention. Inspect whole outputs after hash/session checks and location-only
search. Raw material stays under runs/invention-cause-20260910/phase3.

If repetition remains under blank, the removed native catalog prose is not necessary on
these draws. If blank breaks the cluster while control retains it, the removed templates
become a candidate mechanism requiring narrower isolation. Neither outcome establishes
training-data origin, actual backend sampling, or the exact reason a model selected a name.
Keep conclusions at the tested boundary; this experiment does not authorize a production
prompt edit or a thematic exclusion.
