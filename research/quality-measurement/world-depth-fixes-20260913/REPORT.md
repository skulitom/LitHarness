# Wren's forced-depth refusal is removed; the opposing snapshot remains incomplete

**State: OBSERVED. The full registered success criterion was not met.** The old runtime
reproduced both captured first checks exactly. The changed runtime completed Wren's
original declarations and the explicit-depth control without changing input material.
The opposing first-check snapshot was still missing its ability definitions and had a
malformed status sheet; it appropriately remained incomplete. No model was called and no
original store or receipt changed.

Engineering was frozen at `18ed80d`; registration was pushed as `53d8f7c` before either
replay. The comparator uses the preceding runtime's frozen `91271ac` source and the same
interpreter/dependencies. Exact source, script, runbook, store and receipt hashes are in
`registration.json`. `audit.py` derives the result from the retained first replay outputs.

| Fixed input | Old completion | Changed completion | Declared depth retained |
| --- | --- | --- | --- |
| Wren before first world check | Refuses because no capability exceeds one | Completes with configuration only; maximum one; no deepening moves | Ownership and rank requirements remain unchanged |
| Wren with the registered threshold-two control | Refuses the long configuration label | Completes with maximum two and deepening available | The explicit threshold remains two |
| Opposing world before first check | Reports no depth | Reports zero governed abilities; the malformed sheet also remains | No system or missing world fact is invented |

## What the replay establishes

For the captured Wren declarations, the former minimum-depth and configuration-label
rules were sufficient to prevent completion. Removing those rules allows the same world
facts to finish. Only the magnitude-scale and system-digest configuration records are
minted; no ability, rank or prerequisite is added. The synthetic control shows that the
change does not flatten a supplied numerical threshold into ownership.

The opposing snapshot exposes a registration assumption: its first check happened before
the model declared any capability roles or governance edges. The old no-depth message
masked that incomplete structure. The changed completion reports the missing abilities,
and the original malformed-sheet complaint is preserved. This case does not establish
completion of the opposing story under the new prompt, and it is not counted as a pass.
There was no replacement snapshot or second attempt.

## Limits and validation

This is a deterministic completion test, not a fresh model run under seed v7. It verifies
removal of a concrete source-distortion pressure for Wren; it does not prove that future
generations will preserve every mechanic or that several later chapters will remain
coherent. The existing system's scalar ceiling and the wider system grammar remain
limitations of its representation. No reader-quality claim follows from these results.

Repository handoff checks passed with 5,032 tests and 20 skips, 89.87% coverage, lint,
types, wheel build and corpus-history audit. Focused regressions preserve ownership
acquisition, ordinal rank gates, numerical depth, rejection of impossible scales,
configuration-only completion and system round trips. Printed column-label restrictions
remain checked separately from the unprinted scale label.

Rebuild the derived evidence with:

```powershell
uv run python research/quality-measurement/world-depth-fixes-20260913/audit.py
```

Raw replay outputs remain at `runs/world-depth-fixes-20260913/before.json` and `after.json`.
The generation that exposed the problem remains in the
[runtime report](../world-runtime-fixes-20260913/REPORT.md), with its chapter and every
first model output preserved.
