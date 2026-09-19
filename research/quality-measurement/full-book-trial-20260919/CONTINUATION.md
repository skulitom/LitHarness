# Explicit continuation after the runner's scene-id error

The registered first attempt completed its concept invocation (three provider calls,
22,984 recorded tokens) and created the six-scene book. No chapter was drafted. The new
runner then treated scene_nodes()'s list of logical-id strings as Node objects. The same
metadata error interrupted finalization. This is a runner defect, not a manuscript or
provider failure. All provider receipts are complete; there is no unknown model usage.

Preserve the original runner, registration, manifest, progress, tests, log and closed database
under runs/full-book-trial-20260919/runner-stop/. The original new command succeeded in
creating the store, but its after-metadata exception prevented its step receipt from being
saved. Keep that receipt gap explicit; do not fabricate an original receipt or run new again.

Correct metadata to retain the returned logical ids directly, and test it against real CLI
new and extend operations. Finalization must leave a partial status if metadata fails again.
Freeze amended runner/test/continuation bytes and the preserved originals before further calls.
Commit the explicit continuation first. Validate both the stopped source and current database.

Resume the same concept, world-empty store and frozen production revision at seed. Retain
all three original calls and the original first-dispatch clock. All original call, token,
time, phase and chapter limits remain; preparation time counts. No fresh concept, changed
author brief, selection, model change, production change or ceiling increase. No generated
narrative was read during this correction.

Only this exact stopped state may continue, once. The final result must report the interrupted
first attempt, the missing new-step receipt, the continuation and its extra usage. It cannot
be described as an uninterrupted run. The original readout and no-quality-claim boundaries
remain. The amended files are frozen in continuation.json; original registration.json remains.

```powershell
uv run python tools/check.py handoff
uv run python research/quality-measurement/full-book-trial-20260919/continue.py prepare
# Commit amended code, tests and continuation before:
uv run python research/quality-measurement/full-book-trial-20260919/continue.py run
uv run python research/quality-measurement/full-book-trial-20260919/run.py audit
```
