# Handoff: can this system declare any LitRPG book on the market?

**Scope:** a brief for one worktree session. Read `CLAUDE.md` first, then `CONTRIBUTING.md`,
`plan/system-generality.md` (all five phases closed, stage-0 §202 to §212.1), and the
census files under `research/quality-measurement/system-displays/` (`FINDINGS.md` is the
record; the scripts are the method). Before proposing any quality or craft metric read
`research/quality-measurement/BRIEF.md` and `EPISTEMIC_GOVERNANCE.md`; this brief asks for
none, and a session that finds itself proposing one has left its scope.

## The goal, in one sentence

Measure, by declaring rather than by arguing, how much of the market's progression
furniture this house's vocabulary can already express without a code change, name every
gap by its share of the market, and land the largest gaps as measured slices in the house
form — so that "will our system fit any LitRPG story" becomes a number with a list behind
it instead of a belief.

## What the generality track already settled (do not re-derive)

- The line is a declared projection of the snapshot; unheld columns do not print (§203).
- Typed attributes (number, ordinal, name, text, set) on any owner: a person, a place, a
  creature, a role (§204, §206).
- No default sheet: a book's own evidence declares its columns (§205).
- The choice display with its text and gates (§207); the gain notice (§208).
- The floor asks for a display the book can print, not a numeric sheet (§209).
- A grant the rungs hand out and a grant paid in it (§210); a system that grows after the
  seed with its sheet following (§211); a change of kind as one declared change the sheet
  folds and the scene prints (§212); growth is a grant set, not a digest (§212.1).
- What is **not** in the plan and stays refused unless a gap census earns it: genre modules
  (a quest module, an inventory module, a notification module), a model that ranks or
  prefers displays, any change to how the corpus is used, and the reviser.

## The fit census (deliverable 1, measurement side only)

RS1 is the axiom that bounds this work: no corpus text or digest crosses to the generation
side. A fit census reads the corpus on the measurement side and produces **shapes**, never
text — a shape is a sentence like "level, six attributes, free points per level, skills
with levels in a list, a class chosen at level ten". That is admissible research material;
a line of a book is not.

1. **Draw the shapes.** From the RoyalRoad shards (the MirrorBench interpreter,
   `research/quality-measurement/system-displays/corpus_io.py`, one CPU job at a time),
   sample sixty stories that print windows (the §202 classifier finds them) and write down
   each story's shape in the vocabulary of `litharness world vocabulary`: which fields, of
   which kinds, on which owners; which moves (gain, deepen, rise, choose, spend, growth, a
   change of kind, a loss); which displays (a line, a box, an offer, a notice, a readout of
   another's sheet, an item's box). Add the four shelf anchors under `book-library/` (their
   shapes are drawn from the operator's own reading, the one place corpus material may be
   named by hand; stage-0 §196). Store the shapes as `research/quality-measurement/system-fit/shapes.jsonl`
   with the story id and nothing quoted.
2. **Declare each shape.** For each, write the `world declare` sequence that would express
   it and run it against a fresh store through `litharness world check` and `world accept`.
   Record the result per shape: declared cleanly; declared with a workaround (say which);
   refused (quote the check's complaint, which is house text and not corpus text); not
   expressible (say what is missing). This is the census: a table of shapes against four
   outcomes, with the share of the sampled market in each.
3. **Rank the gaps** by the share of shapes they block. Expected candidates, to be found
   and not assumed: a multi-line box for a wide sheet (the market's widest window carries
   nineteen fields; ours prints every held column on one line); a readout of another
   subject's sheet where the protagonist reads it (owed since §209); item and equipment
   boxes; a title or class with an effect on a column; skills with their own levels and
   ranks (a set field carries id and depth; a rarity does not fit); a pool that refills (a
   paired column exists, its refill rule does not); a quest or notification display; a
   party sheet; a per-rung schedule for a stock (§210 credits a fixed amount).

Write `research/quality-measurement/system-fit/FINDINGS.md` in the house form: what was
measured, the table, the ranked gaps, what it cannot show (a sample, shapes drawn by one
reader, furniture only). No bar.

## Then the slices (deliverable 2)

Take the gaps in rank order and land each as the generality track did: measured first (the
census row is the measurement), the smallest change that lets a book declare the shape,
books on disk replayed identical, tests, one stage-0 entry in the house form (what was
measured, what shipped, what was refused, anti-scope), the plan note updated. Two rules
from that track that bind here:

- **No default vocabulary.** A gap is closed by letting a book declare a shape, never by
  shipping a shape every book gets. `Level | HP | MP | Gold` was the defect (§205).
- **No model ranks or selects.** A display or a move is declared or derived; nothing here
  asks a model which one is better (§61(5)).

The readout on request and the box view are the two owed items the generality track named;
if the census ranks them near the top, they go first, and the box view should reuse the
sheet's declaration (a `view` node was considered and refused in §209 because the existing
predicates already held every display; revisit only if the census shows a display that has
no home on them).

## What this brief refuses

- A book drawn to prove fit. The census declares shapes into stores; drawing chapters is a
  paid arm and belongs to the pilot loop under the operator's reads.
- Any quality claim. Whether a declared shape produces a chapter that reads as its genre is
  the shelf's question and the operator's read.
- Corpus text in a store, a prompt, a fixture or a test. Shapes only.

## Parallel-session etiquette (binding for every worktree this week)

- The corpus pass is a sustained CPU job: one at a time on the box across **all**
  sessions, never beside a paid arm or the full suite; check the process list first
  (`CLAUDE.md`, "Running things on this box").
- `git status` and `git diff` on shared documents before editing; commit only your own
  files; push after every commit; never `--force`. Stage-0 numbers are claimed with the
  command in `CLAUDE.md` across `main` and every worktree and re-checked at commit time.

## Done looks like

The shapes file, the census table with its shares, the ranked gap list, the slices landed
in rank order with their entries, and this brief deleted in the last commit with its
results pointed at from `plan/system-generality.md` and the ledger.
