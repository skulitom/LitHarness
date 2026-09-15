# Automatic experience brief through the production workflow

Status: preregistration. Read the parent RUNBOOK.md, BRIEF.md and EPISTEMIC_GOVERNANCE.md.
The operator authorized four fresh short premises, two chapters per version, comparing
the previous and implemented automatic-experience workflows. No quality instrument is
being qualified; this is a descriptive whole-workflow trial.

## Fixed comparison

A uses committed 294e93e; B uses 7b0ebc4. The production source delta is exactly the
automatic experience brief in discovery, concept development and outline planning.
Neither source contains the unrelated dirty precision changes in the live checkout.
Four original minimal premises and neutral shared working titles are in inputs.json.
They specify no chapter experience, reward, desired emotional response or successful outcome.
There is no favorite-book prose, title list, review, digest, prior generated story or
research reading in any generation input. No exemplar shelf is enabled.

Each pair gets the same premise, title and fresh 2048-bit opaque invention prefix, the
compiled halloran writer, third-person request, six planned scenes, one scene per chapter
and 1,400 target words per chapter. The normal six-chapter arc is planned; only its first
two chapters are drafted. This does not demand a completed arc in the observation window.
The prefix holds creative input constant; it is not a deterministic sampling seed.

Use the supported existing-premise path: concept -> new --concept -> architect seed ->
world accept -> normal ticks to chapter one -> drain queued evaluation/summary/repair work ->
architect grow for chapter one -> world accept -> ticks to chapter two -> drain its queue.
Public listing, title search, cover, publication and a third chapter are outside this trial.
No final world-growth call is needed to supply a third chapter. The default in-process
evaluator runs; no external continuity executable is configured. Revise, Director,
reader checkpoints, exemplar shelf and external roster are off, as in the ordinary defaults.

All eight books are isolated fresh stores under ignored runs/experience-workflow-20260915.
Production commands retain their own acceptance, state extraction, plan revisions, events,
queue ordering and bounded mechanical retries. All first outputs and any automatic retries
or repairs remain in the receipts; none is ranked, redrawn or manually edited for taste.
An accepted revision is a production-policy result, not literary endorsement. Inspect raw
first drafts and later accepted versions separately if the ordinary workflow changes them.

The fixed phase order is in run.py. Within each phase use AB, BA, AB, BA across the four
premises, reversed at the next phase. One book completes its bounded phase before the next
starts. Different worlds/stories may emerge; this comparison cannot isolate preservation
of identical semantics or the effect of the field apart from changed discovery content,
input length, timing, development instructions and planning guidance.

## Freeze and transport

Archive both committed versions without changing this checkout. A minimal virtual environment
per arm loads the archived src and the same installed dependencies. Its plain .pth entries
avoid the live editable source and remain effective for the native MCP command bridge after
PYTHONPATH is stripped. Freeze source archives/modules, migrations, lockfiles, executable,
runtime configuration, this driver/test/runbook, premises and per-pair seeds. Verify origin
before each application step and hashes before every provider invocation.

The research recorder wraps CodexCliProvider.complete only to record the unchanged request,
result and raw transport, and enforce admission limits. It does not alter a prompt, schema,
sampler, output allowance, timeout, provider result or application decision. Normal health
probes are retained and counted too. The scoped world-command bridge remains the only tool
allowance; all other model requests are tool-free. No web search or external messages.
Use the existing signed-in native Codex subscription, requested gpt-6-astra / medium, with
ephemeral sessions, user/project instructions and memory disabled. No model switch,
fallback, API-key generation, credit reset or purchase. The resolved backend is not reported
unless the trace independently exposes it.

## Limits and stops

Hold runs/box.lock and confirm no competing sustained job. One native call at a time; never
run sustained checks beside generation. Admission ceilings: 240 application provider calls
including health probes, 4,000,000 recorded Usage.total tokens, 240 minutes from dispatch,
45 calls per book. Individual application requests retain their production timeouts and
output allowances. An admitted call may cross a ceiling; report actual usage and every
raw usage component. These are subscription resource counts, not dollar prices.

Each chapter/drain phase gets at most 20 ordinary ticks. Do not tick an empty queue in a
drain phase: that would begin the next chapter. Stop a book on a terminal parked/poisoned
job, non-tick command failure, operational exit 2, no_work before the target, or phase cap.
Ordinary retryable tick failures keep their existing bounded policy. A per-book ceiling
stops that book; global ceilings stop new calls across the trial. No manually repaired
worlds, revived jobs, extra concepts or substituted output. Preserve incomplete pairs.

A provider/transport failure or interrupted call stops all further calls, retaining unknown
usage rather than recording it as zero. Frozen-file or source-origin mismatch refuses work.
Existing preparation/dispatch roots cannot be overwritten or silently resumed; interruption
requires an explicit preregistered continuation. Never delete an attempted receipt.

## Verification and execution

Before dispatch run focused offline checks and tools/check.py handoff, then commit and push
the registration. Never set LITHARNESS_LIVE_PROVIDERS during verification.

```powershell
uv run python research/quality-measurement/experience-workflow-20260915/run.py prepare
uv run python research/quality-measurement/epistemic_governance.py research/quality-measurement/experience-workflow-20260915/claim.json
uv run python tools/check.py handoff
# Commit and push the registered files, then:
uv run python research/quality-measurement/experience-workflow-20260915/run.py run
uv run python research/quality-measurement/experience-workflow-20260915/run.py audit
```

During generation inspect only counts, statuses, profiles, timestamps and other transport
metadata. No story reading or prompt adjustments before generation finishes or stops.
Audit exact application/transport strings, source origin, schema transport, session IDs,
tool allowance, receipt chain, resource admissions, retained author brief and B field through
concept/outline, and complete revision attribution. Flag missing or invalid controls; they
void the affected contrast rather than triggering replacement generation.

## Reading and reporting

Read every reached narrative draft in full and every discovery, concept and outline. Follow
the stored scene dossiers and world records where they explain a handoff or discrepancy.
Use the local debug-book read workflow for dossiers; all stores are this isolated research
arm's own outputs. No dossier or reading note feeds any production prompt or editorial action.

For each version and premise locate:

1. The concrete activity the character wants, how they make it possible, what they experience
   as a consequence, and any subsequent choice. Describe omissions, changes and ambiguity.
2. The opening/later/unresolved coverage in the proposal, the actual projected planning input,
   scheduled events and enacted prose. Do not demand later rewards inside chapter one.
3. Whether access, a skill or a reward is used and experienced, or immediately creates a new
   obligation; record examples of both, without treating either as automatically bad.
4. What comes from discovery, mechanical development, world construction, planning or prose.
   Distinguish a supplied instruction from an autonomous choice and an intention from canon.
5. Contrary cases: payoffs the baseline delivers, opportunities B misses, mechanical failures,
   changed tone/relationships and consequences, even when a broad activity is retained.

No enjoyment scores, preference votes, winners, automatic candidate selection, statistical
quality rates or popularity claims. Located agent readings remain interpretation, not
validated reader measurement. Four premise pairs and one generation per workflow are small
descriptive cases; chapters from the same book are not independent units. Operational
survival is reported for all eight books, including those that cannot reach two chapters.

Keep raw prose, stores, requests, transport, dossiers and reading notes/report under the
ignored run root. Commit hashes, identifiers, numeric control/resource/volume evidence and
methodological conclusions. The claim may become observed; this trial has no rule that can
promote it into supported literary quality or production reader-mechanism qualification.
