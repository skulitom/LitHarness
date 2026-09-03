# Handoff: the evaluator boundary — the instrument is the product, the launch is its test

**Scope:** one worktree session (`claude/litharness-evaluator-boundary-073f5a`, branched from
`main` at `12040ea`), no model budget, no paid arm, no corpus pass. The brief is the operator's
2026-09-03 direction "the evaluator is the product; the launch is the instrument's test", plus
the same-day addendum "the record is the distribution artifact". This file is deleted once its
results have a canonical home: the decision in `plan/stage-0-decisions.md` (§221), the code under
`src/litharness/packs/`, `application/instrument.py`, `domain/audience.py`, `domain/release.py`,
and the registration at `research/launch-outsample/PREREG.md`.

**Re-anchoring, stated first.** The brief asks to start "at the repo root, on `main`". This
session runs in a linked worktree, which is how parallel sessions work here (CLAUDE.md,
"Parallel sessions are real"); the coordinator session (`litharness-48`) merges. Nothing else in
the brief conflicts with the repo, except the places recorded under "Refusals".

## What the brief asks

1. One stage-0 entry recording four decisions: the product is the instrument; the Royal Road
   launch is the instrument's out-of-sample test and nothing else; publication becomes a staged,
   operator-gated release queue (a partial reversal of §62 that keeps "the tool never posts");
   real-reader data keeps exactly §126's role.
2. Slice 1: a domain-agnostic evaluator port and a domain-pack seam, LitRPG as the first pack,
   a non-fiction `plain` pack exercised through `providers/fake.py`, the existing suite green
   with no behavioural change to a LitRPG book. Addendum: the record is self-describing and
   portable, and `instrument.report(record)` renders a Markdown validity report from it alone.
3. Slice 2: `research/launch-outsample/PREREG.md` at REGISTRATION; a release-queue migration
   and CLI with no posting path; the library's pastable copy pinned to the queue by hash.
4. Slice 3 held as CONJECTURE: an agent-facing MCP surface; a second non-fiction pack; the two
   numbers side by side; (addendum) a public index of validity reports keyed by record hash and
   a `packs/` contribution guide.

## What the repo already has (measured by reading, pointers not restatements)

- **Stopped-part-way reading:** `domain/text.stop_point` (§124's registered rule; the research
  copy pinned equal by `test_the_package_and_the_registered_probe_cut_in_the_same_place`).
- **Two disjoint rosters:** `application/readers.py` — steering and measurement, nobody in both;
  `BLIND` as the no-taste arm.
- **Behaviour-not-verdict elicitation:** `CHOICE_SCHEMA`, `LEAVE_SCHEMA`, `START_SCHEMA`,
  `PICK_SCHEMA`, `ANTICIPATION_SCHEMA`; no verdict slot anywhere (§89, §97.4).
- **The E6 frame:** every `because` and every steering field is a description of what is there,
  never a preference.
- **The validity rails, as research code:** positional rate and VOID (`analysis.positional_rate`,
  `verdicts`), recognition with its `unprobed` class (`recognition.py`, `backtest.probe_book`),
  sham floor (`analysis.sham_floor`), label shuffle (`analysis.label_shuffle`), under-run
  (`backtest.py`'s `under_run` block, FINDINGS.md).
- **Content-addressed records and the claim vocabulary:** `EPISTEMIC_GOVERNANCE.md`;
  `blinding.Blinded.digest`; `population.population_digest`.
- **A rival admission rule with its genre set inside it:** `domain/rivals.admit` over
  `rivals.GENRES`.
- **A library with a pastable per-chapter copy and release volumes and no release unit:**
  `application/library.py` (its docstring counts itself as one of §62's seven absences).
- **What it lacked:** no port, no pack seam, no general audience type (the reader's framing
  sentence is a literal inside `Reader.system`), no release table, no registration for the
  launch.

## The inventory (slice 1, step 1)

Filled from an eleven-module classification with three adversarial passes over it (a
workflow of this session; agent prose, so every "both" line was re-read by hand before it was
acted on). Kinds: *general* works on any passage and any audience spec; *litrpg* references
genre vocabulary, the game-system detectors, `house.READER`, the LitRPG rival shelf or the RR
corpus; *both* names the lines; *corpus-bound* cannot run without the shards.

Eleven modules, fourteen agents, twenty disputes, and every dispute was read against the file
before the table below was written. The disputes that changed a row: the five `render_*`
requests in `readers.py` are general in mechanism and carry the genre only through
`reader.system()` (the framing sentence was at line 99 of the old file), so the genre is the
audience's and not the renderer's; `pool`, `Reading.of`, `Anticipation.of` and `Browsing.of`
were bound to the module roster through `pool()` and were therefore not general as written;
`rivals.admit_all` inherited the genre check; `rivals.MIN_FOLLOWERS` is an integer floor
whose Royal Road calibration is docstring, not code; and the backtest's `REASON_CODES`,
`STAGE2_SCHEMA` and `stage2_turn` carry a genre word only in a trailing comment the model
never sees. The recruiter and roster disputes refine line lists on writer-side modules the
slice does not touch.

| module | general | LitRPG, and where | disposition in slice 1 |
| --- | --- | --- | --- |
| `application/readers.py` | the profiles, `CALL_CLASS`, the five schemas, `render_choice_request`, `render_anticipation_request`, `render_pick_request`, `render_start_request`, `render_appetite_request`, `accumulated_passage`, `prior_reading_memory`, `side_of`, `Pairing` | `Reader.system`'s framing sentence (old line 99); `READERS` (the eight tastes, old lines 117–176); `BLIND` inherits the framing; `pool` and the three `.of` aggregates were bound to `READERS` | `Reader` to `domain/audience.py` with `framing` explicit; `READERS`, `BLIND`, `pool` to `packs/litrpg`; the aggregates take a roster; the renderers unchanged |
| `domain/text.py` | all five symbols | — | the port's `StopRule` wraps `stop_point`; nothing moves |
| `domain/rivals.py` | the floors, `Rival`, `draw`, `ours_first`, `IllegalRival` | `GENRES` (old lines 92–103); `admit` at the membership check (old 202–204); `admit_all` by inheritance | `GENRES` to `packs/litrpg`; `admit` and `admit_all` take `genres` |
| `domain/house.py` | `CLARITY`, `demands`, `with_clarity_floor` | `READER` (667–685), `ACCUMULATION` (705–707); `HOUSE_RULES` and `with_house_rules` compose them; `MACHINERY_WORDS` names the genre's own machinery | stays; the pack points at the two essays as tier 3 |
| `application/recruiter.py` | the profiles, `ALLOWED_TOOLS`, `MAX_OUTPUT_TOKENS` | `SLATE`, `NEAR_PAIRS`, `SUPPLEMENTARY` (the shelves); `shape_for` and `render_recruit_request` name shelf slugs | writer side; stays; inventoried only |
| `application/roster.py` | `VIEWS`, `appetite_markers`, `reserved_name`, the census arithmetic | `SPECIALIZATIONS` (47–81); `EXAMPLE_DECLARE`, `vocabulary`, `show`, `check`, `rehearse` carry shelf examples | writer side; stays; inventoried only |
| `research/quality-measurement/elicit.py` (+ `personas.py`'s two turns and schema) | the cache, the transport, the digest, `Sample`, `Comparison`, `positional_bias`, the two-stage protocol's mechanism | the protocol methods default to `personas.PANEL`/`GENRE_PANEL` (1160, 1228 and the four beside them) | research; stays; the port carries the describe-then-behave shape without importing it |
| `research/sim-readership-backtest/blinding.py` | `Blinded`, `first_words`, the phrase patterns | `blind` strips platform words (`_PLATFORM`, line 56 names Royal Road and Patreon) | research; stays; exposed later through an adapter |
| `research/sim-readership-backtest/recognition.py` | all twelve symbols | — (the probes say "serialised web fiction"; a probe for another pack rewrites two strings) | research; stays; the port's `recognition` rail carries its three classes |
| `research/sim-readership-backtest/population.py` | `SALT`, `REWARD_SIZE` | `GENRE_FAMILIES` (34–41), `POPULATION` (67–78); `Persona`'s axes and `system_prompt` are fiction-shaped | research; stays; a pack's roster is the general form of this table |
| `research/sim-readership-backtest/analysis.py` | all fourteen symbols (pure arithmetic over votes) | — | research; stays at the path PREREG §10 names (K1a); the port's `Validity` mirrors its names |

## What slice 1 builds, and the one design decision that shaped it

**The port is a new module, `application/instrument.py`, not an extension of `ports.py`.**
`ports.py` names what the application layer needs from outside (stores, a generator); the
instrument is what the application layer *offers* to a caller. Putting an inbound protocol
beside the outbound ones would blur the one thing `ports.py` is for.

**The audience becomes a domain value (`domain/audience.py`)** — `Reader` with an explicit
framing sentence, the two pool names, `pool()` over any roster, and the three specs the port
takes (`StopRule`, `AudienceSpec`, `CurrencySpec`). `application/readers.py` re-exports `Reader`
and the pool names so every existing import resolves.

**The LitRPG roster and genre set move behind `packs/litrpg/`.** `readers.READERS`, `BLIND`,
`pool` and `rivals.GENRES` are gone from `application`/`domain` and live in the pack; the
application layer takes a roster where it used to reach for the module constant. That reaches
the editorial control plane: `editorial.mechanism_spec_digest` hashes the steering roster's
system text into `reader.anticipation.v0`'s spec digest and `_validate_observation_job` refuses
a job whose persona is not on it. The roster is now an explicit argument there (the digest is
computed from the same bytes, so every stored `spec_digest` and every frozen job still
validates); `cli.py`, the composition root, passes the pack's roster. Tests were edited only
to point at the moved names and to pass the roster the functions used to reach for
implicitly; no assertion changed.

**What stays where it is, with the reason:** `house.READER` and `house.ACCUMULATION` are the
LitRPG pack's tier-3 essays and the pack points at them; the text stays in `domain/house.py`
because `HOUSE_RULES` reaches every writer prompt byte for byte and a move would change every
stored policy digest for nothing. `recruiter.py` and `roster.py` are the writer side of the
house, not the evaluator; the inventory classifies them and slice 1 does not touch them.

**The record (`Readout`) is the distribution artifact.** Content-addressed over everything it
carries; self-describing (`schema`, pack id and digest, provider and model, stop rule, audience
and currency specs, per-reader behaviour with the reader's own words, the validity block, the
transport failures, the passage and stopped-passage hashes). It refuses a verdict slot at
construction — a dataclass field named `score`, `verdict`, `rating`, `grade`, `rank`,
`quality` or `preference`, at any nesting — and `test_a_record_refuses_a_verdict_slot_added_later`
adds one and watches it refuse. `instrument.report(record)` renders a Markdown validity report
from the record alone; `test_the_report_carries_the_record_hash_and_nothing_the_record_does_not`
pins it.

**The validity block names every rail and says what it did.** For a single-passage read on
the fake provider: `under_run` is measured (planned against answered, with the failures
listed); `positional` is `not_applicable` (one text, no slot); `recognition` is `unprobed`
(no probe ran, and the record says so rather than `clean`); `sham_floor` and
`shuffle_clear_share` are `not_run`. A rail that did not run is written as not having run.
The rails' arithmetic stays in `research/sim-readership-backtest/analysis.py`, where PREREG
§10 names it (K1a); the port exposes them later through an adapter.

## Refusals, each with its reason

- **No research module moves into `src/`.** `analysis.py` has no corpus dependency and could
  move, but the backtest's registration names its path (`PREREG.md` §10) and the pilot was a
  paid call (K1a). The port's validity vocabulary mirrors the registered names; the arithmetic
  is not duplicated.
- **No convenience score.** The record carries counts and a share per behaviour and its
  validity flags. A consumer wanting one number gets the distribution.
- **No edit to the backtest's `PREREG.md`.** Its cost correction is the operator's (see the
  questions below).
- **`house.READER` and `house.ACCUMULATION` are not moved** (above).
- **`recruiter.py` / `roster.py` are not moved**: generation side, not the evaluator.
- **No `release post`.** The tool never posts; Royal Road's Terms prohibit automated access
  without express permission, and the repo builds no such path. `approve` and `record-posted`
  write the operator's name and refuse without one.
- **The table is `release_queue`, not `release`**: `RELEASE` is a SQLite keyword
  (`RELEASE SAVEPOINT`), and `CREATE TABLE release` is a syntax error.
- **No prediction driver for the launch is built.** The registration names the refusal rule
  it must implement (a prediction record timestamped after a chapter's `posted_at` is refused);
  building it is slice 2's sequel, after the operator answers the questions below.
- **No CLI surface for the port this session.** `litharness readers` keeps its behaviour on a
  LitRPG book untouched; the port is reached in code and by the test that proves generality.

## Not this session (CONJECTURE, no design beyond these lines)

- An agent-facing surface: an MCP server exposing `instrument.read(passage, audience_spec)` and
  `instrument.validity(record_id)`, behind the spend rails `force_remote.SingleRun` and the cost
  ledger already carry. Consumers get behaviour and validity; never a score.
- A second, non-fiction domain pack with its own rival source, so the tool is visibly not a
  fiction tool.
- A written result: the backtest's number and the launch's number beside each other, in the
  BRIEF's house form, whatever they are.
- A public index of published validity reports keyed by record hash.
- A `packs/` contribution guide, since each pack brings its own audience.

## Questions for the operator (left unanswered here)

- The backtest's registered full stage prices at roughly the measured per-pair cost times the
  registered n, against the registered programme ceiling; `FINDINGS.md` records the refusal
  and says the correction is the operator's under K1a. Which of: raise the ceiling naming the
  number seen, reduce n with a re-sized power statement, or run the confirmatory set in stages?
- Whether to ask Royal Road for express written permission to post from an automated queue.
  Until that exists, posting stays an operator act.
- Which non-fiction domain the second pack targets (slice 3), so its rival source can be chosen
  without touching RS1.

## The test edits, exactly

Tests were edited in two ways only, and every assertion is the one it was. **Pointing at moved
names:** `readers.pool(readers.MEASUREMENT)` became `litrpg.pool(readers.MEASUREMENT)` (and the
steering twin) in `test_house_genre_promise.py`, `test_prompt_budget.py`,
`test_readership_prior_life.py`, `test_listing_loop.py` and `test_reader_futures.py`;
`rivals.admit(row)` became `litrpg.LITRPG.admit_rival(row)` and `rivals.admit_all(rows)` gained
`genres=litrpg.GENRES` in `test_reader_futures.py`. **Passing the roster the function used to
reach for implicitly:** `experimental_mechanism(..., roster=ROSTER)`,
`mechanism_spec_digest(ROSTER)`, `reader_jobs_for_checkpoint(..., roster=ROSTER)`,
`make_reader_observation_handler(..., roster=ROSTER)` and
`make_scene_draft_handler(..., reader_roster=ROSTER)` in `test_editorial.py` and
`test_cli.py`, with `ROSTER = litrpg.LITRPG.steering`; `Anticipation.of(..., roster=STEERING)`
in `test_reader_futures.py`. Four research scripts were re-pointed the same way
(`listing_arena.py`, `blurb_gradient.py`, `readers-order-control/run.py`, `rival_pool.py`);
none is a registration.

## The free sizing run behind the launch registration

`research/launch-outsample/PREREG.md` §4 quotes this table; the script that produced it, run
once under `uv run python` on 2026-09-03 with seeds `20260903 + n`, is kept here rather than
as a module because it is a sizing aid and not an instrument:

```python
import math, random
def spearman(a, b):
    n = len(a)
    ra = sorted(range(n), key=lambda i: a[i]); rb = sorted(range(n), key=lambda i: b[i])
    ranks_a = [0] * n; ranks_b = [0] * n
    for r, i in enumerate(ra): ranks_a[i] = r
    for r, i in enumerate(rb): ranks_b[i] = r
    ma = sum(ranks_a) / n; mb = sum(ranks_b) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(ranks_a, ranks_b))
    va = sum((x - ma) ** 2 for x in ranks_a); vb = sum((y - mb) ** 2 for y in ranks_b)
    return cov / math.sqrt(va * vb) if va and vb else 0.0
def boot_lb(pairs, rng, resamples=400, alpha=0.05):
    n = len(pairs); vals = []
    for _ in range(resamples):
        s = [pairs[rng.randrange(n)] for _ in range(n)]
        vals.append(spearman([p[0] for p in s], [p[1] for p in s]))
    vals.sort(); return vals[int(resamples * alpha / 2)]
for n in (8, 10, 12, 16, 20, 24, 30, 40):
    rng = random.Random(20260903 + n); base = list(range(n)); nulls = []
    for _ in range(20000):
        b = base[:]; rng.shuffle(b); nulls.append(abs(spearman(base, b)))
    nulls.sort(); crit = nulls[int(0.975 * len(nulls))]
    t1 = sum(boot_lb([(rng.random(), rng.random()) for _ in range(n)], rng) > 0 for _ in range(400))
    pw = 0
    for _ in range(400):
        x = [rng.gauss(0, 1) for _ in range(n)]
        y = [xi * 0.58 + rng.gauss(0, 1) * 0.815 for xi in x]
        pw += boot_lb(list(zip(x, y)), rng) > 0
    print(n, round(crit, 3), t1 / 400, pw / 400)
```

## Checks and commits

- `tools/replay_books.py` (default stores under the primary checkout): 8/8 identical, 0
  skipped, run after every change to `readers.py`, `rivals.py`, `editorial.py` and
  `handlers.py`.
- Focused modules under `LITHARNESS_ENV=test`, `-n 0`, green: `test_instrument.py`,
  `test_release.py`, `test_reader_futures.py`, `test_editorial.py`, `test_architecture.py`,
  `test_listing_loop.py`, `test_prompt_budget.py`, `test_house_genre_promise.py`,
  `test_readership_prior_life.py`, `test_library.py`, `test_check_tool.py`, `test_store.py`.
- `uv run ruff check .` and `uv run mypy` (src and tools): clean.
- `uv run python tools/check.py handoff`, run 2026-09-03 at 23:06 local under the box lock
  (taken and released by this session, announced to the coordinator both ways): ruff, mypy,
  `git diff --check` and `uv lock --check` clean; **3,799 passed, 20 skipped**, coverage
  88.54% against the 85% floor; the wheel built. Its last step, the corpus leak audit,
  **exits 1 — and it exits 1 on `main` too, with byte-identical output**, so the failure
  predates this branch.
- **The audit's finding, verified and not fixed here.** It names one path,
  `research/quality-measurement/system-fit/census.json` (committed by `c857710`, §217's
  census), for 35 excerpt-sized strings, the longest 316 words at
  `.shapes[42].check.gaps[0]`. The text is this system's **own** complaint prose — the
  unfinished-system gap sentence `gamesystem` writes — concatenated per shape, not third-party
  corpus text, so the audit is measuring length rather than provenance here. It is another
  track's file and the repair is an exemption in a leak audit, which
  `tests/test_corpus_leak_audit.py` calls "a dangerous thing to add"; the coordinator and the
  operator own that call, and this session refuses to widen a leak rail to make its own check
  green.
- Commit: `1bc0004`, pushed to `origin/claude/litharness-evaluator-boundary-073f5a`.
