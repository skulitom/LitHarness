# Serial Pilot 5 — the same two chapters, on a world whose protagonist's rung can rise

**Status: FORGED, 2026-08-22. §3 NOT RUN; nothing picked.** Companion to
[`plan/serial-pilot-2.md`](serial-pilot-2.md) and [`plan/serial-pilot-4.md`](serial-pilot-4.md);
the design record is [`plan/world-architect.md`](world-architect.md), the build record is
stage-0 §113, and the handoff is [`plan/handoff-numbers-go-up.md`](handoff-numbers-go-up.md).
**§4 was written before any paid call**; §5 records the forge; §6 is empty until §3 runs.

## 0. What this pilot is for, and the one thing it may not be read as

**One difference from Serial Pilot 4, and everything else held.** Same brief
(`"progression fantasy"`), same shape (`--shape direct`), same K (3), same scene count (8), same
chapter shape, same target words, same context budget, same provider, same craft constraints —
`plan/serial-pilot-5-craft.json` carries pilot 4's `directives` array byte-for-byte and adds only
a **proposed** entry nothing issues. The difference is the rule set the forge is written under:

- at least one criterion has the comparator `ordinal` and a chain of at least three ranks,
  listed lowest first, each with a `visible_form` and a `cost_to_reach`;
- the protagonist declares a `standing` on that chain, at a rung that is not the top;
- the inversion rule may remove any genre default **except** that one;
- a world that declares a ladder declares a `graph_line` carrying a `stands_at` phrase;
- the outline is asked for `standing_milestones` and refuses an outline whose schedule does not
  rise;
- the writer is handed the next rung and one filled example of the line the book prints;
- a printed rung on a declared chain is read back as canon at that position.

**It cannot support a quality claim and no reading of it may make one.** Two chapters is not a
sample; §61's bar is a blinded position-swapped win rate against matched published prose and this
is not that. Every question in §4 is structural: does the forge declare it, does the schedule
rise, does the number move on the page, whose number is it, and is the price anywhere near it.
Pilot 2's §0 said this about itself and pilot 4 repeated it; it is repeated again rather than
referenced, because a package that assumes its reader has read the previous package is how a bar
gets quietly relaxed.

**What this pilot is NOT.** No model is asked whether a ladder is good, which rung is right,
which of K worlds to pick, or whether a rise "lands". The forge stops and a person chooses
(`plan/world-architect.md` §2; `forge --pick` is `VerdictSource.HUMAN`). Nothing here declares a
bar on how often a standing should move — that is the operator's to set over the distribution in
[`research/quality-measurement/numbers-go-up-results.md`](../research/quality-measurement/numbers-go-up-results.md).

---

## 1. The world, and how it will be chosen

Recorded before the forge runs, because the choosing is the part that must stay auditable.

```powershell
uv run litharness --database pilot5\forge.db forge "progression fantasy" `
  --k 3 --shape direct --out pilot5\direct1 --scenes 8
```

**The pick rule, written down before the candidates exist:** the first candidate, in the order
the model returned them, that clears every gate **and whose declared `domain` was not forged in
pilots 2, 3 or 4**. The four already used are Western water law / prior appropriation (pilot 2,
*First In Time*), prior-appropriation water law again (pilot 3 candidate 0, *Senior Water*),
horticultural grafting and rootstock science (pilot 3, *What Takes*, picked), and land surveying
and geodesy (pilot 3 candidate 2, *The Closing Error*) — plus whatever pilot 4 forges if it runs
first, in which case its picked domain joins this list and the fact is recorded here.

The domain clause is new and it is arithmetic, not taste: the brief is the same as pilots 3 and 4,
so a fourth water-law world would make "the rule set is the only change" false in the one place
the reader would not check. It orders nothing and prefers nothing among the candidates that clear
it. The operator may re-pick later and that is a different row with its own decision id.

The decision id, the candidate index, the title, the domain and the rule text under which it was
picked go into §5 beside the `report()` output for all three.

---

## 2. Standing it up

```powershell
.\tools\serial-pilot-2-setup.ps1 -Forge pilot5\direct1 -Scenes 8 -Database serial5.db `
  -Craft plan\serial-pilot-5-craft.json
```

It refuses rather than proceeds on every precondition Serial Pilot 1 learned the hard way: an
existing database, `LITHARNESS_ENV=test`, `LITHARNESS_FAKE_PAD_CHARS`, a missing `claude` on PATH,
and a forge directory where `--pick` has not been run. It draws no prose and makes no provider
call.

---

## 3. The two phases

Direction first, gated, before a paid call is spent on prose — unchanged from pilots 1, 2 and 4.
Phase 1's tick budget is ~2× the directive count.

```powershell
.\tools\run-loop.ps1 -Database serial5.db -Ticks 14 -DelaySeconds 2 `
  -TickArgs '--target-words','900','--context-budget','16000','--chapter-scenes','4','--max-cost-usd-per-day','10','--max-invocations-per-day','80'
uv run python tools/serial_pilot_check.py --database serial5.db --phase directives `
  --spec pilot5\direct1\directives.json --spec plan\serial-pilot-5-craft.json
```

Only when the early gate is green:

```powershell
.\tools\run-loop.ps1 -Database serial5.db -Ticks 48 -DelaySeconds 2 `
  -TickArgs '--target-words','900','--context-budget','16000','--chapter-scenes','4','--max-cost-usd-per-day','10','--max-invocations-per-day','80'
uv run python tools/serial_pilot_check.py --database serial5.db `
  --spec pilot5\direct1\directives.json --spec plan\serial-pilot-5-craft.json
```

`--spec` is repeatable and this pilot needs both: the gate sums the counts, and one spec alone
would report the inbox short by the size of the other.

**`--context-budget 16000` is a precondition, not a preference.** Pilot 2 measured a ~329-record
world at a flat ~46% of a 16,000-token packet's usable budget; at the 6,000 default the same world
dropped every prior scene and 92 facts. This world carries the same order of records plus a
standing edge per scene the schedule places.

**Box discipline.** `claude -p` fails under box load and the failure is silent-ish — a failing
call still returns and the run completes with unanswered cells. No other paid arm, pilot loop or
forge on the box; one CLI arm at a time; read `transport_failures` before reading any count.

---

## 4. What is pre-registered, before the loop runs

Numbered so a later reading cannot quietly become a different question. Every one is structural;
none asks whether the prose is good. The measured priors each sits against are in
[`numbers-go-up-results.md`](../research/quality-measurement/numbers-go-up-results.md) §1 and are
restated here only where the outcome names depend on them.

| # | question | how it is answered | outcomes named in advance |
|---|---|---|---|
| **P1** | does the forge declare a ladder and place the protagonist below its top, and does the inversion leave the ladder alone | `report()` per candidate: `ladders`, `rungs_per_ladder`, `opening_rung_index`, `graph_line_declared`, `gate_complaints`; `inversion_text` verbatim, read beside the four inversions of pilots 2 and 3 | **0 of 3 candidates with a ladder, or every candidate inverting the ladder anyway, is a failure of the rule text** and is reported as one rather than repaired in-run. `spread` is read against pilot 2's 0.930 and pilot 3's 0.896: **a collapse onto one ladder shape — spread well below 0.9 — is the stop condition**, and the run does not proceed to §3 |
| **P2** | does the schedule rise | the stored `book_outline` job payload carries `world.ladder`; `standing_milestones` validated by `_standing_milestones`; number of scheduled rises within the 8 scenes; opening and final scheduled `rung_index` | a refused outline is a **validator finding, not a prose finding** — record every refusal and its reason verbatim. The prior is that no outline in this project has ever been asked this question, so a first-attempt refusal rate above zero is information about the rule text rather than about the model |
| **P3** | does the number move on the page | `standing.py`: rises read back from prose (count), the scene and word offset of the first, graph lines per 1k words, DELTA non-null of 8, `zero_delta` count | **0 rises read back while ≥1 was scheduled is the defect this handoff exists for** — report it, do not repair it in-run. The measured prior is 0 rises and 0.0 graph lines per 1k on both existing books, and *What Takes* declared an ASSIZE line and printed none of it across 7,704 words |
| **P4** | is the rise the protagonist's | `stands_at` changes by subject: the protagonist against every other subject, from `standing.py`'s `other_subjects` | **descriptive**. "Faster than anyone else" is a count beside another count and never a bar. The prior is 0 for every subject on both books |
| **P5** | is the price on the page | for each rise read back, does the same scene's summary (`EVENTS` / `DELTA` / `paid`) name a cost — a count over `standing.py`'s `priced_rises` | the existing report channel, no new question, count only. **The word list cannot tell a price paid from a price mentioned** and is reported because it is checkable, not because it is the question |

**No bar is declared and none may be read in.** n is three candidates and eight scenes; §108.5's
"any subgroup of two is empty" applies to every split of it, and a pre-registered null is a result
(§61). No model is asked a question anywhere in P1–P5.

**What P3 cannot see, stated before it runs.** A rise the prose narrated without printing the
declared line is invisible to `standing.py`, by construction — the chain is *declare → ask →
print → read* and the counter reads the last link. If P3 comes back 0 while P2 came back ≥1, the
next question is which link broke, and the answer is in the stored prompts rather than in a
larger n.

**The stop condition, restated because it is the one that costs money.** If the forge under the
new rules collapses K worlds onto one ladder shape (spread well below 0.9 on the same brief), or
if the standing cannot be read back without a model, or if the only way to make the number move
on the page turns out to be an instruction about how to write the scene — **stop and write that
up instead of running §3.** A packet that quietly tells the writer how a rise should feel is a
worse failure than a world whose number still does not move.

---

## 5. What was forged

### 5.1 Forge 1 — P1 answered, and the stop condition does not fire

`dec-25c58304a408437ec81d74a3`, `arch-d425316522615ff9fa369e68`, 2026-08-22T18:28:50Z. One
invocation, `accept`, no fallback (`fell_back_from: []`), **98,521 tokens, $1.4955**, provider
`claude_code`, model `claude-opus-5`, profile `architect.world.v0`. **3 of 3 clear of every gate**
and every validator; nothing was refused and nothing was retried, so there is no transport failure
to read before the counts.

**Within-forge spread 0.9163** — against pilot 2's 0.9302, pilot 3's 0.8959 and pilot 4's 0.9158
on the same brief. **The stop condition does not fire**: the new rule set did not collapse the
forge onto one ladder shape, and §3 would have been reachable on this leg alone.

| | [1] *The Full Mark* | [2] *What Two Eyes Hold* | [3] *Whole Skein* |
|---|---|---|---|
| real domain | assaying and hallmarking — fire assay by cupellation, the touchstone, the sealed trial plate | land surveying and geodesy — triangulation from a measured baseline, orders of control, loop closure | sericulture — five instars and their moults, the mulberry supply, cold storage, stifling, grading by longest filament |
| geometry | chain | graph | cycle |
| records / edges | 355 / 110 | 347 / 104 | 345 / 102 |
| rules at min consequence domains | 6 at 3 | 5 at 3 | 5 at 3 |
| manifestation coverage | 1.00 | 1.00 | 1.00 |
| answered claims / reveals inside these 8 scenes / hidden at start | 34 / 1 / 23 | 34 / 1 / 23 | 34 / 1 / 23 |
| cardinality shapes | 3 | 3 | 3 |
| **`ladders`** | **1** | **1** | **1** |
| **`rungs_per_ladder`** | `fineness_grade: 5` | `order_of_control: 5` | `instar_count: 5` |
| **`opening_rung_index`** | **3** of 5 | **3** of 5 | **3** of 5 |
| **`graph_line_declared`** | **True** (`ASSAY`) | **True** (`REGISTER`) | **True** (`TURN`) |
| `gate_complaints` | **none** | **none** | **none** |
| `validator_complaints` | **none** | **none** | **none** |
| protagonist / exception / premise names them | yes / yes / yes | yes / yes / yes | yes / yes / yes |

**The chains run lowest first, which is the clause the measurement forced.** *The Full Mark*:
`sweep → quarter_mark → half_mark → three_quarter_mark → full_mark`, protagonist `neve_ardrick` at
`half_mark`. *What Two Eyes Hold*: `unfixed → traverse_point → minor_station → principal_station →
baseline_station`, `odile_sarn` at `minor_station`. *Whole Skein*: `first_skin → second_skin →
third_skin → fourth_skin → fifth_skin`, `bel_cassoway` at `third_skin`. Every rung of all fifteen
carries a `visible_form` a reader can see and a `cost_to_reach` payable on the page — the bottom
rung of each costs nothing and says so as the fact it is ("nothing, which is exactly what it is
worth").

**P1's second half: 3 of 3 inversions leave the ladder alone**, verbatim:

| world | what it removed |
|---|---|
| *The Full Mark* | "the private grind. Effort still puts metal in you, but nothing done alone moves your mark — the mark only changes in the Hall, in fire, in front of paid witnesses, and the test burns away the sample it reads." |
| *What Two Eyes Hold* | "the solo climb. Nothing here is earned alone — an order is only ever conferred by other people occupying stations and writing you into their books, and one re-observation takes it back." |
| *Whole Skein* | "choosing when to advance. Nobody here trains up to a rung; the fen warms and the whole town splits inside a fortnight, ready or not, and the only lever is cold." |

Against pilots 2 and 3, where **3 of 3 on this brief removed a rule-1 ingredient** — portable
personal power, that a gain can be created, monotonic growth. Every one of these three keeps the
rung, keeps the rise and keeps it countable, and removes something adjacent instead: *who* moves
it, *whether it is yours alone*, *whether you choose when*.

### 5.2 Two convergences, reported because they are real and not because they are faults

Neither is a gate failure and neither is a verdict. Both are descriptors a later reading should
have rather than rediscover.

1. **All three chose five rungs and put the protagonist on the exact middle one.** The rule asks
   for a chain of *at least three* and a rung that is *not the top*; three of three answered five
   and three-of-five. `opening_rung_index` is a counter and this is what it counted; whether a
   rule that named a floor produced a de-facto default is a question for the next forge on this
   brief, not an amendment to make with three candidates already in view.
2. **The printed phrase is effectively fixed by naming the predicate.** All three rendered the
   `stands_at` edge as the English `"now stands at"`, first in the edge list. That is the cost of
   the graph-line amendment naming the predicate by its constant: the parser needs the predicate,
   and the model reaches for the phrase that reads like it. The worlds' *other* four phrases are
   entirely their own (`took a bead from`, `closed the loop at`, `was held over by`), so the
   variety the graph line had is intact everywhere except on the one edge this handoff added.

### 5.3 The pick is not made here

**The recorded rule** (§1): *the first candidate, in the order the model returned them, that
clears every gate and whose declared `domain` was not forged in pilots 2, 3 or 4.* Checked against
what is on disk rather than from memory — pilot 4 forged three times, so the excluded set is
larger than §1 anticipated:

| forged before | where |
|---|---|
| Western water law and hydrology | pilot 2, picked (*First In Time*) |
| prior-appropriation water law and irrigation hydrology | pilot 3 candidate 1 (*Senior Water*) |
| horticultural grafting and rootstock science | pilot 3, picked (*What Takes*) |
| land surveying and geodesy | pilot 3 candidate 3 (*The Closing Error*); pilot 4 forge 3 candidate 1 (*The Ninth Order*) |
| glassworking, locksmithing, pomology | pilot 4 forge 1 |
| municipal water engineering, historical linguistics | pilot 4 forge 2 |
| water law in an arid basin, immunology — graded inoculation | pilot 4 forge 3; the second was picked (*A Good Take*) |

So **[2] *What Two Eyes Hold* is excluded outright** — land surveying and geodesy, forged twice
before. **[3] *Whole Skein* (sericulture) is untouched by the list.** And **[1] *The Full Mark*
turns on the same one word pilot 4's pick turned on**: assaying and hallmarking has never been
*forged*, so under the rule read literally it qualifies and, being first in returned order, it is
the pick. Under the rule read as *a subject this project has not already written a book in*, it
does not: Serial Pilot 1's operator-typed seed and the only assembled book in this repository —
*Reappraisal* — are set in an assay house, and `tests/test_architect.py`'s fixture world is
"assay and provenance". Pilot 1 was hand-typed rather than forged, which is exactly why the rule
as written does not reach it.

**That is not resolved here and it is not this session's to resolve.** `forge --pick` is
`VerdictSource.HUMAN`, [`plan/world-architect.md`](world-architect.md) §2 says the forge stops and
a person chooses, and pilot 4 §5.4 records the same ambiguity being put to the operator rather
than read away by the session that found it. **Nothing was picked.** The three worlds are on disk
at `pilot5/direct1/forge.json` with the ambiguity named, and the pick is one command that makes no
provider call and records its own decision:

```powershell
uv run litharness --database pilot5\forge.db forge --out pilot5\direct1 --pick <n>
```

### 5.4 What this leg does not answer

P2, P3, P4 and P5 need §3, and §3 has not run. The forge answers P1 and the stop condition and
nothing else. In particular: **that three worlds declared a countable ladder says nothing about
whether a schedule will rise, whether a scene will print the line, or whether anyone will read a
rung back off prose.** Those are the three links this handoff built and the three that have never
been exercised.

---

## 6. What the run produced

*Empty until the run happens.* In §6.2's form: ticks / jobs / decisions / invocations / tokens /
cost / scenes / words / parked / findings / gate; the per-scene packet table (facts / hidden /
threads / prose / summaries / prompt tokens); and P1–P5 as counts.

Expected cost, for the budget guard rather than as a claim: ~$1.50 for the forge and ~$5 for the
two phases.
