# Institutional comparison in discovery: fixed-premise pilot

## Question

The operator asked whether our own instructions hinder quality on 2026-09-08.
CONJECTURE: naming employment, licences and institutional rank while asking for
independent personal progression may invite the inventor to add those institutions.
The preceding premise-before-development pilot located such additions, but its
unmatched stories cannot isolate their cause. This pilot tests one phrase against
the same source. It is generation inspection, not a reader measure or quality gate.

## Frozen procedure

Use the unchanged initial premise at
`runs/diagnostics/premise-before-development-20260908/premise-first/initial-premise.txt`
with that pilot's promise-preservation wrapper. This is the first premise from that
run, not a model-selected candidate. Freeze its bytes and the rendered requests.

Control: the current production discovery request, third person, no writer dossier.
Deletion: remove exactly ` independently of employment, licences or institutional rank`
from its system text. Everything else, including source, schema, model, quota path
and output allowance, stays fixed. Assert the exact one-clause difference offline.
Run four fresh first-response calls in this order: control-1, deletion-1, deletion-2,
control-2. Keep every response; no selection, retry, manual edit or adaptive prompt.

Use Discovery.from_invention, the same entry point as production, on every response.
Retain failures with their text. A structural failure does not cancel independent
slots; transport, authentication or quota failure stops all remaining calls.
There are no development, precision-editing, listing or chapter calls. In particular,
do not render a treatment downstream, where the stored discovery direction would
reintroduce the deleted clause. No accepted manuscript or plan changes.

## Inspection and limits

Read every complete treatment against the common premise. Record field and paragraph
locations for added administrative actors, permission/payment transactions, and
explanations contrasting power with authority. Inspect whether changed vocabulary
leaves the same administrative activity. Also locate premise displacement, personal
progression, incidental counts and explanatory formulations. Preserve counterexamples.
These questions never enter generation. They are not scored features or quality bars.

Repeated disappearance of the administrative additions would justify another test;
their persistence in both deletion draws kills the narrow expectation that this
deletion is sufficient on this source. Mixed results leave that expectation unresolved.
Neither result establishes the causal mechanism, overall quality, or Chapter 1 appeal.
Four stochastic outputs from one premise cannot establish a general fix. Source
selection, the salvage setting, shorter system text and call order remain limitations.
No model judges, ranks or selects outputs. Nothing is automatically promoted to
production; observations remain located inspection, not qualified feedback.

## Execution and records

Read CONTRIBUTING.md, BRIEF.md, EPISTEMIC_GOVERNANCE.md and the parent RUNBOOK's
shared-box procedure. Check processes, acquire runs/box.lock atomically and release
only this run's owned lock. Do not overlap sustained checks or generation jobs.

Use the configured claude-opus-5 through Claude Code's claude.ai subscription login,
--safe-mode, replacement system prompt, empty tools/MCP and a fresh empty working
directory. Strip API credentials and provider-routing environment variables. No
direct API, --bare, provider fallback, model change or live-provider test flag.
Record only sanitized auth method, subscription type and CLI version.

Bound the run to four invocations, 60,000 recorded tokens, $15 reported list-equivalent
quota accounting and 600 seconds per completion. These are subscription accounting
ceilings, never API authorization; a single response can exceed a token forecast,
which prevents further calls. Use the production metered completion path.

Keep prompts, raw output, argv, model/usage, validation and operational scripts under
`runs/diagnostics/discovery-institution-cue-20260908/`. Commit this registration with
source/runner/request hashes before dispatch. Run offline wiring checks and repository
handoff first. Commit source-free results with artifact hashes; no generated prose
enters tracked research files. Record deviations visibly. No new production prose
instruction is installed by this pilot.
