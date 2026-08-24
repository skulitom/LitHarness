# Handoff: the promise ledger — the call that settles debts is never shown them, and the rows it cannot settle are what fills the packet

You are working in `C:\DEV\LitHarness`, an autonomous fiction-production system whose objective is
popcorn-genre fiction (LitRPG, progression fantasy, isekai) a defined audience voluntarily
continues and recommends, with no human in the production loop. Superhuman literary
quality is the long-term goal (stage-0 §126). Your task is one bounded piece: make the promise ledger **able to settle** — show
the one call that records payments the debts it is being asked about — prove it structurally, then
re-run Serial Pilot 2 once on the same forged world as a pre-registered question (**S5′**), and
record what happened. Nothing here teaches the system *what* to pay or *when*; nothing here asks
any model whether a payoff was good. Read the boundaries before you read the tasks.

File names, line numbers and measurements below were verified on 2026-08-22 against `main` at
`83de11c`. If the repo has drifted, the repo wins; re-anchor rather than following this document
into a stale reference. Parallel sessions run on this repository — `git status` before you commit,
commit only your own files, and see "Coordination" below.

## Why this exists (context you need, then stop reading context)

Four books, zero payments: **32 opened / 0 paid**, then **40 / 0** (`serial.db`, the live pilot-1
serial), then Serial Pilot 2 ran twice on a forged world whose six debts were seeded *with their
answers in canon* and two of them disclosed to the writer at their scheduled scenes — **41 / 0** and
**47 / 0** (`plan/serial-pilot-2.md` §6.2). Stage-0 §107.9.2 and the pilot record both name the
next question as "the summary call is not told which debts are due". Measured against the code, it
is sharper than that, and it is structural:

- **The settling call is never shown the ledger.** `application/summarize.py:361` hands the
  summariser `state_mod.open_threads(store.state_records(...))` — THREAD-kind **state records** —
  and `:363` renders them as "The book records these as still owed" (`:209-213`). The promise
  ledger (`store.promises(book_id, branch_id, open_only=True)`, `adapters/sqlite_store.py:1481`)
  appears nowhere in the summary prompt.
- **Payment needs an exact key the model was never given.** Each `promises_paid` string goes
  through `normalise_subject` (`domain/extraction.py:639-642`: NFC, casefold, whitespace →
  underscore) into `promise_id_for(book_id, subject)` = `sha256(book_id + subject)`
  (`domain/promises.py:144-155`), then `store.pay_promise` runs `UPDATE … WHERE status='open'`
  (`sqlite_store.py:1448`) — paying a subject the ledger never opened is a no-op by design. So a
  payment lands only if a one-scene, no-memory call reproduces a subject string coined scenes
  earlier (`m_holts_date`, or whatever the summariser itself named in scene 2). That is not a model
  failing; it is an impossibility by construction. The loop is `summarize.py:456-467`.
- **The writer sees the ledger; the summariser does not.** `application/planner.py:578-583`
  passes the open rows into the packet's THREADS section as `describe_owed` lines
  (`domain/context.py:476-500`, `promises.py:343`); the outline call sees their subjects
  (`application/outline.py:489`, W2 payoff windows). The one call that can mark a debt paid is the
  one call not shown it.
- **The same rows are what fills the packet.** Across pilot 2's eight stored drafting prompts the
  world holds flat at 229–231 facts while the threads section grows **6 → 41**, prompt tokens run
  9,052 → 14,443, and prose stops fitting at three prior scenes from scene four
  (`plan/serial-pilot-2.md` §6.2 table). `plan/world-architect.md` §5.1 recommends a **ledger
  policy before any world retriever** — and a policy over a ledger where nothing ever settles
  would be pruning debts nobody pays. That is why this comes first.
- **W4 is waiting on exactly this.** `research/quality-measurement/payoff_landing.py`'s docstring:
  the `paid` and `mismatched` arms have no substrate, and the verdict is NOT VALIDATED until "both a
  ledger with payments and an owner-read set exist". A ledger with payments is what Task 2 can
  produce.
- **The pilot-2 substrate is gone from disk.** `pilot2/` is gitignored and absent, and no
  `serial2*.db` exists on this machine (checked 2026-08-22). What is committed is the source:
  `plan/serial-pilot-2-world.json` (the chosen candidate's model answer — `architect.records_for`
  regenerates the seed records byte-identically, `tests/test_architect.py:611`),
  `plan/serial-pilot-2-directives.json` (already in the shape `forge --pick` writes as
  `directives.json`), `plan/serial-pilot-2-promises.json` (ditto `promises.json`), and
  `plan/serial-pilot-2-craft.json`. `tools/serial-pilot-2-setup.ps1:77-82` requires a forge
  directory holding `seed.json`, `directives.json`, `promises.json`. You will regenerate that
  bundle; see Task 2.

That is the whole context. Everything below is the bounded work.

## The hard boundaries

These are not preferences. Work that breaks one of them is worse than work not done.

1. **Advisory stays advisory.** `promises_paid` remains a model claim; `promise.overdue.v0` stays
   MINOR and `heuristic` (`domain/integrity.py:364-401`); nothing built on the ledger may block,
   park, rank, or select anything (`domain/promises.py` module docstring; stage-0 §61 Add 2). No
   finding severity moves.
2. **Exact match on purpose; looseness belongs to W4.** Showing the ledger lets the model *name*
   a subject; whether anything actually landed on the page is W4's report-channel question on the
   research side, graded by its own controls. Do not add fuzzy or majority-word matching to the
   handler. A ledger that pays on loose matches is worse than one that pays nothing, because W4
   grades against the ledger's own wording.
3. **No instruction about what to pay or when, anywhere.** Showing the open rows to the
   summariser is information, the same class as the THREAD block it already gets. Nothing of the
   form "pay these", "resolve X by scene Y", "this debt is due now" enters the summary prompt, and
   **the writer's packet and drafting prompt are not touched at all in this handoff**. No model
   chooses which debt to pay.
4. **No verdict channel.** Do not ask any model whether a payoff is good, whether a scene pays a
   debt well, or which of two payoffs it prefers. E6 stays byte-frozen
   (`domain/discrimination.py`); no new verbal frame.
5. **LLM-only regime; scope axiom (stage-0 §95).** No human readers, labels, or solicited
   judgment. The operator's acceptance read is not spent here (pilot-2 §5: not unless the gate
   exits 0, and then it is theirs, not yours). RS1: no corpus prose or digest reaches
   `src/litharness/`.
6. **Declare no bar.** S5′ is a question with named outcomes, not a bar; report counts, never
   rates — n is six seeded debts plus whatever the summariser opens, and "any subgroup of two is
   empty" (§108.5) applies. A pre-registered null is a result (§61).
7. **Counts point to canonical homes; corrections in place; the ledger is append-only.** The next
   stage-0 number is **§109 or later**: §108 is the last entry on `main` at `83de11c`, and the
   highest in any worktree is 107. Re-check at commit time:

   ```bash
   for f in plan/stage-0-decisions.md .claude/worktrees/*/plan/stage-0-decisions.md; do grep -oE '^#{2,3} [0-9]+' "$f" | grep -oE '[0-9]+$' | sort -n | tail -1; done | sort -n | tail -1
   ```

   Never cite a test name that does not exist (`tests/test_architecture.py` enforces it).
8. **`serial.db` is read-only.** Demonstrate every repair on a copy; redraft no accepted scene;
   re-mint nothing. The pilot-2 world, directives, promises and craft JSON are not edited.
9. **No re-forge.** S5′ is on the *same* world, or it is a different question. Re-forging costs
   $1.53, yields a different world, and would need a person to pick again.
10. **New files where you can.** The one shared document you extend is `plan/serial-pilot-2.md`,
    because it is the run record: a pre-registration addendum before the run, a §6.3 after.

## Coordination

Worktrees dirty on 2026-08-22: `busy-spence-0cf6eb` (`domain/calibration.py`,
`domain/failures.py`, `tests/test_architecture.py`), `modest-kalam-94e683` (`py.typed`),
`scene-book-preference-experiment-ff67a9` (`research/scene-book-grain/`). None touches
`summarize.py`, `planner.py`, `outline.py`, `promises.py`, `sqlite_store.py`, or the pilot-2
package. Branch `claude/brave-vaughan-ea11ed` shows +1 over `main`, but its fix is already on
`main` by content (`cli.py:3451-3454`) — ignore it.

**Before the paid run:** check that no other paid arm is running on this box (`claude -p` fails
silently under load — `CONTRIBUTING.md`; look for `research/quality-measurement/results/.*.pid`
locks and running `claude` processes). Budget one run: the two pilot-2 runs cost $5.67 and $5.89 at
eight scenes; the loop args already carry `--max-cost-usd-per-day 10`.

## Task 0 — measure before building (no provider call, all local)

Record these as output in your note, not as prose claims. `debug-book` (a project skill) answers
provenance questions from stored rows; use it before opening the database by hand.

1. **What the summariser actually returned.** On `serial.db` (pilot 1, the only live ledger on
   this machine): `store.promises()` — rows, open, paid. Then for every stored scene summary
   (`record_scene_summary` writes a `promises` JSON `{opened, paid}` beside the summary row —
   check the table and column names, don't assume), list every `promises_paid` string the model
   returned, and for each whether `promise_id_for(book_id, normalise_subject(name))` matched any
   row that existed at the time. Expected: most `paid` arrays empty, and none of the non-empty ones
   matching. Also count how often the summariser re-coined a subject it had already opened (two
   scenes → one row under `INSERT OR IGNORE`) — that is the only path by which a payment could ever
   have landed, and its rate says how often the model reproduces a key unprompted.
2. **The prompt fact.** Confirm `render_summary_prompt` receives THREAD state records only and
   that `promises` appears nowhere in the summary prompt path; record the line numbers at your
   commit. Confirm the summary job id is keyed on the scene's content hash and excludes the prompt
   (`tests/test_summarize.py:98`), which is what lets Task 1 change the prompt without re-minting
   any stored job.
3. **The packet-pressure baseline you will compare against.** From `serial.db`'s stored
   `scene_draft` payloads: threads-section row count and prompt tokens per scene. Pilot 2's own
   table is in `plan/serial-pilot-2.md` §6.2 and its databases are gone, so say which store each
   number came from.
4. **The bundle is regenerable.** From `plan/serial-pilot-2-world.json`:
   `architect.records_for(Candidate(0, package["world"]), authority=ACCEPTED_CANON, scenes=8)` —
   report the record count you get (run B was 329; the committed test pins determinism, not the
   count) and that `worlds.validate(records) == ()`.

## Task 1 — show the settling call the ledger, and prove it structurally

In `make_summary_handler` (`application/summarize.py`), load
`store.promises(book_id, branch_id, open_only=True)` and pass the rows to `render_summary_prompt`
under a new keyword (e.g. `open_promises: Sequence[Promise] = ()`), rendered as the ledger's own
lines — the `subject` exactly as stored, then `describe_owed(promise)` — in a block that states
its register and is kept **separate** from the THREAD block, because the two are different
classes of claim (canon-backed records versus model/forge-sourced debts; the same reason
`context.py` phrases `describe_owed` as a debt rather than a fact). Change the `PROMISES_PAID`
instruction (`summarize.py:207`) to ask for subjects **copied exactly from that list** and
empty if none. Leave `promises_opened`, `OPEN`, `DELTA`, the system message's other lines, and the
THREAD block as they are.

Rules, each pinned by a test beside the existing ones in `tests/test_summarize.py` and
`tests/test_promises.py`:

- **Byte-identical control.** With an empty ledger the prompt is byte-for-byte today's — pin it
  next to `test_the_prompt_shows_the_book_its_own_open_threads` (`tests/test_summarize.py:276`).
- **The ledger reaches the prompt**, in the store's order (due-soonest first, NULL due last,
  `sqlite_store.py:1481`), uncapped. If you believe a cap is needed — the ledger is 41 rows by
  scene eight and the rows are one line each — record what was dropped in the summary row rather
  than truncating silently. Prefer no cap.
- **A name copied from the list pays its row; a name not on the list pays nothing** — and both
  are recorded: extend the summary row's `promises` JSON with what the model said *and* what
  matched (`paid_matched` / `paid_unmatched`), so Task 0's measurement is re-runnable from the
  store without re-deriving it.
- **A seeded (forged) promise can be paid.** `Promise.model` is `""` on seeded rows (§107.8's
  stated limit) — check `pay_promise` carries no condition on it. The `promises` table has no
  authored-versus-model column; do not add a migration for it here. If you find you need one,
  that is a scope decision — write it up and stop.
- **Nothing re-mints.** A tick over an already-summarised book summarises nothing new; the W1
  `kind` path is unchanged; `promise.overdue.v0` is unchanged.
- **The `normalise_subject` round trip.** A subject copied from the rendered line must
  normalise to the stored subject (it is already normalised, so this should be the identity —
  pin it, since a render that title-cased or re-spaced the subject would silently break the key
  it exists to let the model reproduce).

The claim you may make is "the ledger is now in the call that settles it", and only that. Report
the summary prompt's token growth with the ledger shown (one line per row) beside the claim.

## Task 2 — S5′: pre-register, regenerate the bundle, run once, record

**Pre-register first**, as an addendum to `plan/serial-pilot-2.md` §4 (or a new §4.1), before any
paid call, in the pilot's own table form:

| # | question | how it is answered | outcomes named in advance |
|---|---|---|---|
| **S5′** | with the open ledger shown to the settling call, does anything settle | per promise: `status`, `paid_at_key`, `paid_by_revision`, `kind`, seeded-or-model-opened; counts, no rate | (i) ≥1 seeded debt paid at or after its scheduled scene (`m_holts_date` s4, `m_orrin_last_call` s7) → the summariser was the block; (ii) 0 of 6 seeded paid with the list shown → S3 already showed the reveal reaching the writer mechanically, so "disclosed to the writer" ≠ "paid on the page" — the next question, not this task's; (iii) model-opened debts paid but seeded ones not → a subject-vocabulary mismatch; check the render and the normalisation before reading anything else into it |

Also pre-register the **packet trace**: the same per-scene table as §6.2 (facts / hidden / threads
/ prose / summaries / prompt tokens). Paid rows leave the packet (`open_only=True`), so any
settled debt is the first measurement a ledger policy needs. And the hidden-count trace
`20,20,20,19,19,19,18,18` should reproduce — S3 is untouched by this work, and if it moves you
changed something you should not have.

**Regenerate the bundle** — `pilot2/` is gone. Read `cmd_forge`'s `--pick` branch
(`cli.py:3162` onward, the write at roughly `:3200-3250`) and reproduce **exactly** what it writes
into a fresh directory: `seed.json` via `architect.snapshot_for(Candidate(…, package["world"]),
book_id=…, branch_id=…, revision_id=…, architect_id=package["architect_id"], created_at=…,
authority=ACCEPTED_CANON, scenes=8)`, and `directives.json` / `promises.json` from the two committed
files (they are already in that shape; check `cmd_new --state`, `cli.py:3530-3545`, and
`serial-pilot-2-setup.ps1:77-82` for what each must contain, and mint fresh ids only where the
snapshot demands them). A small tool beside the setup script is the right home; pin with a test
that its seed records equal `records_for`'s and validate clean. Record in the run record that the
**operator's pick is not re-made** — it was recorded on 2026-08-22 (`picked` in the world JSON) —
the bundle is re-materialised from it. Two known pre-existing conditions to carry, not fix:
defect 8 (the world's graph line is unusable, so the second extractor family is inert on this
world) and the four arc debts carrying no due key (defect 9's fix, already in code for run B).

**Run once**, exactly as `plan/serial-pilot-2.md` §3, with a new database name:

```powershell
.\tools\serial-pilot-2-setup.ps1 -Forge <dir> -Scenes 8 -Database serial2c.db
```

```powershell
.\tools\run-loop.ps1 -Database serial2c.db -Ticks 14 -DelaySeconds 2 `
  -TickArgs '--target-words','900','--context-budget','16000','--chapter-scenes','4','--max-cost-usd-per-day','10','--max-invocations-per-day','80'
uv run python tools/serial_pilot_check.py --database serial2c.db --phase directives `
  --spec <dir>\directives.json --spec plan\serial-pilot-2-craft.json
```

Only when the early gate is green, the 48-tick phase and the full gate with the same `TickArgs`
and both `--spec`s (§3; one spec alone reports the inbox short). `--context-budget 16000` is a
precondition, not a knob (§3's table). **Keep the database.** It is gitignored and should stay so,
but do not delete it: if anything settles, it is the first ledger with payments in this repository
and W4's substrate. Record its path and a digest in the run record.

**Record** as `plan/serial-pilot-2.md` §6.3, in §6.2's form: ticks / jobs / decisions /
invocations / tokens / cost / scenes / words / parked / findings / gate; the per-scene packet
table; and the ledger table (subject, kind, opened_at, due, status, paid_at, paid_by, seeded or
model). Counts, no rate, no bar. What is deliberately not claimed: whether any payoff is good, and
whether the prose is.

## Task 3 — W4's free legs, and what the paid arm now has

```bash
uv run python research/quality-measurement/payoff_landing.py --selftest
```

```bash
uv run python research/quality-measurement/payoff_landing.py --dry-run --book-db serial2c.db
```

Report, per arm (`paid`, `mismatched`, `unpaid`, `placebo`), how many pairs the new ledger can
build. If zero paid, record `paid` and `mismatched` as NOT RUN with the reason, in the table,
never omitted. The model legs touch the 4090 and carry the duty-cycle/temperature governor; running
them is an operator call, and the verdict stays NOT VALIDATED regardless — the owner-read set is
out of scope here.

## Task 4 — design note only: what a ledger policy would need

One page, no code, in your results note (or `plan/world-architect.md` §5.1 if it is cleaner to
keep it beside the measurement it extends): from the before/after packet traces, what "still worth
carrying at scene N" would have to decide; what it must not do (drop a debt because it is old —
`domain/context.py`'s packer already drops the oldest prose rather than the least relevant, the
§12 defect §108.3 shows biting a deliberate change); whether settled debts alone relieve the packet
or whether the policy is still needed at the measured open rate; and where the writer-side "due
now" cue would sit if the operator ever wanted one (it is not yours to add). Name the migration or
column a persisted policy would need. Do not build it.

## Out of scope, named so you do not drift into it

- Any change to the drafting prompt, the packet, or `planner.render_prompt`.
- Any "pay now" / "due now" instruction; any model choosing which debt to pay; any ranking; any
  fuzzy matcher in `src/`.
- A retriever, a pruning policy, or a migration for an authored-versus-model column (name it if
  you need it; do not build it).
- `lock-constraints` on `serial.db`, the `[STATUS]` line at chapter ends, an ending clause in
  pilot 2's directives — operator decisions, all still open; the repo will show it if one has been
  taken since.
- Re-forging; a different world; any edit to the committed world, directives, promises or craft
  JSON; any redraft of an accepted scene.
- Any claim about prose quality, any comparison of prose between runs, any reader, judge, persona,
  BCR, axis or pool change, any pre-registration beyond S5′.

## Deliverables

1. Task 1's change with tests in `tests/test_summarize.py` / `tests/test_promises.py`, including
   the byte-identical control and the round-trip pin; the "never shown the ledger" fact turned into
   a regression test that fails on `main` as it stands today.
2. The bundle-regeneration tool and its test (Task 2).
3. The pre-registration addendum in `plan/serial-pilot-2.md` **before** the run, and §6.3 after.
4. A results note, new file under `research/quality-measurement/` (or `plan/` if mostly design),
   carrying Task 0's tables, Task 1's before/after summary prompt, Task 2's tables, Task 3's per-arm
   counts, and Task 4's note.
5. One stage-0 entry (§109 or later, re-checked at commit) in the house form: measured first, what
   shipped, what was refused, no bar declared, corrections in place — pointing §107.9.2's "why the
   ledger pays nothing" and `plan/serial-pilot-2.md` §6.2's "concrete next question" at it.
6. Your own commits. Run `uv run pytest`, `uv run ruff check .`, `uv run mypy`, `git diff --check`
   first — and check that no paid arm is running on this box before the full suite.

If Task 1 turns out to be unsafe — the summary call starts failing its schema or its 512-token
answer budget once 41 rows are shown, or the only way to get a match is a loose one — **stop and
write that up instead**. A ledger that pays on loose matches is worse than a ledger that pays
nothing, and a summariser that loses its four prose fields to a debt list is a worse packet than
the one it was meant to spare.
