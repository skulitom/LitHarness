# Decisions

Entries are at most 5 lines, keyed `## YYYY-MM-DD slug`, rewritten in place when superseded. "plan N" cites
`experiments/2026-09-27-rebuild-plan/PLAN.md`; "§N" cites the stage-0 ledger at the incumbent tag.

## 2026-09-27 replace-in-place
Main is replaced in place by this package, grown from LitHarnessLite; history is kept, nothing is forced. The
incumbent stays at tag `legacy/incumbent-2026-09-27` and branch `legacy/main`, Lite at
`legacy/lite-2026-09-27`. Side prototypes die (the 09-08 clean start), so the rebuild replaces main. Ignored
data moves to `C:\DEV\LitHarness-archive` under a manifest, never deleted. (plan 1, 2.17, 6)

## 2026-09-27 stdlib-line-cap
`litharness/` imports only the standard library (Python 3.11+, a signed-in Codex CLI): any file <=350, tests no
longer than the runtime; no database, queue, MCP server or dependency. The first build plus the review's fixes
came to 1,314 lines against the plan's 1,070: the address, cast and digits reports were cut and the 1,300 cap
became 1,350 (bb87c71). No admission reserve is left; each needs its own one-line cap commit. (plan 3.2, 5)

## 2026-09-27 data-root
Serials are plain-file folders under `$LITHARNESS_HOME` (default `~/LitHarness-data`), outside every git tree.
Nothing is deleted: `redraw` moves chapters to `attempts/<utc>/`; every call keeps its request, events,
`final.md` and a sha256 receipt. Third-party prose never enters the repo. (plan 1.2, 3.3)

## 2026-09-27 pitch-then-two-calls
One pitch call per serial writes a bible (<=900 words) the operator glances at before any chapter spend. Each
chapter then costs 2 Codex calls, plan (with state) then draft, plus a located tells rewrite when 2 or more
tell families exceed shelf ceilings: ~21-27k tokens. The draft sees brief, bible, sheet, state, plan and the
previous chapter in full, never a fact packet (§182). (plan 1.2, 3.4, 3.6)

## 2026-09-27 code-owned-sheet
Code owns numbers go up: he opens his status on the page as `[Label: value]` lines, which code reads into
`sheet.txt` (<=12 lines; integers, Ladder ranks from 1, pools n/m); nothing is extracted from prose. Every
plan names one Rise earned by an on-page act (chapter 1: movement 1), and `rise` checks it is printed.
Printing is diegetic; no "print on change" rule, which read 10 called noise. (plan 1.3, 3.3, 3.5)

## 2026-09-27 hard-checks-redraw
Eight hard checks can redraw a stage (money, leak, person, rise, fields, pitch-shape, plan-shape, length); the
rest are inert reports. A money hit whose word is in our own request exits 1 naming its file and line (§266);
otherwise the stage is redrawn unchanged, at most 3 draws per input set, "draw k of n" shown; a changed input
opens 4-6. Transport retries (<=2) are not draws, and a draft never re-plans by itself. (plan 1.4, 3.6, 5)

## 2026-09-27 operator-read-gate
The operator's read, with household reads the operator relays (§148), is the only quality gate; no model
judges or selects. Simulated readers no longer measure the objective (§126): they continued 4/4 on shuffled
copies and preferred a shuffled opening of ours over The Primal Hunter 20/20. The coordinator's hand read
against `reads/CHECKLIST.md` records residuals only, never a pass. (plan 1.4, 3.6, 10)

## 2026-09-27 prompt-policy
All model-facing text is in `prompts.py`, <=700 words: no register or craft clauses, examples, example lives,
operator quotes, content lists or permission-form quantity rules, no banned word even negated. The one story
rule is positive: a Limit takes from his body or time, or puts him at risk. A new defect gets the cheapest fix
(delete text, field, check, transform); a clause comes last, with a fixture. (plan 3.5)

## 2026-09-27 slot-brief-first
The first serial is a fresh draw on Lite's Slot brief, verbatim (`briefs/slot.txt`). Lite's chapter is not
continued: it fails v1 checks (no status lines, 4,069 words, an institutional premise). (plan 10)

## 2026-09-27 chapter-length
One chapter is one Royal Road post of 1,500 words. `len-band` reports outside 1,200-2,000; `length` redraws
only below 900 or above 2,700. Both bands scale with `--words`. (plan 3.6, 10)

## 2026-09-27 wait-for-operator
Royal Road export, the bench and the exemplar shelf wait for the operator to ask: export when a chapter is
ready to post (the first real paste is its test), the bench for a comparison, the shelf re-applying §196. The
first two would be spend or code with no consumer yet. (plan 4, 10)

## 2026-09-27 model-and-voice
Defaults: Codex `gpt-6-astra` at medium effort, close third person, past tense. Every call goes through
`transport.py` from an empty temp directory with no `.git` above it; `canary` pins the CLI version. `claude()`
exists only if the bench is built, and never generates. (plan 3.7, 3.8)

## 2026-09-27 admission-and-deletion
Admitted only when the trigger is a named failure on a real chapter, committed first as a failing fixture; the
fix is the cheapest class, never a register clause; net lines stated; a change to calls or to what the writer
sees is judged by the operator's read. Code off the chapter path and unexercised by a fixture is deleted
(530f40e); experiments are frozen under `experiments/`, never imported. (plan 4, 11; AGENTS.md)

## 2026-09-27 pitch-lexicon
inspect, inspection, inspector and permit left the pitch `money` list for `admin`: on the six read-21 concepts,
inspect* fired in 5, mostly as a System mechanic or a physical check, and "permits" once as a verb. Lite's
plan.md:7 still fails on council and probation. (plan 3.6 one-false-positive rule; commit 6ef1a46)
