# Continuation baseline runbook

Read `PREREG.md` first. The operator authorized this bounded experiment in the current task.
Check the process list and acquire `runs/box.lock` under the shared runbook before preparation,
validation, or generation. Keep one sustained job on the machine. Preserve unrelated changes.

From the repository root, prepare without model calls:

```powershell
.venv/Scripts/python.exe research/quality-measurement/continuation-baseline-20260910/run.py prepare
uv run python tools/check.py handoff
```

Commit only this experiment's registration, runner, and runbook before generation. Then run
with the isolated interpreter created by preparation:

```powershell
runs/continuation-baseline-20260910/runtime/Scripts/python.exe research/quality-measurement/continuation-baseline-20260910/run.py run
```

`prepare` fixes the exact committed source, dependency inventory, native executable hash, and
registration/runner hashes. It will not overwrite an existing prepared runtime. `run` refuses
an already started run. Do not resume a failed book by editing its request or stored state.
Progress and aggregate usage are written to `progress.json`; native requests and results are
stored by book, while the provider also retains its complete transport traces. The research
runner does not alter manuscript content or take over an applied production migration.

After completion, inspect each `checkpoint-*` and `final` folder using the stored CLI outputs.
The debug-book skill governs diagnostic interpretation. Audit existing volume-screen records
separately; do not rewrite or silently adopt another session's raw evidence. A subsequent
costed-reader arm needs its own source admission, matched controls, independent book split,
attainability calculation, registration, and runbook before new reader calls.

Release only this task's coordination lock when the sustained work ends. Keep the holder record
in the ignored run directory as the run's receipt. Never remove another task's lock.
