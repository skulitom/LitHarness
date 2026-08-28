# Handoff: tie the codex-era loose ends, then put the current results in front of the operator

**Status: OPEN, 2026-08-28. In execution on `claude/handoff-operator-read-5-d827aa`.** Written
after re-anchoring on the 2026-08-26/27 work (the reader evidence architecture, the editorial
control plane, the release-volume and cover pipeline, the agent runway). The occasion: the
operator asked to test the current results personally. That is the fifth operator read;
[`plan/reader-read-4.md`](reader-read-4.md) is the form it takes.

**Correction, 2026-08-28, same day, from the operator.** The two books in the table below are
*"old generations"* the operator has *"already reviewed"*. ~~The package that exists on disk
today is the read target.~~ **The read target is a fresh generation under the current
architecture — task 6's second bullet, promoted from operator-gated option to the main path.**
Tasks 1, 2 and 5 stand unchanged; tasks 3 and 4 apply to the fresh book rather than the two
below. The pilot-10 listing surface was not named in the correction — confirm with the
operator whether the sixteen listings are also already-seen before including or dropping them.
The inventory table stays what it is, a record of what exists; nothing in it is the thing
being tested. If the operator's earlier reviews of the two books surfaced defects that never
reached a `reader-read-*.md`, harvesting those quotes is still legitimate — but it is a
recovery of an old read, never a substitute for reading the fresh book.

## Boundaries, before the tasks

1. **The read is a defect harvest and not data** (§95's scope axiom; reads 1–4 are the
   precedent). The operator's words are quoted verbatim, the analysis is ours, and nothing the
   operator says becomes a prompt, directive, finding or plan item directly (§97.1, and the
   `debug-book` rule). Route every defect through task 5's question instead.
2. **No cross-pilot comparison is a treatment comparison.** Every input differs between the
   books below at once. A counter beside another book's counter is a description of two books.
3. **A steered book never rejoins §61's measurement set.** *Copy Costs A Hand* was steered by
   the since-retired direct appetite path (`plan/serial-pilot-7.md` §0 records this). The read
   does not change that either way.
4. **No model picks what the operator reads** (§84). This handoff lists what exists; the
   operator chooses order and depth.
5. **No instrument number is cited before its transport failures are attributed.** The run
   output of every CLI arm says so, and task 1 below is the standing instance.
6. Before committing anything: `uv run python tools/check.py handoff`, and the parallel-session
   rules in CLAUDE.md (diff shared documents first; claim stage-0 numbers by the cross-worktree
   scan; commit only your own files).

## What exists on disk today, and what each thing is

| artifact | where | provenance |
| --- | --- | --- |
| ***Copy Costs A Hand*** — title, 106-word listing, 3 chapters (6 scenes, ~6,054 words), 2 cover sets | `book-library/copy-costs-a-hand/`, store `runs/pilots/databases/serial8.db` | Serial Pilot 7: the first book the listing loop produced by itself, writer `halloran`, steered by the retired path. [`plan/serial-pilot-7.md`](serial-pilot-7.md) |
| ***Patch Notes For Earth*** — title, listing, 2 chapters, 2 cover sets | `book-library/patch-notes-for-earth/`, store `runs/pilots/databases/serial9.db` | Seeded the same evening as pilot 7's second seed, writer `ferreira`; recorded only inside serial-pilot-7.md §3.1 ("third seed"). No pilot doc of its own. |
| **Pilot 10: sixteen listings under a 2×2, plus one loop run** — the `genre_clarity` arm shipped | `runs/pilots/pilot10/overviews.md`, title in `runs/pilots/pilot10/title.txt`; `serial10.db` holds zero revisions (no book was drafted) | The current listing surface: four writers × prompt arms, fresh draws under an empty brief. No doc of its own. |
| **Older books** — *A Good Take* (8 ch, read 4 done), *What Takes*, *Reappraisal* (2 ch, no `overview.txt`, provenance unrecorded in `plan/`) | `book-library/<slug>/` | Prior pilots; not the current result. Include only if the operator asks. |
| **Tribunal run results** — `blurb_tribunal.v0`'s first run, registration digest `97bed1fb14cdaf2d` | `research/quality-measurement/results/blurb-tribunal.json` | Committed as-found from the codex-era session; **no run section exists in its validity doc and no stage-0 entry records the run.** Task 1. |

## Tasks, in the order they should land

*(Read the correction block above first: tasks 3–4 target the fresh generation, and task 6's
second bullet is the main path, not an option.)*

### 1. Write the tribunal run into the record before anyone quotes it

The JSON holds a complete-looking run: KG separated (8 of 8 pairs, bootstrap interval
[1.0, 1.0]), KD above its floor on both legs, KA low — and an `ours` leg of **one target with
zero flags**, which under the registered acceptance test reads as our listing blending into the
market. That reading is exactly the direction boundary 3 forbids believing, and it is **unreadable
anyway until the transport failures are attributed**: `transport_failures` records 10 failed flag
calls and 8 failed defend calls, and a failed flag call on the single `ours` target would
manufacture its zero. Attribute the failures per leg and per draw from the local raw JSONLs (the
`derived/` sidecar is gitignored by design), then write the run section into
[`plan/blurb-tribunal-validity.md`](blurb-tribunal-validity.md) in house form and add the stage-0
entry (claim the number by the cross-worktree scan). If the attributed result changes what §144's
family table says about the tribunal, correct that table in place.

### 2. Close the pilot record

- `plan/serial-pilot-7.md` still says **RUNNING, 2026-08-25**. The run is over: the chapters
  are drafted, `_say` landed, §139.3 validated, the vocabulary-shapes fix is live in
  `application/world.py`. Settle the status line and note what landed since.
- Give pilots 9 and 10 the short record a read needs — one file, `plan/serial-pilot-9-10.md`:
  what produced each artifact, which prompt arm each listing came from, what was never
  measured. Without it the operator is reading artifacts whose provenance lives in a section
  of another pilot's doc and in an untracked run folder.
- Record where *Reappraisal* came from, or state that its provenance is lost and exclude it
  from the package.
- Carried, not blockers: pilot 7 §5.2's title-blind screen (the `--no-title-to-readers` flag
  exists; the fresh listings per side were never drawn), and handoff-listing-loop task 3 (title
  availability as an agent tool).

### 3. Assemble the read package

- Re-publish the reading copies so they carry the current revisions: `uv run litharness
  --database runs/pilots/databases/serial8.db library`, and the same for `serial9.db`.
- Per book, the reading order that matches how a platform reader meets it: cover set → title →
  `overview.txt` → chapters in order, from `book-library/<slug>/` (the styled HTML reading copy
  is the artifact meant for a person).
- The listing surface: `runs/pilots/pilot10/overviews.md`, arms labelled as they are in the
  file, shipped arm first.
- Hand the operator file paths, not pasted text.

### 4. Run the read, and record it as `plan/reader-read-5.md`

The form of read 4: the operator's words quoted and not paraphrased, the analysis ours, and the
standing question asked of each defect — *did any directive forbid it, or is this a gap?* Three
prompts worth putting to the operator, because they are the behaviours the instruments try to
simulate and the operator is the one reader whose behaviour we may watch (§97.1 diagnostics):

- covers + titles: which would you click, and which would you not — with the sentence why;
- listings: start reading or not, per listing, same sentence;
- chapters: **where you stopped and why**, not a score.

### 5. Route every defect; fix nothing inline

For each harvested defect, one of three routes, written into read 5 next to the quote:

- **enforcement defect** — a standing rule forbids it and the book did it anyway;
- **direction gap** — nothing asked; reads 1–3's usual answer. A new clause is not the reflex:
  §127, §135 and §138 are the three entries on what clause-adding costs;
- **instrument question** — the defect is real and nothing counts it. That routes to the
  reader-architecture programme's battery families
  ([`plan/reader-perception-research.md`](reader-perception-research.md)): does an admitted
  damage family cover it, and if not, is there a mechanical key that could? It does not route
  to a new ad-hoc metric (BRIEF.md before proposing anything).

### 6. Operator-gated options, priced so they can be chosen

- **Extend *Patch Notes For Earth*** past two chapters for read parity: ordinary drafting
  ticks on `serial9.db`. One sustained job at a time on this box; check the process list.
- **A fresh pilot 11 under the current architecture** — post-§139.3 accept, editorial control
  plane present and inert, no retired steering path anywhere in its history. The
  architecture-honest artifact, at roughly a seed's cost (pilot 7 §3.2: one seed ran ~$10.69)
  plus drafting. Worth it only if the operator wants to read a book the retired path never
  touched; the prose path itself did not change.
- **The owed title-blind arm** (task 2's carry): one `listing` loop per listing, both sides
  from one code path.

## What this handoff is not

Not a licence to run any research arm (RUNBOOK first, registration before any paid call). Not a
backlog: when read 5 is recorded and tasks 1–2 have their canonical homes, delete this file.
