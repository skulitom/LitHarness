<img src="docs/banner.jpg" width="100%" alt="LitHarness: a constellation dragon rising from an open book in a workshop of one-eyed archive creatures">

# LitHarness

LitHarness writes LitRPG serial chapters from a short brief. A **pitch** call writes a bible you glance
at before any chapter money is spent; each ~1,500-word chapter then costs two Codex calls (plan, then
draft), plus one located rewrite when the tells counter says so. Code owns the numbers: the hero opens
his status as `[Label: value]` lines, and code reads them back into the sheet. Everything is plain files;
nothing to install beyond Python 3.11+ (standard library only) and a Codex CLI signed in with ChatGPT.

The previous implementation is kept, unchanged, at the tag `legacy/incumbent-2026-09-27` and the branch
`legacy/main`. The design is frozen in [experiments/2026-09-27-rebuild-plan/PLAN.md](experiments/2026-09-27-rebuild-plan/PLAN.md);
[LEARNINGS.md](LEARNINGS.md) says why it is this small.

## Verbs (`python -m litharness VERB`)

| Verb | Does | Calls |
|---|---|---|
| `new SLUG --brief FILE [--words 1500]` (500-1700) | creates the serial, draws the pitch, stops for your glance | 1 (up to 3) |
| `next SLUG [-n K]` (K up to 10) | plan, draft, checks, sheet, tells rewrite, report per chapter | 2-3 each |
| `status [SLUG]` | chapters, words, failing checks with quotes, tokens, hand edits, locks | 0 |
| `redraw SLUG --from N` | moves chapter N and later to `attempts/<utc>/` (0: the pitch too) | 0 |
| `check FILE [--stage pitch\|plan\|chapter] [--serial SLUG]` | every deterministic check on any text | 0 |
| `canary` | live isolation canary; pins the Codex CLI version | 1 small |

Resuming means re-running the same command: finished calls are adopted from their receipts and never
bought twice. Exit codes: 0 done, 1 needs you (a failed stage with its quotes, a held lock, the canary),
2 fault.

```powershell
python -m litharness canary                       # once, and after every Codex CLI upgrade
python -m litharness new slot --brief briefs/slot.txt
python -m litharness next slot -n 3               # after you have read ch00/bible.md
python -m litharness status slot
```

A stage that fails a hard check (`money`, `leak`, `person`, `rise`, `fields`, `pitch-shape`,
`plan-shape`, `length`) is redrawn unchanged, at most 3 draws per input set. A money word that our own
request carried stops at once with its file and line. Editing the brief, bible, state or plan opens
draws 4-6; chapter text is never hand-edited, redraw instead.

## Data

Serials live in `$LITHARNESS_HOME/serials/<slug>/` (default `~/LitHarness-data`), outside every git
tree: `serial.json`, `brief.md`, `manifest.json`, `ch00/` (the pitch) and `chNN/` with `state.md`,
`plan.md`, `final.md` (the raw draft), `chapter.md`, `sheet.txt` and `report.md`. Every call keeps its
request, system prompt, events, stderr, answer and receipt under `chNN/calls/`. Nothing is deleted.

Back up the generated books to OneDrive with:

```powershell
Compress-Archive -Path "$HOME\LitHarness-data\serials" -DestinationPath "$env:OneDrive\LitHarness-backups\serials-$(Get-Date -Format yyyy-MM-dd).zip"
```

Chapters posted to Royal Road carry its AI-Generated tag.

## Genre census

`python bench.py baseline SLUG` places every chapter of a serial among 182 LitRPG titles on RoyalRoad at the
same chapter number, by code alone: no model call, seconds after the first run. The report lands in
`serials/SLUG/baseline/` and describes; it never decides. The corpus and its protocol are in
[experiments/2026-09-28-genre-baseline](experiments/2026-09-28-genre-baseline/PROTOCOL.md).

## Tests

`python -m unittest -q`: serial, stdlib only, a few seconds, and no test spawns a model CLI.
