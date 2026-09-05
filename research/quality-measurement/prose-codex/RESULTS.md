# Subscription Codex diagnostic results, 2026-09-05

Four Codex CLI invocations completed through ChatGPT subscription authentication. The requested
model was `gpt-6-astra` at high reasoning; the event envelope does not independently report a
resolved model, so that field remains unavailable. No direct API, fallback, reset or redraw
occurred. All four complete scenes were read. No quality ranking or production change follows.

The calls reported 49044 input tokens, zero cached input, 6469 output tokens and a separate
1841 reasoning-output tokens. The registered input-plus-output counter totals 55513; including
the separate reasoning field conservatively totals 57354. Both are below the 120000 stop.
The four-invocation limit was met. Dollar cost is unavailable, not zero.

| Condition | Words | Paragraph blocks | Wall seconds |
| --- | ---: | ---: | ---: |
| full-1 | 881 | 63 | 85.316 |
| focused-1 | 947 | 63 | 90.087 |
| focused-2 | 906 | 64 | 79.414 |
| full-2 | 900 | 64 | 100.058 |

These counts describe execution only. Dialogue and standalone displays count as paragraph
blocks; paragraph count is not a craft metric. Original input strings are unchanged from the
earlier full-neutral and focused framing conditions, including rules, plan and word target.

## Parser correction and provenance

The first invocation exited zero and returned a single prose message and completed turn.
The initial validator rejected two pre-turn CLI configuration notices typed `error`. Neither
was a tool call. The raw output was read while diagnosing that failure. Before invocation 2,
[AMENDMENT-1.md](AMENDMENT-1.md) registered a narrow parser correction, committed with tests
at `ab6cf23`. It accepts the two exact notice forms before turn start and still rejects tools,
runtime errors and ambiguous output. Every invocation reported the same two notices.

The first scene was reparsed locally with zero new invocations. Original failed validation,
manifest and runner bytes remain in the ignored artifact directory. The amended manifest and
correction record link all old and new identities. No input, CLI argument, model, effort or
prose changed. [execution.json](execution.json) records the original validation outcome and
artifact hashes. The initial registration commit was `20bfef8`; the source and procedure are
in [PREREG.md](PREREG.md) and [RUNBOOK.md](RUNBOOK.md).

## Located reading, not literary qualification

`full-1` P23-28 establishes the private display through an exchange with a student, and P36-38
adds a request for direction. P39 and P47 nevertheless restate the prices after their display.
P33-35 adds a CHAPERONE label absent from the source; P59 describes the register name without
giving it. The ending reaches movement and the first payment. The exact twenty-second timing
is already present in the source; it is not a newly invented elapsed interval.

`focused-1` P8/P28 gives and reinforces an instruction to remain still; P42-49 connects that
instruction to the danger and reverses it. P57 prints the victim's name at the lookup. P23 and
P29-34 still explain the scheme at length, including an unsupported exclusion of evacuation
from removal. P36 invents possible mundane identities for the threat. The first-award endpoint
is retained.

`focused-2` P14-16 connects an instruction to students with an attempted administrative response.
P16 seats Kellow where the source's first-ability description has him standing at twenty seconds.
P37-46 repeatedly revisits the scheme; P51 begins a half-stand before withdrawal, creating an
unresolved scoring question under the attempt rule. P59 makes the attendance tick still wet
after forty minutes of the paper. P60 commits to the visible countdown measuring stillness,
a relation not specified in the source. The final movement and award occur at the endpoint.

`full-2` opens with the later victim asking for help, gives Kellow an instruction to stop writing,
and later has him postpone the victim's request while he checks the scheme. The victim's
compliance is spoken before withdrawal. The lookup names Callum Prewitt. The same output adds
a paper-entry announcement and a disembodied withdrawal announcement and retains explanatory
passages about the scheme. The scene ends at the first award.

These are descriptions and defect locations from agent reading. They do not establish that the
Codex package writes better prose. Model, transport and reasoning implementation changed
together, and the Claude controls are historical. The samples do show that the fixed source
permits staged interactions; they do not prove a method for reliably producing them or preserving
all source facts. The separate staging diagnostic tests a generic planning procedure using only
source material; these generated scenes are not its input or examples.

The full comparison, raw events, reviewed notes and provenance remain under ignored
`runs/ab/prose-codex-20260905/`. The amended parser's handoff passed 3985 tests, with 19 skipped
and 88.76% coverage, plus lint, types, build and corpus-history audit.
