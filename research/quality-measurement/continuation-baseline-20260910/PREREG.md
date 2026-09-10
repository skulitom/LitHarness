# Fixed-pipeline continuation baseline

Registered before generation on 2026-09-10 following the operator's approval to try the
three-book continuation baseline, audit the existing volume screens, and then test the
costed reader on a milder manipulation. This registration covers generation only. A reader
validity arm requires its own frozen registration and attainable analysis before calls.

## Question and unit

Can the pipeline at commit `d5ccb9ec7a244e8a573a0c26612373672d3c2bd7` carry three independently
invented books through three accepted chapters while preserving their recorded history?
This is an engineering pilot, not an estimate of literary quality or an experiment proving
that the recent prompt changes improved writing. Three books are a bounded diagnostic batch,
not a powered reader-validity sample. All books and failures remain in the denominator.

## Fixed configuration

- Three fresh databases, in numbered order, with the same empty author brief and default
  genre direction. No supplied story, existing prose, corpus, exemplar shelf, or writer persona.
- Codex subscription transport, `gpt-6-astra`, medium reasoning, native CLI 0.153.4. No fallback.
- Six planned scenes per book, one scene per chapter, six chapters per arc; stop after Chapter 3.
  Target 1,800 words per scene. A target is not an acceptance threshold.
- Ordinary `concept`, `listing --concept --scenes 6 --person third --no-title-check`,
  `architect seed`, `world check`, `world accept`, and `tick` commands. Title collision lookup
  is omitted because these books are unpublished research material.
- The listing command's bundled experimental observations remain inert. They are neither a
  new validity arm nor evidence in this pilot. Chapter reader checkpoints and optional revision
  remain off. Ordinary deterministic gates and within-command shape retries remain unchanged.
- After each accepted chapter, drain its queued non-drafting work, run ordinary `architect grow`
  and `world accept`, and preserve a checkpoint before the next chapter. Never draft Chapter 4.
- One persistent registry avoids buying a fresh health probe for every command. The transport
  wrapper records and bounds calls but leaves requests, results, and production decisions intact.

## Freeze, bounds, and failures

The runner extracts the named committed source and migrations into an ignored runtime snapshot;
an isolated interpreter imports that snapshot, including in the Architect's command bridge.
Dependencies come from the existing installed environment and are inventoried. The unrelated
working-tree precision edit is excluded. Source, runner, registration, native binary, and
dependency identities are frozen before the first provider call and checked during the run.

At most 120 native completion attempts and 2,000,000 reported tokens across the batch; at most
40 attempts and 700,000 reported tokens per book. These include health probes and failed
attempts. The next call is refused once a bound is reached; an in-flight call may overshoot
the token bound because Codex does not enforce the requested output limit. No new call starts
after three hours. Existing request timeouts remain unchanged. No automated quota reset.

A command failure or parked/failed tick stops that book with its first failure retained;
no manual repair, reroll, revival, or altered instructions rescue an arm. Other independent
books may proceed after a deterministic book-specific failure. Transport failure, unknown
usage, authentication failure, binary/source drift, or the aggregate bound stops all new calls.
No extra book replaces a failed one. Read-only exports and reporting may finish after a bound.

## Recorded outcomes

For every book retain creation inputs, every provider request and raw response, accepted
manuscript, command logs, job/decision provenance, state and audit views, and checkpoint hashes.
Report how many of the three chapters were accepted, where progress stopped, invocation/token
usage, immutable earlier-chapter checks, and located continuity observations with provenance
limits. Diagnostics never enter generation as feedback. No ranking, score, quality bar, or
qualification follows. Separate the ability to support a feed session from reader sensitivity.

Generated prose and databases stay under ignored `runs/continuation-baseline-20260910/`.
Commit only reproducible code, registrations, hashes, derived numbers, and bounded conclusions.
