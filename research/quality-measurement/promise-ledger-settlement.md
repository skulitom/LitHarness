# The promise ledger: the call that settles debts was never shown them

**2026-08-22.** Measurements and design note for
the stage-0 §110 promise-ledger task; the decision record is
[stage-0 §110](../../plan/stage-0-decisions.md), the run record is
[`plan/serial-pilot-2.md`](../../plan/serial-pilot-2.md) §4.1 and §6.3.

Everything below is a count. Nothing here says whether a payoff is good, whether a scene pays a
debt well, or whether any prose is any good — no model was asked, and no reader was.

---

## 1. Before: what the four books actually did (Task 0)

### 1.1 The ledger on `serial.db`, the only live ledger on this machine

Pilot 1's serial, book `d0c90550`, eight scenes, plan head at `83de11c`. Read-only
(`file:…?mode=ro`); no verb in `debug-book` reads the ledger, and the CLI has no `promises`
command, so this is the store queried directly.

| | count |
|---|--:|
| rows in `promises` | **40** |
| of those, `status = 'paid'` | **0** |
| seeded rows (`model = ''`) | 0 — every row on this book is model-opened |
| `promises_opened` items across all eight summaries | **41** |
| distinct subjects among them | 40 |
| summaries with a non-empty `promises_paid` | **1 of 8** |
| `promises_paid` strings returned in total | **2** |
| of those, matching a row that existed at that moment | **0** |
| of those, matching a row that ever existed | **0** |
| per-kind (`plot` / `mystery` / `progression` / `character`) | 20 / 9 / 6 / 5, all open |

The two strings, both from scene 6, with the key each one produces:

| returned by the model | `normalise_subject` | `promise_id_for` | existed then | ever existed |
|---|---|---|---|---|
| `The tarnished blank at Kessel's stall` | `the_tarnished_blank_at_kessel's_stall` | `prm-42a80b94bf6e455fe78d5877` | no | no |
| `Turrow's ring appraisal` | `turrow's_ring_appraisal` | `prm-74a6f9f2c48cb86fdaaeef4b` | no | no |

Both are fluent prose names for debts the book plausibly owed. Neither is a ledger key, and
neither could have been: the summariser had never been shown one.

### 1.2 The rate at which the model reproduces a key unprompted

This is the number that turns "the ledger pays nothing" from a model failing into a structural
one. Payment runs `normalise_subject(name)` → `promise_id_for(book_id, subject)` → `UPDATE …
WHERE status='open'`, so a payoff lands only when a one-scene, no-memory call reproduces a
subject string coined scenes earlier. The only observable evidence that this ever happens is a
subject re-reported in `promises_opened` and collapsed by `INSERT OR IGNORE`:

| | count |
|---|--:|
| opportunities (opened items after the first mention of any subject) | 41 |
| subjects re-coined exactly | **1** (`kelling_ledger`, scene 4, first opened at scene 1) |

**One in forty-one, and in the wrong channel.** The single reproduction landed in
`promises_opened`, where it is a no-op, and never in `promises_paid`, where it would have been a
payment. Nothing about this is a model's fault; it is the arithmetic of asking a call with no
memory to guess a hash input.

### 1.3 The prompt fact, at `main` `83de11c`

| claim | where |
|---|---|
| the summariser is handed THREAD **state records**, nothing else | `summarize.py:361` — `state_mod.open_threads(store.state_records(...))` |
| they render as "The book records these as still owed" | `summarize.py:211` |
| the ask that settles a debt | `summarize.py:207` — "the subject names of previously open threads this scene pays off" |
| `store.promises(...)` appears **nowhere** in the summary path | grep of `summarize.py` at `83de11c`: `promises` occurs only in the schema, the write loop, and docstrings |
| the writer **does** see the ledger | `planner.py:582` → `context.py:476-500` → `promises.describe_owed` (`promises.py:343`) |
| the outline call **does** see the subjects | `outline.py` W2 payoff windows |
| the job id excludes the prompt | `summary_job_for` keys on the scene's content hash; `tests/test_summarize.py::test_the_job_is_keyed_on_the_scenes_text_and_not_on_the_revision` |

The last line is what made Task 1 safe to do at all: changing this prompt re-mints no stored job.

### 1.4 The packet-pressure baseline, from `serial.db`'s eight stored `scene_draft` payloads

Counts are from each job's frozen `context.sections`; `packet tokens` is the payload's own
`context.tokens` under `regex-v1`. **This is pilot 1's store**, not pilot 2's — pilot 2's
databases are gone and its equivalent table is `plan/serial-pilot-2.md` §6.2, reproduced in the
last two columns for comparison.

| scene | facts | hidden | threads | prose | summaries | packet tokens | omitted | §6.2 threads | §6.2 tokens |
|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 1 | 14 | 0 | 0 | 0 | 0 | 717 | 0 | 6 | 9,052 |
| 2 | 15 | 0 | 4 | 1 | 0 | 2,203 | 0 | 10 | 10,061 |
| 3 | 16 | 0 | 11 | 2 | 0 | 3,603 | 0 | 16 | 11,536 |
| 4 | 17 | 0 | 17 | 3 | 0 | 5,013 | 0 | 21 | 12,808 |
| 5 | 18 | 0 | 21 | 4 | 0 | 6,291 | 0 | 27 | 13,415 |
| 6 | 19 | 0 | 26 | 5 | 0 | 7,762 | 0 | 32 | 13,744 |
| 7 | 20 | 0 | 31 | 6 | 0 | 9,257 | 0 | 37 | 14,077 |
| 8 | 21 | 0 | 35 | 7 | 0 | 10,600 | 0 | 41 | 14,443 |

Two different books, and the shape is the same in both: **facts flat or nearly so, threads
monotone up, and nothing ever settles.** Pilot 1 opened 35 packet threads by scene 8 out of 40
ledger rows (the rest not yet open at that beat); pilot 2 reached 41.

### 1.5 The bundle is regenerable

`architect.records_for(Candidate(0, package["world"]), authority=ACCEPTED_CANON, scenes=8)` over
[`plan/serial-pilot-2-world.json`](../../plan/serial-pilot-2-world.json):

| | |
|---|---|
| records | **329** — the same count run B ran on |
| `worlds.validate(records)` | `()` |
| `architect.gate_candidate(candidate, scenes=8)` | `()` |
| committed `directives.json` vs `architect.directives_for(candidate)` | equal |
| committed `promises.json` vs `architect.promises_for(candidate)` | equal |

The two committed files are byte-equal to what the forge derives from the world, which is a
stronger statement than "they were copied from the bundle": they *are* this world's directive and
promise sets, and `tools/rematerialise_forge_bundle.py` refuses if they ever stop being.

---

## 2. After: the ledger in the call that settles it (Task 1)

`render_summary_prompt` takes `open_promises: Sequence[Promise] = ()`. The handler loads
`store.promises(book_id, branch_id, open_only=True)` (`summarize.py:426`) and passes the rows
straight through, in the store's order — due-soonest first, NULL due last, `promise_id` as
tiebreak (`sqlite_store.py:1495`) — **uncapped**.

### 2.1 The block, and what it does not say

Rendered with Serial Pilot 2's six seeded debts:

```
The book's ledger of debts still unpaid, as it stores them. These are the book's own record of
what it owes rather than established fact; each line is the name a debt is filed under, then
what is owed:
- m_holts_date owes: Why does the Holt family, who dug the Ninefold lateral, hold no date? (due by s4)
- m_orrin_last_call owes: Who has been speaking Orrin Veck's date for her, and what happens in August when she cannot be carried? (due by s7)
- m_pells_lateral owes: What is Ferris Kane actually assembling out of the fifth years he keeps buying?
- ...
```

and the one changed line of the system message:

> `PROMISES_PAID: the names of open debts this scene pays off, each copied exactly as the ledger writes it. Empty if this scene pays none.`

Four properties, each pinned by a test:

- **Its own block, never folded into the THREAD block.** Open threads are canon-backed state
  records; a promise is a model-reported or forge-seeded debt. `domain/context.py` already keeps
  them apart by phrasing `describe_owed` as a debt rather than a fact, and one list under one
  heading would launder the second into the register of the first.
- **Byte-identical with an empty ledger.** Both halves — system and prompt. The `PROMISES_PAID`
  line is conditional precisely so that a prompt never names a list it does not carry. Every
  research caller of `render_summary_prompt`, every golden fixture, and every scene before the
  first promise opens is asking exactly the question it asked before.
- **The subject round-trips.** `normalise_subject(copied) == promise.subject` and
  `promise_id_for(book_id, normalise_subject(copied)) == promise.promise_id`, asserted by slicing
  the name back out of a rendered line. A render that title-cased or re-spaced a subject would
  look right and silently break the only key it exists to supply.
- **No instruction about what to pay or when.** Asserted rather than trusted, in §108.4's manner:
  the block header and the added ask are both checked against the vocabulary an instruction would
  need (`pay`, `due`, `now`, `should`, `must`, `resolve`, `settle`).

**One tension, named rather than buried.** `describe_owed` renders `(due by s04)` and, on a
promise an outline call has scheduled, `; pay within s07-s09`. That second clause is the ledger's
own stored wording — it goes into the *writer's* packet identically today — but read as an
imperative it is the shape the handoff's boundary 3 forbids adding. The handoff names
`describe_owed` explicitly as the line to render, so it is rendered; what is checked is that
nothing was *added* around it. It is also currently moot in this substrate: `serial.db` carries
**0 scheduled windows** across 40 open rows, so the clause never appears there, and §6.3 reports
the count for the new run.

### 2.2 What the summary row now records

`promises_json` gains `paid_matched` and `paid_unmatched` beside `paid`, so Task 0's measurement
is re-runnable from the store rather than re-derived from prose. `paid_matched` is exact set
membership against the subjects rendered into that call's prompt. Deliberately not looser: a
ledger that pays on near-matches is worse than one that pays nothing, because W4 grades payoff
landing against the ledger's own wording. One case is neither, and the handler says so in a
comment: a subject the same scene both opens and pays was not on the list, so it is recorded
unmatched while the ledger still settles it — pre-existing behaviour this change does not touch.

### 2.3 The cost, measured on `serial.db`'s 40 real rows

A real 900-word scene from the same book (1,360 tokens) under `regex-v1`:

| rows shown | system | prompt | total | delta |
|--:|--:|--:|--:|--:|
| 0 | 248 | 1,363 | **1,611** | — |
| 6 | 262 | 1,604 | 1,866 | +255 |
| 20 | 262 | 2,067 | 2,329 | +718 |
| 40 | 262 | 2,696 | 2,958 | +1,347 |
| 41 | 262 | 2,733 | **2,995** | **+1,384** |
| 47 | 262 | 2,924 | 3,186 | +1,575 |

**~32 tokens per row** net of a 44-token header. At pilot 2's scene-8 ledger of 41 rows the
summary call's input grows by 1,384 tokens — against 753,551 total tokens for run B, about
0.1% of the run if it held for all eight scenes.

**Why no cap.** One line per row; the largest ledger this project has measured is 47; and a cap
would drop exactly the debts a long book most needs settled while reporting nothing about having
done so. If one is ever needed, the handoff's rule stands: record what was dropped in the summary
row rather than truncate silently.

**The one thing that could still go wrong, and it is an output-side risk not an input-side one.**
`max_output_tokens` on this call is 512 and is untouched: showing rows costs input, not answer
budget. But a model shown 41 names has 41 names it could echo, and a `promises_paid` array long
enough to crowd out the four prose fields would truncate the JSON, fail the schema, and cost the
scene its summary. §6.3 reports whether any summary job failed or retried.

---

## 3. S5′ (Task 2)

Pre-registered in [`plan/serial-pilot-2.md`](../../plan/serial-pilot-2.md) §4.1 before the run and
before any paid call; the full record is §6.3 and is not repeated here. The three numbers this
note needs:

| | run A | run B | **run C, with the ledger shown** |
|---|--:|--:|--:|
| promises opened | 41 | 47 | 40 |
| **paid** | **0** | **0** | **8** |
| `promises_paid` strings returned | — | — | 8 |
| of those, naming an open row on the list shown | — | — | **8** |
| of those, naming nothing | — | — | **0** |

**Eight of eight.** On `serial.db`, with no list, two of two missed and neither string had ever
been a key. The prediction §1.2's one-in-forty-one rate implies — that a call with no memory
cannot reproduce a hash input — held, and so did its converse.

The run cost **$5.60** against run A's $5.67 and run B's $5.89, took 65 ticks and 46 jobs, and
**no job ran a second attempt**: the 512-token answer budget held with up to 32 rows in the
prompt, which was §2.3's named risk and did not happen. The gate exits 0.

**Two facts from the run that this note is the right place for.** Payoff windows: **0 of 40 rows**,
so `describe_owed`'s `pay within` clause — §2.1's named tension — appeared in no prompt in this
run either. And five of the eight payments land in scene 8, which is the terminal-dump cadence
`promises.schedule_fault` exists to refuse in a *schedule*; nothing scheduled anything here, so it
is an observation about one run and not a finding.

---

## 4. W4's arms (Task 3)

```bash
uv run python research/quality-measurement/payoff_landing.py --selftest
```

`selftest: passed`.

### 4.1 An instrument defect found before any arm could be counted

The plain `--dry-run` cannot open its default `--book-db` (`corpora/toll.db` is not on this
machine). Pointed at `serial.db`, it reported **every arm at zero** — and that was not the
ledger's doing.

`read_scenes` minted keys at `width = max(len(str(len(units))), 2)` while `beats_for` pads to
`len(str(len(scenes)))` with no minimum. On an eight-scene book the ledger holds `s1…s8` and the
instrument built `s01…s08`, so every `in scenes` test failed and the census reported four empty
arms as if the ledger had supplied nothing. `toll.db` is ten scenes, where both rules agree on 2,
which is why nothing had noticed. Fixed in `read_scenes` to `beats_for`'s rule exactly; nothing
changes for any book of ten scenes or more.

| `serial.db` (40 promises, 0 paid, 8 scenes) | pairs before | pairs after |
|---|--:|--:|
| `paid` | 0 | **0 — NOT RUN: the ledger records no paid promise** |
| `mismatched` | 0 | **0 — NOT RUN: the ledger records no paid promise** |
| `unpaid` | 0 | 35 |
| `placebo` | 0 | 10 |
| `constructed_positive` (DIAGNOSTIC) | 0 | 40 |

### 4.2 What the new ledger can build

`serial2c.db`, 40 promises, **8 paid**, 8 scenes. This is the first ledger in the repository from
which the middle arm — the one the module's docstring calls "the whole study" — can be built at
all.

| arm | pairs | note |
|---|--:|---|
| `paid` | **8** | opened scene + the scene the ledger credits with the payoff |
| `mismatched` | **8** | opened scene + the scene that paid a *different* promise. **The bar** |
| `unpaid` | 27 | the false-positive half, available before |
| `placebo` | 8 | the opened scene against itself |
| `constructed_positive` (DIAGNOSTIC) | 32 | floor test of the matcher, in no bar |

`census.unrunnable` is **`[]`** for the first time; it was `["paid", "mismatched"]` on every book
before this.

### 4.3 The verdict is unchanged and is not about the ledger

`SCORER_UNUSABLE`, on the pre-existing grounds the module already records: `check_open_threads`
was built to ask whether a summary of the same prose mentions a recorded thread, and W4 asks it
whether a one-sentence paraphrase names the same debt. **W4 needs a different scorer before it can
be run at all**, and that is true whether or not the ledger settles anything. The match rates a
`--dry-run` prints are cache replays of a run built against a different book and are not readable;
only the pair counts above are.

The verdict stays **NOT VALIDATED** regardless: the owner-read set is out of scope here, and the
model legs touch the 4090 and carry the duty-cycle and temperature governor, so running them is an
operator call.

---

## 5. What a ledger policy would need (Task 4 — design note, no code)

`plan/world-architect.md` §5.1 recommends a **ledger policy before any world retriever**, and the
reason this had to come first is now measurable: a policy over a ledger where nothing ever settles
is a rule for pruning debts nobody pays.

### 5.1 What "still worth carrying at scene N" would have to decide

From the two traces in §1.4, the packet's THREADS section is the only section that grows
monotonically. The world is flat (229–231 facts on pilot 2, 14–21 on pilot 1); hidden claims shrink
by design as they are disclosed; prose is capped by the packer; summaries are capped at
`SUMMARY_SHARE`. Threads have no ceiling at all, and every open promise is one line in them
forever.

So a policy has exactly one question to answer per row per scene: **is this debt still the kind of
thing the writer of *this* scene needs in view?** Three inputs exist today and no others:
`due_key` (how far off payment is), `opened_at_key` (how long it has been owed), and `kind`. A
window (`window_start_key`/`window_end_key`) exists when an outline call has proposed one, and is
PROPOSED-grade.

### 5.2 What it must not do

- **It must not drop a debt because it is old.** That is the §12 defect the packer already has —
  it drops the *oldest* prose rather than the least relevant — and §108.3 is the first recorded
  case of that biting a deliberate change, where a locked constraint arrived by displacing a scene
  summary. A ledger policy that repeated the rule would silently evict exactly the arc debts a
  serial exists to pay: `m_first_water` is due at scene 41 of a book whose first eight are written.
- **It must not rank debts, and it must not ask a model which matter.** `PROMISE_KINDS` carries no
  valence by construction, and which kinds of debt a reader minds going unpaid is a measurement
  nobody has made.
- **It must not become a gate.** Everything on this ledger is model-sourced or forge-seeded;
  `promise.overdue.v0` stays MINOR and `heuristic`, and nothing built on the ledger may block,
  park, rank or select.
- **It must not silently truncate.** Whatever it drops belongs on the record — the packet already
  has the shape for it (`Omission`, with a reason), and `context.assemble` already emits
  `"budget: promise"` when a row will not fit.

### 5.3 Do settled debts alone relieve the packet?

**No — and now this is measured rather than argued.** Run C settled eight debts and its packet
still carried **32 threads at scene 8**, against run B's 41 with nothing settled:

| | run B | run C |
|---|--:|--:|
| threads in the scene-8 packet | 41 | **32** |
| promises opened over the book | 47 | 40 |
| promises paid | 0 | 8 |

Nine fewer lines, and **the eight payments are not the whole of that difference**: the summariser
also opened 40 rather than 47, which is model variance the two runs cannot separate. Settlement
relieved the packet by at most eight lines out of forty.

The ledger's growth is dominated by *opening*, not by *failing to pay*: **34 of run C's 40 rows
were opened by the summariser itself**, at 3–5 new debts per scene, and settlement subtracts from
a number that addition drives. At that rate a 100-scene serial carries ~400 lines of THREADS with
a perfect payer at the wheel. **So the policy is still needed**, and what run C changes is only
that a policy would finally have a `paid` population to be calibrated against rather than a column
of zeros.

The number to watch is not `paid` but **`opened` per scene**. Nothing in this handoff touches it,
and it is the other half of the same problem.

### 5.4 Where a writer-side "due now" cue would sit, if the operator ever wanted one

`domain/context.py`'s promise loop, at the point `describe_owed(promise)` is called: it already has
the row and the packet already knows the beat. `overdue_promises(open_rows, beat.story_order_key)`
is the arithmetic and it exists. **It is not mine to add** — it is an instruction to the writer
about what to do in this scene, which is a different class of change from showing a summariser what
the book owes, and it belongs to whoever owns the drafting prompt. Recorded here so that the fact
that it is one line is not mistaken for the fact that it is a small decision.

### 5.5 The migration a persisted policy would need

Nothing so far requires one: a policy that decides per packet is pure arithmetic over rows the
store already has, and `context_omitted` already records what a packet dropped.

Two columns would be needed the moment the policy becomes *stateful* or *auditable per row*:

- **`promises.source`** (or `authored_by`) — the authored-versus-model distinction. Today it is
  inferred from `model = ''`, which is a sentinel doing a column's job, and §107.8 already names
  it as a stated limit. A policy that treated a forge-seeded arc debt differently from a
  summariser's hook would be reading a sentinel. **Named, not built** — the handoff makes this a
  scope decision and it has not been taken.
- **`promises.carried_until_key` / a `promise_omissions` table** — if "dropped from the packet at
  scene N" must be answerable later rather than only reconstructable from each frozen payload's
  `context_omitted`. Probably unnecessary: the payloads are already frozen and already carry it.

Neither is built here, and neither should be built before a run reports what settlement actually
does to the open count.

---

## 6. What is deliberately not claimed

- Whether any payoff is good, or whether a scene that names a debt actually settles it on the
  page. That is W4's report-channel question, and W4's scorer does not yet work. **This matters
  more after run C than before it**: the one seeded debt the ledger marks paid,
  `m_the_wrong_table`, is an arc debt scheduled for scene 63 whose answer stayed hidden for the
  whole run, so the book was never told what settles it. The ledger's word for that is `paid` and
  the ledger cannot check itself — which is the self-grading defect `payoff_landing.py` opens on.
- Whether the prose is any good. No reader has seen it, no sim has run on it, and no counter here
  is entitled to an opinion.
- Any comparison of prose between runs.
- Any bar. S5′ is a question with named outcomes; the counts in §6.3 are counts — and the
  outcomes as written did not cover what happened, which is recorded in §6.3 as a defect in the
  pre-registration rather than reinterpreted after the fact.
