# Gate ledger — every mechanical check on the shelf has refused fourteen attempts in its whole history, eleven of them in two stores, and one gate owns a quarter of its own book's bill

Commissioned by read 13 (`plan/serial-pilot-18.md` §6) as one input to the attribution report.
This file answers one question and no other: **for each gate and mechanical check, what does the
stored record say it refused, whether the refusal was correct on that record, and what the refused
attempts cost.** Operator-facing diagnostics, §95's sanctioned channel. No metric is minted, no bar
is declared, nothing here ranks a gate against another, and there are no recommendations — the
coordinator synthesises.

## 0. Method, and what may not be read into these numbers

**Sources.** The twenty-six stores at `runs/pilots/databases/*.db`, plus the pilot records
`plan/serial-pilot-13.md`, `-16.md`, `-17.md`, `-18.md` and stage-0 §178, §180, §183, §184, §185.

**Every store was copied to a scratchpad before any read**, §184.1's own precedent, because
`SqliteStore.open` creates and migrates the file it opens (`cli.py:477`, `cli.py:2935`) and a report
must not write a production store. **No database under `runs/` was opened by this work**; the
listing bundles at `runs/pilots/*/listing.json` were read as files, and the stores' modification
times are unchanged.

**Verbs first, and the two places a verb could not answer.** `status`, `events`, `why`, `jobs`,
`exceptions`, `plans`, `findings` and `world check` supplied everything below except two things,
both read from the scratchpad copies' `policy_decisions` table directly and named here rather than
left implicit:

1. **Per-decision `cost_usd` on a job whose scene the head did not come from.** `why --scene N`
   reaches only the job that produced the accepted revision, so the six rows on serial18c's poisoned
   job `beat-775aee133999053d8dba6440` — which is exactly §184's three-refusal sequence — are
   unreachable through any verb.
2. **A cross-store census of outcomes and gate verdicts.** No verb lists decisions; `events` carries
   the gate ids and the outcome but no spend, and `status` carries a day's spend but no breakdown.

**One documented verb does not exist.** The `debug-book` skill's Workflow-1 section names
`litharness blame --book … --branch … --axis em_dash` as the whole-book view of a measurable trait;
`litharness` has no `blame` subcommand. So the "how many em dashes were in the pre-§180 books the
strip would have taken out" counterfactual has no instrument behind it and is **not reported** here.

**A double-counting trap, named because the shelf-wide rows walk into it.** `serial13` and
`serial13b` share **36** decision rows by identical `decision_id` (39 rows in one, 41 in the other),
including all nine recruiter refusals. Shelf-wide figures below are de-duplicated by `decision_id`
and say so; per-store figures are not.

**What these numbers are not.** A refusal count is not a quality measurement, a cost is not a
verdict, and "correct on the record" below means *the stored detail supports the reason the gate
gave* — never that the book is better for it. §61's four attainability checks have nothing to run
on: nothing here is a threshold anything must clear.

**Shelf baseline, for scale.** 226 distinct policy decisions across the twenty-six stores,
**$194.9299** total, of which **23 rows are refusals costing $7.3260** — 3.8% of the shelf's spend.
Nine of the twenty-three are the operator's own recruiter refusals at zero cost, so **fourteen
mechanical refusals carry the whole $7.3260.**

---

## 1. §184's progression gate (`integrity.progression.v0`) — three refusals, one poisoned job, one replan

Shipped 2026-08-30 15:52 BST (`482ee0d`), merged 15:56 (`c1d2112`). Blocking,
`VerdictSource.DETERMINISTIC`, veto `PROGRESSION_UNMOVED`, class `RETRYABLE`. One store has ever run
it against a live writer: **serial18c**.

| store | decision id | job | attempt | outcome | gate detail, verbatim | cost |
| --- | --- | --- | --- | --- | --- | --- |
| serial18c | `dec-ccca11d00b85e81faacc3dcf` | `beat-775aee133999053d8dba6440` | 1 | `retry` | *"Rating was named as moving here; rating reads 2 at s1 before and after"* | $0.378116 |
| serial18c | `dec-55f02ba2f22a5ef67de7f2ec` | same | 2 | `retry` | *"Rating was named as moving here; rating reads 2 at s1 before and after"* | $0.342591 |
| serial18c | `dec-6bef0d67da8f0d7b83b5a475` | same | 3 | `park` | *"Rating was named as moving here; this scene wrote down no state for ines at s1, and rating stands at 2"* | $0.401732 |
| serial18c | `dec-aee826c50b424bc8e5824721` | `beat-2fa7437d1e03794d0ae13e65` | 1 | `accept` | *"Rating moved: rating 2 to 3 at s1"* | $0.370787 |

**Catches: 3 refusals, all on one scene, all on one named quantity.** Every one of the three
attempts passed `shape.draft.v0` (954, 981 and 938 words against a 900 target),
`integrity.standing.v0` and `integrity.findings.v0` (*"4 detector(s) ran, nothing found"*) and
failed only this gate. Without it all three would have been accepted.

**The poisoned job and the replan.** The third refusal exhausted the attempt budget
(`ExceptionRaised`, seq 12, *"attempt budget spent after 3 attempts: attempt budget exhausted with
progression_unmoved outstanding"*), the job poisoned, and `plan/serial-pilot-18.md` §5 records
`resolve` + `replan` — **`replan`'s first production use** — reissuing the beat as `PlanChanged`
seq 13, `plan_epoch: 1`, reason *"reissue under §186's moved-line render"*. The reissued job accepted
on attempt 1. `status` on the store still shows `{'poisoned': 1, …}` and `exceptions 0 open`.

**Correct on the record?** The refusal detail and the accepting detail read the same two integers out
of the same stored records, and they disagree in the way the gate says: the refused drafts left
`rating` at 2 at `s1`, the accepted one moved it 2 → 3. `plan/serial-pilot-18.md` §5 records the
prose consequence independently (*"the rung-up prints on the page (hand → mate, Rating 3, earned by
a mend that costs her an arm)"*). **No false-positive evidence exists on the record**, and there is a
recorded reason the refusals were not the writer's fault either: §184.3's own diagnosis, quoted in
pilot 18 §5, is that *"the frozen prompt handed the entering line as 'the state as it stands' while
the plan named a move"* — the machinery defect §186 closed. The gate refused something genuinely
unmoved; what it could not say is that the ask itself was mis-rendered.

**The abstention, visible as an absent row.** serial18b's and serial18c's scene 2 decisions
(`dec-a3fd66b57b34bd83bcf8ca71`, `dec-d1a0989e0b183d116370f4d0`) carry **no** `integrity.progression.v0`
gate at all — §184.5's refusal of a row on a scene with no named beat, working as written.

**Cost, exact.** The three refused attempts cost **$1.122440** in writer calls. Each of them also paid
for a §185 reviser call on the draft the ladder then threw away — `dec-833af522e2051a3dc9497854`
$0.305478, `dec-043ec99f490da086134d0a29` $0.505035, `dec-35e044358482cff30bee5fd3` $0.305061 —
**$1.115573**. The three-refusal sequence therefore cost

> **$2.238013**, which is **27.6% of serial18c's whole $8.104494 bill.**

§184's prediction was that this would be cheap ("a refusal costs the book nothing" is §185.3's
sentence about the reviser, not this gate). On its first production run the gate cost more than a
quarter of the book.

---

## 2. §185's revision containment (`revision.containment.v0`) — five calls, five adoptions, no discard

Shipped 16:51 BST (`f9cacac`), merged 16:55 (`af13dcc`). `GateKind.SHAPE`, deterministic,
**non-blocking by construction** (§185.7: `decide` is never called on the reviser's decision, whose
outcome is `ACCEPT` on every path so a `PARK` row can never poison a job that drafted well). One
store has ever run it: **serial18c**.

| decision id | job | attempt | containment | adopted | tokens | cost |
| --- | --- | --- | --- | --- | --- | --- |
| `dec-833af522e2051a3dc9497854` | `beat-775aee…6440` (poisoned) | 1 | PASS | true | 54,271 | $0.305478 |
| `dec-043ec99f490da086134d0a29` | `beat-775aee…6440` (poisoned) | 2 | PASS | true | 62,310 | $0.505035 |
| `dec-35e044358482cff30bee5fd3` | `beat-775aee…6440` (poisoned) | 3 | PASS | true | 54,251 | $0.305061 |
| `dec-805501d7037b7fcc358969fe` | `beat-2fa743…3e65` (scene 1) | 1 | PASS | true | 62,840 | $0.517421 |
| `dec-09c3bd77af45c6451ef38e45` | `beat-fda00f…1b2` (scene 2) | 1 | PASS | true | 60,684 | $0.434826 |

**Adoptions 5, discards 0.** Every `PolicyDecisionRecorded` event for the stage (seq 3, 6, 9, 16, 21)
carries `"stage": "revision"`, `"adopted": true` and a passing `revision.containment.v0`. None of the
five containment predicates — machine lines character-for-character, no introduced name or number,
length ratio in [0.85, 1.20], empty, unchanged — has ever fired in production. The four end-to-end
refusal paths §185.3 asserts are proved only against the fake provider (§185.10).

**Catches: none. Cost: $2.067820 on serial18c**, against **$1.896380** for every writer call in the
same store. **The reviser stage costs 109% of the drafting it revises**, and $1.115573 of it (54%)
went on drafts §184 then refused. §185.7 predicted the shape — *"a stage adding one call per scene
doubles the ceiling that exists for it"* — and this is the first store that puts a number on it.

**False-positive evidence: none available, and none possible from this store.** A false positive here
would be a contained, adopted revision that broke something downstream; every gate that could have
said so passed on the revision, which §185.3 argues is by construction for the status-line gates. The
one gate whose verdict could have moved — `shape.draft.v0` — passed on all four accepted revisions
(1036, 931 words on serial18c; the reviser's own length band held).

**What the stage invalidated, on the record rather than in the abstract.** §185.8's list is now a fact
about two stores: serial18c's two acceptance events carry `revised_by: claude-opus-5`, so every
register count over its accepted prose is a count of the second call's output, and its
`em_dashes_removed: 0` is a fact about the reviser (§185.8 item 2). serial18b's two acceptance events
carry `revised_by: None` — the last chapter on the shelf whose accepted prose is the writer's alone.

---

## 3. §178's schema-name check — five names in two worlds, and nothing since it shipped

Shipped 13:17 BST (`7c95bf4`), merged 13:20 (`dd5078d`). Three call sites: `world check` reports,
`world accept` refuses under `--force`, the listing and title loops redraw.

**§178's own base-rate census is cited, not re-run**: 173 world-facing names across nine pilot
worlds, 9 listings, 9 titles; the check refuses **5 names in 2 worlds** (pilot 16's four, pilot 15c's
`standing`) and **1 listing and 1 title, both pilot 16's**.

**Re-run only where it was cheap** — `world check --json` over all twenty-six scratchpad copies, one
free deterministic verb per store, no model and no spend — to extend the census past the nine §178
read and cover every store drawn since:

| store | `machinery_names` | the names |
| --- | --- | --- |
| serial15c | 1 | *the name of `mender_standing` 'standing'* |
| serial16 | 4 | *the name of `rung` 'Rung'*; *`ladder`'s status line label '[LADDER]'*; *`ladder`'s printed column 'Rung'*; *the name of `ladder` 'Ladder'* |
| serial, serial11, serial12, serial12b, serial13, serial13b, serial14, serial14b, serial15, serial15b, serial15d, serial17, serial17b, serial18, **serial18b**, **serial18c**, serial3, serial4, serial7, serial8, serial9 | 0 | — |
| bz3, reader-book, serial10 | n/a | no book in the store |

**Catches: 5 names, 2 worlds, both drawn before the check existed.** Correct on the record on both
counts — pilot 16's four are the operator's own read-11 item (`plan/serial-pilot-16.md` §7, *"'Ladder'
included in Title perhaps the biggest unecessary leak of internal architechture to date"*), and
serial15c's `standing` is §120's own defect. §178's identity-vs-containment split is what keeps
pilot 15's *"Seams standing in Ashfen"* off this list, and 21 clean worlds are the evidence the
predicate is not simply matching everything.

**Fires since it merged: zero.** All five stores drawn after 13:20 BST — serial17, serial17b,
serial18, serial18b, serial18c — return `machinery_names: []`. `plan/serial-pilot-18.md` §3 records
the same for serial18b independently (*"§178's machinery_names came back empty (the fork is 'the
Turn', the rungs are shipyard tickets)"*).

**Cost: $0.00, and no store holds a record of it.** `world accept`'s machinery branch refuses before
writing a policy decision (`cli.py:4105-4111`), and the listing/title loops redraw inside the
listing stage. So a machinery refusal leaves no row anywhere; the only record is the run's stderr,
which was not captured. **No refusal by this check has ever been paid for on the shelf** because it
has never fired in production.

**False-positive evidence: none, and §178 records the one near-miss it found before shipping** — the
containment form of the name check refused pilot 15's column *"Seams standing in Ashfen"*, and the
identity form was chosen because of it (`test_an_ordinary_name_is_left_alone`).

---

## 4. §183's listing floor and the coordinator-density redraw loop (`writer.overview.v0`)

Two different things at one call, and only one of them is a check.

**§183's house-genre floor is a prompt clause, not a gate.** Merged 14:08 BST (`62d43c3`). §183.5
records the return-side check as explicitly refused: *"There is no code-only predicate for this
promises a system"*. It therefore has **no gate row, no refusal, and no cost in any store**. Its one
production draw is serial18b's listing (`dec-66c5a76cab233f2ced8c2586`), which
`plan/serial-pilot-18.md` §3 records as passing the coordinator's read with *"both halves"* present.
One draw, a description, never a treatment effect.

**The density gate and its redraw loop are the mechanical half.** `writer.overview.v0`,
non-blocking, `passed = not listing_chained`, ceiling 5.89 coordinators/100w. Every listing decision
on the shelf:

| store | decision id | words | coordinators/100w | redraws | invocations | listing spend |
| --- | --- | --- | --- | --- | --- | --- |
| serial7 | `dec-4f7cdbe06be7001b46d3c2ae` | 106 | *(pre-gate)* | — | 12 | $2.700084 |
| serial9 | `dec-8bb8d7f4d0106b269e442c95` | 112 | *(pre-gate)* | — | 12 | $2.575551 |
| serial10 | `dec-e4cf16be545bb7b36dc67523` | 113 | *(pre-gate)* | — | 12 | $2.776051 |
| serial11 | `dec-587e11d7913b3c7d7a71a406` | 108 | *(pre-gate)* | — | 11 | $2.601151 |
| serial12 | `dec-a35952839d93c6b7effb5dd1` | 103 | 2.91 | 0 | 11 | $2.616096 |
| serial13 | `dec-b41aede21cd3daab60d0e602` | 99 | 5.05 | 0 | 11 | $2.204142 |
| serial14 | `dec-50867e943a476caa12971105` | 113 | 3.54 | 0 | 11 | $2.613534 |
| serial15 | `dec-034b914670063e44c12df27b` | 110 | 4.55 | 0 | 11 | $2.554521 |
| serial16 | `dec-dfcf9bfecc644e9a5428cad3` | 119 | 5.04 | 0 | 11 | $2.637525 |
| **serial17** | `dec-d49629cbb814b1c8a3732785` | 104 | 4.81 | **1** | **12** | $3.116743 |
| serial17b | `dec-9f041806758c7fc3f40afb85` | 103 | 4.85 | 0 | 11 | $2.454164 |
| serial18 | `dec-6d04cb7a907ca5b2a11d0739` | 118 | 2.54 | 0 | 11 | $2.414161 |
| **serial18b** | `dec-66c5a76cab233f2ced8c2586` | 102 | 3.92 | **1** | **12** | $2.717564 |

**Catches: 2 redraws in thirteen listings.** serial17's reason is on the pilot record —
`plan/serial-pilot-17.md` §1, *"One in-loop redraw fired on the coordinator-density ceiling
(6.19/100w over 5.89)"* — and the kept draw came back at 4.81. **serial18b's redraw reason is not
recoverable**: the decision detail records the count (*"after 1 redraw(s)"*) but not the predicate,
`listing.json` stores only the kept draw (`draft` and `listing` are byte-identical in ten of the
thirteen bundles on disk, the three exceptions — pilot7, pilot9, pilot10 — being the retired
listing-revision path that predates the density gate), the stdout line that names the reason was not
captured, and no pilot record mentions it. Either predicate could have fired.

**The gate itself has never failed.** No kept listing exceeded 5.89 anywhere, so `listing_chained` is
false on every row and the `litharness: kept a listing at …` fallback has never printed. The gate is
advisory and the loop is what does the work.

**Cost: not separable, and the invocation count is what the record gives.** A redraw is exactly one
extra overview call, visible as invocations 12 against the 11 every other post-gate listing spent.
The two redraw stores' listing decisions total $3.116743 and $2.717564 against a $2.554521 median
over the seven 11-invocation listings drawn under the same ceiling — **two draws beside seven, never
a marginal cost.** The decision row aggregates the whole stage (overview draws, four appetite
readers, title draws, availability lookup, four browsing readers) into one `cost_usd`, so the
redraw's own price is not on the record.

**False-positive evidence: none available.** A false positive here would be a discarded draw that was
better than the kept one, and nothing stores the discarded draw. §183.1's own framing is the
standing caveat: the counter is a shape property, and *"a listing under the ceiling is not good, it
is merely not chained"* (`application/overview.py::coordinator_density`).

---

## 5. §180's em-dash strip — two marks, one scene, and the subject changed underneath it

Shipped 13:19 BST (`b832fc1`), merged 13:23 (`26a32ee`). One call site,
`application/handlers.py:639`, on the drafting path only; `em_dashes_removed` lands on the
`ManuscriptRevisionAccepted` event (`handlers.py:879`).

**Every acceptance event on the shelf that carries the field** — four, in two stores, because
serial18b and serial18c are the only chapters drafted after it merged:

| store | event seq | scene | `em_dashes_removed` | `revised_by` | chars |
| --- | --- | --- | --- | --- | --- |
| serial18b | 3 | scene-1 | **2** | `None` | 4,918 |
| serial18b | 7 | scene-2 | 0 | `None` | 5,010 |
| serial18c | 14 | scene-1 | 0 | `claude-opus-5` | 5,350 |
| serial18c | 19 | scene-2 | 0 | `claude-opus-5` | 4,769 |

**74 acceptance events across the shelf carry no `em_dashes_removed` field.** Two of them are
serial18b's and serial18c's own book-creation events (`litharness new`, which mints empty scenes and
touches no prose); the other **72** are in the twenty-two stores drafted before the strip existed —
serial 9, serial3 9, serial4 9, serial8 7, serial9 5, then 3 each in serial12b, serial13b, serial14b,
serial15, serial15b, serial15c, serial15d and serial16, 2 in serial14, and one each in serial7,
serial11, serial12, serial13, serial17, serial17b and serial18. (serial13's 1 and serial13b's 3
overlap in the same way their decision rows do; see §0.)

**Catches: 2 em dashes, on one scene, in one store.** Correct on the record in the only sense a
character-class rewrite can be: the mark is a frozen code point and the strip is deterministic. The
operator's item that commissioned it (`plan/serial-pilot-16.md` §7, *"I see em dashes again"*) is
about pilot 16, drafted before it existed.

**The subject changed after §185.** serial18c's two zeros are counts of marks in the **reviser's**
output, not the writer's — §185.8 item 2, in advance, and the `revised_by` column is what makes the
two rows separable. `plan/serial-pilot-18.md` §5 records *"zero em dashes"* on the page for draw 3;
the store says the strip removed none, so the reviser produced none.

**Cost: $0.00.** A rewrite of an accepted string; it refuses nothing, retries nothing, and adds no
call.

**Reach, and a recorded gap.** §180.7 and §185.9 both name the same open seam: `application/repair.py`
writes prose through `apply_patch`, which the strip does not reach, so prose repaired after
acceptance ships unstripped. No store on the shelf has run that path, so it has cost nothing yet.

---

## 6. The integrity and shape gates, over every store the shelf holds

Every gate verdict recorded in `policy_decisions` across the twenty-six stores, de-duplicated by
`decision_id`:

| gate id | blocking | fails | where | refused-attempt cost |
| --- | --- | --- | --- | --- |
| `integrity.findings.v0` | yes | **7** | serial7 (scenes 1, 2, 3) | $2.410180 |
| `integrity.progression.v0` | yes | **3** | serial18c (scene 1) | $1.122440 |
| `integrity.standing.v0` | yes | **1** | serial7 (`dec-8af852fcdb71605eebea0cc8`) | $0.000000 |
| `shape.plan_proposal.v0` | yes | **1** | serial4 (`dec-b12c701d23d9dd22dc5be08d`) | $0.491772 |
| `budget.max_tokens_per_day.v0` | yes | **1** | serial12b (`dec-0da361a070442a1d35ba6f87`) | $0.000000 |
| `shape.forge.conforms.v0` | yes | **1** | reader-book (`dec-2f7b2936bb1c8cf66772f556`) | $3.301572 |
| `shape.draft.v0` | yes | **0** | — (ran on every drafted scene) | — |
| `revision.containment.v0` | no | **0** | serial18c, 5 runs | — |
| `writer.overview.v0` | no | **0** | 13 listings | — |
| `architect.seed.v0` | advisory | **8** | serial7, serial8 (×2), serial9, serial12, serial13, serial13b, serial15d | $0.000000 (all on accepted decisions) |
| `world.accept.v0` | advisory | **4** | serial7, serial8, serial9, serial13b | $0.000000 |
| `architect.world.v0` / `architect.screen.v0` | advisory | 8 / 6 | reader-book (retired Forge) | $0.000000 |
| `craft.scene_echo.v1`, `craft.repeated_span.v0` | advisory | **0** | serial4 and others | — |

**`shape.draft.v0` has never refused a draft in the shelf's history.** It appears on **65** decision
rows and passed all 65, at 100%–121% of target across them. It is the oldest blocking gate on the
drafting path and its catch count is zero.

### 6.1 serial7 is the expensive case, and one contradiction blocked three scenes

Eight refused attempts, **$2.410180**, three parked jobs, and every one of them names the same
finding.

| decision id | scene | attempt | outcome | failing gate | cost |
| --- | --- | --- | --- | --- | --- |
| `dec-e7ff9d2835136efed12a0369` | 1 | 1 | retry | `integrity.findings.v0` | $0.333212 |
| `dec-8af852fcdb71605eebea0cc8` | 1 | 2 | park | `integrity.standing.v0` (pre-flight, no call made) | $0.000000 |
| `dec-2702d1662ca7641627018867` | 2 | 1 | retry | `integrity.findings.v0` | $0.375594 |
| `dec-def6fdc191a34c642ec60f16` | 2 | 2 | retry | `integrity.findings.v0` | $0.367178 |
| `dec-89b8ebabf8dfd211975af229` | 2 | 3 | park | `integrity.findings.v0` | $0.315748 |
| `dec-a862a0e26ba532d13d980770` | 3 | 1 | retry | `integrity.findings.v0` | $0.352803 |
| `dec-7e621ef7851585c16a899dae` | 3 | 2 | retry | `integrity.findings.v0` | $0.334757 |
| `dec-629de99658df512acf6d14f8` | 3 | 3 | park | `integrity.findings.v0` | $0.330888 |

**All eight cite `f-055aeae95449f57b16cb65da`**, a `state.contradiction.v1` [major] reading
*"crit_glasses manifests_as holds 2 different values at story position (unplaced)"*. The store holds
**four** findings, all created at 2026-08-25T17:59:53 against scene-1, all later set
`accepted_intentional` (`FindingStatusChanged`, seq 7–10, 18:02:38). **Three of the four are probe
records by their own text** — `q_probe asks` holds *"Real question?"* and *"The probe question?"*;
`q_probe claim.content` holds *"Real answer."* and *"The probe answer."*; `rule_probe world_rule`
holds *"A probe rule."* and *"Real rule text."* Only `crit_glasses` is story canon.

**Correct on the record, and the record also shows what the gate could not do about it.** A
contradiction did exist in canon — `world accept` had already flagged it (`dec-5f259c34174e80f2c97c2012`,
`world.accept.v0` FAIL, *"208 proposal(s) accepted; 1 complaint(s)"*), advisory, and the world was
accepted anyway. The gate then refused three consecutive scenes for a defect **none of them
introduced and none of them could remove by rewriting**: the contradiction is at story position
`(unplaced)` in the seeded world, the prompt is frozen at enqueue, and each retry re-drafted against
the same canon. The human dismissal at 18:02:38 cleared scene 1's standing block but did not stop
scenes 2 and 3 being refused at 18:05:19 and 18:10:41 — the detector re-fires per draft. This is the
nearest thing on the shelf to false-positive evidence for a blocking gate, and it is not quite that:
the finding was real, the refusals were consistent with it, and what the record shows is a gate
correctly refusing something no attempt it licensed could fix.

### 6.2 The other four blocking refusals

- **serial4, `dec-b12c701d23d9dd22dc5be08d`**, $0.491772: *"NarrativePlanOutputError: provider
  response did not conform to the plan proposal schema"*. The retry (`dec-6df79829e811fd1a06642021`,
  $0.525477) conformed and was accepted. **Correct on the record**, and the cheapest possible shape of
  a catch: one malformed response, one retry, no park.
- **serial12b, `dec-0da361a070442a1d35ba6f87`**, $0.000000: *"4983966 tokens spent today plus a
  projected 34953 would exceed the daily ceiling of 5000000"*. Parked scene-2 **before** the call, so
  the refusal is free by construction — the only gate on the shelf that costs nothing when it fires.
- **reader-book, `dec-2f7b2936bb1c8cf66772f556`**, $3.301572, `escalate`: *"the answer does not
  conform to the world schema (84381 output token(s)); kept at reader-book-forge\refused.txt"*. The
  retired Forge, 2026-08-24; the single most expensive refused attempt on the shelf, and the response
  was kept rather than discarded.
- **serial7, `dec-8af852fcdb71605eebea0cc8`**: the standing gate parking pre-flight, $0.000000 — the
  behaviour §184.5 cites as its reason for *not* routing the progression refusal through a finding.

### 6.3 The nine recruiter refusals are a human's, and they are counted once

serial13 and serial13b each carry nine `park` rows reading *"a person turned these writers down: …"*
(`dec-5ce51f0387d9968082bdfc0b` … `dec-11ce41254e9dc5d16f0c769e`, 2026-08-28 22:03–22:30). **The
decision ids are identical in the two stores — these are nine refusals, not eighteen**, and every one
carries `cost_usd` null. Not a gate: the operator's own `roster refuse` reasons, recorded verbatim
in the store.

---

## 7. The coordinator's own listing refusals — judgment calls, listed because the operator asked about all agents

Not gates. `plan/serial-pilot-17.md` calls the coordinator's read *"the operator's sanctioned
diagnostic channel"* and §183.5 records that it stays the listing gate *"until something qualified
exists"*. No store holds a row for any of them.

| pilot | store | title | recorded reason, in the record's own words | listing spend |
| --- | --- | --- | --- | --- |
| 17 draw 1 | serial17 (`book=366aa0d9`) | *Legally His Goblins* | *"the progression engine is guild-issued — badge, registry, bylaws, promotion inside the Guild"*: the institutional-paper family the operator rejected in reads 7, 8 and §116, plus *"the §160 anti-pattern at premise level"* (`plan/serial-pilot-17.md` §1) | $3.116743 |
| 17 draw 2 | serial17b (`book=31aaef92`) | *Coroner of Monsters* | *"the system is named the Ledger and pays skills for clerical duties; register, statute and fee line carry the engine"* — the same engine, confirming the dossier per §2's pre-registered rule (`plan/serial-pilot-17.md` §3) | $2.454164 |
| 18 draw 1 | serial18 (`book=c9aef7d8`) | *The Machine That Mends* | *"it is a good sci-fi horror listing and it is not LitRPG. No system, no interface, no promised furniture"* (`plan/serial-pilot-18.md` §1) | $2.414161 |

**Total listing spend on refused draws: $7.985068** — 4.1% of the shelf's $194.9299, and more than
the whole shelf's mechanical-gate refusals ($7.3260) put together.

**Correct on the record?** Each cites an operator address rather than a taste: reads 7/8 and §116 for
pilot 17, read 9's *"It's not litrpg"* and §183's constraint for pilot 18. Pilot 17's two draws were
also the evidence for a pre-registered dossier finding, and pilot 18's refusal is what commissioned
§183 — both refusals produced a recorded consequence rather than only a discard. **What the record
cannot supply is a false-positive check**: no refused listing was drafted, so there is no observation
of what the refused books would have been.

**One discrepancy between two records, recorded and not resolved here.** §183.1's table heads three
rows *"Three books were refused at the coordinator's gate before a chapter was drafted"* and includes
pilot 13 (larkin). The record it cites says otherwise: `plan/serial-pilot-13.md` §8 has the chapter
drawn, the covers made, and the genre failure named by **the operator on first sight of the book**
(*"One big problem i noticed right away with the book. It's not litrpg"*), and
`plan/house-genre-constraint.md`'s opening says the same — *"The operator, on first sight of pilot
13's book"*. serial13's store carries a full book —
39 decisions, $15.3030 — not a stopped listing. So the "three refusals in one day" are two
coordinator listing refusals (pilots 17 and 18, three draws) plus one operator refusal of a finished
book. The consequence for this ledger: **pilot 13's cost of refusal is a whole book, $15.3030, not a
listing.** Flagged for §183.7's corrections-in-place; not corrected here.

---

## 8. Summary

| check | shipped | fires in production | correct on the record? | false-positive evidence | cost of refused attempts |
| --- | --- | --- | --- | --- | --- |
| §184 `integrity.progression.v0` | 2026-08-30 15:56 | **3** (serial18c scene 1) | yes — refused drafts left `rating` 2 at s1; the accepted one moved 2→3 | none; §186 later showed the *ask* was mis-rendered, not the check | **$2.238013** ($1.122440 writer + $1.115573 reviser), 27.6% of serial18c |
| §185 `revision.containment.v0` | 2026-08-30 16:55 | **0** (5 calls, 5 adoptions, 0 discards) | n/a — never fired | none; refusal paths proved only against the fake provider | $0 refused; **$2.067820 stage cost**, 109% of the writer's $1.896380 |
| §178 schema-name check | 2026-08-30 13:20 | **0** since merge; 5 names in 2 pre-existing worlds | yes — pilot 16's four are read 11's own item, pilot 15c's is §120's defect | none; the near-miss (*"Seams standing"*) was designed out before shipping | $0 (refuses before any decision row is written) |
| §183 listing genre floor | 2026-08-30 14:08 | **0** — a prompt clause, no gate row exists | n/a | n/a | $0 |
| coordinator-density redraw loop | earlier (§147) | **2 redraws** in 13 listings (serial17, serial18b) | serial17 yes (6.19 over 5.89, on the pilot record); serial18b's predicate not recoverable | none possible — discarded draws are not stored | not separable; one extra invocation each (12 vs 11) |
| §180 em-dash strip | 2026-08-30 13:23 | **2 marks**, serial18b scene-1, of 4 eligible scenes | yes — a frozen code point, deterministic | n/a | $0 |
| `integrity.findings.v0` | pre-existing | **7** (serial7 scenes 1–3) | yes on the finding; the finding was inherited canon no attempt could fix, and 3 of the store's 4 findings were probe records | closest thing on the shelf, but not a false positive | **$2.410180**, 3 jobs parked |
| `integrity.standing.v0` | pre-existing | **1** (serial7) | yes — parked pre-flight on a standing finding | none | $0 |
| `shape.plan_proposal.v0` | pre-existing | **1** (serial4) | yes — schema non-conformance; retry conformed | none | $0.491772 |
| `budget.max_tokens_per_day.v0` | pre-existing | **1** (serial12b) | yes — arithmetic against a declared ceiling | none | $0 |
| `shape.forge.conforms.v0` | retired Forge | **1** (reader-book) | yes — schema non-conformance at 84,381 output tokens | none | $3.301572 |
| `shape.draft.v0` | oldest blocking gate | **0** in the shelf's whole history | n/a | n/a | $0 |
| `craft.scene_echo.v1`, `craft.repeated_span.v0` | advisory | **0** | n/a — advisory, annotate only | n/a | $0 |
| `architect.seed.v0` / `world.accept.v0` | advisory | 8 / 4 complaints | advisory; serial7's `world.accept.v0` complaint is the same contradiction that later cost $2.41 at the drafting gate | n/a | $0 at the world; downstream cost recorded above |
| coordinator's listing read (not a gate) | — | **3 listings refused** (pilots 17×2, 18×1) | each cites an operator address, not a preference | none possible — no refused listing was drafted | **$7.985068** |
| operator's `roster refuse` (not a gate) | — | **9** recruits (counted once across serial13/13b) | the operator's own words, recorded verbatim | n/a | $0 |

**Two lines that carry the ledger.** Of 226 distinct decisions and $194.9299 on the shelf, 23 rows
are refusals; nine of those are the operator's own recruiter refusals at no cost, so **every
mechanical gate in the shelf's history has refused 14 attempts for $7.3260** — 3.8% of spend — and
**eleven of the fourteen sit in two stores** (serial7's eight, serial18c's three). The two judgment
channels the operator asked to see beside them refused **three listings for $7.985068** and nine
recruits for nothing, so **the un-mechanised half of the refusal system has cost more than the
mechanised half.**

## 9. Anti-scope

No metric is minted and `research/quality-measurement/BRIEF.md` governs; nothing here is a bar, a
threshold, a score, or a comparison between books. No model was called, no book was drawn, no paid
call was made, and no store under `runs/` was opened — every read was against a scratchpad copy. No
corpus was read, so RS1 is untouched. No research claim is promoted, no mechanism qualified, no axis
admitted. Nothing here reaches a prompt, a dossier, the writer, the roster, the listing task, the
editorial control plane or the reader loop: this is operator-facing diagnostics under §95 and the
`debug-book` rule, and the one thing it may not become is an input to generation. The two record
discrepancies it surfaces — §183.1's pilot-13 row, and the `debug-book` skill's `blame` verb — are
described, not fixed. Nothing here says a gate is worth its cost or is not; the coordinator
synthesises.
