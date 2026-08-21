# Serial Pilot 1 — the preflight

**Status: TECHNICAL REQUIREMENTS, 2026-08-21.** Everything `plan/serial-pilot-1.md` needs in
order to run, checked against the code rather than against the plan. Nothing was drafted. The
whole command sequence was rehearsed end to end on the deterministic fake in a scratch store,
which is where the numbers and the one serious failure mode below come from.

**Revised 2026-08-21, after the reseed.** This document records the *first* preflight, run
against the package as originally written. All six mechanical corrections below still stand and
are now applied in the package itself (`plan/serial-pilot-1.md` §8). What changed after it: the
seed and five of eight directives were rewritten out of the stat idiom, and `domain/extraction.py`
grew per-book sheets to make that possible. The rows marked **(reseeded)** were re-verified
against the new seed; everything else was left as measured.

**Verdict: go, after six corrections.** One of them stops the run dead on its first tick; one
of them can hand the operator a complete-looking book that the acceptance read would be wasted
on. The rest are arithmetic.

---

## 1. What is verified, and how

| claim | verdict | how |
|---|---|---|
| Seed parses, no story position, `ACCEPTED_CANON` (§2) **(reseeded)** | ✅ | 15 records — 4 ability nodes, 7 edges, 3 world rules, a declared `Loop \| Day` sheet and its snapshot |
| Lowercase `silas` is load-bearing (§2) | ✅ | `extract_state` builds `subjects` from canon records verbatim and skips any name not in it; `normalise_subject("Silas") == "silas"` |
| A `[STATUS]` line on the page reads back into canon **(reseeded)** | ✅ **proved end to end** | `extract_state` run with this exact seed against `[STATUS] Silas — Loop 2 \| Day 1` → 1 record, subject `silas` |
| C2 matches the line the parser accepts (§4.1) **(reseeded)** | ✅ | character for character, U+2014 included — now against the book's **declared** sheet rather than the module default |
| The four directive kinds exist | ✅ | `constraint`, `tone_note`, `arc_note`, `chapter_note` are all in `DirectiveKind` |
| `--scenes 8` is a legal book | ✅ | `arc_template(8)` → `template.arc-8.v0`, `chronological=True` (needed, see §5) |
| Unscoped directives need no `--book`/`--branch` (§3) | ✅ | `_resolved_directive_scope` resolves when **exactly one** branch matches — so the store must hold exactly one book (enforced by the setup script) |
| The five tick flags are global options | ✅ | all five sit on the root parser, and `run-loop.ps1` places `@TickArgs` *before* `tick` — correct position |
| `--context-budget 16000` is enough | ✅ | 14,500 usable after the 1,500-token output reserve; premise (126) + four constraints (225) + seven prior 900-word scenes (~7,000) ≈ 7,351, leaving ~7,100 headroom. The 6,000 default binds at ~4 prior scenes, matching `planner.py`'s own measurement |
| `context_omitted` shows up in `status` (§3) | ✅ | bumped into the daily digest, and `status` prints `digest today` |
| `--chapter-scenes 4` gives two pastable chapters | ✅ | rehearsal produced `01-scene-1-1-4.{txt,html}` and `05-scene-5-5-8.{txt,html}` |
| The provider is the unflagged default and the env gates are as described (§3) | ✅ | `build_default_registry()`; `LITHARNESS_ENV`/`LITHARNESS_FAKE_PAD_CHARS` unset in user and machine scope |
| `claude` CLI present and its flag surface intact | ✅ | 2.1.236 on PATH; all eight flags the adapter passes still exist (the adapter's comment cites 2.1.227) |
| An unhealthy provider parks/requeues rather than degrading (§3) | ✅ | `ProviderUnavailable` → attempt refunded and requeued; auth/invalid-request/context-overflow → parked, revivable |
| `serial.db` and the library stay out of git | ✅ | `.gitignore` covers `*.db` and `book-library/` |
| The harness is green | ✅ | 1,148 passed, 5 skipped, 0 failed |

---

## 2. The six corrections

### 2.1 The loop command as written fails on its first tick — **blocking**

`run-loop.ps1` declares `[string[]] $TickArgs` and splats it. A single quoted string binds as a
**one-element array**, so the splat produces one argv token containing spaces:

```
uv run litharness --database serial.db "--target-words 900 --context-budget 16000 …" tick
```

Run verbatim, it produced `usage: litharness …` and exit 1 — and the loop would have repeated
that 40 times. The script's own `.EXAMPLE` uses the array form. Corrected:

```powershell
tools\run-loop.ps1 -Database serial.db -Ticks 48 -DelaySeconds 2 `
  -TickArgs '--target-words','900','--context-budget','16000','--chapter-scenes','4','--max-cost-usd-per-day','10','--max-invocations-per-day','80'
```

### 2.2 There are eight directives, not seven

§3 says "the seven directives in §4". §4 issues four constraints, one tone note, one arc note
and two chapter notes. Eight commands, eight rows, eight jobs.

### 2.3 §7 counts four things that are not what happens

§7 prices "the outline call, six interpretive-directive passes, and evaluations". Measured
against the code: **four** interpretive directives (each one model-backed job), **four**
constraints (deterministic lane, no model call), one outline call, and — absent from §7
entirely — **eight scene-summary calls**, one per accepted scene. Evaluations cost nothing:
with no `--continuity-evaluator-command`, `EVALUATE_REVISION` runs `InProcessEvaluator` and
never touches a provider.

The summaries are not optional and not cosmetic: **the promise ledger is written by the
scene-summary handler and nowhere else.** If those eight calls fail, §5 has nothing to read
back.

### 2.4 The tick floor is 33, not 25–35

One job per tick, and the clean path is:

| ticks | job kind | model call? |
|---:|---|---|
| 4 | `directive_plan` (the constraints) | no |
| 4 | `narrative_plan` (tone, arc, two chapter notes) | yes |
| 1 | `book_outline` | yes |
| 8 | `scene_draft` | yes |
| 8 | `evaluate_revision` | no |
| 8 | `scene_summary` | yes |
| **33** | | **21 model calls** |

`-Ticks 40` leaves six spare, and one retry ladder costs two (three attempts, then the unit
stops). Idle ticks are free — a `no_work` tick makes no provider call — so over-provisioning
costs nothing. Use 48.

### 2.5 The cost model is missing its largest line

`ClaudeCodeProvider.health()` is a **real billed round trip**, measured at **$0.3386**
(PLAN.md §15). The positive verdict is cached for the life of the process — and `run-loop.ps1`
starts a fresh process per tick, so the cache never helps. Every tick that makes a model call
pays one probe first: **21 probes ≈ $7.11**, against §7's $1.70 of drafting payload.

It passes neither `budget_check` nor any recorded decision, so **`--max-cost-usd-per-day 10`
cannot see it** and will not park anything on account of it. The ceiling is still worth
setting; it just governs about a third of the spend. Honest estimate for the whole run:
**$9–13 of quota-equivalent**, of which the ceiling sees perhaps $2–6.

Two related notes. §7's $0.2097/scene came from six-scene books at the 6,000-token default; at
16,000 the packets are larger and the per-scene figure will run higher. And spend is recorded
**per store** — a parallel session ticking `bz3.db` burns the same subscription where this
ceiling cannot see it.

### 2.6 `verify` prints a line

§3 makes "must print nothing and exit 0" a criterion. It prints `N revision(s) rebuild
cleanly` on success. Exit 0 is the criterion; the text is not.

---

## 3. The failure mode the rehearsal found — read this one

In the rehearsal, **every interpretive directive and the outline job poisoned, and the book
drafted all eight scenes anyway.** The loop printed nothing alarming. The library published a
complete-looking two-chapter book of 8,600 words. `verify` passed.

That is §4.1 working exactly as specified — "a blocked or parked item never stalls the queue" —
and it is the worst possible state to read in. The tone note, the arc note and both chapter
notes had reached no plan revision: the operator's taste never touched the prose. §6 spends
this candidate's one consultation either way (cadence cap), so the bit would be spent on a
book that was never given the direction it was supposed to be judged against.

The failures themselves were a fake-provider artifact — the fake synthesises minimal
schema objects, so its plan proposals carry zero edits. **The silence is not an artifact.**

Two things close it.

**Run the loop in two phases.** Land the direction first, check it, then write prose:

```powershell
# phase 1 — direction only, ~9 ticks
tools\run-loop.ps1 -Database serial.db -Ticks 12 -DelaySeconds 2 `
  -TickArgs '--target-words','900','--context-budget','16000','--chapter-scenes','4','--max-cost-usd-per-day','10','--max-invocations-per-day','80'
uv run python tools/serial_pilot_check.py --database serial.db --phase directives
```

If the direction lands cleanly the last two or three ticks will start scene 1, which is
harmless. If a directive stops, it is cheap to fix here and expensive to find afterwards:
re-issuing it mints a new id (`received_at` is in the material) and therefore a new job.

**Then the gate, before reading a word.** `tools/serial_pilot_check.py` answers one question —
*is this book fit to spend the acceptance read on* — and exits non-zero when it is not. It
checks: one branch only; eight directives, none still unread, none conflicted; nothing parked
or poisoned; the outline covering all eight scenes; eight of eight drafted; **at least one
state record read off the book's own prose** (zero means C2 did not take); `context_omitted`
zero; every revision rebuilding and attributed. It reports the promise ledger and the spend
without gating on either.

Run against the rehearsal store it printed `DO NOT READ IT YET` and named all four unread
directives, the poisoned outline, the zero outline coverage and the zero state read-back.

---

## 4. Things to know, not to fix

- **`revive` refuses a poisoned unit.** §7's "revive is the verb" is true for a provider
  outage or a blocked call, which park. A unit that exhausts its three attempts on a gate
  failure **poisons**, and poisoned is terminal — the job id is spent. The recovery is to
  re-issue the directive, not to revive.
- **The promise ledger's grain is one row per `(book, subject)`**, deliberately
  (`promise_id_for` ignores the description). §5's P1 and P4 are both plausibly subject
  `silas` and would collapse into one row. Worth pre-registering as expected divergence
  rather than discovering it in the read-back.
- **A scene over ~1,300 words is refused as a runaway** — `DraftPolicy.max_chars` is 8,000 —
  and retried. At a 900-word target there is room for a third of overshoot.
- **`--target-words 900` is already the default.** Harmless, and still worth passing: it is
  recorded in the policy digest of every decision.
- **Chapters here are ~3,600 words** (4 × 900), against the ~1,500-word chapter format
  recorded for the publication route. Fine for a reading copy; a decision if these ever become
  the publication unit.
- **Chapter files are named off scene nodes**, not chapter titles: `01-scene-1-1-4.txt`,
  `05-scene-5-5-8.txt`.
- **`NOTES.md` in the library invites exactly the located defects §6 forbids in band.**
  Nothing reads it back — it is written once and never re-read by any code path — so notes
  there are out of band, and compatible with §97.1. Worth knowing before the file asks.

---

## 5. What is staged, and what is not

Prepared and rehearsed (all re-run after the reseed):

- `plan/serial-pilot-directives.json` — the premise and all eight directives, **extracted
  programmatically from §1 and §4** rather than retyped, with the source document's sha256.
- `tools/serial-pilot-setup.ps1` — preconditions, `init`, `new`, `state`, all eight
  directives, postconditions. Makes no provider call. Refuses on: an existing database,
  `LITHARNESS_ENV=test`, `LITHARNESS_FAKE_PAD_CHARS` set, a missing `claude`, a spec that is
  not eight directives.
- `tools/serial_pilot_check.py` — the gate above, now also checking that the book's declared
  sheet matches the keys its snapshots actually hold. That mismatch has no symptom: extraction
  would read the book with a line its own canon does not use, match nothing, and leave a book
  that established plenty looking exactly like one that established nothing.
- **Two code changes**, both green on the full suite, ruff and mypy: per-book status sheets
  (`domain/extraction.py` — template and parser derived from one declared field list, with the
  old `Level | HP | MP | Gold` line as the default so both golden fixtures are untouched by
  construction), and configuration predicates excluded from the context packet
  (`domain/context.py`) after the first reseeded rehearsal handed a scene
  `silas status_sheet fields=[{'label': 'Loop'…}]` as an established fact about the world.

Rehearsed on a scratch store: the full setup, all eight directive texts stored **byte-identical
to the plan** (U+2014 intact through PowerShell — verified, since a mangled dash would silently
break every `[STATUS]` line), 56 ticks to quiescence, the library, `verify`, and both gates.

**Not done, deliberately: `serial.db` does not exist.** The book has not been created, no
directive has been recorded against it, and nothing has been drafted. One command starts it:

```powershell
.\tools\serial-pilot-setup.ps1
```

Before that, §6 step 1 stands: **write the grab criterion first.** It is the one input here
that no amount of preflight can supply, and the package makes it a precondition of the read
rather than a note to write afterwards.

---

## 8. The run, as it happened

**2026-08-21. Eight scenes, 8,385 words, gate green, exit 0.** Recorded here because a preflight
that never says what the flight did is half a document.

### What the run cost to get right

Four harness defects, all found by running rather than by reading, all fixed and pushed before
the book finished. Three were on the directive-to-draft path and none had a symptom an operator
surface would show.

1. **An outline refused for answering an unasked question.** `_payoff_windows` validated a
   payoff schedule the prompt only requests when the promise ledger has open rows — and the
   ledger is empty at every book's *first* outline. Two of three attempts burned on a good
   outline.
2. **A directive's scene plan was unreachable by construction.** New plan items were built with
   `scope=None` and the schema offered no way to set one, so eight correct scene plans from the
   chapter notes reached no scene. The drafts fell through to an outline written from the
   premise alone — a different cast, a different ending, a milestone schedule reaching Loop 23
   in a two-loop book. Caught because the gate printed statements that named a character the
   directives never mentioned.
3. **The prompt was a command-line argument.** Windows caps a command line at 32,767 characters;
   scene 6's packet was 35,714. `OSError` classifies as retryable, so the loop refunded and
   requeued 61 times while `status` reported nothing needing attention. Five scenes had drafted
   cleanly first, which is what made a wall look like an outage.
4. **A book could not declare its own numbers.** Not a defect so much as a missing seam, and the
   reason the pilot could be reseeded at all.

The first store is kept as `serial-run1-outline-divergence.db` in the session scratchpad; it is
the only artifact showing what the outline planned when it could not see the direction.

### What the run measured

- **The loop mechanic reached the page and came back.** Eight `[STATUS]` lines written in the
  book's own declared `Loop | Day` sheet, all eight read back into canon by `extract_state`, and
  the reset landing at scene 4 exactly where chapter note 1 puts it: `s1 s2` Loop 1 Day 1, `s3`
  Loop 1 Day 2, **`s4` Loop 2 Day 1**, then Loop 2 through Day 2. C1 and C2 both took.
- **The promise ledger replicated this project's oldest measured defect, on a fresh book.**
  **40 promises opened, 0 paid.** The prior record was 32 opened and none paid across ten
  scenes; this is 40 across eight. §5 pre-registered that P2 pays at s6 and P3 at s5, and the
  ledger recorded neither — divergence between intent and record, which §5 called pilot data
  rather than failure, and which is now data on a book whose directives were followed.
- **Nothing was parked, poisoned, or left unattributed.** 38 jobs succeeded, 9 revisions rebuild
  cleanly, `context_omitted` zero at a 16,000-token budget across all eight scenes.
- **Cost: roughly $11 across both runs** — $4.23 recorded on the finished book, about $3 on the
  abandoned one, ~$2.9 of health probes no ceiling can see, and ~$0.7 of direct diagnostic
  calls. The probe is **$0.12 warm**, not the $0.3386 cold figure §15 records, so §7's estimate
  was conservative on its largest line.

### What the operator surfaces still cannot say

The reason defect 3 hid for 61 ticks: a genuine provider outage and a permanently unexecutable
unit are the same `TransientFailure` and the same `provider_unavailable` counter, so "wait, the
provider is down" and "retry this forever, it can never work" are indistinguishable everywhere an
operator looks. And `run-loop.ps1` exits on the *last* tick's status, so a run that rode out an
outage and left the book healthy still exits 1 — the gate is the signal, the exit code is not.
