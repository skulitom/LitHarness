# LitHarness

An autonomous book-production system with a human director. See [PLAN.md](PLAN.md) for the
master plan and [plan/](plan/) for companion design documents — in particular
[plan/stage-0-decisions.md](plan/stage-0-decisions.md), which records the load-bearing
design decisions and why each went the way it did.

**Status: Stage 0 slices 1–6.** The manuscript spine, the Conductor loop, four provider
adapters, a provider-backed draft handler behind a shape gate, recorded acceptance
decisions, a direction inbox, and a way to get a book in. It runs; it does not yet write a
book. See [What is not built](#what-is-not-built).

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

Then get a book in. Nothing else works without this — every other command acts on a
revision, and `import` is the only one that creates one. The golden fixtures come from the
sibling contracts checkout:

```bash
uv run litharness --database book.db import --fixture mystery
```

It prints the revision id, which is the argument `enqueue` takes. Scene prose is **cleared**
so each scene can be drafted; `--keep-content` keeps it and tells you that nothing is
draftable, because a draft may only fill an empty node. Use `--path` for a manuscript of
your own.

```bash
uv run litharness --database book.db enqueue draft-1 --revision <id> --node scene-1 --prompt "Draft the study scene."
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
  it. Refuses a poisoned unit, whose attempt budget really was spent. A unit stopped by a
  budget ceiling is parked, not poisoned: the ceiling resets and the work is still there.
- `pause` / `resume` — durable, so it survives the process a cron tick starts and ends in.
- `exceptions` / `resolve` — what policy could not resolve. Resolving closes your side; it
  deliberately does not requeue the unit, because an escalation may have been *right*.
- `revert <revision> --book --branch` — restore an earlier revision as the new head. Goes
  forward: the mistake and the correction both stay in the record.
- `backup <path>` — online backup, safe while ticking. Uses SQLite's backup API because
  this store runs in WAL mode and a file copy would silently omit everything since the
  last checkpoint.

Budget ceilings apply to every generating call and are checked **before** it is made:
`--max-tokens-per-day`, `--max-invocations-per-day` (the one tokens cannot express — see
§15's per-call harness tax), `--max-tokens-per-operation`, `--max-cost-usd-per-day`. Pass
`-1` for unbounded, which has to be asked for rather than being what you get by forgetting
a flag. `status` prints spend against plan.
- `verify` — rebuild every revision from canonical records, check the content hashes, and
  report any revision no policy decision explains. Exits non-zero if it finds one.

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

- **No planner.** Nothing decides what scene to write next. A book can be imported and a
  draft job enqueued by hand with its prompt supplied, but there is no beat sheet and no
  context packet, so nothing enqueues the next scene on its own.
- **No craft gate.** The only gate is shape — a draft exists, is the right size, and did
  not overwrite anything. Nothing measures whether the prose is any good (PLAN.md §1a).
- **No game-system validation.** The LitRPG rules pack lives in ContinuityEvaluation and
  is not wired in, so accepted prose is not checked against the ledger.
- **Directives are captured, not read.** See above.
