# Serial Pilot 21 — the first draw shown the shelf, with a story-shaped brief and no reviser

**Status: PROTOCOL, 2026-09-02, written before the listing call.** The first book drawn after
stage-0 §196: the listing writer is shown the anchors' blurbs and the scene writer is shown two
anchor openings as *how this shelf sounds* (`--exemplars book-library`, order *The Primal
Hunter* then *Defiance of the Fall*), the reviser is off, the brief is a story rather than a
list, and everything §195 shipped is still live (the opening beats, `--person first`, the
re-signed listing clause). Writer `marsh`, the same as pilot 19, so that pilot 19 is the
nearest description to read this one against — and they are two draws, never a treatment
effect (`serial-pilot-7.md` §0).

## 0. What this is, and what it is not

A description of one draw under a reversed rail. Read 15 is the readout that decided the
reversal and the operator's next read is the readout of this; the panel is void for the
question (§195.5) and is not asked. The coordinator's gate before the seed is §183's checklist
plus one new item: the leak gate's row on every accepted scene, which says whether any run of
eight words came from an exemplar (it refuses the draft if one did, so an accepted scene's row
reads clean by construction, and the row is what proves the gate ran).

## 1. The draw, as it was set up

- **Writer:** `marsh`. **Person:** first. **Shape:** six scenes, two per chapter.
- **Brief** (`runs/pilots/pilot21/brief.txt`): pilot 19's situation retold as a story with a
  turn and a want — Owen, twenty-three, the walked-out degree, nights at the depot, the dead
  fighting game; the Monday message and the sheet; the line nobody else has; the first thing
  through the floor moving like an opponent he has beaten a thousand times; off nights for
  good, and a ladder he is already ahead on. Read 15's first item was the listing as a list of
  facts, and the cause was the brief's shape; this is the fix at the brief.
- **Exemplars:** `book-library/PrimalHunter`, `book-library/DefianceOfTheFall` (the shelf's
  `exemplars.json` names the order), 1,630 and 1,563 words, both blurbs on disk; shelf digest
  `dd832792c5476b1a`.
- **Reviser:** off (the default since §196).

```bash
uv run litharness --database runs/pilots/databases/serial21.db init
uv run litharness --database runs/pilots/databases/serial21.db \
    --roster-database C:/DEV/LitHarness/runs/roster/roster.db --chapter-scenes 2 \
    --exemplars book-library \
    listing --writer marsh --brief-file runs/pilots/pilot21/brief.txt \
    --scenes 6 --person first --out runs/pilots/pilot21
# the gate, then the pilot-15b recipe with --exemplars book-library on the seed and the ticks
```

## 2. What is refused before the draw

Pilot 19 §2, and one more: **no exemplar text is read into any record this file cites.** The
job payload names the exemplars by digest; the frozen prompt holds their text inside a
gitignored store and nowhere else.

## 3. The listing

**Drawn 2026-09-02 in one draw, with the two anchors' blurbs shown above the brief**: *The
Line Nobody Else Has*, 121 words, three paragraphs, first person,
`runs/pilots/pilot21/listing.txt`; serial21.db, book `d5635294`.

**It has the shape read 15 asked for and the anchors' blurbs have.** Paragraph one is the life
before in one sentence (a year short of a chemistry degree, nights at a depot, the dead
fighting game). Paragraph two is the turn: the System on every screen, a sheet and a class to
pick, the line nobody else's carries, the first monster out of the floor moving like an
opponent beaten a thousand times. Paragraph three is the want and the promise: off nights for
good, and a ladder that starts where he already stands. Pilot 19's listing was six sentences
of fact in one paragraph; this is a situation, a turn and a want. Two draws, and the brief
moved between them as much as the blurbs did, so this is a description of what the brief and
the blurbs together produced and not an effect of either.

**The coordinator's gate, §183's checklist — PASS.** The sheet and the class to pick; the
line nobody else has, and what it does; System, sheet, class, monster, ladder in plain words;
the life before as one sentence; first person; no machinery words, no dashes, no title inside
the listing; the want in the last line.

**The browsing pool: 3 of 4 would start it, 1 passed.** The pass is `magic_m`'s typicality
item again, the same reader that passed on pilot 19 (*I've read that opening a dozen times*);
the three starts name plain nouns, a small edge that has to be earned, and a blurb that says
what he wants *instead of being coy about it*.

**One residual, recorded and not acted on.** The title is built on an absence — *Nobody Else*
— which is the family read 15 named in the prose (*nobody bowls in*) and §179's clause
forbids at the reviser, and the listing carries it once more (*a line I have not found on
anybody else's*). The title loop carries no such rule and the title passed its two frozen
predicates; the anchors' titles are noun phrases. Left standing, because the readout of this
draw is the operator's read and a title the coordinator retitled by hand would be the
coordinator's.

## 4. The seed and the chapter

**The seed** (one draw, clean check, accepted without `--force`, 189 records): *the System* as
the sole issuer of Rank and of seven kept grants — Push, Hold, Step, Mend, and behind the
fork Break, Sift, Bind — each bought once with a night of dead sleep and never spent back; a
printed line of the ladder's word and the seven grants and nothing else; the fork (*the
Class*: Hand opens Break, Wall opens Bind, Eye opens Sift) at Entrant, the second rung, so the
choice is reached inside chapter one; Danny Poole's edge as a line under the columns that
reads a move a beat early, which works on a riser and a fist and not on a person deciding
whether to lie; Cormack Freight pricing a day shift at a rung and a Registry that cannot read
a sheet; and a rival already a Contender.

**The system completed on the first draw after §196's two seed-side sentences**: seven grants
inside the bound, the sheet's columns the system's own, `world check` clean with no gap, the
scale and digest minted at `world accept`, and canon holding scheduled snapshots at rank two
and at Push one. Pilots 19 and 20 both drew a system the completion refused; this is the first
pilot whose progression beats speak the system's own vocabulary and whose fork can print as
the `[OFFER]` line where it opens.

**Chapter 1:** *(filled after the ticks)*

## 5. The loop, as the operator set it

**The operator, 2026-09-02, verbatim:** *"once you put all the necessary fixes and regenerate
it, could you hand read again? I feel like you understand the flaws much better than previous
models and you go much more indepth on your analysis than me. Then we could repeat the loop."*

So the loop from here, on this settled listing unless a read finds the listing itself at
fault: the coordinator hand-reads each draw's chapter 1 in depth against the two anchors,
routes every defect (enforcement, gap, structural), makes the fix that is structural rather
than a clause wherever one exists, redraws under the same listing, and reads again. Each draw
is recorded below as §5.N with its read, its routing, and the fix that followed; the
operator reads at milestones and his read is what the loop answers to. **The coordinator's
read is a diagnostic and never evidence** (§95, and the standing frame of every read file):
an LLM reading prose is what this project measures with, and this one steers but certifies
nothing. Two draws under one listing are two draws (`serial-pilot-7.md` §0).

### 5.1 Draw 1

*(the read, after the chapter)*
