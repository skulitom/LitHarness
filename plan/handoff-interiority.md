# Handoff: the character's felt state as canon, and the leak that has to be closed first

You are working in `C:\DEV\LitHarness`, an autonomous fiction-production system whose objective is
popcorn-genre fiction (LitRPG, progression fantasy, isekai) a defined audience voluntarily
continues and recommends, with no human in the production loop. Superhuman literary
quality is the long-term goal (stage-0 §126). Your task is one bounded piece: make **what the protagonist wants and fears**
something the system tracks and shows to the scene being drafted, at the right point in story
time.

File names and measurements below were verified on 2026-08-21. If the repo has drifted, the repo
wins; re-anchor rather than following this document into a stale reference. Parallel sessions run
on this repository — `git status` before you commit, and commit only your own files.

## Why this exists (context you need, then stop reading context)

The operator's direction, verbatim: *"by interiority i mean simulating how the character inside
the book feels and what their desires are, especially the main character."* It is named as one
of the most important aspects of the project, and two independent measurements agree.
`interiority` is one of only three axes in the registry, admitted from the 2026-08-18 human read
that named "no interiority" as a defect; and against 800 RoyalRoad LitRPG chapters this
project's prose sits at the **27th–29th percentile** — 2.67 and 2.80 per 1k against a genre
median of 4.23.

The design, including the reader-side half you are **not** building, is
`plan/interiority-model.md`. Read §1 and §3 of it. Stop there.

## The hard boundaries

These are not preferences. Work that breaks one of them is worse than work not done.

1. **The counter must never become the target.** `axes.interior_per_1k` counts verbs —
   *thought, realised, felt, wanted, knew*. Do not write, propose, or imply a directive that
   names those words, and do not optimise against that counter. A prompt that moves it without
   producing felt state is the shallow-because-easy metric §1a.1 exists to refuse.
2. **Author no directive and admit no axis.** This task changes what the *packet* carries, not
   what the generator is told in prose and not what the registry holds.
3. **Do not touch `research/quality-measurement/personas.py` or the panel.** The reader-side
   half is an instrument change in a validity program, it is capped at four personas by
   protocol, and it is the operator's decision. Out of scope entirely.
4. **New files where you can.** Do not restructure shared planning documents; parallel sessions
   are editing them.

## Task 1 — the leak, which blocks everything else

**A state record dated later in the book is shown to earlier scenes.** Reproduce it first; do not
take it on trust:

```python
# uv run python
import litharness_contracts as lc
from litharness.domain import context as ctx
from litharness.adapters.sqlite_store import SqliteStore

def want(rid, text, key):
    return lc.StateRecord(record_id=rid, kind=lc.StateRecordKind.KNOWLEDGE, subject="silas",
        predicate="wants", value=text, story_position=lc.StoryPosition(order_key=key),
        authority=lc.StateAuthority.ACCEPTED_CANON, pov_visibility=[], evidence=[])

store = SqliteStore.open("serial.db")
book, branch, _ = store.branches()[0]
head = store.head(book, branch)
packet = ctx.assemble(head, "s1", state_records=[
    want("w1", "the senior seal on his card", "s1"),
    want("w5", "to know what the token is", "s5"),
], token_budget=8000)
print(packet.render())   # both wants appear while drafting scene 1
```

`context.assemble` accepts a `story_time_cutoff` and `planner.packet_for` never passes one. That
omission is **documented and correctly reasoned** — read the docstring before you change
anything. Its argument is that nothing defines a mapping from a manuscript scene to an
`order_key`, and that in the live loop the question does not arise because records are extracted
from accepted prose and therefore only ever describe scenes already written.

**That argument is sound for extracted records and does not reach seeded ones.** A want that
changes across a book is future-dated by construction, so modelling an arc of desire tells scene
one what the character will want in chapter two — the story's engine handed over before it
starts.

The fix and its precedent: `extraction.stated_position` already accepts the beat's
`story_order_key` as a position when the book has no vocabulary of its own, on the explicit
ground that it is *the planner's claim* rather than an inference about the book. The beat already
carries that key into the job payload as `selected_by.story_order_key`. Passing it as
`story_time_cutoff` is the same move one layer over.

Two things to get right, and both are why this is a task rather than a one-line edit:

- **A book with no story vocabulary must be unaffected.** `stated_position` abstains when the
  book has one of its own (`has_story_vocabulary`); whatever you do here must abstain in the
  same cases and for the same reason, or an imported book's packet silently changes.
- **Unplaced records must not vanish.** `records_before` slices on `order_key`, and a record with
  no position is *true of the book rather than of a moment in it* — the ability-graph seed is
  fifteen such records. Losing them would empty every packet in the project.

Golden context suites grade `assemble` (`tests/test_context.py`, `GoldContextSuite`). If a gold
case changes, that is a finding to report, not a number to update.

## Task 2 — seed the protagonist's interiority, and prove it lands

With Task 1 closed, add dated `wants` / `fears` records for Silas to
`plan/serial-pilot-seed.json`, sparingly — three or four across the book, not one per scene.
Predicates are free-form and `StateRecordKind.KNOWLEDGE` is in the contract and used by nothing,
so no migration and no contract change is needed.

Prove two things and report both:

- the record dated at or before the scene being drafted **is** in that scene's packet;
- the record dated later **is not**.

`plan/serial-pilot-seed-abilities.json` no longer exists; the current seed is
`plan/serial-pilot-seed.json`, which already carries an ability graph, a declared `Loop | Day`
sheet and its snapshot. Read it before adding to it, and keep the existing property that no two
canon records share a `(subject, predicate)` pair — until scoped cardinality lands
(`plan/state-model-abilities.md` §2), a repeated predicate is reported as a *blocking*
contradiction. Several dated `wants` records for one subject **will** collide under that rule.
Decide deliberately: distinct predicates, or land the cardinality fix first, or place them at
distinct story positions and verify the detector's grouping key actually separates them. Whatever
you choose, say which and why.

## Out of scope, named so you do not drift into it

- **Reading a changed desire off the page.** Nothing extracts non-stat facts from prose, so a
  seeded interiority is static: it shapes the prose and the prose cannot grow it. That is a
  second extractor family, it is shared with the ability graph, and it is item 9 of the change
  surface in `plan/state-model-abilities.md`. Do not build half of it here.
- **The reader who projects onto the protagonist.** See boundary 3.
- **Any claim that this improves prose.** It changes what the generator is told. Whether that
  produces felt state is a reader question, and the only reader in this project is an instrument
  you may not touch.

## Deliverables

1. The cutoff change, with tests beside the existing context tests, and the reproduction above
   turned into a regression test that fails on `main` as it stands today.
2. The seeded interiority, with the two-part proof from Task 2 reported as output rather than
   asserted in prose.
3. A short results note under `research/quality-measurement/` or `plan/` — new file — recording
   what the packet carried before and after, and any gold context case that moved.
4. Your own commits. Do not fold this into anyone else's.

Declare no bar, admit nothing to the registry, author no directive. If Task 1 turns out to be
unsafe — if the beat's story key cannot be trusted as a cutoff for some book shape you find —
**stop and write that up instead**. A packet that silently drops established facts is a worse
failure than an interiority feature that does not exist.
