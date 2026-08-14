# Provider adapters: local-first inference for LitHarness

**Status: BUILT AND GREEN.** `src/litharness/providers/` — focused adapter, recovery, and
Conductor tests (+3 opt-in live), ruff clean, mypy strict clean. Parsing is verified against the real captured envelopes
recorded in this document, not invented shapes.
**Directive:** Default to the local Claude Code session; fall back to the local Codex
CLI; use Ollama for iterative testing, because paid-model iteration is expensive.
**Probe baseline:** All numbers and flags below were measured on this machine
2026-08-12. They are facts, not estimates. Re-measure after any CLI upgrade.

## 1. Why this is a plan-level decision, not an implementation detail

PLAN.md §2 says "work with local models or API providers behind adapters; two
adapters suffice", and Stage 0's exit criteria name "provider fake + one local
adapter (+ one API adapter)". This document fixes *which* adapters, in what
precedence, and — critically — records the per-call overhead of the default one,
which changes the §15 cost model.

The important structural point: **`claude -p` is an agent, not a completion
endpoint.** It ships its own system prompt, tool definitions, session store,
CLAUDE.md discovery, MCP config, and permission engine. Used naively as an
inference backend it costs ~24k input tokens per call before your prompt is even
considered. The adapter's job is to strip it down to a single-shot completion.

## 2. Local tooling as measured (2026-08-12)

| Tool | Version | Status | Role |
|---|---|---|---|
| `claude` | 2.1.227 | Works | **Default** inference backend |
| `codex` | codex-cli 0.147.0 | Works (`gpt-5.6-sol`, ChatGPT-account auth) | Fallback |
| `ollama` | 0.32.8, server up on :11434 | Works, 8 models pulled | Test + cheap-loop backend |

Ollama models available locally: `qwen3:4b`, `gemma3:4b`, `gpt-oss:20b` (13 GB),
`deepseek-r1:8b`, `phi4:latest`, `gemma2:2b`, `llama3.2:1b`, `llama3.2:latest`.

### 2.1 Codex required an upgrade — keep the health probe anyway

On 0.107.0 the fallback tier was dead in three separate ways, all reproduced:
the default model returned `"gpt-5.6-sol requires a newer version of Codex"`; the
models cache failed to decode against the live server (`unknown variant 'max'`, a
client/server version skew); and every explicitly named older model
(`gpt-5-codex`, `gpt-5.1`, `gpt-5.1-codex`) returned `"not supported when using
Codex with a ChatGPT account"`. Every attempt wrote an empty
`--output-last-message` file.

Upgrading to 0.147.0 fixed all three, and `gpt-5.6-sol` now works against the
existing ChatGPT-account auth with schema-enforced output.

**Keep the lesson, not just the fix.** For an entire CLI generation, `codex` was
installed, authenticated, and on `PATH` — and failed every call. A liveness check
that only runs `codex --version` would have passed it and routed real work into a
provider that returns empty files. Health probing must be *probe-then-use*: a
real round trip against the configured model, not a version string (§5, rule 1).

## 3. The measured cost of the CLI backends

Both CLI adapters carry a fixed per-invocation tax. It is large, it is unrelated
to your prompt, and the two tools amortize it very differently.

Repeated identical `claude -p` calls, trivial prompt, Haiku 4.5:

| Call | cost | input | cache read | cache write | output |
|---|---|---|---|---|---|
| cold | $0.049 | 10 | 0 | 24,037 | 99 |
| warm | $0.013 | 10 | 19,057 | 4,982 | 112 |
| warm | $0.013 | 10 | 19,057 | 4,979 | 87 |

Repeated identical `codex exec` calls, trivial prompt, `gpt-5.6-sol`:

| Call | input | cached | cache write | output |
|---|---|---|---|---|
| 1 | 14,887 | 0 | 0 | 21 |
| 2 | 14,679 | 0 | 0 | 21 |
| 3 | 14,887 | 0 | 0 | 21 |

Read these carefully, because they drive design:

- `claude -p` has a **~24k-token harness tax**. About 19k is cacheable (1-hour
  ephemeral); **~5k is re-written on every call and never cache-reads**. Floor:
  **~$0.013/call on Haiku**, ~3.5–4.2 s wall, of which ~1.3 s is process startup
  before the first API byte. Proportionally worse on Opus-tier models.
- `codex exec` has a **~14.8k-token tax that never amortizes** — `cached_input_tokens`
  was `0` on all three calls, including back-to-back repeats of a byte-identical
  request. Wall time ~7.8 s.
- So in effective full-price input tokens per warm call: `claude -p` ≈ 7k
  (5k written + 19k at the 0.1× cache-read rate), `codex exec` ≈ 14.8k. Claude is
  the cheaper *and* faster steady-state choice, which is the right default.
  Codex bills against a ChatGPT-account quota rather than dollars, so it reports
  no cost — `cost_usd` is `None` for that adapter and only its token counts and
  invocation count are meterable.

**Design consequence — batch, don't chatter.** A 100k-word draft at 140–160
scenes with 5–8 model calls per accepted scene (generate, extract, evaluate,
retry) is ~1,000 invocations, i.e. **~7M tokens of pure harness overhead on
`claude -p`, ~15M on `codex`**, against the §15 payload estimate of 2–4M. The
overhead is 2–7× the actual work. Two mitigations, both mandatory:

1. **Every small, mechanical call goes to Ollama, not `claude -p`.** State
   extraction, gate-failure feedback rewrites, status-block rendering, summary
   recomputation — these are cheap-model work and must default to the local
   backend even outside test runs.
2. **Fold multiple asks into one invocation.** Draft-plus-extract in a single
   call with a structured envelope beats two calls, because the second call pays
   the full 24k tax again.

This also means the Conductor's budget governor (§4.2, §15) must meter
**invocations**, not just tokens — token accounting alone hides a cost that
scales with call count.

## 4. Adapter contract

One interface, four implementations, no provider types above the adapter edge.

```python
@dataclass(frozen=True)
class CompletionRequest:
    prompt: str                    # the assembled context packet, rendered
    system: str | None = None      # role framing; NOT the harness system prompt
    schema: dict | None = None     # JSON Schema; None => free text
    max_output_tokens: int = 4096
    profile: str = "default"       # frozen generation profile name
    stop_after_seconds: float = 300.0

@dataclass(frozen=True)
class CompletionResult:
    text: str                      # raw text, fences already stripped
    parsed: dict | None            # validated against schema, else None
    provider: str                  # "claude_code" | "codex" | "ollama" | "fake"
    model: str                     # resolved model id, as reported by the tool
    usage: Usage                   # input/output/cache-read/cache-write tokens
    cost_usd: float | None         # None when the provider cannot report it
    wall_ms: int
    invocations: int = 1           # for the budget governor (see §3)
    raw: dict                      # full provider envelope, for provenance
```

Every field of `CompletionResult` is provenance material: PLAN.md §2 requires
every claim traceable to "exact inputs, tool/model versions, and the policy that
accepted it", so `raw` and the CLI version string get recorded with the artifact.

### 4.1 `claude_code` adapter (default)

```
claude -p <prompt>
  --output-format json
  --model <model>
  --append-system-prompt <role framing>
  --allowed-tools ''                       # no tools: we want completion, not agency
  --strict-mcp-config --mcp-config '{"mcpServers":{}}'
  --no-session-persistence
  --permission-mode manual
  < /dev/null
```

Non-obvious requirements, each learned the hard way:

- **`< /dev/null` is mandatory.** Without it the CLI waits on stdin and prints
  `Warning: no stdin data received in 3s, proceeding without it` — three seconds
  of dead time on every single call.
- **`--strict-mcp-config` with an empty `--mcp-config` is mandatory.** Otherwise
  the invocation inherits whatever MCP servers the user's machine has configured,
  which is both slow and non-reproducible. Reproducibility (§11) requires the
  packet be a pure function of its inputs.
- **`--allowed-tools ''`** keeps it a completion call. A tool-enabled agent could
  read and write files outside the revision store, which would violate "no
  subsystem mutates canon directly" (§5).
- **`--no-session-persistence`** — otherwise every scene leaves a session on disk.
- **Response parsing:** the envelope's `result` field holds the model's text.
  Read `is_error`, `subtype`, `api_error_status`, and `stop_reason` before
  trusting it; `usage` and `total_cost_usd` feed the budget governor; `modelUsage`
  gives the canonical model id and context window for the provenance record.
- **No native structured output.** Asked for JSON, the CLI returned it wrapped in
  a ```` ```json ```` fence. The adapter must strip fences, parse, validate
  against `schema`, and treat a validation failure as a *shape-gate* failure
  (§4.2 ladder step 1) with a bounded retry — not as a crash.

### 4.2 `codex` adapter (fallback)

```
codex exec <prompt>
  --output-schema <schema.json>       # native JSON Schema for the final response
  --output-last-message <out.txt>     # final message, isolated from event noise
  --json                              # JSONL events on stdout, for usage/provenance
  --skip-git-repo-check               # LitHarness is not a git repo (verified)
  --sandbox read-only
  --color never
  -c 'mcp_servers={}'
  < /dev/null
```

Notes:

- `--output-schema` is a genuine advantage over `claude -p`: schema enforcement
  is native. Verified — `last-message` contained exactly
  `{"ok":true,"word":"litharness"}`, unfenced, no preamble. No fence-stripping
  heuristic needed on this adapter.
- **Event stream is small and stable.** With `--json`, a single-turn run emits
  exactly four JSONL events: `thread.started`, `turn.started`, `item.completed`,
  `turn.completed`. Usage rides on `turn.completed`:
  `{"usage": {"input_tokens", "cached_input_tokens", "cache_write_input_tokens",
  "output_tokens", "reasoning_output_tokens"}}`. Read the final text from the
  `-o` file rather than reassembling it from events — the file is the contract.
- **No cost field.** ChatGPT-account auth means quota, not dollars; map to
  `cost_usd = None` and rely on token + invocation metering (§3).
- `reasoning_output_tokens` is reported separately and was `0` here only because
  the probe was trivial; at the default `reasoning effort: high` it will not be,
  so add it to the output-token total when metering budget.
- stderr still prints `Reading additional input from stdin...` even with
  `< /dev/null`. Harmless, but don't parse stderr for errors on this adapter —
  use the exit code and the presence of a non-empty `-o` file.
- `--skip-git-repo-check` is required today because `C:\DEV\LitHarness` is not a
  git repository. (Neither are `litharness-contracts`, `LongRangeContext`,
  `ContinuityEvaluation`, or `RevisionPropagation` — worth fixing separately.)
- `codex exec` starts configured MCP servers by default (observed:
  `node_repl`, `interface3d`, `agentui`); suppress with `-c 'mcp_servers={}'`.
- `--oss --local-provider ollama` exists and routes codex through Ollama. Not
  needed here — the `ollama` adapter talks to the daemon directly with far less
  machinery — but it is the escape hatch if codex-specific behaviour is ever
  wanted against a local model.

### 4.3 `ollama` adapter (testing and cheap loops)

`POST http://localhost:11434/api/chat`, `stream: false`:

```json
{ "model": "llama3.2:latest",
  "messages": [{"role": "user", "content": "..."}],
  "format": { "<JSON Schema>": "..." },
  "options": { "temperature": 0, "seed": 7 },
  "stream": false }
```

- **Native JSON-Schema structured output** via `format` — verified returning
  exactly `{"ok": true, "word": "litharness"}` with no fences.
- `temperature: 0` plus a fixed `seed` gives the closest thing to determinism
  available from a model, which is what the fixture-regeneration tests in Stage 1
  need.
- Usage comes back as `prompt_eval_count` / `eval_count` and durations as
  `total_duration` / `load_duration` / `eval_duration`; `cost_usd` is `None`
  (hardware time only, per §15).
- Liveness probe: `GET /api/version` (returned `{"version":"0.32.8"}`).
- Suggested model tiers: `llama3.2:latest` or `gemma2:2b` for fast shape/plumbing
  tests, `qwen3:4b` or `gemma3:4b` for mid-tier, `gpt-oss:20b` for the largest
  local option when test output quality actually matters. Avoid `deepseek-r1:8b`
  for structured extraction — reasoning models emit preamble that fights schema
  conformance.

### 4.4 `fake` adapter

Already required by Stage 0's exit criterion ("revisions, patches, events, and
restore work end-to-end without a model"). Deterministic, zero-cost, keyed off
the request hash. This is the adapter the whole IR/revision/jobs test suite runs
against; the three real adapters are only exercised by a small conformance suite.

The fake also accepts a FIFO script of strings, complete results, and exceptions. This is
the deterministic way to exercise sequences such as overload → recovery, malformed answer
→ retry, or exhausted test fixture; tests no longer need a one-off fake class for every
multi-attempt path.

### 4.5 Failure contract and recovery

Adapters preserve the provider diagnostic but also classify it into a provider-neutral
`ProviderFailureKind`: unavailable, timeout, rate limit, overload, server error,
authentication, invalid request, context overflow, refusal, safety refusal, malformed
response, aborted, or unknown. The exception carries status, provider error type, request
id, retry delay, and a bounded raw diagnostic when the backend exposes them.

The classification controls the Conductor rather than merely improving logs:

- unavailable, timeout, rate limit, overload, server error, and aborted calls are requeued
  without charging the candidate's attempt budget;
- authentication, invalid request, and context overflow are parked without charging an
  attempt and create an operator-visible exception, because retrying unchanged cannot work;
- refusal, safety, malformed response, and unknown errors remain bounded candidate
  failures and therefore consume the ordinary attempt budget.

This keeps a provider outage from poisoning work while also preventing an expired key or
oversized context packet from spinning once per heartbeat forever.

## 5. Resolution order and configuration

Selection is config, versioned like every other policy (§4.3 "all config, all
versioned"), never hardcoded:

```toml
[providers]
order = ["claude_code", "codex", "ollama"]   # first healthy wins
test_order = ["ollama", "fake"]              # LITHARNESS_ENV=test

[providers.claude_code]
model = "claude-opus-5"          # cheap tier: "claude-haiku-4-5"
health = "claude --version"

[providers.codex]
enabled = true                   # verified working on codex-cli 0.147.0
model = "gpt-5.6-sol"            # CLI default; pin it so upgrades are visible
health = "codex exec --output-schema <probe> ..."   # round trip, not --version

[providers.ollama]
base_url = "http://localhost:11434"
model = "qwen3:4b"
health = "GET /api/version"
```

Rules:

1. **Health-probe with a real round trip, and cache the verdict per tick.** Codex
   on 0.107.0 proved that "installed" ≠ "working": the binary existed, was
   authenticated, was on `PATH`, and still failed every call with an empty output
   file. A probe that only checked `--version` would have passed it and silently
   routed scene generation into a dead provider. The probe is a schema-enforced
   round trip against the configured model, and a version-string change alone is
   grounds to re-probe rather than trust the cached verdict.
2. **`LITHARNESS_ENV=test` forces `test_order`.** No test run may reach a paid
   model by accident. This is the user's stated requirement and belongs in a
   test-suite assertion, not a convention.
3. **Route by call class, not just by availability.** Tag each call site
   `generation` | `extraction` | `evaluation` | `mechanical`, and let config map
   classes to providers. The default map sends `extraction` and `mechanical` to
   Ollama even in production, for the reason in §3.
4. **Falling back is an event.** A provider switch changes the artifact's
   provenance and may invalidate reproducibility claims, so it is recorded in
   the event log and surfaced in the daily digest — never silent.

## 6. Amendments this implies for PLAN.md

- **§2** — "two adapters suffice" becomes four: `fake` + `claude_code` + `ollama`
  are required for Stage 0/1, with `codex` as a verified fallback tier. The
  deferral in §18 of "more than two provider adapters" is superseded for these
  four; it still holds for hosted-API providers beyond them.
- **§15 cost model** — add the per-invocation harness tax (~24k input tokens,
  ~$0.013 floor on Haiku, ~3.5 s wall) alongside the existing per-token
  estimate, and state the batching rule from §3.
- **§4.2 budget gates** — meter invocations as well as tokens.
- **Stage 0 exit** — add: each configured adapter passes a conformance suite
  (schema-conformance, usage reporting, health probe, timeout, and a forced
  fallback), and `LITHARNESS_ENV=test` provably cannot reach a paid provider.

## 7. Open items

- ~~Upgrade the Codex CLI~~ — done, 0.107.0 → 0.147.0, re-probed and enabled.
- ~~Implement the adapters~~ — done. Two things the build changed relative to this spec:
  `bills` became a property of each adapter rather than registry config (it decides whether
  a test run may touch a provider, so it belongs to the adapter's identity), and
  `reasoning_output_tokens` is counted into the budget total after the probe showed codex
  reports it separately at a default reasoning effort of `high`.
- Decide whether `claude -p`'s ~5k non-cacheable per-call overhead can be reduced
  (settings that suppress CLAUDE.md/skill/plugin discovery) — worth one
  experiment, since it is the difference between a $0.013 and a ~$0.003 floor.
- Measure the same numbers for an Opus-tier model before Book Zero, since §15's
  budget depends on the tier actually used for generation.
