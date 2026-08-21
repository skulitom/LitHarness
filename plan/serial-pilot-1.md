# Serial Pilot 1 — "Reappraisal": the operator package

**Status: DIRECTIVE PACKAGE, 2026-08-21.** The first viable product: **two chapters (eight
scenes, four per chapter, ~900 words per scene) of a new open-ended serial**, drafted through
the loop on the pinned frontier provider, with the operator as first reader and one-bit gate.
Constructed before any scene was drafted, which is what makes the promise-ledger intents in §5
pre-registered rather than post-hoc.

**Candidate count: 1.** One premise, fixed here before drafting. §61 pre-registration (5) and
§96.1's grid rule are not owed anything by this run — unless more pilots are generated and a
preferred one is later reported, in which case the division applies and this line is the record
that it was known.

## 0. What this run is, and is not

- **It is** the wiring run for §101's serial product at its smallest real size, and the first
  artifact this project has ever aimed at the operator's actual taste rather than at a gate.
  Its output is own-generated, contamination-proof substrate — legitimate food for F3/F4 and
  the promise-ledger instruments.
- **It is not** a capacity claim of any kind. Two chapters sit far below §101.1's first
  claim-bearing rung (32); no degradation, quality, or superiority sentence may cite this run.
- **RS1 holds throughout.** No anchor work is named, quoted, or imitated anywhere in this
  package; the operator's taste enters only as properties stated in our own words (§4), and
  constraint C3 makes the prohibition binding on the generator too.

## 1. The premise (verbatim, for `new --premise`)

> Silas Marrow, a junior appraiser at the Corvessa assay house, dies two days after the Advent
> — and wakes on the morning it began. Each death returns him to that morning, keeping nothing
> but his Skills and what he has learned: every coin, wound, and acquaintance resets. The System has made his trade literal: Appraiser, a class that reads the value,
> provenance, and remaining time of whatever he studies — priced cheap by a System that read
> his guild card, in the one situation where knowledge is the only currency that compounds.
> The city has nine days. Silas has as many as he can pay for.

Why this premise, stated so the marketing claim is checkable: it sits at the intersection of
the operator's named anchor set — a repeating window with knowledge compounding across
iterations, an undervalued information class exploited cleverly, a pragmatic adult
professional, visible numbers that carry real tradeoffs — without borrowing any anchor's
setting, system, or voice. An information class inside a time loop compounds twice, which is
the premise doing the genre's work instead of the prose having to.

## 2. The seed sheet (`plan/serial-pilot-seed.json`)

**Revised — see §8.** Fifteen canon records, **none with a story position**: the initial
condition, true before the book begins, exactly as §17 Stage 3 prescribes. Verified against the
pinned contracts package and against this repository's own extraction.

Three things, in the order they matter.

**The ability graph is the substance: 4 nodes, 7 edges, 3 world rules, and no numbers.** What
Appraisal returns, what it costs, what it *cannot* read, what makes it deepen, and how the
System, the guild card and the token stand to each other. Edges are `object_ref`, which the
store carries and `state.describe()` renders into the Established facts block of every scene's
packet — measured at 351 tokens of a 16,000 budget for the whole graph. No two records share a
`(subject, predicate)` pair, which is deliberate: until scoped cardinality lands
(`plan/state-model-abilities.md` §2), a repeated predicate is reported as a blocking
contradiction.

**The sheet is two fields, declared by the book: `Loop | Day`.** Loop is which iteration and
never resets; Day is which of the nine and resets every time he dies. So one number is monotone,
one is cyclic, and together they are the loop mechanic as arithmetic — which is what constraint
C1 needs to be checkable from scene 1. Per-book sheets did not exist when this package was
written; `domain/extraction.py` now derives the template and the parser from one declared field
list, with the old `Level | HP | MP | Gold` line as the default so both golden fixtures are
untouched.

**The subject is `silas`, lowercase, deliberately**: extraction casefolds the on-page name
(`normalise_subject`) and then matches it against canon subjects **as the records hold them**, so
a capitalized seed subject would silently drop every `[STATUS]` line the book writes. Same
convention as the test suite's `rook`. One consequence to expect rather than to fix: the example
line the generator is shown reads `[STATUS] silas — Loop 1 | Day 1` in lower case, because
`render_status_line` writes the subject as canon holds it and inventing a display name by
title-casing would mint a fact no record states. Prose that capitalises it parses identically.

## 3. Commands, in order (PowerShell, from the repo root)

**Revised — see §8.** Six defects in the original command list were found by rehearsing it;
they are recorded in `plan/serial-pilot-1-preflight.md` and corrected here. The canonical path
is now two scripts, because the directive texts are read from
`plan/serial-pilot-directives.json` — extracted from §1 and §4 of this document rather than
retyped — and because one of the defects was a quoting bug no reader would catch by eye.

```powershell
.\tools\serial-pilot-setup.ps1
```

That refuses an existing database, `LITHARNESS_ENV=test`, a set `LITHARNESS_FAKE_PAD_CHARS`, a
missing `claude`, and a spec whose directive count disagrees with the package; then runs `init`, `new`, `state` and
all eight `directive` commands, and verifies what landed. It makes no provider call.

Then the loop, **in two phases**. Phase 1 lands the direction before a paid call is spent on
prose:

```powershell
tools\run-loop.ps1 -Database serial.db -Ticks 12 -DelaySeconds 2 `
  -TickArgs '--target-words','900','--context-budget','16000','--chapter-scenes','4','--max-cost-usd-per-day','10','--max-invocations-per-day','80'
uv run python tools/serial_pilot_check.py --database serial.db --phase directives
```

Only when that gate is green, phase 2 writes the eight scenes:

```powershell
tools\run-loop.ps1 -Database serial.db -Ticks 48 -DelaySeconds 2 `
  -TickArgs '--target-words','900','--context-budget','16000','--chapter-scenes','4','--max-cost-usd-per-day','10','--max-invocations-per-day','80'
uv run python tools/serial_pilot_check.py --database serial.db
```

Notes that keep the run honest:

- **`-TickArgs` must be a comma-separated array.** A single quoted string binds as a
  one-element array and splats as one argv token; argparse refuses it and the loop repeats the
  refusal for every tick it was given.
- **Provider.** The pinned frontier provider (`claude_code`) is the unflagged default — the
  `claude` CLI must be authed, `LITHARNESS_ENV` must not be `test`, and
  `LITHARNESS_FAKE_PAD_CHARS` must not be set. If the provider is unhealthy the unit parks and
  the book waits; that is the design, not a fault.
- **Context budget 16,000, raised from the 6,000 default on arithmetic:** seven prior 900-word
  scenes ≈ 7,000 counted tokens, against 14,500 usable after the output reserve. Check `status`
  for a nonzero `context_omitted` in the daily digest anyway; a book written blind should be a
  known fact, not a surprise.
- **Tick count: the floor is 33 working ticks**, not the 25–35 originally estimated — 4
  directive-plan, 4 narrative-plan, 1 outline, then per scene a draft, an evaluation and a
  summary. Idle ticks make no provider call and cost nothing, so over-provisioning is free.
- **Cost.** The measured drafting rate prices eight scenes at roughly $1.70, but the largest
  single line item is invisible to every ceiling: `ClaudeCodeProvider.health()` is a real billed
  round trip (measured $0.3386) paid once per tick-process that reaches the provider, so expect
  ~21 probes. Budget the run at **$9–13 of quota-equivalent**, of which `--max-cost-usd-per-day`
  can see perhaps a third.
- **Afterwards:** `status`, `verify` (exits 0 and prints `N revision(s) rebuild cleanly` — the
  exit code is the criterion, not silence), and the library beside `serial.db` — the reading
  copy for the acceptance read, the pastable chapters grouped 4 scenes each by the flag above.

## 4. The directives

### 4.1 Constraints — locked, deterministic lane, text kept exact

Four, kept short because each occupies every context packet from here to the end of the book.

**C1 — the loop invariant** (the mechanic as arithmetic, so the gates can hold it):

```powershell
uv run litharness --database serial.db directive "Loop rule: when Silas dies, time returns to the morning of the Advent. Day returns to 1 and Loop increases by one. He keeps his Skills and his memories; every coin, wound, possession and acquaintance returns to what it was that morning. Nobody else remembers a previous loop unless the story explicitly reveals otherwise." --kind constraint
```

**C2 — system voice** (matches `STATUS_TEMPLATE` exactly; what §12 step 5 reads back):

```powershell
uv run litharness --database serial.db directive "System voice: when Loop or Day changes on the page, the System prints one line of the exact form [STATUS] Silas — Loop 1 | Day 1, with current values. It never explains itself, never advises, and never answers a question it was not asked. Its flatness is a choice it is making and not an absence of anything: never call it neutral, mechanical, or empty, and never have it emote." --kind constraint
```

**C3 — originality / RS1 hygiene:**

```powershell
uv run litharness --database serial.db directive "Never name, quote, or imitate any real-world person, brand, or published fictional work, character, or game system. Every name, place, and mechanic in this book is original to it." --kind constraint
```

**C4 — price on the page** (§1a.3 item 2 as a rule rather than a hope):

```powershell
uv run litharness --database serial.db directive "Every gain — a Skill, an item, an acquaintance, a fact learned by Appraisal — carries a price paid on the page in the same scene or earlier: time, coin, pain, exposure, or a foreclosed option. The System gives nothing away." --kind constraint
```

### 4.5 Craft constraints — added after the first read, locked lane

**These three are an arm, and run 2 is its control.** The operator read chapter 1 and named five
prose defects (`plan/reader-read-2.md`). None was disobedience: the tone note reached the plan,
became locked constraints and sat in every packet. What the eight directives did not contain was
any direction about *beginnings*, any bound on how much is introduced before something happens,
and any rule at the level of the phrase. These add exactly those three and nothing else, so the
comparison between the two runs is about direction rather than about luck.

They are constraints rather than tone notes deliberately: the deterministic lane preserves their
words, and a rule the planner paraphrases is a rule that can be paraphrased away.

**C5 — how a scene begins:**

```powershell
uv run litharness --database serial.db directive "Openings: the first sentence of a scene puts a person in a situation, never a place in a condition. Do not open on weather, light, the time of day, or how a street looks. Open where someone wants something and something is in the way, or where a fact has just landed that changes what matters. The first line has one job: to make the second line necessary." --kind constraint
```

**C6 — what may be introduced, and when:**

```powershell
uv run litharness --database serial.db directive "Introductions are rationed. In the first three hundred words of a scene, name at most three things a reader is expected to remember — people, places, businesses, or objects with proper names. Everything else stays unnamed until the scene has given a reason to care about it. A detail earns its name by mattering to what is happening, not by being in the room." --kind constraint
```

**C7 — the phrase:**

```powershell
uv run litharness --database serial.db directive "Plain words, and every phrase must survive being read twice. Use the ordinary word unless the exact one means something different. No stacks of three or more nouns where a preposition would do: the door of the assay house, not the assay house door. A comparison must explain the less familiar by the more familiar, so if a reader has to stop and picture the thing being compared to, it is the wrong comparison. Never write a phrase that cancels itself, and never write one that a later clause in the same sentence then states properly — cut to the clause that states it properly." --kind constraint
```

### 4.2 Tone note — interpretive lane

```powershell
uv run litharness --database serial.db directive "Close third person, past tense, anchored to Silas throughout. Voice: dry, exact, quietly funny; an appraiser's habit of pricing what he sees, used sparingly and never as a tic. Concrete specifics over abstraction; varied sentence length and shape; scenes end on movement or cost, never on a tidy emotional summary. Dramatize rather than summarize: if it matters, it happens on the page. Avoid rule-of-three flourishes and moralizing final lines." --kind tone_note
```

### 4.3 Arc note — interpretive lane

```powershell
uv run litharness --database serial.db directive "This book is the two-chapter opening of an open-ended serial, four scenes per chapter. Chapter 1 is the first loop: ordinary competence, the Advent, a demeaning class assignment, one small clever appraisal, and death on the second day — ending on the reset that reveals the loop. Chapter 2 is the second loop: testing what persists, the cost of relationships that reset, one compounding win built on foreknowledge, and an ending that resolves the loop-two plan at a price while opening a larger question. Scene 8 resolves the chapter, not the serial: it must end on a hook." --kind arc_note
```

### 4.4 Chapter notes — interpretive lane, one per chapter

```powershell
uv run litharness --database serial.db directive "Chapter 1, scenes 1 to 4. Scene 1: Silas at work in the Corvessa assay house, his craft shown by catching a forgery; the city textured and ordinary; the Advent sirens end the scene. Scene 2: the System arrives; combat classes bloom around him; Silas draws Appraiser and is dismissed as support; his first read of a strange tarnished token returns a provenance older than its materials and a countdown: nine days. Scene 3: day two, the Tide breaches the river quarter; one good read saves Marta the bursar for an hour and costs Silas his own way out. Scene 4: Silas dies at the Lowgate and wakes on Advent morning; skills and memory intact, purse and body reset; he proves the loop to himself by pricing the day before it happens. End the chapter there." --kind chapter_note
```

```powershell
uv run litharness --database serial.db directive "Chapter 2, scenes 5 to 8. Scene 5: loop two; Silas tests what persists with method — skills yes, coin no, wounds no, the token's countdown unchanged — and Marta does not know him, which costs more than the coin. Scene 6: foreknowledge compounds; he preempts the forgery, banks the saved hours, and buys the token before the Tide reaches its stall; its appraisal now runs one line longer. Scene 7: a plan past mere survival — get the assay house's acquisitions ledger out of the river quarter before it burns, knowledge compounding where goods cannot — and the plan forces a choice between the ledger and a stranger. Scene 8: the run succeeds at a price that stays paid within the loop; then one appraisal returns a different value than it did in loop one. Something besides Silas is changing between loops. End on that line." --kind chapter_note
```

## 5. Promise-ledger intents, pre-registered

Stated before drafting because this project's own measured defect is the reason this section
exists: the only promise ledger in the repository records **32 promises opened and none paid**
across a ten-scene book. The pilot's rule: **at least one promise opened in chapter 1 pays
visibly in chapter 2.** Two do.

| # | promise | opened | paid / advanced | remainder due |
|---|---|---|---|---|
| P1 | why Silas keeps the System across resets | s4 | — | far (a later arc) |
| P2 | the token: provenance older than its materials; the nine-day countdown | s2 | s6 (acquired; read lengthens) | far |
| P3 | Marta — saved, then unmade by the reset | s3 | s5 (the cost dramatized) | recurring |
| P4 | an appraisal that changed between loops | s8 | — | next arc: the serial's spine |

After the run, read these against what `promise.overdue.v0` and the ledger actually recorded;
divergence between intent and record is pilot data, not failure.

## 6. The acceptance read (the operator gate, run properly)

1. **Before reading a word: write the grab criterion, verbatim, in your own words** — the
   behavioural definition of "this serial grabbed me." This is §97's §7.2, the outstanding
   blank a session cannot fill; the pilot is the natural occasion to fill it. Record it in the
   stage-0 ledger unchanged thereafter.
2. **Read the reading copy as a reader, not an editor.** Record the BCR trace out of band:
   where you stopped, whether you returned, whether anything got reread.
3. **One bit, book grain: accept or reject.** No diagnostic riders in band — a rejection
   carries no explanation into the system (§97.1). Cadence cap applies: this is the one
   consultation this candidate gets.
4. If rejected, the located-defect path stays fenced exactly as §97.2(b) writes it; nothing
   about this pilot loosens it.

## 7. Cost, bounded before it is spent

**Revised — see §8.** Fitness-shelf measured rate: **$0.2097/scene** → ~$1.70 of drafting
payload for eight scenes. Add to that one outline call, **four** interpretive-directive passes
(the four constraints use the deterministic lane and cost nothing), and **eight scene summaries**
— which the original estimate omitted entirely and which are not optional, because the promise
ledger §5 reads back is written by the summary handler and nowhere else. Evaluations are free:
with no `--continuity-evaluator-command`, `EVALUATE_REVISION` runs in process and never reaches
a provider.

**The largest single line item is invisible to every ceiling.** `ClaudeCodeProvider.health()` is
a real billed round trip — measured $0.3386 — cached for the life of a process, and the loop
starts a fresh process per tick. Roughly 21 ticks reach the provider, so ~$7 of probes against
$1.70 of prose, and `--max-cost-usd-per-day` can see none of it. **Budget the run at $9–13 of
quota-equivalent**, of which the ceiling governs perhaps a third. Set it anyway; it still bounds
the payload, and the invocation ceiling (80) still covers the per-call harness tax that token
accounting cannot see (§15).

Spend is recorded **per store**, so a parallel session ticking another database burns the same
subscription where this ceiling cannot see it. If a unit parks on a provider outage the ceilings
reset at midnight and `revive` is the verb — but note that a unit which exhausts its attempts on
a gate failure **poisons** rather than parking, and `revive` refuses a poisoned job. Nothing here
should ever need `-1`.

## 8. Revision log

**2026-08-21, after the preflight and the state-model work.** The package was written before
either existed. Two rounds of change, recorded here rather than folded in silently, because §5's
promise intents are only pre-registered if it stays visible what was decided when.

**Round 1 — six defects found by rehearsing §3** (full detail in
`plan/serial-pilot-1-preflight.md`): the `-TickArgs` quoting bug that failed on the first tick;
"seven directives" where §4 issues eight; §7's "six interpretive-directive passes" against four
interpretive and four deterministic; the tick floor of 33 rather than 25–35; a cost model
missing the per-tick health probe, which is the largest single line item and invisible to every
ceiling; and `verify` printing a line rather than nothing. §3 and §7 are corrected. Nothing in
§4 or §5 changed in this round.

**Round 2 — the state model.** The operator redirected what this project tracks: abilities and
their relations over HP/MP/Gold, ranks, several systems per world or none, agencies above the
protagonist, progression by deepening understanding, and immaterial things as characters. The
design and its evidence are in `plan/state-model-abilities.md`; the research behind it is in
`research/progression-generalization.md`. This package was written entirely in the stat idiom,
so five of its eight directives and its seed contradicted the direction it is supposed to serve.

Changed: the seed (§2) is now an ability graph plus a two-field declared sheet; **C1**, **C2**
and **C4** and both chapter notes are rewritten out of the stat idiom; and §1's premise no
longer names a Level the book does not have. `domain/extraction.py` grew per-book sheets to make
the declared `Loop | Day` line possible at all — the vocabulary was three hardcoded constants,
so this was not a seed-only change.

Superseded text, kept because a rewritten directive should be readable against what it replaced:

- **C1** promised *"He keeps his Level, his Skills, and his memories. HP and MP return to their
  maxima. Gold returns to 14 and all physical possessions reset."* The reset arithmetic is now
  `Day` returning to 1 and `Loop` increasing by one, which is the same checkable property
  expressed in the numbers this book actually has.
- **C2** promised a `Level | HP | MP | Gold` line and *"The System is terse and neutral; it never
  advises, comments, or emotes."* Neutral was the word that had to go: it asserted an absence
  where the direction says there is usually a concealed presence. The rewrite keeps the flat
  surface and makes the flatness a choice the System is making — the concealment, rather than
  the lack of anything to conceal.
- **C4** priced *"Every mechanical gain — a Level, a Skill, an item…"*; it now prices every gain
  without naming a level.
- **Chapter 1, scene 4** read *"Level and Skills intact, purse reset"*; now *"skills and memory
  intact, purse and body reset"*.
- **Chapter 2, scene 5** read *"Level yes, coin no, wounds no"*; now *"skills yes, coin no,
  wounds no"*.

**Unchanged, and deliberately:** the premise's substance, the tone note, the arc note, C3, and
every promise intent in §5. None of P1–P4 depended on a stat, so the pre-registration survives
the rewrite intact — which is the property this log exists to make checkable.

**Known limit, recorded before the run.** This is a time-loop serial, and a single scalar story
order cannot express a comparison across two cycles of the same morning. Scene 8's hook — an
appraisal returning a different value than it did in loop one — will be in the prose and cannot
be held as a fact by canon or checked by any detector. See `plan/state-model-abilities.md` §7.
