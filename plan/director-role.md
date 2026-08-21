# The Director role: a personality that says what the book is, and never whether it is good

**Written 2026-08-19, before any code in this design was written and before any machine wrote
a directive.** Companion to [reader-judge-loop.md](reader-judge-loop.md), which owns the two
roles that handle prose *after* it exists. This one owns the role that acts *before*.

---

## 0. Why a third role is not a fourth attempt at the frame that died

Three roles now, and the obvious objection is that this project has spent months establishing
that a machine cannot be trusted to have opinions about prose. It has. That finding does not
reach this role, and the reason is worth stating precisely rather than waved at.

**Every dead frame was evaluative and downstream.** T0's panel, §89's E1/E2, the persona
reader's absolute verdict — each was handed prose that existed and asked *how good is it*. Each
died. The Reader/Judge split is the response: valence to humans, location to E6.

**A Director is generative and upstream.** It says *what the book should be* — a premise, an arc
note, a tone. That is not a measurement of anything, so it cannot be an invalid measurement.
It can be a bad idea, and a book written to it can turn out badly, but "this direction was
wrong" is a claim about the finished book that only a reader can settle — which is exactly
where it already goes.

    role      acts        on              answers                       licensed by
    DIRECTOR  before      nothing yet     what should this book be      nothing; it measures nothing
    JUDGE     after       two drafts      what differs, and where       E6, 3 of 3 families
    READER    after       two drafts      which would I keep reading    the only surviving valence channel

So the Director needs no validity licence. What it needs is **containment**, because a role that
makes no measurement is exactly the role through which unmeasured taste can walk into the system
wearing something else's authority. §1 and §2 are that containment, and both are bought by
failures already on the record.

---

## 1. PREREQUISITE — the third costume of the laundering path

`plan/judge-validity-program.md` §1.1 found it in the pair table. `plan/reader-judge-loop.md` §6
found two more when the Judge was split out. Here it is a third time, and it was checked in
source before this document was written rather than assumed:

- `directive_planner._constraint_edit` writes an explicit `constraint` or `veto` into a plan item
  with **`locked=True`**, verbatim, by design — those words are the director's and must not be
  paraphrased.
- `narrative_planner` lets the *model* set `locked` on every edit it proposes: the schema carries
  a `locked` boolean and the parser accepts whatever the model returns.
- `plans.constraints_of` selects locked constraints, and `context.assemble` puts them in the
  packet's **CONSTRAINTS** section — priority 2, above threads, facts and prose, effectively
  never dropped.
- **`Directive` has no author.** Not a column, not a field, not a check. The property "this is
  the director's word" is carried by the fact that only a human could write one.

**So the moment a machine writes a directive, its words enter every subsequent context packet as
a locked constraint carrying the director's authority, and nothing on the record says a machine
wrote them.** That is §86.1's shape exactly: a property enforced by who happens to hold the pen.
It is inert today because the `directives` table has no machine rows. It stops being inert on the
first tick of the first Director.

**Two fixes, and both are cheap now.**

1. **Directives get an author, content-addressed into their own id.** `Directive.author` is
   stored, printed, and part of `directive_id_for`'s material, so a machine row cannot be
   silently reattributed to a person and the same words from a person and from a director are
   two directives rather than one.
2. **A machine-authored directive may not produce a locked plan item.** The lock is the human
   director's authority and nothing else earns it. Enforced twice, because the two lanes fail
   differently: the **verbatim** lane refuses machine authorship outright, and the **interpretive**
   lane forces `locked=False` on every edit derived from a machine-authored directive whatever
   the model returned.

Fix 2 has a corollary worth naming, because it is the licence rule in one line: **the machine
Director's kinds are exactly `INTERPRETIVE_KINDS`.** `CONSTRAINT` and `VETO` are `VERBATIM_KINDS`
— preserve the words, lock them — and a veto is a *refusal*, which is authority rather than
direction. `CONTROL` is operator state (pause, resume, kill) and is not narrative at all. So a
Director may say what the book is about; it may not refuse anything and it may not stop the
machine. That maps exactly onto what a personality is for.

---

## 2. A brief may name what the book is about; it may not name what good prose is

The sharper rail, and it exists because the Reader/Judge loop would otherwise have a back door
straight through it.

`reader-judge-loop.md` §2.1 makes axis admission a four-step path: a human read names a defect, a
deterministic counter is built, E6 is shown to clear the family, readers establish a direction.
Nothing reaches a draft prompt as a prose instruction without all four.

A Director brief goes **straight into the drafting context**. So a brief saying *"use short
punchy sentences"* or *"cut the em dashes"* would inject a prose axis into every prompt with no
counter, no E6 validation and no reader behind it — the admission path bypassed by a role that
was never asked to respect it. That is not a hypothetical: `em_dash` is a registered axis whose
own pre-registered hypothesis §78.3 currently leaves **VOID with the estimate leaning toward the
mark**. A director confidently instructing against em dashes would be asserting as premise the
thing the loop exists to test.

**So: a brief may be about story — subject, arc, stakes, world, mood, what happens — and may not
be about prose quality.** Enforced as far as a machine can enforce it: a brief or a directive body
that *instructs about* a registered axis is refused. It is a narrow guard aimed at exactly the
bypass that matters, and it is honest about being narrow: it catches "avoid em dashes", it does
not catch a paraphrase, and no regex could. What it does buy is that the *registered* axes — the
ones the loop is actively measuring — cannot be pre-empted by direction.

**The first version of this guard reused the Judge's frozen `AXIS_MATCHERS`, and it had to be
withdrawn.** Reuse looked obviously right: those matchers *define* what naming an axis means, so a
second vocabulary would drift from the first. Run once, it rejected this design's own first
example brief on the sentence *"every level gained should have cost something"* — because
`stat_flatten`'s matcher contains `level`, `tier`, `stat`, `value` and `count`, which are ordinary
LitRPG **story** words.

The lesson generalises and is worth carrying: `elicitation_study` says in as many words that those
matchers are *"deliberately generous about vocabulary and strict about topic"*, because E6 asks
whether an axis reached the output at all. **They are tuned for recall on a description task, and
a refusal gate inverts the error economics** — in E6 a generous list costs a false positive that
reads as a miss; here it costs a refusal of legitimate direction. Same list, opposite cost. So the
brief guard has its own deliberately narrow vocabulary, tuned for precision, and the trade is
stated rather than hidden.

---

## 3. A personality has to be earned, because this project has measured that personas are usually inert

The strongest prior against "give it a personality" is in this repo's own ledger:

- **§89.1** — `qwen3:14b` returned **one distinct answer vector across all four personas,
  byte-identical**. The persona system prompt was inert; the panel was one judge replicated, and
  64 comparisons were 16 independent decisions.
- **§83** — four simulated states of mind, one voice: the register was invariant to simulated
  phenomenology.
- **§77 / §86.2** — persona-to-passage sum-of-squares ratios of **0.0028, 0.0071 and 0.0342**,
  while changing *the question* by one word moved a rate by ten points. The persona was nearly
  inert and the wording was the load-bearing knob.
- `persona-reader-validity.md` §6 already carries the remedy in another instrument: a
  persona-shuffled control, because "if shuffling the personas does not hurt, the personas are
  decorative".

**So "we can experiment with different directors" is a claim that has to be checked before it is
made, or it is §89.1 in a third costume: one director in three hats, and any comparison between
them is noise wearing a result.**

The control, `director_distinctness.py`, and it is cheap and machine-only:

- Draw `K` directives from each director on the same book state, varying only the sampler seed.
- **Byte-identity first**, because it is free and it is what actually happened in §89.1: any two
  directors whose directive sets are byte-identical read `IDENTICAL` and the comparison stops.
- Otherwise compare **between-director distance against within-director distance**, using the
  compression distance `domain/craft.py` already uses. Between must exceed within.

    IDENTICAL           two directors produced the same bytes. One director in costumes.
    INDISTINCT          between-director distance <= within. The brief is decorative.
    DISTINCT            between > within, with a within-director floor above zero.
    DISTINCT_NO_FLOOR   the sets differ and the floor was ZERO, so the gap cleared nothing.
    UNREADABLE          fewer than the declared floor of draws. Says so rather than passing.

**`DISTINCT_NO_FLOOR` is the fifth reading and running the harness is what produced it.** The
first version had four. Run on the fake provider, every pair came back `DISTINCT` with
`within = 0.0000` — every draw from each director was byte-identical to its siblings, because a
deterministic generator handed the same request returns the same answer. With no wobble to
clear, *"between exceeds within"* is satisfied by a single differing character: the rail passed,
and it could not have failed. **A control which cannot fail is not a control** (§50), and a
four-reading version would have let a temperature-0 run be quoted as having cleared a noise
floor it never measured.

The split keeps what the weaker reading does establish — the briefs are **not inert**, which is
the thing §89.1's failure was about — while refusing it the word that implies a margin. Both
count as comparable; only one may be reported as `DISTINCT`.

**The rail: a director comparison may not be reported until every pair in the run reads
`DISTINCT` or `DISTINCT_NO_FLOOR`.** It binds on the set rather than pair by pair, because
reporting "A beat B" out of a three-director run in which B and C are one director in hats is
still reporting the seed.

---

## 4. What experimenting with directors costs, and it is not free

The obvious experiment is: run N directors, see whose book readers prefer. That is a reader
question, so it rides the pairwise engine on the **internal** frame (system versus system) and
in the **steering** pool — it is not §61's comparison and does not touch it directly.

**But it does touch §61's headline, and the correction is already pre-registered.** §61
pre-registration (5): *"If more than one book could have been reported, the confidence level is
divided by the candidate count — §6.4's selection family applied to the headline claim itself."*
Picking the best of N directors and then measuring that book against matched published prose is
precisely reporting one of N candidate books.

**So N directors divide §61's confidence level by N.** At three directors the superiority claim
is made at α/3, and §61's own sizing already records what a thinner margin costs: at a true win
rate of 0.60 roughly 100–150 decisive judgments clear the bound, at 0.55 it is 400–500, and
clustering inflates both. This is the price of the experiment and it is payable — but it is
payable in the currency the whole project is short of, and nobody should run three directors
without having read this paragraph.

The cheap half is not blocked: **whether directors differ at all** (§3) costs nothing and runs
today. Whether a difference is *worth* anything is a reader question and waits with everything
else.

**Run, on the three built-in briefs through the padded fake provider:** all three pairs read
`DISTINCT_NO_FLOOR`, `between = 0.8462` against `within = 0.0000`, verdict `COMPARABLE`, with the
floor warning attached. What that establishes is that the briefs reach the request and change it;
what it cannot establish is anything about a real model's personality, because the fake answers
by request digest. It is a wiring pilot and the results file says so in its own `kind` field.

---

## 5. What the Director may do, in one table

| | |
|---|---|
| **May** | emit `PREMISE`, `ARC_NOTE`, `TONE_NOTE`, `CHAPTER_NOTE` — `INTERPRETIVE_KINDS`, and nothing else |
| | run with an empty inbox, which is the point: no human direction is required |
| | be one of several, compared as an arm against the no-director control |
| **May not** | emit `CONSTRAINT`, `VETO` or `CONTROL` — refusal and operator state are the human director's |
| | produce a **locked** plan item by either lane |
| | name a registered prose axis in its brief or its directives (§2) |
| | evaluate prose, score a scene, or select among candidates — that is the Judge/Reader loop, and a Director doing it would be a judge in a hat |
| | outrank human direction: machine directives sit below both human lanes in the queue |
| | emit unboundedly: at most one live machine directive per book, so the inbox cannot fill with machine direction and bury a human's |

**And nothing here can block.** A Director cannot construct a gate, set `blocking`, or park a
unit — I3 from `reader-judge-loop.md`, extended to the third role and enforced the same way, by
the absence of the capability rather than the absence of a caller.

---

## 6. Off by default, and the default is the control

`--director <id>`, mirroring `--plan-search`, and for the reason that flag states in its own help
text: *"this is the search arm of the K=3 acceptance experiment, and the default is its control"*.
A director is an arm. No director is its control. A change to autonomous drafting behaviour that
could only be produced by editing code would be an arm nobody could reproduce.

"Works with no human direction" is the *role's* property, not a statement about the flag: with a
director selected, the loop needs nothing from a person. With none selected, it behaves exactly
as it does today.

---

## 7. What is not built

- **No director has been compared to another on prose.** The distinctness control is built and
  runs; the reader-side comparison is blocked on the same missing readers as everything else, and
  costs §4's α division when it unblocks.
- **The prose-doctrine guard is a vocabulary check, not comprehension.** It catches a brief that
  names a registered axis. A brief that means the same thing in other words gets through, and no
  regex fixes that. Stated here rather than discovered later.
- **Directors do not read their own books' reception.** A Director that adjusted its direction in
  response to reader verdicts would be a second steering loop with none of `reader-judge-loop.md`'s
  firewall discipline, and it would put unmeasured taste back on the path the split exists to
  keep clean. If it is ever wanted, it is a new design with its own pre-registration.
- **No director personality is claimed to be good.** The shipped briefs are examples with
  deliberately different subjects, written to exercise the distinctness control, not to be good
  directors. Which briefs are worth running is an operator act.
- **A Director cannot choose who writes.** The drafter is anonymous — three sentences of system
  prompt with no name, no career and no subject (`application/planner.py:354`) — so "select a
  writer" is not a capability the role is missing so much as a role that does not exist yet.
  Designed 2026-08-20 in [writer-roster.md](writer-roster.md), which also records why casting is
  not expressible under §5's table as it stands: `DIRECTOR_KINDS` is `PREMISE`, `ARC_NOTE`,
  `TONE_NOTE`, `CHAPTER_NOTE`, and casting is none of them. A fifth kind is a new containment
  argument, because a Director choosing the writer is a Director acquiring a lever over prose.
