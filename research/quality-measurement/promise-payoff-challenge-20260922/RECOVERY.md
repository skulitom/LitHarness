# Authentication recovery, 2026-09-22

After the first attempt stopped before an isolation response, the operator reported logging
in again and asked us to continue. Preserve that attempt's registration, error and observations.
This amendment authorizes one fresh attempt with the identical model, executable, prompts,
source book, tasks, order, scoring and limits. No book observation has been seen or selected.

`recover.py` imports the frozen original implementation and redirects only its local outputs
and derived reports into `recovery/` subdirectories. It checks the original registration and
all its frozen files before every call, requires byte-identical tasks, and additionally verifies
this amendment, wrapper, regression test, original failure and recovery registration. Commit
the amendment and registration before dispatch. Existing outputs still cannot be overwritten.

The new attempt has the original 27-call, 1,600,000-token, $8-equivalent and one-hour admission
ceilings. Across both attempts this allows 28 dispatch attempts: one recorded authentication
failure plus up to 27 fresh calls. No usage was returned for the first failure. Re-run the
isolation probe first. All original stop rules apply; no implicit further retry is authorized.
The requested npm Codex CLI update is unrelated to the pinned Claude executable used here.

```powershell
uv run pytest tests/test_promise_payoff_challenge.py tests/test_promise_payoff_recovery.py -n 0
uv run python research/quality-measurement/promise-payoff-challenge-20260922/recover.py prepare
# Commit the amendment, wrapper, tests and recovery registration before dispatch.
uv run python research/quality-measurement/promise-payoff-challenge-20260922/recover.py run
uv run python research/quality-measurement/promise-payoff-challenge-20260922/recover.py analyse
```
