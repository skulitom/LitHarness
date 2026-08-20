# The Writer roster: named professionals a Director casts, and the prior that says it will not work

**Written 2026-08-20, before any code in this design was written and before any writer had a
name.** Companion to [director-role.md](director-role.md), which owns the role that acts *before*
prose exists. This one owns the role that has been acting all along and has never had an identity.

---

## 0. What was asked

The operator directive, 2026-08-20:

> The director should have access to writers they select, and each writer should have a deep
> backstory. All professional writers, but with deep topics of interests, varied across many
> subjects.

Four claims, and they are separable — which matters, because they do not all cost the same and
they do not all face the same prior. **(a)** A Writer becomes a first-class named record instead
of an anonymous call. **(b)** A Director *casts* — it selects which writer drafts. **(c)** Each
writer carries a deep backstory. **(d)** The roster's variation is *subject expertise*, spread
wide, with professional competence held constant across all of them.

(a), (b) and (d) are cheap and buildable today. **(c) is the one that runs straight into this
repository's own measurement record**, and §2 states that before §3 designs around it.

---

## 1. What exists today: the drafter has no identity at all

The whole of the writer's self, in `application/planner.py:354`:

> "You are drafting one scene of a novel. Write only the scene's prose: no headings, no
> commentary, no summary of what you wrote. The context below is established and may be relied
> on; do not contradict it."

Everything else appended to that system message is mechanical rather than characterological: the
status-line example and its progression, `target_words`, and the feedback set from the
reader → writer loop. Nothing names a person, a career, a taste or a subject. There is not even a
genre — `genre` exists in the schema only as metadata on human library excerpts
(`adapters/sqlite_store.py:1626`), never on the drafter.

Every topical thing the writer knows arrives through the context packet
(`domain/context.py:269`): premise, locked constraints, open threads, established facts,
prior-scene summaries, the scene-plan line. That is a *book*-shaped input. The system has never
had a *writer*-shaped one.

The nearest existing thing is the Director's brief, and it is not this. A brief is upstream of the
plan: its directive goes to the narrative planner, which turns it into plan edits, and the writer
sees the result as scene-plan lines and locked constraints. **The writer never sees the brief.**

---

## 2. The prior against a backstory, stated before the design rather than after it

Two independent findings in this repository point at (c), and both were expensive:

- **Personas here are usually inert.** §89.1 measured `qwen3:14b` returning *one distinct answer
  vector across all four personas, byte-identical*. §83 found the register invariant to simulated
  phenomenology. §77 / §86.2 measured persona-to-passage sum-of-squares ratios of 0.0028, 0.0071
  and 0.0342 while changing *the question* by one word moved a rate ten points. A roster that has
  not been checked is §89.1 in a fourth costume — one writer in many hats, reporting the sampler
  seed.
- **Backstory specifically was tried and rejected on the reader side, for a named failure mode.**
  `research/quality-measurement/personas.py` opens with it: a persona described demographically
  ("a 34-year-old warehouse worker who reads on his commute") elicits *stereotype performance* — a
  model writing what it thinks that person sounds like — which is a different behaviour wearing
  the same words. The remedy adopted there was taste anchors on named works: something checkable.

**Neither finding forbids this design, and the distinction is the load-bearing one.** Both were
about a persona held to make a *judgment*, where inertness silently converts N opinions into one
and a stereotype converts a verdict into a performance. A writer makes no judgment. It produces
text, and whether two writers produce different text is directly measurable at no model cost
beyond the drafts themselves. So the prior does not veto the roster; it dictates **the shape of
the backstory** (§4) and **the gate that has to clear before any writer comparison is reported**
(§5, R2).

---

## 3. The design

### 3.1 The record

`domain/writers.py`, mirroring `domain/directors.py` closely enough that the divergences are
visible:

    Writer
      writer_id         content address over (name, dossier, interests, exemplar_digest)
                        — sha256, `wtr-` prefix
      name              provenance; "which writer drafted this book" must stay answerable
      dossier           the backstory: career, training, the work they have done, how they came
                        to it
      interests         an ordered tuple of named subjects this writer knows from the inside
      exemplar_digest   optional; digest of an own-generated exemplar. **Socket only** — see below
      note              operator annotation, never sent to a model

Content-addressed for the reason the Director is: editing one word of a dossier mints a different
writer, so a roster cannot drift under the books it wrote.

**`exemplar_digest` is in the addressed tuple from the first mint, and is left unpopulated**
(operator, 2026-08-20). The distinction it protects is between two kinds of id change. Populating
an exemplar later *should* mint a new writer — an exemplar changes what the writer drafts, and
that is identity, not drift. Adding the *field* later would instead re-address every writer that
already existed without changing what any of them does, which is a schema re-mint and is pure
loss. Including it now, canonically empty, buys the first at no cost and avoids the second
entirely.

**If exemplars are ever admitted, they are own-generated only.** Third-party prose in a dossier is
leak-audit class — it would ride in the system message of every scene call for a whole book, which
is the most-repeated text in the system and the worst possible place for text this project may not
commit. Stored by digest rather than inline for the same reason. Admission would sit directly on
R1's boundary: an exemplar is a demonstration of what good prose looks like, which is precisely
what a dossier may not assert, so admitting one is an operator act and not a build decision.
**Build the socket; do not populate it.** The decision to follow.

### 3.2 Where the dossier lands, and where it may not

**In the drafting system message, appended by `render_prompt`, ahead of the mechanical
instructions. Never in the context packet.** This is the same boundary `feedback` already
observes and for the same stated reason: the packet's contract is *"established and may be relied
on; do not contradict it"*, and a writer's biography is not a fact about the story. Putting one
under that heading is how a novelist's career becomes canon in the book they are writing.

**And the packet outranks the dossier where they meet.** A writer who knows metallurgy from the
inside is being asked to write *this* book, not a book about metallurgy. §6's contamination check
exists because that is the first way this fails.

### 3.3 Casting

`--writer <name>`, mirroring `--director` and off by default, because **no writer is the control**
and a change to drafting behaviour that could only be produced by editing code is an arm nobody
can reproduce.

Director casting — claim (b) — is deliberately staged second, and the open question is in §7. The
honest reading of `DIRECTOR_KINDS` is that casting is not currently expressible: a Director may
emit `PREMISE`, `ARC_NOTE`, `TONE_NOTE`, `CHAPTER_NOTE` and nothing else, and "use this writer for
this book" is none of them. Making it expressible is a new kind with its own containment
argument, because a Director choosing the writer is a Director acquiring a lever over prose,
which is the boundary `director-role.md` §2 exists to hold.

---

## 4. Deep in domain, shallow in demography

This is how (c) gets built without walking into §2's second finding.

**A dossier says what this writer knows and has done. It does not say who they are
demographically.** Not an age, not a hometown, not a commute. What earns its place is
*professional and topical*: what they trained in, what they worked at before they wrote, what
they have reported on or lived through in a subject, which questions in that subject still bother
them. That is deep — deeper than a paragraph of demography, and specific enough to change what
lands on a page — and it is the half of "backstory" that does not summon a stereotype
performance.

**Professional competence is held constant across the whole roster, per the directive.** No
writer's dossier says they are new, struggling, or bad at this. Craft is not the variable here.
The variable is *what this person knows the inside of*, and that is exactly what a novel can use:
a scene about a foundry, a court, a tide, a supply chain or a diagnosis written by somebody who
knows what is actually true there.

**Variation across many subjects, and the slate is examples rather than recommendations** — the
same status `directors.BUILTIN` carries. A first slate spread wide enough to make §5's
distinctness gate meaningful: field geology and high-altitude survey; military logistics and
supply; medieval agriculture and land tenure; marine biology and long-voyage fieldwork; orbital
mechanics and flight operations; forensic accounting and fraud; historical linguistics and
translation; epidemiology and outbreak fieldwork; ceramics and materials craft; competitive games
and the mathematics of them. Nothing here claims any of them is a good writer for any book; which
roster is worth running is an operator act, the way admitting a fixture family is (§84).

**Two of the subjects are deliberately *adjacent* to two others, and that is the load-bearing part
of the slate** (operator, 2026-08-20). A roster of ten far-apart subjects can only ask whether
binding happens at all; the answer would be a single bit, and **a far-pair pass has fooled this
project before** — §77's persona ratios looked like separation until the same measurement was run
against a question that changed by one word. Adjacency turns G2 into a *graded* reading: if the
dossiers bind, a far pair should separate more than a near pair, and if far and near separate
identically then what is being read is the label rather than the subject.

So the slate carries two neighbour pairs:

| anchor | neighbour | what makes them adjacent |
|---|---|---|
| field geology and high-altitude survey | **volcanology and eruption monitoring** | same earth-science field tradition, overlapping instruments and terrain; different hazard, different timescale |
| marine biology and long-voyage fieldwork | **estuarine ecology and fisheries survey** | same water, same sampling craft; coastal and applied against open-ocean and basic |

The prediction that makes this falsifiable rather than decorative: **far pairs separate more than
near pairs, and near pairs still separate more than a writer against itself.** A run where near
and far are indistinguishable is a run where the subject did not bind, whatever the far pair said.

---

## 5. The rails, each bought by a failure already on the record

**R1 — A dossier may name what the writer knows; it may not name what good prose is.** Inherited
from `directors.legal_brief` and enforced by reusing it.

> **Found while writing the first slate, 2026-08-20: every dossier is a small exemplar, whether
> anyone intended one or not.** The guard refused four of the ten example dossiers on the
> `em_dash` axis — not because any of them *said* anything about punctuation, but because
> `_CRAFT_INSTRUCTION`'s pattern matches the mark itself and the prose contained em dashes.
>
> That reads like a false positive and is not one. A dossier rides in the system message of every
> scene call for a whole book, so a dossier written with em dashes **demonstrates** em-dash usage
> on every draft; §83's finding is precisely that demonstration moves register where description
> does not, and §78's em-dash hypothesis is still VOID and under test. A dossier that instructs
> about the mark and a dossier that simply uses it reach the model through different channels and
> the second is the stronger one.
>
> This is exactly the boundary §3.1 draws around `exemplar_digest`, arriving early and by
> accident: an exemplar is prose that demonstrates, and a dossier *is already prose*. The slate
> was rewritten without the mark rather than the guard being widened. What it does not fix is the
> general case — a dossier still demonstrates *some* register, and R1's vocabulary check cannot
> see that. G2b is the reading that would detect it, which is one more reason it is worth
> splitting out rather than folding into a single verdict. A dossier is a lot of text going into
every drafting call, so one sentence in it about sentence rhythm, punctuation or how much
interiority to put on the page injects a prose axis into every prompt with no counter, no
validation and no reader behind it — bypassing `reader-judge-loop.md` §2.1's four-step admission
path entirely. `em_dash`'s own hypothesis is still VOID with the estimate leaning *toward* the
mark (§78.3), so a dossier saying "she never could stand a dash" would assert as premise the
thing the loop exists to test. The guard is a vocabulary check and not comprehension; a
paraphrase gets through, and no regex fixes that. Stated here rather than discovered later.

**R2 — A roster has to be earned, and the control is prose-side.** `writer_distinctness.py`,
built the way `director_distinctness.py` is built, but comparing *drafts* rather than directives:
K draws per writer on the same beat and packet, varying only the sampler seed; byte-identity
first because it is free and it is what actually happened in §89.1; then between-writer
compression distance against within-writer distance, using the distance `domain/craft.py` already
carries. The five readings carry over unchanged — `IDENTICAL`, `INDISTINCT`, `DISTINCT`,
`DISTINCT_NO_FLOOR`, `UNREADABLE` — and `DISTINCT_NO_FLOOR` matters more here than it did there,
because a deterministic provider makes within-writer distance zero and *"between exceeds within"*
is then satisfied by a single differing character. **No comparison between writers may be
reported until every pair in the run reads `DISTINCT` or `DISTINCT_NO_FLOOR`.**

**R3 — A writer never judges.** It drafts. It does not score a scene, select among candidates,
read its own reception, or hold an opinion about a draft that exists. A writer doing any of those
is a judge in a hat, and that frame is buried.

**R4 — A roster multiplies arms, and the α division is already pre-registered.** §61
pre-registration (5): if more than one book could have been reported, the confidence level is
divided by the candidate count. `director-role.md` §4 applies it to N directors. A roster is
multiplicative on top: **N directors × M writers is N×M candidate books**, so three directors and
a ten-writer roster is α/30, and §61's own sizing says what a thinner margin costs — at a true win
rate of 0.60 roughly 100–150 decisive judgments, at 0.55 it is 400–500, clustering inflating
both. **This is the expensive claim in the directive and it is worth being explicit about it.**
The way out is not to pretend the division does not apply; it is to fix the casting *before* the
book is measured and report that book, rather than picking the best of M afterwards.

**R5 — The packet outranks the dossier.** Established facts and locked constraints are the
director's word and the book's; expertise is the writer's flavour of attention, not a licence to
introduce material the book has not established.

---

## 6. What has to be measured, in order, before the roster is claimed to do anything

- **G0 — wiring.** Does the dossier reach the request and change its bytes? Fake provider,
  costs nothing, runs the day the code lands. This is what `director-role.md` §4's pilot
  established for briefs and it establishes exactly as little: the input arrives.
- **G1 — distinctness on a real model, *with the shuffle control in the same run*.** R2's control
  against a local model with a real sampler. If it reads `INDISTINCT`, the roster is decorative and
  the honest output of this whole design is that finding, reported as such. That is a real possible
  outcome and it is cheap to reach.

  **The shuffle-dossiers control runs here, not at G2** (operator, 2026-08-20). It was written
  into G2 and that was the wrong gate. Distinctness without shuffle-sensitivity is decorative:
  a roster whose writers differ from each other *and differ just as much when their dossiers are
  swapped between them* has shown that the drafting call varies with its system message, which is
  not news and is not what R2 exists to establish. Shuffled here, the two readings answer one
  question together — **does prose track the dossier, or merely the fact that a dossier is
  present?** — and it costs one extra set of draws at the cheapest gate rather than the dearest.

- **G2 — does the *interest* bind, and if so in which channel?** Split into two pre-registered
  readings rather than one verdict (operator, 2026-08-20), because they can come apart and a
  single pass/fail would hide which one moved:

  - **G2a — content binding.** Does the subject change *what the writer attends to* — what gets
    noticed, named, measured, worried about on the page? Read through E6 "name the difference",
    the one channel that survived §87–§89, and it must *locate* the difference rather than merely
    prefer a side.
  - **G2b — voice binding.** Does the dossier move *register* in z-space — the same measurement
    `voice-binding` already runs, on the same footing.

  **Prediction registered before the run: G2a binds, G2b is inert.** Per §83's
  description-versus-demonstration finding — a model told *about* a way of being produces the
  content that description implies while its register stays where it was. A dossier says what this
  writer knows, which is a description; it demonstrates nothing. **Both outcomes are informative
  and neither is a failure of the design.** G2a binding with G2b inert is the predicted result and
  a usable roster: writers who attend to different things in the same book. G2b binding as well
  would be a genuine surprise and would put §83 in question, which is worth more than a
  confirmation. G2a inert would mean the subject never reached the page and the roster is names.
- **G3 — contamination, which is a defect and not a feature.** Does a writer deep in marine
  biology drag tides and salinity into a book that established neither? Measured against the
  packet's own facts, and a writer that fails it is a writer that outranks canon, which R5
  forbids.
- **G4 — is any of it worth anything to a reader?** Blocked on the same missing readers as
  everything else, and it costs R4's α division when it unblocks.

**Sequencing, recorded as a constraint on how G4 is bought rather than as a task** (operator,
2026-08-20): any real-book contact for the roster is **G4-class and rides the next fitness-book
batch**, never bespoke drafting commissioned for this design. One spend then feeds BCR, F3's
own-generated arm — which §94.3 left blocked on exactly one qualifying text — and this roster at
once. Three arms have the same substrate need and buying it three times is how a budget gets spent
on the same books in three different names.

**Token cost is measured at G0 and not assumed.** A deep dossier rides in the system message of
*every scene call* for the whole book. At thirty scenes with repairs on top that is the most
frequently re-sent text in the system, and its size is a budget line, not a detail.

---

## 7. Open questions, none of which block the first slice

- **How does a Director cast?** A fifth directive kind with its own containment argument; an
  operator act at book creation with the Director merely advising; or a per-book field that no
  machine touches. §3.3 records why this is not free. The first slice can ship `--writer` with
  the operator casting, and leave the Director out of it.
- **One writer per book, or per scene?** Per book is the conservative default and the one that
  keeps R4's arithmetic honest. Per scene — a specialist drafting the scene that needs them — is
  the more interesting idea and a much harder measurement, because it puts two writers inside one
  book and makes "which writer" a within-book variable that voice continuity has to survive.
- **Does the roster interact with the reader → writer loop's feedback set?** A dossier and a
  feedback line both sit in the system message and both say something about how to write. They
  must not be able to contradict each other, and R1 is what keeps a dossier out of that space.
- **How many writers?** Wide enough that G1 can fail informatively; small enough that R4's
  divisor stays payable.

---

## 8. What is not built

Everything in this document. No `domain/writers.py`, no dossier in any prompt, no roster, no
casting, no distinctness control over prose. The drafter is anonymous as of 2026-08-20, and the
first thing to build is §6's G0, because it is the one that costs nothing and it is the one that
says whether the rest is worth building.

---

## 9. Operator amendments, 2026-08-20, before G0 and before any writer was minted

Five, all design-time; none touches a running arm. Recorded here as a list so a later reader can
see what was decided by the operator rather than by the document.

1. **`exemplar_digest` joins the addressed tuple at the first mint**, unpopulated. Own-generated
   only if ever admitted, stored by digest, admission an operator act on R1's boundary. §3.1.
2. **G2 splits into G2a content-binding and G2b voice-binding**, with the prediction registered
   before the run: G2a binds, G2b inert, per §83. Both outcomes informative. §6.
3. **Two adjacent subject pairs join the slate** so G2 reads graded binding rather than far-pair
   separation alone, because far-pair passes have fooled this project before. §4.
4. **The shuffle-dossiers control moves to G1**, run in the same pass as distinctness rather than
   deferred, because distinctness without shuffle-sensitivity is decorative. §6.
5. **Real-book contact rides the next fitness-book batch**, not bespoke drafting. Sequencing
   constraint, not a task. §6.

Everything else in the document stands as written.
