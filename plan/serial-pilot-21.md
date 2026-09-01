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

*(filled after the call)*

## 4. The seed and the chapter

*(filled after the ticks)*

## 5. Read 16

*(the operator's)*
