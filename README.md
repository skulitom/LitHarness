<img src="docs/banner.jpg" width="100%" alt="LitHarness: a constellation dragon rising from an open book in a workshop of one-eyed archive creatures">

# LitHarness

LitHarness writes LitRPG serial chapters from a short brief. A **pitch** call writes a bible you glance
at before any chapter money is spent; each ~1,500-word chapter then costs two calls (plan, then
draft), plus one located rewrite when the tells counter says so. Code owns the numbers: the hero opens
his status as `[Label: value]` lines, and code reads them back into the sheet. Everything is plain files;
nothing to install beyond Python 3.11+ (standard library only), an agent CLI signed in with its
subscription (Codex, Claude Code, or both) and, from chapter 3 on, Ollama with `embeddinggemma-2:270m`.

The previous implementation is kept, unchanged, at the tag `legacy/incumbent-2026-09-27` and the branch `legacy/main`;
the design is frozen in [PLAN.md](experiments/2026-09-27-rebuild-plan/PLAN.md), and [LEARNINGS.md](LEARNINGS.md) says why it is this small.

## Verbs (`python -m litharness VERB`)

| Verb | Does | Calls |
|---|---|---|
| `new SLUG --brief FILE [--words 1500] [--DANGER-API-USE]` (500-1700) | creates the serial, draws the pitch, stops for your glance | 1 (up to 3) |
| `next SLUG [-n K] [--DANGER-API-USE]` (K up to 10) | plan, draft, checks, sheet, tells rewrite, report per chapter | 2-3 each |
| `agent [codex\|claude]` | shows, or switches, the one agent that writes for the whole project | 0 |
| `status [SLUG]` | chapters, words, failing checks with quotes, tokens, hand edits, locks, the agent | 0 |
| `redraw SLUG --from N` | moves chapter N and later to `attempts/<utc>/` (0: the pitch too) | 0 |
| `check FILE [--stage pitch\|plan\|chapter] [--serial SLUG]` | every deterministic check on any text | 0 |
| `canary [AGENT]` | live isolation canary; pins that agent's CLI version (default: the project's agent) | 1 small |

Resuming means re-running the same command: finished calls are adopted from their receipts and never bought
twice. Exit codes: 0 done, 1 needs you (a failed stage with its quotes, a held lock, the canary), 2 fault.

```powershell
python -m litharness agent claude                 # or codex; holds until the next switch
python -m litharness canary                       # once per agent, and after every upgrade of its CLI
python -m litharness new slot --brief briefs/slot.txt
python -m litharness next slot -n 3               # after you have read ch00/bible.md
python -m litharness status slot
```

**One agent writes for the whole project**, Codex or Claude Code, and `agent` switches it between any two
commands; a full model id and an effort can ride along (`agent claude:claude-opus-5-5:high`). The choice lives in
`$LITHARNESS_HOME/agent`, every receipt names the agent that made its call, and a switched agent is a
changed input, so it opens draws 4-6. **`--DANGER-API-USE`** sends one `new`, `next` or `draws.py run` to the
Messages API by the `api` agent (`claude-haiku-5-5`), billed per token to `$LITHARNESS_HOME/anthropic-api-key`;
`agent` never selects it, and it needs no canary.

A stage that fails a hard check (`money`, `leak`, `person`, `rise`, `fields`, `pitch-shape`, `plan-shape`,
`length`) is redrawn unchanged, at most 3 draws per input set. A money word that our own request carried stops
at once with its file and line. Editing the brief, bible, state or plan opens draws 4-6; never hand-edit chapters.

## Data

Serials live in `$LITHARNESS_HOME/serials/<slug>/` (default `~/LitHarness-data`), outside every git
tree: `serial.json`, `brief.md`, `manifest.json`, `ch00/` (the pitch) and `chNN/` with `state.md`,
`plan.md`, `final.md` (the raw draft), `chapter.md`, `sheet.txt` and `report.md`. Every call keeps its
request, system prompt, events, stderr, answer and receipt under `chNN/calls/`. Nothing is deleted.
From chapter 3 the plan also sees EARLIER: passages of chapters before the previous one, ranked by EmbeddingGemma 2
against the last state and kept in `chNN/recall.md`; each chapter's vectors are in `chNN/vectors.json`.

Back up the generated books to OneDrive with:

```powershell
Compress-Archive -Path "$HOME\LitHarness-data\serials" -DestinationPath "$env:OneDrive\LitHarness-backups\serials-$(Get-Date -Format yyyy-MM-dd).zip"
```

Chapters posted to Royal Road carry its AI-Generated tag.

## Genre census

`python bench.py baseline SLUG` places every chapter of a serial among 182 RoyalRoad LitRPG titles at the same
chapter number, by code alone, with no model call; the report in `serials/SLUG/baseline/` describes and never
decides. Corpus and protocol: [experiments/2026-09-28-genre-baseline](experiments/2026-09-28-genre-baseline/PROTOCOL.md).

## Pitch draws

`python draws.py run --agent codex` draws fresh pitches for 11 past briefs and reports how often a draw passes
its hard checks, which check fails and what a draw costs: one call a row, graded by code, describing and never
deciding. `python draws.py approve` is yours to run first. Protocol: [experiments/2026-10-02-pitch-draws](experiments/2026-10-02-pitch-draws/PROTOCOL.md).

## Tests

`python -m unittest -q`: serial, stdlib only, a few seconds, and no test spawns a model CLI.
