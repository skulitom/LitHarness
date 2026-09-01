# Serial Pilot 19 — the first opening drawn under the summit shape, a genre-centre writer, a situation brief and the first person

**Status: PROTOCOL, 2026-09-01, written before the listing call.** The first book stood up under
everything stage-0 §195 shipped: the opening's two beats, the printed `[OFFER]` line, `--person
first`, the re-signed listing clause, and a writer recruited for the genre's centre. It is the
"treatment" opening the opening-parity measurement (`research/opening-parity/`) will read
beside the four "baseline" openings and the six summits, on the same frozen panel, once its
chapter exists.

## 0. What this is, and what it is not

**A description of one draw.** Everything moved at once — writer, brief, person, three pieces of
machinery — so nothing here is a treatment effect (`serial-pilot-7.md` §0, the standing
boundary). The comparison that carries information is the parity panel's: this opening beside
the summits, read with the baseline openings beside the same summits. That comparison is
descriptive too (PREREG §4), and one draw is one draw.

**No model chose anything here.** The writer is cast by the coordinator for the shape the
operator named; the brief is the coordinator's, written as a situation and not a shelf label
(§136); the listing gate is the coordinator's deterministic checklist; the pilot follows the
settled recipe of pilot 15b §1 flag for flag except where this file says otherwise.

**The operator reads at milestones, not per iteration** (`plan/continuous-loop-direction.md`):
the listing and the chapter go on the shelf, the parity panel reads them, and the operator's
read is asked for at the point the panel's description makes it worth asking.

## 1. The draw, as it was set up

- **Writer:** `marsh` (progression-fantasy, several-with-beat), accepted on the installation
  roster 2026-09-01 — the integration-day shape named on purpose.
- **Brief** (`runs/pilots/pilot19/brief.txt`, the designed input channel; a situation, no
  genre noun, no read quote): a twenty-three-year-old a year short of a chemistry degree, night
  shifts at a parcel depot, one old game he is uselessly good at; on an ordinary Monday every
  screen on Earth shows the same message and everybody gets the same sheet except him. The
  exception itself is left to the writer.
- **Person:** `--person first`, the operator's stated preference (read 4 §3), shipped as a
  position. §195.1's census found the two anchors close third with a reported mind, so this is
  a choice and not a finding; a first-versus-third A/B on this settled listing is the obvious
  next arm.
- **Shape:** six scenes, two per chapter, the standard pilot length.
- **Ceilings:** the pilot-15b recipe's (`--max-cost-usd-per-day 40`,
  `--max-tokens-per-day 20000000`).

```bash
uv run litharness --database runs/pilots/databases/serial19.db init
uv run litharness --database runs/pilots/databases/serial19.db \
    --roster-database C:/DEV/LitHarness/runs/roster/roster.db --chapter-scenes 2 \
    listing --writer marsh --brief-file runs/pilots/pilot19/brief.txt \
    --scenes 6 --person first --out runs/pilots/pilot19
# coordinator's gate on the listing (§183's checklist), then:
uv run litharness --database runs/pilots/databases/serial19.db --roster-database ... \
    --library book-library --writer marsh \
    --max-cost-usd-per-day 40 --max-tokens-per-day 20000000 architect seed
uv run litharness --database runs/pilots/databases/serial19.db world check
uv run litharness --database runs/pilots/databases/serial19.db world accept
uv run litharness --database runs/pilots/databases/serial19.db --roster-database ... \
    --library book-library --writer marsh --chapter-scenes 2 \
    --max-cost-usd-per-day 40 --max-tokens-per-day 20000000 tick    # until chapter 1 stands
uv run litharness --database runs/pilots/databases/serial19.db --library book-library \
    --chapter-scenes 2 library
```

## 2. What is refused before the draw

- **No redraw on taste.** The listing is redrawn only on the two frozen predicates the command
  already carries (coordinator density, machinery words) and on §183's gate; a listing the
  coordinator merely dislikes stands.
- **No prose reads before the panel.** The coordinator's gate reads the checklist (standalone
  comprehension, diegetic interface, the offer on the page, the opening's two beats landed,
  cast bound, no schema words); it does not grade sentences. The register question is the
  reviser's milestone and stays the operator's.
- **No promotion.** Whatever the panel says, this draw is a description. A second draw under
  the same settled listing is what the A/B harness (§191) exists for.

## 3. The listing

**Drawn 2026-09-01 in one draw** (no redraw fired on either frozen predicate): *The Game
Nobody Plays Anymore*, 118 words, first person, `runs/pilots/pilot19/listing.txt`; the book
stood up as serial19.db, book `af68085d`, six empty scenes, no seed state (the floor's advisory
printed as designed; the Architect seeds the sheet).

**The coordinator's gate, §183's checklist, item by item — PASS.**

| item | on the page |
| --- | --- |
| opens something and reads their own capabilities | a sheet with his name on it; a line theirs did not have |
| names one they did not have before | a class offered to nobody else, and a skill that shows what a thing will do before it does it |
| the genre's furniture in plain words | sheet, system, class, skill, monsters, climb |
| the person's life the day before, one clause and no more | scanning parcels on a depot night shift; the one thing he was good at |
| person | first, as asked under the brief |
| our machinery's words | none (`schema_words.named_in` clean) |
| dashes, headings, tags, author | none |
| what the person is after | "Now I climb, and I am not going back to nights" |

**The browsing pool, 3 of 4 would start it, 1 passed, 0 saved.** The pass is the typicality
item (read 5 §4.2's family B5): *"system arrives, I was secretly good at the thing it's made
of — I've read that opening five times this year."* Recorded and not acted on: the shape is
the summit shape on purpose (§195.1), and the parity panel is what says whether this instance
of it stands beside the anchors. The three starts name the ramp (depot night shift to a class
nobody else got) and the exception having a reason rather than a bigger number, which is the
operator's hook direction (read 3) arriving unprompted.

**One thing the listing does that the brief did not ask for:** it makes the system *out of*
the dead game. That is the writer's, and it is the exception's reason.

## 4. The seed and the chapter

**The seed** (one draw, one `world check` read, accepted without `--force`): 257 records, 12
calls, $6.15 with the listing. The Architect built *the Judge* — a system that on the Monday
printed every sheet on Earth in the vocabulary of a dead arcade fighting game: a six-rung
queue-at-the-cabinet ladder (Watcher, Next, Seat, Holder, King, Regional), eleven governed
abilities in a graph (Spacing feeds Guard, Punish and Read; Read feeds Counter; Throw feeds
Ringout), a fork at Seat (*the Pick*: three words touched once, never offered again — Pressure,
Range, Grapple, each opening two abilities), two institutions charging for the climb
(Halloway Logistics by rung; the Rota reading grades off a tablet at a cordon), and Owen Dace
as the exception the listing promised: his sheet opened at Next with his old player tag and a
class no other sheet was offered, and Read came with it. The sheet prints GRADE, LIFE, SPEED,
POWER, WEIGHT; Owen stands at Next; Nell Halloway has taken her Pick (Grapple); nobody else has.

**The system did not complete, and the reason is a bound the Architect was never told.**
`world accept` mints a drawn system's scale and digest (§165's completion), and it refused
this one: *eleven abilities; a drawn system carries five to eight, the upper bound being the
number of columns a status line can print*. `world check` reported it as *"judge lacks a
magnitude_scale"*, which is true and is not the reason. Two follow-ups are owed and neither is
taken here: the seed ask does not state the completion's ability bound, so the Architect can
draw a system the completion must refuse; and the check's gap sentence should carry the
completion's own reason rather than the symptom. Nothing can be retracted on this store, so
the draw proceeds with the system unfinished: the floor is cleared by the accepted sheet, the
progression beat falls to the legacy arm (the sheet's own columns, *Grade moves here*), and
§173's offer beat and §195's `[OFFER]` line abstain — which they would have anyway in chapter 1,
because the Pick opens at Seat and Owen enters at Next. The beats that do fire are the opening's
two and the interaction beat.

**Chapter 1:** two scenes, 1,995 words, every scene accepted on its first attempt, seven ticks
(three of them the eval and summary follow-ups; the seventh drafted chapter 2's first scene
as a bonus), $9.00 on the store with the listing and the seed. Published to
`book-library/the-game-nobody-plays-anymore/`.

**The coordinator's gate read, the checklist and nothing else.**

| item | on the page |
| --- | --- |
| the opening beat: who he was before, on the page before the first printed line | the belt at Sallow Lane, the written warning for scan rate, the bowling-alley back room and *Vantage*, all before the Monday |
| the first printed line landing inside that | the message on every screen, then the sheet read aloud in the sorting shed by Priya, then his |
| the interface as business in the scene | Priya reads hers out; the blank class row is what everyone minds; Nell reads his with her chin on his shoulder |
| the exception on the page | CLASS: VANE and READ where every other sheet has a blank; the monster's tell known from the game |
| the grade moving where the reader can see it | `[STATUS] Owen — GRADE 3` printed once per scene, NEXT gone to SEAT after the fight |
| the hook: the chapter ends on something offered and unanswered | the Pick's three words and a cursor that does not blink, and Nell's job at ten o'clock, both open |
| person | first, throughout |
| cast bound | three named per scene (Owen, Priya, Baz; Owen, Priya, Nell) |
| dashes, schema words | none; none |

**Residuals below the line, for the reviser's milestone and the operator, not fixed here:**
three similes of the *the way you …* shape in scene 1 (§171's family, on the page despite the
reviser); *"which is the part everyone kept coming back to"* restates a thing the paragraph
already gave (§179's family); two *to me she looked like* inferences narrated (§171). Scene 2
has no fight and spends its length on the cordon and Nell's offer, which is the chapter's
hook and is also the pace read 10 called stagnant on a different book; the panel is what says
whether a reader stays for it.

**What the machinery did and did not do.** The opening's two beats and the interaction beat
fired and landed; the progression beat fired on the legacy arm (*Grade moves here*) and landed
(NEXT → SEAT); the `[OFFER]` line did not print, because the system is unfinished (above) and
because the fork opens at Seat, which Owen only reached on the page — the writer put the
three words on the sheet from the world's own facts anyway. The shape census puts this
opening beside the summits on the axis §195.1 measured: first-person marks and interior verbs
in the summits' range where the four baseline openings had almost none.

## 5. The panel's reading

*(filled from `runs/opening-parity/summary.md` once this opening has been added to the
manifest as an "ours" entry and the pairs against the six summits have been bought)*
