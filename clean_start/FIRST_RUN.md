# First clean-start chapter — 2026-09-08

## Question and setup

Does a single fresh chapter written directly from the user's desired reading experience avoid
the problems seen after the accumulated production pipeline?

The user requested a fresh magical adventure for Royal Road LitRPG readers. The submitted
request is the default in `chapter.py`: a short replacement system prompt and that experience
brief. No old persona, treatment, scene plan, house rules, example prose, book state or research
result was supplied. One CLI invocation, one completed turn, no retry or revision.

Local artifacts: `runs/clean-start-20260908-first/` contains `request.json`, `stdout.json`,
`stderr.txt`, `result.json` and the unchanged `chapter.md`.

- CLI: Claude Code 2.1.263, safe mode, tools disabled, empty temporary working directory.
- Authentication: the matching isolated preflight reported `claude.ai`, subscription type Max.
- Requested model: `claude-opus-5`; recorded canonical model matches. The CLI also reports a
  small auxiliary Haiku usage entry. Its list-price estimates are not evidence of an API bill.
- Started 17:15:57 UTC; finished 17:17:12 UTC. Completed with `end_turn`, one turn.
- Main response usage: 403 input tokens, 3,882 output tokens. Chapter: 1,967 whitespace words.
- Request file SHA-256: `5b303a1197b9ab36bba177d715e5b3e7ae9cceaad1cd93b500acf8a86f5a7fba`.
- Chapter SHA-256: `5fc2876ad29765e772adee770abc3007a6470bd18c49765d9fd2d8cb86583cf6`.

## Reading notes

The complete first response, **The Debt of Salt**, was read without editing it. These are
located observations about this artifact, not readership labels or a validated quality score.

The ancient room, responsive mosaic and newly usable perception ability provide a readable
discovery sequence (chapter lines 25–97). Opening the door drains the chamber and reveals an
illuminated passage (113–126). The final armored figure creates an immediate next situation
(144–148).

However, the requested problems remain:

- The opening specifies exactly four seconds of falling. Before magic appears, the text adds
  ledger-page counts, years, weeks, service duration, meal counts and ignition attempts
  (3–23). Eleven recurs as years, weeks and counted heartbeats. Node 41 and 1,208 dormant years
  supply more numerical decoration (43, 60).
- The narrator explains the reassuring thought immediately after it (11–13), explains why
  she says “please” (69), and repeats the debt consequences before explaining her decision to
  pull the pin (103–109).
- Magical discovery becomes account opening, assessment, service charges, scrap resale and a
  credit balance (43–97). The protagonist's concluding ambition returns to owing money (138).
  That financial framing was invented by this response, not specified by the visible request.
- The burning rag is about to go out (76–78), but an hour of searching follows (97–101) without
  establishing replacement illumination. The corridor only supplies light later (119).
- At six remaining Attention, a reward says the account is credited with +3, raising maximum
  capacity to 23, yet the character still says she has six (99, 128–134). A skill costs 40;
  replenishment and capacity growth are not clearly distinguished.

## Decision

**This run does not meet the purpose of the proposed replacement.** Removing the old pipeline
was not sufficient for this response. Keep the small independent generator as a reproducible
baseline, and do not mass-delete the existing engine on the claim that this chapter solves it.

This is a single sample with a new story, not a controlled estimate of improvement. It does
not isolate which model tendency, request wording or remaining CLI context is responsible;
safe mode still permits managed policies. It also says nothing about long-serial continuity.

The next discriminating test would use this exact brief through another subscription writer,
with a separately recorded first response. That would test whether these tendencies persist
across writers before adding any planning or editorial machinery back. It was not run here.

Implementation checks: all eight standalone offline tests and the repository handoff checks
passed. Those verify software behavior, not the chapter's appeal.

Follow-up, later on 2026-09-08: the exact brief was subsequently run through subscription
Codex. See [the comparison record](CODEX_COMPARISON.md); the original run and decision above
remain unchanged.
