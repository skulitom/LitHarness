# Epistemic governance

LitHarness's repository is the long-term memory of a research collective whose individual
agents are short-lived. That makes repeated prose unusually dangerous: one plausible proposal
can become repository precedent, then apparent consensus, without acquiring any evidence.

The governing boundary is:

> **Agent prose is not evidence. Proposal, evidence, and belief are different records.**

Plans, handoffs, summaries, issues, comments, and repeated agreement may point to evidence.
They do not add to it. Five agents repeating a conclusion still contribute zero observations.

## Claim states

Use these labels for claims about quality-measurement or reader architectures:

| State | Exact meaning |
|---|---|
| `CONJECTURE` | A mechanism or explanation somebody thinks may work. It has no empirical weight. |
| `REGISTERED` | The experiment, target claim, controls, kill conditions, and analysis rule were committed before observing the relevant result. |
| `OBSERVED` | A content-addressed raw or deterministic derived artifact exists. No interpretation has passed yet. |
| `SUPPORTED` | The observation survived the controls and decision rule fixed in the registration. This means supported by this test, not true in general. |
| `REFUTED` | A registered kill condition or destructive control killed the claim. Preserve the result and add mechanism-class failures to `BRIEF.md`. |
| `QUALIFIED` | The exact mechanism version met the stronger production qualification contract, including transfer and anti-confound controls. |

These are research states, not the production lifecycle. `ReaderMechanismStatus` remains
`experimental`, `qualified`, or `withdrawn`; only its existing qualification command can grant
production authority. A research claim labelled `SUPPORTED` cannot steer a book.

Do not turn the states into a score or vote. One result can support a narrow claim while another
refutes a broader one. State the smallest claim the artifacts warrant.

## What can cross the evidence boundary

Evidence is one of:

- committed raw results;
- deterministic derived results that identify their inputs and rebuild command;
- an exact literature source, with the relevant location and inference recorded;
- a code-checkable control; or
- reproducible experiment output tied to the frozen registration.

A test proves the code behavior it checks, not literary validity. A decision-log entry proves
that a decision was made, not that its empirical premise is true. A model's conclusion is an
observation only when the registered experiment makes that output the measured datum; the
conclusion's rhetoric is never independent corroboration.

References are content-addressed. If bytes change, the old claim no longer validates. Literature
citations belong in a committed source or registration artifact so the record can point to exact
bytes rather than a remembered paraphrase.

## Claim records

Create a claim record when a claim will allocate substantial research work, become a premise of
another experiment, or justify mechanism qualification. Do not create one for ordinary
implementation facts. Existing results need not be retrofitted unless a new decision relies on
them.

The record is a pointer layer, not another results ledger:

```json
{
  "schema": "litharness.epistemic-claim.v1",
  "claim_id": "example-reader-mechanism-v1",
  "statement": "The exact registered mechanism detects the registered damage family.",
  "status": "supported",
  "artifacts": [
    {"kind": "registration", "path": "research/example/PREREG.md", "sha256": "<64 lowercase hex>"},
    {"kind": "raw_result", "path": "research/example/results/raw.json", "sha256": "<64 lowercase hex>"},
    {"kind": "control_result", "path": "research/example/results/report.json", "sha256": "<64 lowercase hex>"}
  ]
}
```

One file may appear under more than one kind when, for example, the same immutable report holds
both the target observation and its controls. Validate records with:

```bash
uv run python research/quality-measurement/epistemic_governance.py path/to/claim.json
```

The validator enforces the minimum evidence shape and verifies every SHA-256 against a
repo-relative file. It cannot establish semantic validity; reviewers still compare the claim to
the preregistered decision rule. The canonical raw result and refutation remain where their
experiment and `BRIEF.md` put them. Never copy their counts into a claim record.

## Operational failures and amendments

A registration fixes an arm's design, sample, analysis and reading. A change to any of them after
registration is an **amendment**: a committed file beside the registration (`AMENDMENT-N.md`, or
a `RECOVERY.md` that changes anything below), written before the next dispatch and never
replacing what it amends. An amendment is required for:

- anything a model sees: a request's bytes or order, the model, effort, provider or executable,
  or the context and isolation of the call, including a fix to how the call is made (the
  working-directory leak behind `cost-that-bites-milder-20260922/AMENDMENT-1.md` changed what
  the reader saw);
- the sample, the items, the stop rules, the ceilings or the spend envelope, the analysis, the
  decision rule or the reading;
- a production fix, a new writer, or continuing a stopped run on changed code;
- any further attempt after an answer from the failed attempt has been read, scored, gated or
  printed beyond its transport status.

**An operational failure is retried under the same registration with a failure note, not an
amendment**, when every condition below holds.

1. The registered procedure could not run as written for a cause outside its design: an expired
   login, a transport error or timeout, a killed process or a machine shutdown, a lock or
   environment fault, or a runner defect found before any answer was read.
2. No answer from the failed attempt has been read, scored, gated, cached as an answer or
   printed beyond its transport status. Whether to retry therefore cannot depend on what a model
   said. A retry chosen after reading an answer is the rejection sampling `BRIEF.md` §6 prices.
3. The retry sends exactly the registered requests, from the registered frozen inputs and
   executable, in the registered order. The ceilings count every attempt together, and a failed
   call's usage is recorded as unknown, never as zero. A retry the remaining ceilings cannot
   cover is an amendment, with the operator's sign-off when it exceeds a registered envelope.
4. A runner fix is operational only when a committed test shows it changes no request byte,
   argv, stdin, cache key, sample, stop rule or analysis. The note lists each changed file with
   its SHA-256 before and after, and the commit that changed it.
5. The failed attempt is kept as it stands. It is never deleted, overwritten, resumed from a
   partial answer or replayed as an answer.
6. An arm takes at most two operational retries. After a third failure it stops, and any
   further attempt is an amendment.

Write the note before the retry dispatches, as `FAILURE-N.md` beside the registration. It states
what failed and when, the failed receipt's path and SHA-256, the error class, the remedy (for
example the operator's re-login, or the runner-fix commit), and that no answer was read. The
runner records the note's SHA-256 before it dispatches, and the committed note must match it.
The claim record cites the note as a `registration` artifact. The claim state does not move, and
no new `prepare` is needed.

An arm's own registration governs where it is stricter: a RUNBOOK that says "no retry" keeps it.
This section applies to registrations committed after it that cite it. It reaches an older arm
only through an amendment.

## Multi-agent research

Shared evidence is useful; shared speculation destroys independence. For independent ideation,
use **island then merge**:

1. Give each proposing agent the same canonical evidence: `BRIEF.md`, relevant registrations,
   and content-addressed results.
2. Do not give it sibling proposals or a prose summary of supposed consensus.
3. Merge the independent proposals only after they are written.
4. Assign adversarial work explicitly: mechanism invention, confound search, destructive-control
   design, prior-failure search, alternative explanation, and evidence synthesis.
5. Reward attacks that kill an idea cleanly. The collective objective is good ideas surviving
   competent attacks, not making the current idea work.

GitHub is the memory of record for registrations, artifacts, decisions, and refutations. It need
not be the shared scratchpad for every speculative thought. Builder agents should still see
failure evidence; hiding it would force the collective to rediscover old confounds.

## Existing authorities

- `BRIEF.md` owns the refutation ledger and its count.
- `RUNBOOK.md` owns reproducible experiment commands and operational constraints.
- `plan/stage-0-decisions.md` owns durable product decisions and reversals.
- `plan/reader-architecture-program.md` owns the mechanism programme and qualification boundary.
- This document owns research claim states and the agent-prose/evidence boundary.
- This document owns the line between an operational retry and an amendment; each arm's
  `RUNBOOK.md` owns its retry command.

When these disagree, do not reconcile them by prose consensus. Re-anchor to the registrations,
artifacts, code, and tests, then correct the canonical owner.
