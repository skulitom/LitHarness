# Contributing to LitHarness

This is the short path for changing the code safely. `PLAN.md` explains the product and
`plan/stage-0-decisions.md` preserves design history; neither should be required reading for
an ordinary local change.

## Set up and verify

The sibling `../litharness-contracts` checkout is required because `pyproject.toml` uses it
as an editable path dependency. A path dependency is the one thing `uv.lock` cannot pin, so
CI pins the contracts commit by SHA in `.github/workflows/ci.yml`; if your local checkout
sits elsewhere, your run and CI's are testing different contracts. Advancing the pin is a
deliberate change that lands with the code that needs it, not a maintenance chore.

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
uv run mypy
```

Tests force `LITHARNESS_ENV=test`, so the provider registry cannot select a billing provider.
Live provider tests require the explicit `LITHARNESS_LIVE_PROVIDERS=1` opt-in.
CI enforces at least 85% branch-aware coverage and treats leaked resources as test errors.
Use `SqliteStore` as a context manager in new embedded or long-lived code.

## Dependency direction

- `domain` contains rules and value objects and imports only other domain modules.
- `providers` implements model access and may use only its own package plus the domain
  failure vocabulary.
- `adapters` implements persistence and external artifact translation; it does not import
  providers or application workflows.
- `application` coordinates through structural ports and does not import concrete adapters.
- `cli.py` is the outer composition and operator surface.

`tests/test_architecture.py` enforces those boundaries and rejects internal import cycles.
If a change needs a new direction, treat that as an architecture decision and update the
test and its explanation together.

## Persistence and audit rules

- Never edit an applied SQL migration. Add the next numbered migration; startup verifies
  migration checksums.
- State mutations and the events describing them belong in the same SQLite transaction.
- `SqliteStore` is the stable composition facade. Put cohesive persistence behavior in a
  capability repository such as `sqlite_jobs.py` or `sqlite_plans.py`, then expose a thin
  delegate on the facade when existing callers need that operation.
- Every accepted manuscript or plan revision needs a recorded `PolicyDecision`.
- Build `PolicyDecisionRecorded` envelopes with
  `application.policy_events.policy_decision_event`; producer-specific facts go in
  `details`, whose reserved canonical keys cannot be replaced.
- Revisions and job identities are content-derived. Replays must converge rather than
  duplicate work.

## Before proposing a quality or craft metric

Read [research/quality-measurement/BRIEF.md](research/quality-measurement/BRIEF.md) first.
It is the refutation ledger: every proxy this project has tried to measure prose quality
with, and how each one died. **Twenty are dead and every one of them died to a control, not
to a bug** — so the cost of skipping it is not lost time, it is re-running a refuted
experiment and believing the headline.

Two things there that are easy to rediscover expensively. `tricolon_rate` separated
declared-AI from pre-2023 chapters at 0.629, which reads as the project's first working
AI-tell detector until the control beside it: *undeclared* 2025 chapters separate from the
same baseline at 0.606, so the metric detects the year. And the structural diagnosis — every
refuted proxy was **static, absolute, and correlational** — is the fastest way to tell whether
a new idea is a fresh one or the fourteenth of the same shape.

That directory is also where prose-measurement experiments belong. It sits outside `src/`
on purpose: nothing there is imported by the package, nothing is gated on, and it depends on
a 12.5GB corpus CI must never need. Use `corpus_io.py` rather than writing another loader —
it already supplies the fixtures, Mother of Learning, and the cached RoyalRoad shards with
cohort labels, and `by_story` groups chapters into books. Commit numbers, never prose.

## Scope discipline

Keep patches narrow and preserve unrelated work in a dirty tree. Add a focused regression
test for the behavior being changed, then run the full suite, Ruff, mypy, and
`git diff --check` before handing off.
