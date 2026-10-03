# Decisions

Entries are at most 5 lines, keyed `## YYYY-MM-DD slug`, rewritten in place when superseded. "plan N" cites
`experiments/2026-09-27-rebuild-plan/PLAN.md`; "§N" cites the stage-0 ledger at the incumbent tag.

## 2026-09-27 replace-in-place
Main is replaced in place by this package, grown from LitHarnessLite; history is kept, nothing is forced. The
incumbent stays at tag `legacy/incumbent-2026-09-27` and branch `legacy/main`, Lite at
`legacy/lite-2026-09-27`. Side prototypes die (the 09-08 clean start), so the rebuild replaces main. Ignored
data moves to `C:\DEV\LitHarness-archive` under a manifest, never deleted. (plan 1, 2.17, 6)

## 2026-09-27 stdlib-line-cap
`litharness/` imports only the standard library (Python 3.11+, a signed-in agent CLI): any file <=350, tests no
longer than the runtime; no database, queue, MCP server or dependency. The 1,300 cap became 1,350 for the review's
fixes, after the address, cast and digits reports were cut (bb87c71), and 1,425 for the agent-neutral transport
(edc478e). No admission reserve is left; each needs its own one-line cap commit. (plan 3.2, 5)

## 2026-09-27 data-root
Serials are plain-file folders under `$LITHARNESS_HOME` (default `~/LitHarness-data`), outside every git tree.
Nothing is deleted: `redraw` moves chapters to `attempts/<utc>/`; every call keeps its request, events,
`final.md` and a sha256 receipt. Third-party prose never enters the repo. (plan 1.2, 3.3)

## 2026-09-27 pitch-then-two-calls
One pitch call per serial writes a bible the operator glances at before any chapter spend, asked for at most 800
words and refused over 900. Each chapter then costs 2 calls, plan (with state) then draft, plus a located tells
rewrite when 2 or more tell families exceed shelf ceilings: ~21-27k tokens. The draft sees brief, bible, sheet,
state, plan and the previous chapter in full, never a fact packet (§182). (plan 1.2, 3.4, 3.6)

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
operator quotes, content lists or permission-form quantity rules, no banned word even negated. Story rules are
positive fields: a Limit takes from his body or time, a rank adds an ability, the Threat kills people, People are
allies (pitch draws, 2026-10-03). Cheapest fix first (delete, field, check, transform), a clause last. (plan 3.5)

## 2026-09-27 slot-brief-first
The first serial is a fresh draw on Lite's Slot brief, verbatim (`briefs/slot.txt`). Lite's chapter is not
continued: it fails v1 checks (no status lines, 4,069 words, an institutional premise). (plan 10)

## 2026-09-27 chapter-length
One chapter is one Royal Road post of 1,500 words. `len-band` reports outside 1,200-2,000; `length` redraws
only below 900 or above 2,700. Both bands scale with `--words`. (plan 3.6, 10)

## 2026-10-02 wait-for-operator
Royal Road export and the exemplar shelf wait for the operator to ask. Instruments fire on his asks, are graded
by code and describe, never decide: the genre census (`bench.py`, 2026-09-28) and pitch draws (`draws.py`,
2026-10-02). Pairwise judging and a model judge stay unbuilt; the model beat inventory waits for his go. (plan 4)

## 2026-10-02 model-and-voice
One agent writes for the whole project and nothing assumes which (operator, 2026-10-02): `agent codex|claude`,
optionally `:model:effort`, switches it between any two commands, as a changed input. Close third person, past
tense. Calls go through `transport.send` from an empty directory outside git; `canary` pins each CLI. (plan 3.7)

## 2026-09-27 admission-and-deletion
Admitted only when the trigger is a named failure on a real chapter, committed first as a failing fixture; the
fix is the cheapest class, never a register clause; net lines stated; a change to calls or to what the writer
sees is judged by the operator's read. Code off the chapter path and unexercised by a fixture is deleted
(530f40e); experiments are frozen under `experiments/`, never imported. (plan 4, 11; AGENTS.md)

## 2026-09-27 pitch-lexicon
inspect, inspection and permit left the pitch `money` list for `admin` (6ef1a46: inspect* fired as a System
mechanic in 5 of 6 read-21 concepts); inspector went back (f0824a6). Where a word mostly hits true, only its
misfiring sense is excused: council before a name, a ball court, court and contract as verbs (pitch draws).
