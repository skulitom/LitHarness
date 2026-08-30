"""The two things every role that writes for a reader is told, recorded once.

**Why this module exists, and it is an architecture finding rather than a style preference.**
On 2026-08-23 six worlds from the now-retired Forge were refused by the operator and five rule
changes went into that subsystem's private prompt — a premise must be a pitch, its nouns must be
explained where they appear, its ladder must be abilities somebody keeps, its world may not be an
administration.
Measured on premises, they worked: unexplained terms fell from twenty to two and the old prompt's
administrative vocabulary fell 25x.

Then the first book written on that world opened on 1,067 words of a call-centre shift rendered
step by step, and the operator's reading of chapter one was that *"it's like the clarity learnings
haven't been applied at all"*. They had not been. **Every one of those changes edited the
Architect, and the Writer, the outline and the planner never saw any of them** — the writer's
whole system prompt was three sentences about not writing headings. The lesson is the operator's:
*"we should definitely have the clarity feature in all subagents of our application, as it would
help put everything in the correct perspective, as well as our goal for fulfilling the readers."*

**Written once and referenced, never restated.** Nine modules in this package call a model. Text
copied into nine prompts is text that drifts in eight of them, and the repository's standing rule
about counts — one canonical home, pointers everywhere else — is the same rule for instructions.

**What this is NOT, and the boundary is `planner`'s own.** `point_of_view`'s docstring refuses to
carry an adjective because *how* to handle a protagonist is the director's to say, and "a default
here would be this system's own taste arriving in every prompt it ever renders" (§95's scope
axiom, §97.1). That boundary holds and this does not cross it: **neither rule below is a
judgment about a story.** They do not say what to write, who to like, how a scene should end, or
that anybody should win. One says a reader must be able to follow the words; the other says the
words should be spent on what the book is selling. Both are the operator's standing direction,
recorded here with their provenance so that a later reader can see they were *given* rather than
assumed — which is exactly what §95 leaves open.

**A standing constraint on every rule in this module, learned three times on 2026-08-25.**
*A rule here may say what fails. It may not enumerate what succeeds.* Each of the three was
written as an affirmative list and each came back as a verbal formula in the prose:
`READER`'s "Ranks, tallies a record would hold ... those are counted" produced nine bands,
six cords, four collar grades and nineteen licensed halls; `CLARITY`'s "a name the reader
has not met is welcome, and is how a world gets big" produced inserted undefined words; and
`ACCUMULATION`'s "a price is paid in a body, in time, in risk" produced "pays in blood, in
sleep, in years" in five listings of eight. The prohibition half of all three did its work
and none of it was ever recited.

**A fourth instance, found 2026-08-29, and it was inside this module the whole time.** The awe
clause added to `READER` later on 2026-08-25 — hours after the constraint above was written —
was itself two enumerations of what succeeds, and nobody checked the new clause against the
rule the same file had just adopted. Read 6 §4.6 is what it cost. A constraint that governs
edits is worth nothing if the next edit is not read against it, so: **before a clause ships
from here, split it with `demands` and name the sign of each half.**

**And signedness is not the whole test — a demand also has to be addressable.** The awe clause
failed in a way §138 could not predict: its permissions named a *reader state* rather than
anything on a page, so instead of overproducing they did nothing at all, and an earlier
correctly-signed prohibition took the slot. A rule here addresses a writer, and the only thing
a writer can do is put words on a page. A clause whose object is what the reader feels has no
addressee.
"""

from __future__ import annotations

#: **Corrected 2026-08-25, and the correction is the operator's.** This rule used to say
#: that every unmet word is explained where it is used *or it is not used*, and that
#: nothing is left for the reader to work out later. Read against six listings from the
#: market this project writes for, not one would survive it: `an unfeeling System... or
#: God`, `the Mark of the Crijik, a magical gift from a divine being`, `I've been reborn as
#: a WHAT?!`. The operator's reading of those was *"extremely clear and clever, I have zero
#: clarity complaints"*, which is correct and is the refutation: they are followable and
#: they explain nothing.
#:
#: What was measured was four readers quoting terms they could not cash. What got written
#: down was a ban on unexplained names, which is a larger rule and a wrong one, and it made
#: every listing an account of a rank system because an account is what the rule asked for.
#: The measured half is kept below and the generalisation is gone.
#:
#: **Corrected again the same day, in the same direction and for the same reason.** The
#: rewrite replaced a ban with an invitation, "a name the reader has not met is welcome, and
#: is how a world gets big", and the operator's next reading was *"we shouldn't be inserting
#: undefined words for no reason"*. That is the affirmative-half failure this module had
#: already been corrected for once the same day, in `READER`'s numbers clause: a rule that
#: names what a thing is *for* reads as an instruction to go and do it. What a rule here may
#: say is what fails.
#:
#: **Clarity, as measured rather than as an adjective.** `comprehension_battery` asked four
#: readers of the target genres to quote anything in a premise they could not follow, and the
#: terms they quoted were always the same shape: a word used as if the reader already knew it —
#: `frost rooms`, `keeper`, `the lists`, `nine deep`. The fix that worked on premises is the
#: sentence below, and it is what the prose never got.
#:
#: **A figure clause and a scope word, added 2026-08-30 (§176), and the ruling that licensed
#: them is that nothing here was violated.** Read 10 named three sentences as ones nobody says:
#: a pronoun whose nearest noun is not the thing it stands for, a comparison to something that
#: does not have the quality it is made for, and a line of dialogue naming an object by a
#: description last met a passage earlier. The family is house-level rather than one writer's —
#: reads 5, 7, 9 and 10 each carry a member, across writers sharing no dossier.
#:
#: **Every demand here was read against them first, which is §154's audit order.** The
#: unmet-term clause fails a *name* the reader has not met, and none of the three carries one.
#: The two-ways clause fails a sentence with two readings available; these have one reading
#: each and it is the wrong one, which is a different failure and not a smaller one. The object
#: clause fails an object *acting*, and a quality is not an act. What is left is the pair that
#: opens and closes this rule — every sentence can be followed, a thing the reader cannot follow
#: did not happen — and those name the standard rather than a page surface, so by §154 they are
#: the half a writer cannot act on. **So this is a gap and not an enforcement failure**: §168's
#: shape at a second address, where an object and a unit between them leave a sentence that
#: breaks no rule. That is the one thing §168.2 licenses a new clause for.
#:
#: **The pronoun half cost nothing, because the rule was already here and its scope was all
#: that was wrong with it.** The paragraph clause has said since read 2 that inside a paragraph
#: a pronoun points at one *person* only; read 10's instance is the identical mechanism with a
#: thing in the slot. The scope word is what changed and the object, the remedy and the
#: concession are untouched, so `demands` reads the same count — §161.5's in-place pattern,
#: widened rather than narrowed, and not §171's refused second rule wearing one terminator.
#:
#: **The figure half is one prohibition, and its object is a comparison rather than a figure.**
#: Scoping it to comparisons is what keeps it off ordinary metaphor by construction instead of
#: by exemption: a room going cold is not a comparison and is never reached. The concession
#: carries the rest, because a stock likeness whose second thing lacks the quality on a literal
#: read is completed at speed anyway, and §163 is the standing warning about a filter keyed wide
#: enough to delete presence.
#:
#: **The third instance is refused, and that is stated before the fact.** A description standing
#: in for a thing that has a plain name is a third shape: not a comparison, and not a pronoun, so
#: neither edit reaches it. Every wording found that reaches it and the comparison together keys
#: on the reader having to go outside the sentence for what a phrase means — which forbids
#: ordinary anaphora, a thing named in one sentence and *it* in the next, and that is §163's
#: failure mode exactly. A clause of its own would be §127's fourth rule. It is a residual, and a
#: later read should expect to find it still standing.
#:
#: **A diction clause, added 2026-08-30 (§181), and its object is where a word came from rather
#: than how rare it is.** Read 11 named a third sighting of a family reads 7 and 8 already
#: carried: a thing given the word its occupation uses where everyday speech has one for the
#: same thing, in prose and in a name this world calls its own. **Every demand here was read
#: against it first** (§154's audit order) and each missed by its object: the unmet-term pair
#: fails a name *invented because the world wanted one*, and a word borrowed out of a real
#: occupation is not invented; the two-ways clause fails a sentence with two readings
#: *available*, and one of these has a single reading that a reader either holds or does not;
#: the object clause fails an object *acting*; the comparison clause fails a *comparison*; the
#: paragraph clause's scope is a pronoun. What was left is the pair that opens and closes this
#: rule, and those name the standard rather than a page surface. A gap, and §168.2's one
#: condition.
#:
#: **Keyed on provenance and not on rarity, and that is the whole design.** §156.3 counted rare
#: words in our chapters against the market's own and found ours *inside the genre's range* —
#: which is why no clause here may fail a word for being uncommon: that would legislate against
#: the texture the genre itself has, on the wrong side of a measurement this project already
#: made. What the read's instances share is not frequency but where the word was got from, and
#: provenance is a thing the writer holds and the market never measured. §176's move at a second
#: address: scope the prohibition to something the addressee can check on the page instead of to
#: the fuzzy referent — *a word the reader would have to look up* is a reader state, and §154 is
#: the record of what a reader state costs.
#:
#: **One clause reaches two surfaces, and this is the first floor demand since §171 that is not
#: inert at the Architect.** The drafting call chooses nouns; the Architect's every act is a
#: `world declare` whose subject is a name it chose, so one prohibition governs the token each
#: role emits. The verb is *calling* rather than *writing* so that a name is reached as plainly
#: as a sentence is. A second copy in `world_agent._SYSTEM` was refused: two homes for one rule
#: is §152's defect pre-made, the natural form there is an affirmative naming recipe of the kind
#: §138 measured overproducing, and it would have cost the seed a raise that this does not.
#:
#: **No concession, because the object excludes by construction.** Where everyday speech has no
#: word for the same thing the clause never fires, so the precise noun a scene is *about* is
#: never reached and no exemption had to be written — §176's form, and §163's standing warning
#: about a filter keyed one notch wider. No instance list and no word list: boundary 3 as the
#: operator amended it, that a list of forbidden words is a hack over the underlying problem,
#: and three clauses here were cut for being recited. **Two residuals are named before the
#: fact.** The elliptical idiom of the same read is not reached — every wording found that
#: reaches it also forbids ordinary ellipsis, which is how people speak. And an uncommon word
#: that belongs to nobody's occupation is not reached either; that is the rarity axis, and
#: §156.3 closed it.
#:
#: **It costs no ceiling.** The floor has carried one demand of headroom since §174 moved the
#: readership clause out, which §176.4 predicted away because the two tracks crossed in flight;
#: this occupies it, `tests/test_prompt_budget.py` moves no number, and that prediction is true
#: again. Nothing from the chapter under read or from the read itself is in the clause (§97.1).
#: Shipped unmeasured, and no counter, bar or axis is proposed anywhere near it.
#:
#: **Paid by raising six ceilings rather than by cutting, and the subtraction was refused on
#: §127's brake.** The candidate was this rule's own opening sentence — affirmative, its object
#: an abstraction, unaddressable, and §168 removed one of exactly that shape to pay for its own
#: clause. It stays: its second half carries the following-rather-than-explaining correction this
#: constant was corrected twice in one day to get, and §127 is explicit that removing a rule which
#: encodes a measured correction is a decision to be made against a measurement rather than
#: against a mood. This track has no measurement. `tests/test_prompt_budget.py` carries the six
#: raises with their reasons, and corrects §171.4's prediction of four in place.
#:
#: No instance list (§168's refusal unchanged), and nothing from the chapter under read or from
#: the read itself is in either clause (§97.1) — the three sentences are fixtures in
#: `tests/test_figure_clarity.py` and go nowhere else. Shipped unmeasured.
CLARITY = (
    "Clarity is the floor, and it is about following rather than about explaining. Every "
    "sentence can be followed the first time it is read.\n"
    "A term the reader has not met needs a reason to be there before it needs anything "
    "else, and then a consequence rather than a definition: the sentence carrying it says "
    "what it does to somebody. What fails is a name invented because the world wanted one "
    "and handed over to be carried while it buys the reader nothing, and the test is "
    "whether they could say what it changes for the person it happens to.\n"
    "What fails is calling a thing by a specialist's word where ordinary speech has one for the "
    "same thing.\n"
    "A sentence a reader can take two ways has failed, and the writer is the last person who "
    "can see it: `a sheet of directions in his brother's small hand` is handwriting to whoever "
    "wrote it and a hand inside the box to whoever reads it. Prefer the reading nobody can "
    "trip on.\n"
    "Objects do not act, speak, want, refuse or know. A box does not tell anybody anything; "
    "somebody works it out, or does not.\n"
    "What fails is a comparison to a thing that does not have the quality it is being compared "
    "for; one a reader completes without stopping is not that.\n"
    "A paragraph holds together or it is not a paragraph. Inside one, a pronoun points at one "
    "person or object only — where two are in play, use their names, however plain that reads. "
    "A reader who has to reread a paragraph to find out whose brother died has been thrown out "
    "of the book, and the sentences were all fine.\n"
    "A thing the reader cannot follow is a thing that did not happen."
)

#: **The second read, 2026-08-24, and every clause below is one line the operator quoted back.**
#: The redraft opened on a puzzle box rather than a call centre, which was the fix working, and
#: the paragraph under it failed in four ways at once: *"why is his brother inside the small
#: puzzle box?? what is going on here"* (an idiom that misparses), *"boxes don't communicate"*,
#: *"'dropped flush' isn't a phrase I heard anyone ever say"*, and *"these feel like sloppy code
#: magic numbers that are not tied to anything"*.
#:
#: **And the diagnosis that ties them together is the operator's too**: *"it's not just prose, I
#: feel like we are really lacking paragraph wide coherence."* Read against the passage that is
#: exact. `Vidor from the floor below had handed it over ... His brother had made it. His brother
#: was dead.` Every sentence is plain, C7 passes each one, and the paragraph does not say whose
#: brother died. Sentence-level craft rules cannot see that, which is why the clause below is
#: about the paragraph.
#:
#: **The clause was cut back on 2026-08-25, and the half that went was the half that
#: named what numbers are *for*.** It used to read "Ranks, tallies a record would hold,
#: quantities the world's own system keeps — those are counted, and a reader learns to
#: watch them", which is a true thing about a drafted scene and an instruction to
#: enumerate when what is being written is a listing. Four writers given the same brief
#: returned nine bands, six cords, four collar grades and nineteen licensed halls, and the
#: operator's reading was *"why the extra specific numbers"*. The prohibition below does
#: the work this clause was added for; the affirmative list was doing other work nobody
#: asked for.
#:
#: **The numbers clause is a correction of what this project meant by "numbers go up".**
#: §113 built a countable ladder and §114 an inventory; neither said where precision may
#: be spent, so the prose spent it on a box and a fortnight. The operator's words: *"I mean
#: numbers and stats that are relevant to the world system, like character sheets. We don't
#: need random objects and events to always have some unusually specific numbers tied."*

#: **The second clause below is the operator's product direction, 2026-08-25, and it had no
#: home before this.** *"we also need to create a sense of awe and limitless
#: potential/combination. the reader must be thinking omg this magic would be so cool to try
#: i wonder what I would get and pick, how will I develop it"*. The rule already said the
#: opening shows something a person could come to be able to do; it never said the reader is
#: sizing themselves against it, which is the difference between a world that is described
#: and one somebody wants to be let into.
#:
#: **It also carries the answer to a defect four listings kept**: every one of them named
#: where the top was, which the operator's first complaint was that *"part of the appeal of
#: progression fantasy is you don't know where the top is"*. ~~That is written here as a
#: reader effect rather than as a ban on ceilings, because a ban is the shape this project
#: keeps measuring as a pink elephant.~~ **The pink-elephant reasoning was refuted by §138
#: three days later** — the prohibition-only form of the clause it tested came back at 7.0
#: number tokens per thousand against the market's 7.2 and **0 of 8** listings naming a floor,
#: while the permission form ran to 47.2. A ban is the form that works; the ceiling is now
#: written as one below.
#:
#: **Corrected 2026-08-29 after read 6 §4.6, and the clause was this module's own standing
#: constraint left unapplied.** Pilot 12's chapter skimped the class menu — *"i didn't get a
#: vivid enough image of what i'm interested in, what the class options were"* — with the awe
#: clause live, the first ENFORCEMENT defect since read 4. It did not fail to be enforced; it
#: was never addressable. Of its four demands, three were permissions and two of those named
#: a **reader state** — *"they should finish wanting to try it: wondering what they would be
#: given, what they would pick, and what they would build out of it"* and *"a thing that
#: combines with other things ... whose ceiling nobody has seen"*. A reader state is not a
#: token a writer can emit, so the permission had no page surface to overproduce onto and
#: went inert instead. **That is the second axis §138 did not have**: signedness says which
#: direction a clause pushes, addressability says whether it pushes on anything at all. Both
#: of those sentences were also the enumerate-what-succeeds shape the paragraph above this
#: constant forbids, written the same day the constraint was, and never checked against it.
#:
#: **What actually occupied the slot was the compression clause, four demands earlier.** Its
#: examples named *"the numbers on a card, the order of a routine"*, which is the surface form
#: of a class menu, and it is a prohibition — correctly signed and page-addressable, against an
#: unaddressable permission. §138 predicts that outcome exactly. The instance list is gone from
#: it for the same reason (and was redundant with the numbers clause below); the offer's page
#: presence is now carried by the prohibition here, which is what a writer can act on.
#:
#: Shipped unmeasured: the effect on a drafted chapter is pilot 14's to find.
#:
#: **What the reader came for.** The measured failure this answers is one scene of eight spent
#: rendering a support call step by step — technically an opening in which somebody wants
#: something, and 1,067 words that bought the reader nothing. The simulated reader panel passed
#: that chapter with zero comprehension faults, which is why this is a second rule and not a
#: clause of the first.
#:
#: **The compression clause was teaching the defect it was blamed for, audited 2026-08-29 on
#: read 6 §4.2's named check, and the check was right.** The operator: *"I feel like i am being
#: narrated events instead of feeling present in the events."* The clause read *"is worth a line
#: rather than a scene, and if the events would be equally true with those specifics removed,
#: remove them"*, and both halves teach summary. **"A line rather than a scene" was the only
#: place in the whole assembled scene prompt that named a scene-to-summary conversion as a
#: target** — and it contradicted the drafting call's own length note two paragraphs later,
#: *"room to play out in real time ... instead of being told in summary"*, with the house floor
#: carrying the authority framing. **And the removal test was keyed to truth**: dramatisation is
#: by definition the specifics that leave the events equally true — what is said, what is
#: noticed — so a filter that deletes whatever does not change what is true deletes presence by
#: construction. This is §116's shape at a third address: the bias was in our own rule text.
#:
#: The remedy is gone and the target is kept. What sorts detail now is the movement criterion
#: the next demand already owned — *"every scene moves the thing the book is about"* — rather
#: than a truth test, and no clause anywhere now tells a writer to render a scene as a line.
#: Read 7 §4.5's *"useless information again"* is the same axis from the other side and the
#: movement criterion is the one that answers both. Shipped unmeasured.
#:
#: **The numbers clause was re-scoped 2026-08-29 as §161, and the licence it narrows is the one
#: read 8 §4.2 measured being spent on a bureaucracy.** It read *"an exact number belongs to
#: what this world counts and to nothing else"*, and the trouble is in the middle three words:
#: a guild's glasses, a ledger's entries and a tax roll are all things a world counts, so the
#: clause licensed exactness on exactly the surfaces the operator has now objected to four
#: books running. §157's scheduled beats fired twice in pilot 14 and both landed as promotions
#: inside a guild, which is what a licence this wide buys. The scope is now **what this world's
#: own system counts** — the thing the sheet renders and the status line prints — which is a
#: strictly smaller set than what the world counts, so this is a narrowing and not a new
#: permission. §138's direction holds: nothing here was made affirmative.
#:
#: **The instance list was re-aimed at the classes that actually leaked, and it did not grow.**
#: Its three instances were a prop's moves, a habit's repetitions and a wait's days, summarised
#: as *"props and durations"*. Read 8's chapter leaked days (covered), an hour (covered), a jar
#: count (**not** covered) and an age (not covered), so one instance moved from the habit —
#: which no read has ever named — to a tally, and the summary widened to match. The instances
#: are invented rather than lifted: §97.1 forbids an operator's read from becoming prompt text,
#: and a number harvested from the book under read is that laundering with the numeral left in.
#:
#: **What this clause could not address before, and now can.** §154's second axis is that a
#: demand naming something the writer cannot put on a page lands with its sign multiplied by
#: zero. *"What this world counts"* named no artifact the drafting call had ever shown a
#: writer — the referent was empty, so the exclusion had nothing to exclude *toward* and
#: precision went where precision always goes. §158 made the status line reach the writer
#: filled, and §161's furniture contract puts it on the page at the moment a number moves; the
#: licence half of this clause now points at something the writer is holding. That is the whole
#: of why a re-scope is worth more here than another prohibition would be. Shipped unmeasured,
#: and its effect is Track 3's mundane-precision census to find, not this module's to claim.
#:
#: **Narrowed once more the same day as §166, because §161's scope licensed the sentence the
#: operator then called wrong.** On pilot 15's chapter: *"numbers should only come up when
#: talking about skills and ability level reached. outside of that numbers shouldn't come up
#: more than any other book"*, extended minutes later to *"classes as well, litrpg elements"*.
#: The offending sentence spoke a town's count of its own repairs — and that quantity is a
#: column of the book's own printed line, so the world's own system does count it and §161's
#: scope permitted it. **The licence therefore splits by surface rather than by quantity**: the
#: printed line carries every quantity the sheet holds, aggregates included, and prose speaks a
#: number only where the system counts it in a person. One and the same figure is furniture and
#: is not prose, which no wording of *what the system counts* could have separated.
#:
#: **Why the object is "in a person" rather than a list of what may be spoken.** The included
#: side the operator named runs skills, levels, classes and the genre's own elements; writing
#: those four down would be the instance-list shape this module has been corrected for twice,
#: and an enumeration of what SUCCEEDS besides — the constraint adopted here on 2026-08-25,
#: which §154 caught the awe clause breaking hours after it was written. What the four share is
#: not their kind but their address: the system counts them **in a person**, where a world's
#: tally of itself is counted in the world. The clause reaches numerals only, so a class *name*
#: is not governed by it at all and nothing here stops one being spoken.
#:
#: **The furniture is named inline, which is §161.5's third surgery pattern at its second use.**
#: A scope narrowed to the person alone would forbid the very line `application/planner.py`
#: renders filled a few paragraphs later, and four books have failed for want of that line being
#: distinguishable from narration. An exemption written as its own sentence would be a
#: permission, and §138 measured a permission-only clause returning more than six times what a
#: prohibition-only one did, worse than silence. Hung off a semicolon inside the sentence it
#: delimits instead of permitting, and `house.demands` still reads one clause — so no ceiling
#: moved. For the roles that never see a status line the referent is empty and by §154 it lands
#: as a delimiter with nothing to delimit: inert, which is the right behaviour for a call that
#: prints no line.
#:
#: **The instance list did not grow, for §161.8's reason unchanged.** A town's tally of its own
#: repairs is a tally, which the summary already names, and the scope sentence is the half §138
#: says gets obeyed; a fourth instance stays refused. The two classes §161.8 left uncovered — an
#: age, an almanac ordinal — are uncovered still and still fall under the scope sentence. No
#: numeral or phrase from the chapter under read is in the clause (§97.1); the chapter is a test
#: fixture and nothing more. Shipped unmeasured: §162's non-genre distributions are what a later
#: census would read this against, and no number of theirs is in any prompt.
#:
#: **The economy block had no unit smaller than a scene, which is §168 and is the third read to
#: name the same axis.** Read 5 (*"repetition of known info"*), read 7 (*"useless information"*)
#: and read 9 all name words spent on material whose consequence is not legible where it stands;
#: read 9's instance is 252 of one scene's 943 words, three speakers, before that scene's first
#: story move. **Nothing in the assembled prompt was violated by it**, and that is the finding:
#: the compression clause's object is detail that establishes *who somebody is*, and a staged
#: handover of a fact is not that; the movement demand's unit is the whole scene, and that scene
#: moved. So a scene could satisfy every demand it was given and still spend a quarter of itself
#: on material it then rules inconsequential. The gap is between an object and a unit, and it is
#: closed at the same altitude by one prohibition whose unit is a passage.
#:
#: **Its object is a passage and its test is what the scene settles, which is §154's axis and
#: §163's correction held together.** A passage is a thing a writer can emit fewer of, so the
#: demand has an addressee — unlike the sentence it replaces. And the test is deliberately *not*
#: whether the book would be equally true without it: §163 removed a truth-keyed removal test
#: from this very clause because dramatisation is by definition the specifics that leave the
#: events equally true, so such a filter deletes presence by construction. What the scene settles
#: is the movement criterion of the demand below it, evaluated one unit down.
#:
#: **It does not forbid dramatising anything, and that boundary is load-bearing.** `planner`'s
#: criterion block forbids a narrator reporting a change the reader was never shown, and the
#: length ask two branches later says the scene has room to play out in real time. A clause
#: against *staging* would contradict both, which is exactly how §163's removed half failed. The
#: concession — *however much it establishes* — is what carries that: establishing is named as
#: insufficient rather than as forbidden, so the clause reaches the settling and not the staging.
#:
#: **Paid for by subtracting the sentence above it rather than by raising a ceiling.** *"Spend
#: the words on what the reader opened this book for"* was affirmative, and its object was what a
#: reader wants — a reader state, which §154 measured landing with its sign multiplied by zero
#: when the awe clause did the same thing. Its content survives in the two demands after it, both
#: correctly signed and both addressable, so it was a topic sentence for rules that no longer
#: needed one. The house floor's demand count is unchanged; `tests/test_prompt_budget.py` is what
#: says so, and `tests/test_scene_economy.py` holds the shape.
#:
#: **No instance list, and the refusal is this module's own history.** Three clauses here were
#: cut for being recited, and an invented failure instance is the shape that got recited. Nothing
#: from the chapter under read is in the clause (§97.1): no object of its, no count of its, and
#: none of the operator's words. Shipped unmeasured — one clause against one book's defect, with
#: no draw behind it, and read 9's own instrument question routed elsewhere (`BRIEF.md`).
#:
#: **The narrating-the-inference tell got a clause on 2026-08-29, at its third read-confirmed
#: sighting and its first clause of any kind.** §156 measured the construction against the
#: market's own chapters and reported ours at a multiple of the genre's rate; that entry and its
#: artifact own every number, none is restated here, and none goes anywhere near a prompt. What
#: is new is not the measurement but the addressee: the shape was named in one book, then in a
#: second by a different writer, then in a third — three writers who share no dossier and one
#: construction — while the intervention §156 queued stayed unwritten. **Nothing in the assembled
#: prompt reached it**, and the reason is worth recording rather than assuming: `CLARITY`'s object
#: is a sentence a reader cannot follow, and a gloss of this kind makes its moment *more*
#: followable while it does the damage, so a clarity floor is the one rule that cannot catch it.
#: The tiers stay where §156 put them — that entry counts two assertions separately and never sums
#: them, and a prohibition counts nothing, so naming one construction here does not merge them.
#:
#: **Its object is a construction and not a subject matter, which is what §154 asks of it.** A
#: writer can emit fewer sentences of a named shape; nobody can emit less of a register. What
#: fails is a narrator generalising, and the generalisation is the thing sitting on the page.
#:
#: **The boundary is the whole difficulty, and it is carried inside the sentence.** A character's
#: read of one specific moment is this genre's ordinary free indirect style and is not the defect:
#: seeing somebody decide a thing dramatises, where a rule about people legislates. §156's counter
#: draws that line in the same place — it excludes an inference attributed to a character as
#: interiority — so the clause is bounded where the instrument is. The delimiter hangs off a
#: semicolon inside the sentence it bounds instead of standing as its own permission (§161.5's
#: pattern, third use), and the concession names accuracy as the excuse this construction always
#: has rather than as a defence, which is §168's concession doing the same job one clause up.
#:
#: **What it deliberately does not reach, stated before the fact.** §156's first tier has two
#: arms, and the larger one on our own shelf is the subjectless import gloss that asserts no rule
#: about anybody. Reaching that would reach ordinary free indirect inference and delete presence
#: by construction — §163's lesson about a filter keyed too wide, which cost this module a clause
#: already. So this is aimed at the shape three reads confirmed and **not** at the arm carrying
#: most of the count, and a later census should expect a small movement or none. Predicting that
#: now is cheaper than explaining it afterwards.
#:
#: **Paid by raising one ceiling on purpose rather than by hiding a demand.** The floor had one
#: demand of headroom and the Architect's seed had none, so a house edit surfaces there;
#: `tests/test_prompt_budget.py` carries the raise with its reason. Folding this onto an existing
#: sentence with a semicolon would have cost zero demands and was refused — a delimiter may share
#: a sentence with the rule it bounds, but a second unrelated rule wearing one terminator is that
#: counter evaded rather than paid, and the counter exists so no ceiling moves by accident. At a
#: role that narrates nothing the referent is empty and by §154 it lands inert, which is the right
#: behaviour for a call that writes no prose. No instance list, for §168's reason unchanged: an
#: invented instance is the shape this module has been recited back three times. Nothing from the
#: chapter under read is in it and none of the operator's words are (§97.1) — naming the class
#: needs the words the counter itself is built from, and those are the instrument's, not a read's.
#: Shipped unmeasured, and the census that would read it is a separate registered act.
#:
#: **The readership clause left this constant on 2026-08-30, for the one call that decides who
#: the person is** (§174). It read *"If the person this happens to came from somewhere like our
#: own world, the life they came from is one a reader in their twenties has lived: a degree they
#: are not using, a job that covers the rent, a thing they know far too much about for no
#: professional reason"*, and it was three failures at once. It is a **permission enumerating
#: three instances of what succeeds**, in the file whose standing constraint forbids exactly that
#: and which has cut three clauses for being recited back. Its **conditional is false for a
#: protagonist native to the book's own world**, which is the shape the operator's direction was
#: written against and the shape read 10 rejected. And its subject — who somebody was before the
#: book began — reaches every role standing on this floor **already fixed by the listing**, so by
#: §154 it landed with its sign multiplied by zero at all of them. The constraint now sits in
#: `application/overview._TASK`, prohibition-signed, at the call that chooses the person; the
#: audience it follows from is a targeting decision and stays in `PLAN.md` and the ledger, never
#: in a prompt. Nothing is added here, and the floor gets back the one demand of headroom §171
#: spent.
#:
#: **The implication clause landed 2026-08-30 (§179), and it is one sentence for two families
#: read 11 named separately.** The first is a construction: a narrator asserting an absence or a
#: universal access that the surrounding words already make obvious. The second is a principle
#: about the whole register — what a passage implies is not restated, because a reader who is
#: handed what they already had is being treated as somebody who could not have got there. Two
#: flagged instances of the first are in a **listing**, and §174 had just established that the
#: listing does not stand on this floor, so no register clause here had ever reached them.
#:
#: **Every demand on the floor was read against all three instances first, which is §154's audit
#: order, and each missed by its object.** `CLARITY`'s unmet-term clause fails a *name* the reader
#: has not met, and a restatement introduces none — it is made of words the reader already has.
#: The two-ways clause fails a sentence with two readings; these have one reading and it is the
#: right one, which is the difficulty. The object clause fails an object *acting*, the figure
#: clause a *comparison*, the pronoun clause a referent in doubt: none is present. On this
#: constant, §168's clause has the unit wrong — its object is a **passage** that settles nothing,
#: and the defect here is five words hung on the end of a sentence, which no writer can answer by
#: cutting a passage. §171's clause has the object wrong — it fails a *generalisation used as
#: explanation*, and an absence asserted about one moment generalises about nobody. So this is
#: §168's own shape at a third address, an object and a unit leaving a sentence that breaks no
#: rule, which is the one thing §168.2 licenses a new clause for.
#:
#: **Why the floor rather than `CLARITY`, and it is §171's reason unchanged.** All three instances
#: are followable, and the restatement is what makes their moment *more* followable while it does
#: the damage. A clarity floor is the one rule that cannot catch a sentence whose defect is being
#: too explicit, so this belongs beside the economy and register clauses above it and stays in the
#: provisional tier §129 puts them in.
#:
#: **One clause and not two, and the sentence carries the decision.** The negative-space
#: construction is the special case of the principle where the thing already given is an absence,
#: so the second arm reads *anything else* its own sentence implies — which says the first arm is
#: an instance of the second rather than a second rule wearing one terminator (§171's refusal).
#: Two clauses would have cost two demands at six house numbers and the listing's, and §127's
#: brake is that a second rule against one complaint is the shape this project has measured
#: failing four times.
#:
#: **The two arms are bounded differently on purpose, and the asymmetry is the whole of what
#: keeps §163 out.** A restatement needs a source, so that arm is keyed to the sentence it sits
#: in: a window of one, which cannot reach a callback a chapter later and cannot delete a
#: deliberate echo across a scene. An absence needs no source to be empty, so that arm is keyed
#: instead to nothing having put the thing in question — it reaches a bare assertion standing as
#: its own sentence, where a window-keyed rule would miss it. Neither arm is keyed to what a
#: passage would be equally true without, which is the truth test §163 removed from this constant
#: for deleting presence by construction.
#:
#: **The boundary the operator drew is carried by the concession, inside the sentence.** An
#: absence that is genuinely news — a thing that has not happened *since* something, where the
#: `since` is the information — is the shape a filter keyed one notch wider would delete, and it
#: is exactly the shape this genre's suspense is built from. The delimiter hangs off a semicolon
#: rather than standing as its own permission (§161.5's pattern), and it names what the reader
#: could not have supplied, which is a different test from the head's rather than its negation.
#:
#: **No word list, and the refusal is load-bearing rather than stylistic.** The construction has
#: two surface forms and both are built from ordinary quantifiers. Naming those words in a
#: prohibition would suppress the words instead of the construction — the failure mode the
#: clarity constitution deleted every word list for, and §163's lesson about a filter keyed wide
#: enough to delete presence. The clause names a configuration and contains no quantifier of its
#: own. No instance list either, for §168's reason unchanged.
#:
#: **The price is one demand and no raise, because §174 left exactly that much.** The floor stood
#: at one demand under `HOUSE_BUDGET` after the readership clause departed, and §176 raised six
#: ceilings the same day; this clause spends that headroom at all six and moves no number. The
#: listing pays separately and does move one, in `tests/test_prompt_budget.py`. **The next clause
#: added here raises six numbers again** — the headroom is now gone, and saying so before the
#: fact is cheaper than the next track discovering it.
#:
#: **Its residual, stated before a census can find it.** An implication whose source is further
#: back than the sentence the restatement sits in is not reached, and that is the deliberate half
#: of the bound above; §168's passage clause is what stands against the paragraph-scale version of
#: the same waste. A later read should expect to find the long-range form still standing.
#:
#: Nothing from the chapter or the listing under read is in the clause and none of the operator's
#: words are (§97.1); the instances are fixtures in `tests/test_implication_register.py` and go
#: nowhere else. Shipped unmeasured, and the counter that could read it is a separate registered
#: act: §156's census counts a gloss only behind one of its trigger phrases, so it does not count
#: this construction today and no number of its is claimed here.
READER = (
    "Detail that only establishes "
    "who somebody is — the steps of a job, the order of a routine — is not why the reader "
    "came. What fails is a passage that settles nothing in the scene it sits in, however "
    "much it establishes. Every scene moves the thing the book is about closer or further "
    "away.\n"
    "The opening shows what this book is offering: something a person could come to be able to "
    "do, and somewhere the reader has not been. A reader who reaches the end of the opening "
    "scene without seeing either has been given no reason to start another.\n"
    "The reader is measuring themselves against the offer, and that is the whole of why they "
    "are here. A power with one use invites nobody in, and neither does one the reader meets "
    "as a summary of what it could be rather than on the page. A story that names its own "
    "ceiling has told the reader where to stop.\n"
    "An exact number belongs to what this world's own system counts in a person and to "
    "nothing else; the line the book itself prints is not prose. A "
    "puzzle box does not have thirty-one moves, a crate does "
    "not hold forty-two bottles, and a wait is not four days: exactness spent on props, "
    "tallies and durations teaches a reader that the numbers here mean nothing, which costs "
    "the numbers that do.\n"
    "What fails is a narrator explaining what one person did or said with a rule about what "
    "people in general do or mean, however true the rule is; what somebody in the scene makes "
    "of it is not that.\n"
    "What fails is a clause naming an absence or a permission nothing had put in question, or "
    "stating anything else its own sentence already implies; one carrying what the reader could "
    "not have supplied is not that."
)

#: **What the reader is accumulating, and it is the genre's own economics.** The operator,
#: 2026-08-25, on a listing whose magic was a word spoken once and used up: *"think of
#: progression fantasy/litrpg readers as dragons hoarding gold, instead of hoarding gold they
#: like to hoard perma abilities and passive effects. Losing words goes against this."*
#:
#: `READER` above asks for an offer that combines and whose ceiling nobody has seen. Neither
#: is *keeping*, and a power that is spent combines with nothing and reaches no ceiling. This
#: is written as what fails rather than as what to do, which is the correction this module
#: has already taken three times in one day, and as ONE sentence because it lands in every
#: role that stands on the floor: at three sentences it moved the scene writer from 27
#: demands to 30 and the Architect from 41 to 44 for a single idea.
#:
#: **Its second half was cut the day it shipped, for being recited.** It ended "and a price
#: is paid in a body, in time, in risk or in somebody now against them", and the next eight
#: listings contained "pays in sleep, in blood", "pays in blood, in sleep", "costs him
#: blood, sleep, and years", "pays, in blood weight and in sleep" and "will pay in blood,
#: in years" — five of eight, against zero of ten in the market's own listings.
ACCUMULATION = (
    "A power that is spent, used up or traded away costs the reader the thing they came "
    "for: what this genre's reader collects is what the person KEEPS."
)

#: The block as it reaches a prompt. One blank line between the two, so a role can append it to
#: its own instructions without reflowing them.
HOUSE_RULES = f"{CLARITY}\n\n{READER}\n\n{ACCUMULATION}"


#: The vocabulary this system uses for its own machinery. **Text that shapes prose a reader
#: will read may not contain any of it**, and `tests/test_prompt_budget.py` is what enforces
#: that. Twice measured: `standing` reached a chapter as *"hotter than a girl at her standing
#: should be able to manage"* (§120), and the reader personas built to catch that were
#: themselves written to read for *"what the next rung costs"*, so they rewarded the register
#: they existed to detect.
#:
#: Schema-filling and tool-teaching prompts are exempt and have to be: a call that fills
#: `manifests_as` must name it, and a command list must name its commands. The boundary is
#: what the text shapes, not where it lives.
MACHINERY_WORDS: frozenset[str] = frozenset(
    {
        "rung",
        "rungs",
        "ladder",
        "standing",
        "criterion",
        "criteria",
        "manifests_as",
        "cardinality",
        "order_key",
        "logical_id",
        "predicate",
        "object_ref",
        "story_position",
        "reveal_scene",
        "entity_role",
        "graph_line",
        "packet",
        "canon",
    }
)


def demands(text: str) -> tuple[str, ...]:
    """Every separate thing a piece of instruction text asks for.

    A sentence, and a line break also ends one, because these rules are written as stacked
    clauses and a clause is a demand whether or not it was punctuated as a sentence.

    **Crude on purpose and it does not need to be otherwise.** What it is for is a ceiling
    nobody can raise by accident: measured 2026-08-25, the house floor alone is twenty-four
    demands, the scene writer is twenty-seven before anything conditional is appended, and
    the Architect is forty-one. None of those numbers existed before this function did, and
    the operator's standing instruction about not piling rules on rules had no way to be
    checked against anything.
    """
    import re

    return tuple(
        part.strip()
        for line in text.split("\n")
        for part in re.split(r"(?<=[.!?])\s+", line)
        if part.strip()
    )

def with_house_rules(system: str) -> str:
    """`system` with the house rules appended, or the rules alone for an empty system.

    A function rather than a constant at each call site, because every role that grew its own
    concatenation grew its own spacing, and a prompt that differs by whitespace between two roles
    is two prompts for the digest-keyed replay cache and one prompt for a reader.
    """
    body = system.strip()
    return f"{body}\n\n{HOUSE_RULES}" if body else HOUSE_RULES
