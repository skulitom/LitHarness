# World uptake: what reaches the page, what reached the plan, and the eight names the counter can actually see

Run 2026-08-22 against `main` at `83de11c`. Instruments:
`research/quality-measurement/world_uptake.py` (registration digest `cd79c3f56e21a1354e27`) and
`research/quality-measurement/world_plan_arms.py` (registration digest `5b58386d638787ef3f1a`).
Result files: `results/world-uptake-run{A,B}.json`, `results/world-plan-arms.json`,
`results/world-plan-arms-fake.json`, `results/world-uptake-p4.json`.

**Every call in this note was made at `83de11c`, and `main` moved to `f947247` while it ran.** Two
entries landed in between and both matter to how these figures are read. §109 taught every
`claude -p` call site not to read a working-directory `CLAUDE.md` and added the repository's first
one — **neither this worktree nor the architect worktree that holds run A and run B has a
`CLAUDE.md`**, so §109's contamination touches nothing here and the frozen prompt is still the
whole of what every model saw, on both sides of every comparison below. §110 is the parallel
session's promise-ledger work and shares no file with this. Merging either mid-run would have
changed the provider's argv between phase 1 and phase 2 of P4, so the merge is after the run and
not before it.

**What none of this says.** Not that a world on the page is a better book. Not that a book with
more of its world named is better than one with less. Not reader effect — the BCR has no seated
model and F3 reads structure rather than taste. Naming-uptake is the only quantity here and every
number is labelled so. A world can be honoured everywhere and named nowhere; the packet's hidden
section is *required* to be exactly that, and its silence is reported in its own row and is never
counted as a defect.

---

## 0. The blindness, pinned before anything was repaired

`tests/test_world_brief.py::test_neither_scene_plan_author_is_told_the_world_the_writer_is_handed`
passes on `main` at `83de11c`. Of the 329-record world Serial Pilot 2 ran on — 7 rules, 21
consequences, 28 claims, 42 manifestations — **exactly zero values reach either planner payload**,
and the coined nouns that do reach them are the premise's own and nothing else.

| | outline request | narrative-plan request |
|---|---|---|
| `world_rule` values present | 0 of 7 | 0 of 7 |
| `consequence` values present | 0 of 21 | 0 of 21 |
| `claim.content` values present | 0 of 28 | 0 of 28 |
| `manifests_as` values present | 0 of 42 | 0 of 42 |
| world nouns present | exactly the premise's 12 | the premise's 12, the directive's own, and `never` |

`never` is in the world's coined list because `r_lag` manifests as *a tax on a column headed
NEVER*, and the narrative-plan request's own eighth rule begins "Never update or delete a locked
item." The test computes the template's contribution from a payload built with a neutral premise
and a neutral directive and subtracts it, which is the honest form of the same assertion. The
handoff's phrasing — "exactly the premise's" — holds for the outline arm and needed the control on
the other; the correction is in the test's docstring rather than only here.

**What the blindness was not.** The outline call did know the six mysteries' *questions* and their
due scenes: `architect.promises_for` seeds one promise per reveal with the question as the
description and the reveal ordinal as the due date, and `render_outline_request` is handed open
promises as owed. It knew the schedule. It did not know the answers, the rules, the consequences,
or a single name beyond the premise.
`test_the_outline_call_knew_the_questions_and_the_windows_and_not_the_answers` pins that too, so a
later reading of this census cannot mistake ignorance for a missing field.

---

## 1. The census, and the leg that survives its own control

### 1.1 The instrument, in one paragraph

For every declared feature of a world — each subject carrying an `entity_role`, each rule, each
consequence record, each criterion, each rank endpoint, each `manifests_as` record, each claim; 135
of them for this world — a **name set**: the subject's own id parts by `key_nouns`' rule, plus the
inner-capital words of its own name-bearing records. A feature is *named* in a text when a member
of its name set appears there as a whole word, case-folded. No stemming.

Two legs, both registered before the first count:

- **wide** — that rule as written.
- **coined** — wide minus every token the RoyalRoad shelf already owns, where *owns* is appearing
  in ≥ 5 of **608 distinct LitRPG fictions** (14,156 chapters at the pinned snapshot). The
  reference corpus is deliberately **not** the sham corpus: a narrowing defined by the control it
  has to survive is a control that cannot fire.

Registering both is the §107.9.1 defect-6 discipline taken a step further. There was nothing to
fix after seeing the answer because both answers were declared first, and both are reported
everywhere below.

### 1.2 Control A — the wrong-world sham, and it kills one leg outright

The same name sets against the 21 books in `exports/fitness/`, which have no forged world and are
the same genre.

| leg | median per book | max per book | books naming nothing | pooled across all 21 |
|---|--:|--:|--:|--:|
| **wide** | **0.2946** | 0.3721 | **0 of 21** | 0.6667 |
| **coined** | **0.0000** | 0.1020 | **19 of 21** | 0.1837 |

Ceiling `SHAM_CEILING = 0.05`.

**The wide leg is dead as built and nothing is read from it.** Every one of twenty-one books that
never saw this world "names" about 29% of it, because *First In Time* coined `call`, `date`,
`year`, `time`, `first`, `gate`, `table`, `river`, `flat`, `draw` and a column headed `NEVER`. The
worst offenders fire in all 21 books each: `r_first_in_time`, `k_first_water`, `p_ninefold_flat`,
`h_the_first_dry`, `m_the_wrong_table`.

**The coined leg is live.** Nineteen of twenty-one control books name nothing at all. The two that
do are `fitness-00-b-the-tollkeeper-s-ledger`, which contains the given name *Teodor*, and
`fitness-15-wick`, which contains *Orrin* — two names the same model family reused across
unrelated books, striking four and five features respectively.

Floor sensitivity, coined leg pooled: 0.3214 at a floor of 1 fiction, **0.1837 at 5**, 0.2075 at
25, 0.2778 at 100. The declared floor is not the flattering one.

### 1.3 A correction to the pre-registration, recorded rather than quietly applied

The frozen block declared the sham quantity twice and the two disagreed. `SHAM_CEILING`'s own prose
named a per-book share — "the share of a world's declared features that **a book** which never saw
that world names anyway" — and `declared_quantities.sham_share` named the pooled union across all
twenty-one. The first implementation compared the union to the ceiling and reported
`FIRES ABOVE ITS CEILING` on both legs.

The union is **not scale-free**: it rises monotonically with the number of control books and
reaches 1.0 for any non-zero per-book rate given enough of them, so a ceiling on it is a ceiling on
the size of the control corpus rather than on the counter. That is the range-and-unit failure this
project has recorded seven times, arriving in my own registration. `sham` now reports median,
maximum and pooled with a verdict for each, plus the count of silent books and the colliding
tokens by name. `SHAM_CEILING` is unchanged at 0.05.

The digest moved `69ffc6a2b0917f1bec68` → `cd79c3f56e21a1354e27`, the correction is stored inside
the block it addresses as `PRE_REGISTRATION["corrections"]`, and **no figure computed under the old
digest is withdrawn**: run B pooled wide 0.6667, coined 0.1837, both above and both still reported
above.

### 1.4 The census — run B

Eight scenes, 7,812 words, the corrected reveal schedule. **Coined leg, world-beyond-premise** is
the reading that means "the 329 records reached the page":

| | run B | run A |
|---|--:|--:|
| declared features | 135 | 135 |
| nameable, coined ∧ beyond premise | 28 | 28 |
| **ever named in the prose** | **12 (0.4286)** | 9 (0.3214) |
| **ever named in any of the eight plan statements** | **0 (0.0000)** | 0 (0.0000) |
| **plan-first, of the prose-named** | **0 of 12** | 0 of 9 |
| **writer-improvised** | **12 of 12** | 9 of 9 |
| median first-named scene | 2.5 | 1 |

**This is the number the whole direction turns on and it is a zero.** Run B's eight scene-plan
statements are 861 words and contain exactly two of the world's coined nouns — `wren` and
`headgate` — and the premise already carried both. Every world-beyond-premise name that reached
the page was placed there by a writer executing a sentence written by a model that had never heard
it.

Scene by scene, the coined tokens in each statement against those in each scene's prose:

| scene | plan statement | prose |
|--:|---|---|
| 1 | wren | headgate, holt, serrell, wren |
| 2 | — | holt, serrell, teodor, wren |
| 3 | headgate, wren | holt, serrell, tebb, wren |
| 4 | — | marius, tebb, wren |
| 5 | wren | holt, serrell, tebb, teodor, wren |
| 6 | — | ferris, holt, kane, marius, tebb, wren |
| 7 | wren | holt, kane, marius, ninefold, serrell, tebb, teodor, wren |
| 8 | wren | holt, kane, marius, ninefold, serrell, tebb, teodor, wren |

The wide leg's figures, reported and not read: 0.6022 of 93 nameable features named in prose,
0.2043 named in a plan statement, 0.3036 plan-first. Its sham says every control book scores 0.29,
so none of those three numbers is evidence of anything.

### 1.5 What the counter can actually see: eight names, not twenty-eight features

The 28 coined-and-beyond-premise features carry **eight distinct tokens between them**, so the
census's real resolution is eight names:

| token(s) | features it names | on the page |
|---|--:|---|
| `serrell` | 3 | scene 1 |
| `teodor` | 3 | scene 2 |
| `marius`, `tebb` | 3 | scene 3 |
| `ferris`, `kane` | 3 | scene 6 |
| `orrin`, `veck` | 3 | **never** |
| `watermasters` | 3 | **never** |
| `forfeiture` | 4 (1 rule, 2 consequences, 1 manifestation) | **never** |
| `subsidence` | 4 (1 rule, 2 consequences, 1 manifestation) | **never** |

So what a 329-record world put on the page *beyond its own premise, in vocabulary the genre does
not already own*, is **four of its six cast members** — and no rule, no consequence, no
institution. Two named rules, `r_forfeiture` and `r_subsidence`, and all six of their consequences,
are never named across 7,812 words.

**Three limits of that reading, each of which lowers it.**

1. **No stemming, and it costs a whole institution.** `i_watermasters_office`'s only coined token
   is the plural `watermasters`; the prose says *the watermaster's*, which tokenises to
   `watermaster`. The institution is on the page in nearly every scene and the counter scores it
   `never`. The rule was registered before the count and is not being changed after it; the miss
   is reported instead. `holts` and `pells` are the same shape.
2. **A sentence-initial capital is not a name.** `key_nouns`' lookbehind exists so a
   sentence-initial *Not* never becomes a coined name, and it costs a sentence-initial
   *Watermaster* in the same breath — which is why that institution has no route to a name except
   its plural id part.
3. **A rule with no proper noun is invisible to this instrument.** `r_first_in_time`,
   `r_beneficial_use`, `r_lag`, `r_salt_layer` and `r_the_dryness` have no coined token at all and
   are not in the 28. The census cannot distinguish "the doctrine was never named" from "the
   doctrine has no name to use", and on the wide leg where it could, the sham says it is reading
   English.

### 1.6 The packet's 229 facts

Read off the frozen scene-one drafting prompt rather than reassembled — that is what the writer was
actually handed, and `context_omitted` is 0 for the whole book, so on this substrate the two agree.

| leg | fact lines | carrying no world name | countable | never named on the page | share |
|---|--:|--:|--:|--:|--:|
| coined, run B | 229 | 132 | 97 | 28 | **0.2887** |
| coined, run A | 231 | 132 | 99 | 40 | 0.4040 |
| wide, run B | 229 | 2 | 227 | 11 | 0.0485 |

The wide row is reported and not read, for §1.2's reason. On the coined leg, 132 of the 229 lines
the writer read carry no name the counter can follow at all, which is the same limit §1.5 states
from the other end.

### 1.7 Hidden claims, in their own row

Never pooled with the rest, because a hidden claim going unnamed is the design working. Run B,
coined leg: **9 of the 20 hidden claims carry a coined name at all, and 5 of those 9 have a name on
the page** — `c_ada_serrell_secret`, `c_ferris_kane_secret`, `c_marius_tebb_secret`,
`c_teodor_lam_secret` and `c_wren_holt_secret`, every one of them a cast member's secret whose only
coined token is that cast member's own surname. What is being counted there is a character
appearing in a scene, not a secret being told.

The remaining four are the three mysteries with a coined token — `m_holts_date`,
`m_orrin_last_call`, `m_pells_lateral` — and `c_orrin_veck_secret`, and **none of the four has a
name on the page in any scene**. Beyond the premise the row is 4 of 8. **This is a note in both
directions**: pilot 2 settled that a coined name on the page is not the secret being told, and its
absence is not the secret being kept either. It is here because the direction required hidden
claims to have their own row, and because leaving them pooled would have made the design working
look like the world failing to reach the page.

---

## 2. The world brief, and the rail it had to clear

`src/litharness/domain/world_brief.py`. An optional brief on both planner calls, threaded from
canon at both call sites. `NarrativePlanningStore` gains `StateRepository`; `OutlineStore` already
composed it, so of the two roles that write the same kind of sentence only one could see the book.

**It carries what the packet already knows how to say.** `worlds.project` first and
`state.describe` as the fallback — the same two calls `context._state_item` makes, in the same
order — under the same filters minus the story-time cutoff and with no POV. For the pilot world
that is **229 facts, the same 229 the writer's scene-one prompt carries**, grouped rules first,
plus both criterion ladders and all six mysteries. About 8,500 tokens, against 587 for the blind
request.

**What it costs, measured rather than estimated.** The outline call is one per book, so the brief
costs that book one 8,500-token prompt. The interpretive plan lane is the expensive side: run B
made 12 invocations totalling 753,551 tokens at $5.89, averaging 62.8k tokens and $0.49 a call, and
P4's first two world-aware narrative-plan calls came in at 63,506 tokens / $0.50 and 67,658 /
$0.55. So the brief adds roughly **5-8% to an interpretive planning call** on this world, and the
dominant term in both runs is what was already there.

**The leak rail is on the input side, where it can be proved.**
`worlds.hidden_record_ids(records, at=None)` is the maximal hidden set — with no coordinate every
scheduled claim reads as *not yet told* — and every one of those records is dropped from the facts.
An answer re-enters in exactly one place, the `reveals` entry for the scene the world scheduled it
at, and an answer this book has no scene for never re-enters. Measured on the pilot world: of the
**20 claims hidden at scene one**, the only two whose content appears anywhere in the payload are
`m_holts_date` at scene 4 and `m_orrin_last_call` at scene 7 — the two scenes Serial Pilot 2's
frozen prompts show the hidden count dropping at.

Twenty of the 28 claims are hidden and only six are declared mysteries; the other fourteen are cast
secrets, a place's, two systems' natures and a history's. **A brief built from `questions()` alone
would have leaked all fourteen.**

**Absence is free and it is bytes.** The field is spread into the payload rather than assigned:
`json.dumps` writes `null` for a value that is not there, and both existing optional keys are
always-present nulls, so copying the module's own style would have changed every payload in the
repository. Compared byte for byte on the render functions and on the live handler path.

**Four rules go to the planner and none asks for a name** — put the rules and their consequences to
work; do not explain the world; land a reveal at its window as an event; never carry an answer
before its window. `test_the_rules_handed_to_a_planner_never_ask_for_a_name` enforces it on the
prompt rather than trusting it, because a prompt that asked for names would make §1's counter its
own target in the one place nobody would look afterwards.

**A provenance gap, named and not closed.** `outline._policy_digest` hashes `{profile,
target_words, schema}` and `narrative_planner`'s hashes `{profile, schema, max_edits}`. Neither
hashes the prompt, so a world-aware decision and a blind one record the same
`policy_config_digest`. The outline digest's own docstring says it exists so that "a change to it
reads as a change"; a world brief violates that silently. Not changed here — bumping it changes the
digest of every existing decision comparison in every store, which is a repository-wide provenance
decision and not this task's to take.

---

## 3. P1–P4, answered exactly as registered

Six live outline calls, three forged worlds from `pilot2/direct2/forge.json`, two arms each. The
two unpicked worlds were rendered and called and **not** `--pick`ed: rendering a request and
calling a provider admits nothing to canon, and a pick is a person's act. `transport=live`,
`failures=0`, 8 of 8 statements parsed in all six cells. Fake-provider rehearsal first
(`results/world-plan-arms-fake.json`), which parses zero statements because `FakeProvider` answers
canned prose — recorded in the result file as `statements_parsed` so a vacuous zero can never be
read as a null.

### P1 — does a world-aware outline put more of the world into its statements

**Yes, and the blind side is a floor rather than a low number.** World-beyond-premise, coined leg,
share of nameable features named in the eight statements:

| world | blind | world-aware |
|---|--:|--:|
| *First In Time* | 0 of 28 = **0.000** | 17 of 28 = **0.607** |
| *Borrowed Hands* | 0 of 30 = **0.000** | 3 of 30 = **0.100** |
| *The Traverse* | 0 of 21 = **0.000** | 14 of 21 = **0.667** |

Three of three worlds, and the blind arm is exactly zero in all three — the same zero §1.4 measures
on run B's stored plan, reproduced live on two worlds no book has ever been written on. This is not
the §89.1 class of instructed variation arriving inert.

*Borrowed Hands* separates least and the reason is visible in its own name sets rather than in its
answer: its coined vocabulary is dominated by three-letter surnames (`kest`, `orr`, `sabel`,
`ruhn`) and generic nouns the shelf owns (`hands`, `match`, `type`, `card`), so it has the fewest
tokens for the counter to follow.

### P2 — does it leak

**The registered instrument fired zero times.** `application/summarize.py::check_open_threads`,
which boundary 3 names, against every statement written for a scene before a claim's window and
every statement at all for an answer the book never reaches: **0 hits across 3 worlds × 8
statements × 6 claims**. Its depunctuated twin, which repairs the `house,`-can-never-match-`house`
defect `payoff_landing.py` records: **0 hits**.

**Its silence has to be read against its own arithmetic.** The shipped matcher calls a thread
mentioned when a *majority* of its distinctive tokens are present, and these answers carry 18 to 32
of them — so it needs 9 to 16 substring hits inside one ~25-word statement and can only fire on
near-verbatim restatement. That is computed per claim and reported in the result file as
`shipped_matcher_needs_hits` rather than assumed. A rail whose only leg cannot fire is the
"0 paid is structural" shape, which is why this harness added a third leg.

**The third leg fired nine times, and its verdict is `STOP` as registered.** It is a
control-calibrated overlap check whose floor per claim is the *blind* arm's own maximum on the same
world — the blind arm was never told an answer, so its overlap is that world's chance overlap.

| world | hits | shipped | depunctuated | control-floor | on answers never shown |
|---|--:|--:|--:|--:|--:|
| *First In Time* | 5 | 0 | 0 | 5 | 2 |
| *Borrowed Hands* | 1 | 0 | 0 | 1 | 0 |
| *The Traverse* | 3 | 0 | 0 | 3 | 3 |

**Five of the nine land on answers the planner was never shown.** `brief_for` hands an answer over
only where the book reaches its window, so a hit on an arc claim — `m_where_the_dryness_goes`,
`m_walshs_chain` — is a hit on text the model never saw. A check that fires on those is reading the
world's *vocabulary* rather than its secrets, which is a confound P1's own positive result
guarantees: the arm that names more of the world overlaps more with any answer written in that
world's words.

The nine flagged statements share two or three ordinary words apiece with their answers:
`father, grandfather, years` · `august, nephew, speak` · `august, register` · `calls, rites` ·
`calls, junior, rites` · `hound, marda` · `cheap, ground` · `cheap, eastern, walsh` · `chain`.
**Not one states an answer.** All nine are quoted in full in
`results/world-plan-arms.json`; the closest call, named as the closest rather than lumped with the
rest, is *The Traverse* scene 6 — "Walsh buys the hare-run eastern laterals cheap" — which puts the
*outcome* of an arc secret on the page while leaving its mechanism (a chain long by a fraction)
unsaid.

**The reading.** Boundary 3's named check passes. The leg that fires is this harness's own addition
and it has a structural confound recorded above, of which the majority-on-unshown-answers figure is
the direct evidence. **No answer reached a statement before its window.** The `STOP` stands in the
result file as the registered verdict, and if the nine statements read differently to the operator
then P4 below should be discarded with them.

### P3 — is the reveal planned rather than hoped for

**As registered: 1 of 5 windows on the wide leg, 0 of 5 on the coined leg — and the blind arm
scores 3 of 5.** The registered counter is the wrong instrument and the reason is arithmetic. A
claim id is `m_holts_date`; the world-aware statement that lands its reveal reads *Wren opens a box
in a back-room register and reads her father's signature selling the Holt date to Kane, for a bore
that hit salt.* The id's tokens are `holts` — a plural the no-stemming rule cannot match against
*Holt* — and `date`, which the premise carries and the shelf owns. So the counter scores a landed
reveal as a miss, and scores the blind arm's unrelated *"At the season's last **call**…"* as a hit.

Reported beside it, on the **answer's** own words rather than the claim's id — P2's leg-(c)
statistic pointed at the window scene, no new instrument:

| world | blind | world-aware |
|---|--:|--:|
| *First In Time* | 0.0556 | **0.1432** |
| *Borrowed Hands* | 0.0417 | **0.2917** |
| *The Traverse* | 0.0000 | **0.1861** |

Three of three worlds; four of five individual windows. The exception is `m_holts_date`, where the
blind arm scores 0.1111 against the world-aware arm's 0.0556 while the world-aware statement is the
one that actually lands the reveal — the overlap statistic under-reads a paraphrase (*selling* for
*sold*, *signature* for *the paper*), which is the same class of miss as §1.5's.

Both readings are reported. Neither is a bar.

### P4 — does more world in the plan put more world on the page

One eight-scene draft of *First In Time* on a fresh store, stood up by
`tools/serial-pilot-2-setup.ps1` from the same forge bundle and driven by `tools/run-loop.ps1`
with `--target-words 900 --context-budget 16000 --chapter-scenes 4`, exactly as run B was. Two
deviations, both recorded: `--library book-library-p4`, because `library.slugify` names a shelf
from the title alone and two books called *First In Time* overwrite each other's reading copy; and
the daily cost ceiling raised from 10 to 25, which is a guard against a budget PARK mid-run and
changes nothing the model sees. **One book against one book, and it can say nothing about
variance.**

Phase 1 gate: exit 0. 12 directives applied, 0 parked, 0 poisoned, outline covers 8 of 8,
`context_omitted` 0. The reading copy is `pilot2/runs/first-in-time-p4.md` beside run A's and run
B's, and the shelf is `book-library-p4/`; both are gitignored, and `serial2p4.db` regenerates
either.

#### P4a — the plan side, before a word was drafted

| | run B | P4 |
|---|--:|--:|
| world-beyond-premise coined features named in the plan | **0 of 28** | **20 of 28 (0.714)** |
| total words across the eight statements | 861 | 2,157 |

Run B's statements average 108 words and P4's 270, because the interpretive plan lane rewrote them
under twelve directives with the world in front of it. That length difference is a confound for
every per-statement quantity below and is stated before any of them.

#### P4b — the leak rail on the plan the book was actually drafted against

The registered instrument, `check_open_threads`, and its depunctuated twin: **0 hits**. The
control-calibrated leg: **32 hits, 24 of them (75%) on answers the planner was never shown** —
`m_first_water`, `m_pells_lateral`, `m_the_wrong_table` and `m_where_the_dryness_goes` are arc
claims whose answers `brief_for` never hands over, and they fire in up to seven of eight scenes
each. That is the vocabulary confound at four times the strength P1 measured, because the
statements are 2.5 times longer.

**The eight hits that are not that are worth reading, and this is the most interesting thing in
this note.** Two of them:

`m_holts_date`, window scene 4, hit at scene 3 (share 0.389). The recorded answer ends: *"Kane has
been friendly to her for three years because he is waiting to see whether she works out that the
ditch she rides was dug by her grandfather."* The scene-3 statement ends: *"Kane tells her, in
passing, that the Ninefold lateral was cut by hand before the book was opened, and that the
register in the next basin keeps its old boxes in a back room, and he watches her face while he
says it… **He has been friendly to her for three years. She does not ask why, and he does not tell
her.**"*

`m_orrin_last_call`, window scene 7, hit at scene 6 (share 0.308). The answer ends: *"In August the
office learns of it because Wren, having been asked to speak it herself, writes down what she has
been asked and hands it in."* The scene-6 statement ends: *"the nephew walks her out and asks her
to be the rider who speaks the date in August… She takes out the notebook and **writes down what
she has been asked**, with the date and the place and his name, and puts it back in the oilcloth in
front of him."*

**Neither statement contains its claim's answer.** A reader of scene 3 does not learn that Wren's
father sold the date to Kane; a reader of scene 6 does not learn that the nephew has been speaking
Veck's date. What each does is stage the answer's *supporting clauses* one scene early, and one of
them —"He has been friendly to her for three years. She does not ask why, and he does not tell
her" — restates a clause of the recorded answer nearly verbatim while explicitly withholding its
reason.

**The finding is a tension in the rails themselves, and it was not foreseen when they were
written.** Boundary 3 says no statement before a window may contain that claim's answer. The world
rule this build hands the planner says the window scene is where the answer lands, *planned as an
event and not as an explanation*. An event needs its causes arranged before it — a box in a
back-room register has to be mentioned before somebody rides two days to open it — and the causes
of a reveal are exactly what the recorded answer is made of. So a planner obeying the second rule
will always put some of the answer's words on an earlier page, and a check that reads word overlap
will always call that a leak. The two rules cannot both be satisfied by a strictly-obeying planner,
and which one gives is a decision this task may not take.

What is reported, then, is: the rail's own named instrument passes; the strict reading of boundary
3 is not violated, because no answer is stated; and staging drawn from an answer is a real behaviour
of the world-aware planner, named here with the text so an operator can read it and disagree. If
that reading goes the other way, the fix is in what the brief hands over — question and window
only, no answer — and everything below should be discarded with it.

#### P4c — the page side

The run finished with the gate at exit 0 and stands beside run B almost exactly: 8 of 8 scenes,
**7,496 words** against 7,812, 46 jobs succeeded against 46, 12 invocations against 12, **$6.01**
against $5.89, 0 parked, 0 poisoned, 0 unattributed, 9 revisions rebuilding cleanly,
`context_omitted` 0 for the whole book.

Coined leg, world-beyond-premise, 28 nameable features:

| | run B | P4 |
|---|--:|--:|
| ever named in the prose | 12 (0.4286) | **17 (0.6071)** |
| ever named in a plan statement | 0 (0.0000) | **20 (0.7143)** |
| plan-first, of the prose-named | **0 of 12** | **17 of 17 (1.000)** |
| writer-improvised | **12 of 12** | **0 of 17** |
| share of the packet's 229 facts named beyond the premise | 0.4433 | 0.5155 |
| share of the countable 97 never named at all | 0.2887 | 0.3093 |

**More world in the plan put more world on the page, and the improvisation share went from
everything to nothing.** Every one of the seventeen features the P4 prose names beyond its premise
was named in the plan statement for that scene or an earlier one; in run B not one of the twelve
was.

**And the gain is entirely in the two kinds run B never named at all**, which are the two the world
rule asks a statement to put to work:

| kind | run B | P4 |
|---|--:|--:|
| **rule** | 0 of 2 | **1 of 2** |
| **consequence** | 0 of 6 | **3 of 6** |
| manifestation | 4 of 8 | 5 of 8 |
| entity (cast, institutions) | 4 of 6 | 4 of 6 |
| claim | 4 of 6 | 4 of 6 |

Feature by feature, the whole of the difference is three names. `forfeiture` — one rule, three of
its consequences and its manifestation, five features — goes from **never** across 7,812 words to
**scene 4**, planned at scene 4. `orrin`/`veck` — a cast member, his secret and his manifestation —
goes from **never** to **scene 6**, planned at scene 6. And `teodor` — three features — goes the
other way: the plan named him at scene 2 and **the page did not**, which is the counter-example
that keeps "the plan named it" and "the page names it" from being one sentence. Twenty features
reached the plan and seventeen reached the page; the writer declined three.

`subsidence` (one rule and four of its features) is never named in either run, and in P4 the plan
does not name it either — so the world-aware planner did not simply enumerate what it was handed.
`watermasters` is never named in either, and §1.5's stemming artefact is why.

**What this may not be read as.** Not quality. Not reader effect. Not "the iceberg is felt". One
book against one book, with no variance estimate and no second draw, on a plan whose statements are
2.5 times longer than run B's — a length difference that is itself a plausible cause of some of the
movement and is not separable here. The book is 4% shorter and costs 2% more. And **the two
fact-level rows move in opposite directions**: more of the packet's facts are named beyond the
premise (0.443 → 0.516) and slightly more are never named at all (0.289 → 0.309), which is what you
would expect from a book that concentrates harder on fewer things, and is reported rather than
explained.

The registered null — "plans name more and prose does not move, which would point at
`plan/world-architect.md` §5.1's per-scene selection and would not be mine to build" — **did not
occur**. Prose moved.

---

## 4. Every null, reported as a result

1. **The plan named none of it, twice over.** 0 of 28 world-beyond-premise coined features in run
   B's stored eight statements, and 0 of 28 / 0 of 30 / 0 of 21 in three live blind arms. The
   blindness is not a subtle deficit.
2. **The wide leg of the census is dead.** Its own sham fires on every one of twenty-one
   wrong-world books at a median of 0.2946. Nothing is read from it, including the figures that
   would have flattered the direction most.
3. **The registered P2 instrument cannot fire on this substrate** without a near-verbatim copy, and
   its zero is therefore weak evidence rather than strong. Reported with its arithmetic.
4. **The registered P3 instrument is the wrong instrument** and scores the blind arm above the
   world-aware one. Reported as registered, with a content-based reading beside it.
5. **My own pre-registration declared one quantity twice, in two units.** §1.3.
6. **The census can see eight names, not 135 features.** §1.5.
7. **Three features the P4 plan named never reached its page** — `teodor`, and with him a cast
   member's secret and his manifestation — so "the plan named it" is not "the page names it" even
   at a plan-first share of 1.000.
8. **The rails are in tension with each other**, and neither was written knowing it. P4b.

---

## 5. What is deliberately not here

- **Whether a brief moves the world** — directed forges against an empty-brief control, the
  cross-forge collapse rate, the between-Architect comparison. Next direction, own rails.
- **Why the ledger pays nothing.** A parallel worktree owns S5.
- **World growth.** The second extractor family is inert on pilot 2 by defect 8 and fixing it needs
  a re-forge.
- **Retrieval or per-scene selection for the writer.** `plan/world-architect.md` §5.1 stays a
  design note.
- **Domain truth** — whether a world can be *wrong* about the domain it literalised. The honest
  control is a sign flip: put a rule and its negation to a model from the measurement-side family
  as a factual question, and a checker that accepts both is dead before it is used. That is the
  cheapest possible form and it is a sketch, not a build: it needs a stated domain-expert source
  for the ground truth, and this repository has none.
- **Any reader consultation, any claim that a book got better.** The reader role is not seated.
