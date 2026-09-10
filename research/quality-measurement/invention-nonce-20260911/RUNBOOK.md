# Random integer Base64 preprompts

The operator clarified that seeding means generating a long random number, encoding it as
Base64, and using it as a preprompt. Earlier authored-world experiments tested a different
interpretation. The prepared invention-format experiment was not dispatched; its preparation
is retained under ignored runs/invention-format-20260911/preparation-before-seed-clarification.

This registration tests literal opaque prefixes, with no authored story ingredients,
instructions to use the random text, excluded themes, prior stories or diagnostic prose.
It is a generation-input experiment, not a quality metric, output filter or candidate ranking.

## Frozen comparisons

Use the production discovery renderer with empty brief, third person, no writer and no
previous concepts. All requests have the same schema, task, user prompt, parameters and
transport settings. Seeded requests prepend only Base64 text and two newlines to the system
message. Native JSON output remains enabled in every arm.

Draw two independent unsigned integers from 2,048 random bits and two from 8,192 random bits
using secrets.randbits, once during preparation. Keep all draws, without replacement or
rerolling. Encode each integer's unsigned big-endian bytes using standard Base64. The
production v3 encoder pads to at least 256 bytes; larger numbers use their necessary byte
width. Retain both decimal integers and exact prefixes. No seed is sent as a native sampler
parameter. The default production prefix uses 2,048 random bits by operator direction; the
longer arm is an experiment, not a model-selected policy.

Eight independent first-response calls, fixed order:

1. control-1: no prefix.
2. short-1: first 2,048-bit draw.
3. long-1: first 8,192-bit draw.
4. control-2: identical to control-1.
5. long-2: second 8,192-bit draw.
6. short-2: second 2,048-bit draw.
7. repeat-long-1: byte-identical request to long-1, fresh native session.
8. repeat-short-1: byte-identical request to short-1, fresh native session.

The repeats test whether the same prefix fixes an output or premise on these draws; the
different prefixes probe variation. This small sample cannot estimate a novelty rate.
Prefix content and length are confounded across the two size arms. Inspect no story text
until the complete batch ends or an operational stop fires. Retain format failures and
never retry, redraw, select, develop or accept an output into a book.

## Controls and interpretation

Use generation_trace to verify captured system prefixes, unchanged remainder, user text,
schema and configuration, distinct sessions, full receipts and exact repeat requests.
The debugger now records native output-schema use separately from JSONL event logging.
Read all complete responses and locate recurring names, settings, first magical payoff,
and later plot/power purposes. Literal searches locate passages, not semantic classes.

If repeated names or story families persist across different prefixes, the tested random
preprompts have not removed that repetition. Different output hashes alone do not show
different premises. A repeated prefix returning different text disproves exact replay for
that pair; matching text does not prove universal determinism. Report counterexamples and
mixed results without a quality judgment. Do not infer a native temperature, backend-resolved
model, distance from training data or general probability from these requests.

## Execution

Freeze committed source overlaid only with the owned invention.py, discovery.py and cli.py
changes. Unrelated precision edits remain outside the snapshot. Freeze source, runner,
protocol, dependency lock, diagnostic tool, Codex binary, seed receipts and prepared requests.
Preparation may refresh before dispatch while retaining all original integers; progress.json
forbids refresh or implicit resume afterward. Commit implementation and registration before calls.

Own runs/box.lock after checking processes; run one sustained check or model job at a time.
Use the subscription Codex provider, requested gpt-6-astra at medium reasoning, fresh isolated
sessions, no tools, API keys, reset credits or fallback. Never enable live-provider tests.
Stop after eight attempts or 80,000 recorded tokens checked before dispatch; an in-flight
call can exceed the bound. Timeout 600 seconds per call; requested output limit 2,400 tokens.
Transport/auth/quota failure, unknown usage or frozen-file drift stops the batch.

Raw prose and receipts stay under runs/invention-nonce-20260911. Commit only code,
registration, hashes and bounded paraphrases. Rebuild the audit without a provider:

```bash
uv run python research/quality-measurement/invention-nonce-20260911/audit.py
```
