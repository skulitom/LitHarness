# LitHarness

An autonomous book-production system with a human director. See [PLAN.md](PLAN.md) for the
master plan and [plan/](plan/) for companion design documents — in particular
[plan/stage-0-decisions.md](plan/stage-0-decisions.md), which records the load-bearing
design decisions and why each went the way it did.

**Status: Stage 0 slices 1–5.** The manuscript spine, the Conductor loop, four provider
adapters, a provider-backed draft handler behind a shape gate, recorded acceptance
decisions, and a direction inbox. It runs; it does not yet write a book. See
[What is not built](#what-is-not-built).

## Setup

This repo depends on a sibling checkout: `../litharness-contracts` must exist next to it.
That is a path dependency in `pyproject.toml`, not a published package, and nothing will
install without it.

```bash
uv sync --extra dev
```

## Running it

```bash
uv run litharness --database book.db init
```

Then a tick — one bounded unit of work. This is what a scheduler invokes:

```bash
uv run litharness --database book.db tick
```

On Windows Task Scheduler or cron, every 5–15 minutes (§4.1). **Exit codes are the
interface**: `0` the tick did its job, including finding nothing to do; `1` a unit failed
or parked and a human should eventually look; `2` an operational fault — locked database,
missing migrations, full disk — which a supervisor should retry next cadence rather than
escalate.

## Operating it

```bash
uv run litharness --database book.db status
```

Reports liveness, queue depth by status, how many units need attention, outbox state, and
unread direction. `--json` for machine consumption. Exits non-zero when the system is
stalled or something needs attention, so it works as a cheap external check.

Everything else the director does:

```bash
uv run litharness --database book.db directive "More dungeon crawling." --kind arc_note
```

- `directives` — what has been captured. Direction is captured but **not yet interpreted**;
  that needs the Narrative Planner, which does not exist, so directives sit in `received`
  and the count is the honest measure of the gap.
- `jobs [--status parked]` — queue depth, or the units in one state.
- `revive <job_id>` — return a parked unit to the queue once you have cleared what parked
  it. Refuses a poisoned unit, whose attempt budget really was spent.
- `pause` / `resume` — durable, so it survives the process a cron tick starts and ends in.
- `backup <path>` — online backup, safe while ticking. Uses SQLite's backup API because
  this store runs in WAL mode and a file copy would silently omit everything since the
  last checkpoint.
- `verify` — rebuild every revision from canonical records and check the content hashes.

## Development

```bash
uv run pytest
```

```bash
uv run ruff check . && uv run mypy
```

The suite is model-free by default. `tests/conftest.py` sets `LITHARNESS_ENV=test` at
import, which makes the provider registry refuse to resolve any billing provider — so a
test run provably cannot reach a paid CLI. Three live round-trip tests are skipped unless
`LITHARNESS_LIVE_PROVIDERS=1`.

## What is not built

Stated plainly, because a system that runs is easy to mistake for a system that works:

- **No planner.** Nothing decides what scene to write next. A draft job is enqueued by
  hand with its prompt supplied; there is no beat sheet and no context packet.
- **No craft gate.** The only gate is shape — a draft exists, is the right size, and did
  not overwrite anything. Nothing measures whether the prose is any good (PLAN.md §1a).
- **No budget enforcement.** Tokens and invocations are recorded per decision; no ceiling
  stops anything. §19's Economics clause is metered, not enforced.
- **No game-system validation.** The LitRPG rules pack lives in ContinuityEvaluation and
  is not wired in.
- **Directives are captured, not read.** See above.
