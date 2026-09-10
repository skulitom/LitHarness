# Phase 2: model and transport controls

Registered after reading all eight phase-1 inventions. Deleting the detailed discovery
system did not eliminate recurrence: all four minimal outputs named the protagonist Mara
Venn, three used a railway lost-property clerk, and restoration/ownership recurred. This is
an observation of these outputs, not a population frequency or a quality judgment.

Use the exact phase-1 minimal CompletionRequest, unchanged in every slot. Compare three
routes: Codex requesting gpt-6-astra at medium reasoning, the same Codex binary and settings
requesting gpt-5.5 at medium, and Claude Code requesting claude-opus-5 through the frozen
production adapter. Claude's effort is its native default, not a claim of matched compute.
The first contrast changes requested model only; the second also changes native transport.
Do not interpret Claude versus Codex as a pure model effect.

Fixed order: astra-1, gpt55-1, opus-1, gpt55-2, opus-2, astra-2, opus-3, astra-3, gpt55-3.
Each is a fresh tool-free completion with no prior outputs in its context. Use the same
platform/auth-location environment allowlist for both launchers. Claude must report an
active claude.ai subscription and first-party provider; no API credentials enter the child.
Capture its actual argv, stdin, effective system, schema, native envelope, CLI version and
session ID separately from the application request. The native modelUsage attribution is
available for Claude; Codex reports the requested model only.

Freeze this document, runner, all baseline source files, request and both native binaries
before calls. Commit registration before dispatch. Keep phase 1 unchanged. Use the existing
owned box lock and isolated interpreter. Retain first responses and failures; no redraw,
application retry, provider fallback, model ranking, candidate selection, downstream book
generation, usage reset or live-provider test flag. Native internal behavior is not assumed
to be single-pass merely because the application calls complete once.

Stop after nine attempts or 180,000 returned tokens; test the token bound before dispatch.
An in-flight completion can exceed it. Auth/transport/quota failure, unknown returned usage,
or frozen-file drift stops the phase. No implicit resume. Read story outputs only after all
slots complete or the stopping condition fires. Validate every returned invention with
Discovery.from_invention. Search with the trace tool and then read all complete outputs;
keyword hits are locations, not semantic labels. Keep raw prose and operational logs under
runs/invention-cause-20260910/phase2; commit only identifiers, hashes and derived conclusions.

If switching the requested model breaks the recurrence while Astra controls retain it,
localize the cause to the requested-model route under this task and launcher, without
claiming access to weights, backend sampling, or hidden provider instructions. If both Codex
routes repeat while Claude does not, investigate shared native framing next. If all repeat,
test residual task/schema framing. A mixed pattern remains mixed. Any further calls require
a new frozen phase; no production prompt change follows automatically from this diagnostic.
