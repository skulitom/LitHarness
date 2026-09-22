# Second authentication recovery, 2026-09-22

The [first recovery](recovery/RESULTS.md) stopped at the isolation probe on the same expired
CLI profile. At about 18:35 the operator ran the CLI-specific `auth login --claudeai` for
`C:\Users\artem\.local\bin\claude.exe` in an interactive terminal; it reported success. The
repository's opt-in live isolation tests (`LITHARNESS_LIVE_PROVIDERS=1`,
`tests/test_providers.py -k test_live_claude`) then passed: a completion returned, a marker
`CLAUDE.md` in the working directory was not read, and git status was not inherited. No
book request or extraction check was sent by those tests.

The operator approved one further attempt by default on 2026-09-22 ("run it once under a new
amendment, then close that line"). This amendment authorizes that attempt and no other.
Preserve both earlier attempts: their registrations, errors, observations and local raw files.

**The one change is the executable.** The pinned binary at the registered path updated itself
from `2.1.263 (Claude Code)` to `2.1.280 (Claude Code)`, most likely during re-authentication,
so the original registration's executable check can no longer pass. `recover2.py` re-applies
every other original check unchanged (frozen sources, inputs, committed registration and
sources), requires byte-identical tasks, and re-pins the executable to the 2.1.280 hash in
`recovery2/registration.json`, recording the previous version and hash beside it. The model,
prompts, schema, tasks, order, scoring, stop rules and the 27-call, 1,600,000-token,
$8-equivalent and one-hour ceilings are unchanged. The run re-executes the isolation probe
first, under the updated CLI, as the original schedule already does.

Across all three attempts this allows 29 dispatch attempts: two recorded authentication
failures plus up to 27 fresh calls. The run requires the shared box lock with a holder
beginning `promise-payoff-challenge-20260922:`, as before, and must not run beside another
sustained job on the workstation.

**After this attempt the line closes.** Whatever it observes, no further builder, challenge or
admission work is built on these three constructed cases; the runbook's boundary stands (no
result can open admission). If this attempt also fails operationally, record it and stop.

```powershell
uv run pytest tests/test_promise_payoff_recovery2.py -n 0
uv run python research/quality-measurement/promise-payoff-challenge-20260922/recover2.py prepare
# Commit this amendment, the wrapper, its test and recovery2/registration.json before dispatch.
uv run python research/quality-measurement/promise-payoff-challenge-20260922/recover2.py run
uv run python research/quality-measurement/promise-payoff-challenge-20260922/recover2.py analyse
```
