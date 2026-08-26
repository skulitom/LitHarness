# Contributing to LitHarness

This is the short path for changing the code safely. `PLAN.md` explains the product and
`plan/stage-0-decisions.md` preserves design history; neither should be required reading for
an ordinary local change.

## Set up and verify

One clone is enough. `litharness-contracts` is a git dependency whose rev is recorded in
`uv.lock`, and the golden fixture books ship inside that package, so `uv sync` gets you
exactly the contracts CI builds against — there is nothing to check out beside this repo and
nothing for the workflow to pin by hand.

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
uv run mypy
```

Advancing the contracts pin is still a deliberate change that lands with the code that needs
it, not a maintenance chore — the discipline survives the mechanism. It is now bump the `rev`
in `[tool.uv.sources]`, run `uv lock`, and commit `pyproject.toml` and `uv.lock` **together
with the code the new contracts version is for**. One commit, because a lockfile that moved
without a reason is a change nobody can review. To develop against an uncommitted contracts
checkout in the meantime, `uv pip install -e ../litharness-contracts` overrides the pin until
the next `uv sync`, and `LITHARNESS_CONTRACTS_ROOT` redirects fixture reads to a checkout root
without touching the install.

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
- `application` coordinates through structural ports in `application/ports.py` and imports
  **neither `adapters` nor `providers`**. It names what it needs — `DraftStore`,
  `TextGenerator` — and the composition root supplies something that fits.
- `cli.py` is the outer composition and operator surface, and the only place that binds a
  concrete `SqliteStore` and `ProviderRegistry` to those ports.

The generation vocabulary (`CompletionRequest`, `CompletionResult`, `Usage`, `Resolution`)
lives in `domain/generation.py` so both sides can name it without either importing the other;
`providers/base.py` re-exports it, so a provider author still has one import site. If you are
adding an outbound capability, the shape to copy is `TextGenerator`: a protocol in `ports.py`
naming only the methods the layer calls, and nothing about who implements it.

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
It is the canonical refutation ledger: every proxy this project has tried, how its controls
killed it, and the structural pattern behind the failures. Do not copy its count or findings
here; they change faster than contributor guidance and the brief owns them.

That directory is also where prose-measurement experiments belong. It sits outside `src/`
on purpose: nothing there is imported by the package, nothing is gated on, and it depends on
a 12.5GB corpus CI must never need. Use `corpus_io.py` rather than writing another loader —
it already supplies the fixtures, Mother of Learning, the cached RoyalRoad shards with cohort
labels, and `generated_scenes`, which reads drafted scenes out of any book database through the
export path; `by_story` groups chapters into books. Commit numbers, never prose.

**Which source you pick is a validity decision, not a convenience one.** Model-based work on
published text must address memorisation explicitly. `generated_scenes` avoids that problem but
carries no reader label. Choose against the question and record the source and limitation.

## Scope discipline

Keep patches narrow and preserve unrelated work in a dirty tree. Add a focused regression
test for the behavior being changed, then run the full suite, Ruff, mypy, and
`git diff --check` before handing off.
