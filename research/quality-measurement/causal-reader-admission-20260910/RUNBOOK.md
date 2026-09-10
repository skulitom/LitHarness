# Admission before a milder costed-reader arm

This call-free census implements the next step authorized with the continuation baseline.
It makes no reader calls, changes no source manuscript, and does not register a validity claim.
Read the quality-measurement BRIEF, EPISTEMIC_GOVERNANCE, and
`plan/causal-salience-interventions.md` before interpreting the output.

## Question and preconditions

The proposed next reader arm needs a story defect with an independently established relation
and exact prose spans. First test whether the existing twenty fitness stores, the available
historical volume sources, and the new baseline supply such material under the current
admission code. Do not invent a relation, add artificial evidence to canon, or ask a model to
certify the corruption it produced.

Use the committed baseline pipeline's `reader-evidence-audit`, on isolated SQLite backup copies
of existing stores. Backups may be migrated; original stores must remain untouched. Use
`corpus_io.generated_scenes` on those copies for manuscript export and feed-length checks.
Enumerate every branch explicitly and report it; never silently substitute the largest branch.
Keep full source text and hidden scoring keys under ignored `runs/` only.

The source list is `corpora/fitness/fitness-00.db` through `fitness-19.db`, the baseline's
`book-1/serial.db` through `book-3/serial.db`,
`runs/volume1/serial.db`, and `runs/ab/pilot25/draw6/serial.db`. Missing sources are reported.
The last two are current long-form artifacts, not verified historical screen inputs.

Record source database hashes, backup identities, manuscript revision IDs, candidate counts
for every family, generator rejection reasons, ecological item counts, and feed-length checks.
Count independent books separately from candidate pairs. An empty subgroup is unavailable.

## Stop or proceed

Zero admissible state-continuity items, or too few independent eligible books for an attainable
held-out design, stops the proposed reader arm before spend. This is a substrate result, not
a failed reader and not a reason to weaken admission. Candidates in other families are not
usable transformations merely because their relations were counted. Their transformation and
matched controls would first need to be implemented and verified independently.

If the substrate exists, freeze clean/damaged/sham texts, a book split, and separate development
and held-out transformation implementations. Check hidden-key validity and shallow edit
fingerprints. Calculate attainable ranges and power from observed costed-reader session
variation, then commit a separate registration fixing analysis, kills, and budget before calls.
Retain intact and surface controls in the same arm; never compare the new books against the
old fitness cohort's contrast distribution as if their reference class were unchanged.

Run the census only while the shared machine is free of generation or validation. Preserve and
release only this task's `runs/box.lock`. The census is read-only research, not production
feedback; all baseline books continue under their frozen generation configuration.

After the baseline process has ended and its status is `finished`:

```powershell
runs/continuation-baseline-20260910/runtime/Scripts/python.exe research/quality-measurement/causal-reader-admission-20260910/census.py
```
