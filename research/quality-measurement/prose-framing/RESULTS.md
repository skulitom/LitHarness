# Framing diagnostic results, 2026-09-05

Completed the registered nine calls: one source selector and eight opening-scene drafts,
two per condition, in the fixed forward/reverse order. Equivalent reported cost was
$1.703702. All calls returned in one provider turn with zero reported permission denials.
No retries, fallbacks, output ranking, manuscript acceptance or production prompt adoption
occurred. These are approximately 900-word scene requests, not eight complete chapters.

The narrow result is that the transport manipulations executed, while located prose habits
and factual inconsistencies remained. This is agent defect harvest, not a literary quality
label, treatment ranking, or evidence that any mechanism is qualified. Two samples per package
on one fixed story cannot establish a null effect generally, transfer, or the cause of the
remaining behavior. The current control already includes the separate no-tools correction.

## Execution and source review

Registration, runner, transport fix and call-free controls were committed at
`a59c9df402c5bdf5d92aceaf974628d9f102f31b` before paid calls. See [PREREG.md](PREREG.md),
[RUNBOOK.md](RUNBOOK.md), and [execution.json](execution.json) for the frozen file hashes,
CLI version, request/result identities, usage, and costs. Model: `claude-opus-5`; installed
CLI: Claude Code 2.1.261.

The selector supplied decisions for all 227 optional units, plus five unrequested decisions
for protected units. The raw optional selection kept 46. Every retained and omitted unit was
read against the source before any draft. Fourteen recorded corrections removed the five
extra decisions and dropped nine optional units containing duplicated or future material.
The protected blocks themselves were retained by the renderer. The reviewed selection kept
37 optional units; it is a source-reviewed treatment, not autonomous selector success.

The immutable review note initially said no model output informed the review. A separately
hashed amendment narrows this to no *draft prose*: the source-selector output was necessarily
read. The frozen decisions were not changed after drafting began. Original source strings
alone formed the focused packet; neither selection explanations nor new prose entered it.

| Condition | Words, draft 1 / 2 | Supplied system + user characters | Reported input tokens including cache, each call |
| --- | ---: | ---: | ---: |
| Current append transport, tools removed | 1024 / 1054 | 44494 | 26412 |
| Replacement system prompt and safe mode | 989 / 996 | 44494 | 15229 |
| Also remove initial writer persona | 997 / 1020 | 44006 | 15087 |
| Also use reviewed scene-context selection | 1001 / 1035 | 21240 | 7376 |

The user-context selection reduced 34744 characters to 11978. All system world rules, costs,
author locks, private information, scene plan, word target and state/milestone instructions
remained, apart from the separately specified opening-persona deletion. Token usage describes
transport, not quality. The isolated condition bundles default-role replacement and safe mode;
this experiment cannot attribute a difference to one of those components separately. Response
envelopes do not expose an independently verified exact model-visible prompt.

## Located observations

All eight outputs were read in full, in generation order. Paragraph numbers below refer to
blank-line-separated blocks in the retained files, including standalone system displays.

| Output | Located defect harvest |
| --- | --- |
| `control-1` | P1 turns the hourly wage and aisle walking into an opening association and gives an invented precise pain routine. P9-11 repeat the scoring implications. P14 announces later recollection. P21 estimates elapsed time without an observed clock. The threat turns again after the planned first-award endpoint. |
| `isolated-1` | P1 repeats the smell/wage opening habits; P3 adds a pool comparison and unsupported inference about how long lights have been off. P10-15 repeatedly explain reading and the prices. The register lookup describes the record without giving its name. |
| `neutral-1` | P1 considers a dimmer before the light change. P9 adds future insomnia and a lengthy explanation of marking schemes. P10 uses 311 before the planned withdrawal from 312. P16 asserts an exact interval while disclaiming knowledge of it. |
| `focused-1` | P1 adds an invented clock time and thesis section. P11-15 re-explain reading and prices; P15 treats the six-mark item as worth all other items combined despite their values of one and two. P23 gives register typography without the name; P24 asserts exact elapsed time. |
| `focused-2` | P4 infers that a student cannot see her paper change, confusing the shared rewrite with private floating text. P10-13 and P21-23 repeatedly explain the scheme and understanding's value. P23 refers back to a bell not previously dramatized. |
| `neutral-2` | P1 extends the opening through wages, payroll, thesis section and a referee. P7-8 and P16 repeatedly explain the scheme and its omissions. P13 announces later knowledge of a name; P15 omits the actual name from the lookup. |
| `isolated-2` | P11 anticipates a later scene on grass; P12 announces future system behavior. P16 introduces an unsupported 400-chair count. P22 calls a blue-biro name printed in the same sentence. P23 invents ninety elapsed seconds and re-explains comprehension versus action. |
| `control-2` | P9-11 re-explain reading, prices and omitted items. P15-17 explain compliance and compare removal to closing a book. P19 describes register print without the name. P20 asserts sixty elapsed seconds; P21 states the reading/action distinction again. |

These observations do not turn the absence of a name, a comparison, or an invented detail into
a universal craft rule. Their locations are retained for diagnosis against this scene's intended
events and viewpoint; no pattern count or defect total is a quality score. In particular, the
samples do not support concluding that context size, persona or default coding framing alone
explains the problem. They also do not establish that those factors have no effect.

## Disposition and artifacts

The production implementation change is limited to removing built-in tools for requests whose
tool allowance is empty. `--allowed-tools` alone controls approval rather than availability;
the provider now also passes `--tools ""` for pure completions. Nonempty agent allowances retain
their existing scope and behavior. The focused regression is
`test_claude_empty_allowance_removes_tools_without_rewriting_agent_permissions` in
`tests/test_providers.py`. See the dated correction in
[provider-adapters.md](../../../plan/provider-adapters.md). No prose improvement is attributed
to this correction; the trial's controls are after it.

Full requests, argv, raw provider results, source audit, fourteen correction records, frozen
review and amendment, numbered reading notes, and the comparison page remain under ignored
`runs/ab/prose-framing-20260905/`. The page retains all eight outputs and opens on fixed condition
positions, without selecting a preferred draft. Only derived counts and identifiers are
committed. There is no corpus text, example opening, story-specific production rule, or
automatic reader-feedback path in this change.

Both the pre-call and final handoff passed 3972 tests, with 19 skipped and 88.76% coverage;
lint, types, build and corpus-history checks also passed. The comparison page was inspected
in a browser, its draft selector exercised, and its console reported zero errors or warnings.
