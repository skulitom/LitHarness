# Replay the declarations that triggered invented depth

The operator requested fixes to world generation. The runtime follow-up retained a
specific sequence: the Wren seed first declared ownership prerequisites plus rank gates;
its first check refused to finish because no capability exceeded one; it then equated
Loadstitch depth with rank. The opposing seed received the same refusal and subsequently
added Fold-depth requirements to Mirror and Echo. These observations identify a tool contract
to change; they do not establish general model causation or reader quality.

## Fixed reconstruction

Use the completed Wren seed receipt from `world-runtime-fixes-20260913/book-1/calls/003.json`
and the opposing seed from `world-runtime-fixes-20260913/book-2/calls/002.json`.
Their exact hashes are fixed in the replay script. For each, select successful declaration
batches before the first explicit `world check`. Refuse partial/failed writes or unfamiliar
write forms. Resolve their identities against the original read-only store, restore their
initial proposed authority, and use the stored declaration times for supersession.

The old frozen runtime must reproduce the entire saved first check exactly. Otherwise
exclude the reconstruction from any before/after inference; do not edit its records to
obtain a match. Add one labelled synthetic control: replace Wren's ownership prerequisite
for Split with a numerical threshold of two. This control tests that real depth is retained.

## Change and readout

Allow scale maximum one for held-or-unheld abilities. Completion represents missing depth
as ownership, without adding prerequisites or world facts. Declared numerical depths still
bound the scale, and rank requirements remain ordinal. The scale's configuration label
must be non-empty but need not obey the printed-column grammar: it never occupies a status
column. Actual column labels retain their existing checks. Seed v7 describes this contract.

Before execution, freeze committed source, registration, script/runbook hashes, both
receipt/store hashes and the old runtime manifest hash. Commit and push registration.
Run the same reconstruction in the old runtime and with the new frozen source first on
PYTHONPATH. Neither run calls a model or writes to an original store. Keep raw results in
the ignored run root and publish hashes, identifiers, numbers and comparison results.

Success for this deterministic test requires exact old-check reproduction on both captured
cases, identical input material between versions, removal of the depth and configuration
label refusals, configuration-only minting, unchanged ability/rank requirements, maximum
one with no legal deepening in the two original cases, and maximum two with deepening
available in the synthetic control. Check both source stores/receipts remain unchanged.

This tests the engineering cause directly. It does not test future model compliance with
seed v7, erase the earlier model elaborations, validate prose quality, or authorize a new
reader role. No model rerun, candidate ranking or editorial intervention is part of this arm.

## Execution

Preparation archives committed source into `runs/world-depth-fixes-20260913/source` and
writes `registration.json`. With registration committed, use the existing runtime:

```powershell
runs/world-runtime-fixes-20260913/runtime/Scripts/python.exe research/quality-measurement/world-depth-fixes-20260913/replay.py before
$env:PYTHONPATH = "$PWD/runs/world-depth-fixes-20260913/source/src"
runs/world-runtime-fixes-20260913/runtime/Scripts/python.exe research/quality-measurement/world-depth-fixes-20260913/replay.py after
Remove-Item Env:PYTHONPATH
```

Run repository handoff checks before the engineering commit. Original native generation
is already complete; coordinate sustained checks under the existing task lock.
