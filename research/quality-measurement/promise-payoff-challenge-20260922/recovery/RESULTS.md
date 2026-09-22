# Authentication retry: no model observations

The explicit retry registered in `79f1c8d` also stopped at the isolation probe. The CLI again
reported an expired Anthropic profile. No extraction checks or book requests ran, and no
model-family substitution was attempted. [failure.json](failure.json) preserves the error;
[observations.json](observations.json) records incomplete collection and closed admission.

After the provider error was flushed, Windows refused cleanup of the temporary marker directory
with `WinError 32`. That secondary error interrupted writing the usual run summary. The local
`run.json` was reconstructed from the preserved error and registration; time, tokens and cost
are explicitly null rather than invented. The complete traceback remains in the local
`runs/promise-payoff-challenge-20260922/recovery/collection.log`.

Read-only authentication diagnosis identified the CLI's `credentials-file` default profile;
the CLI status reported logged in despite the live provider rejecting its expired login. The
operator was given the exact CLI-specific `auth login --claudeai` command to refresh that
profile. The background interactive login was cancelled because it requires a terminal the
operator can type into. No credentials, tokens, account identifiers or browser codes are
committed in this record.

Any subsequent attempt must preserve both failures, use a fresh output directory, and register
the continuation before dispatch. A local marker-directory cleanup failure should be recorded
without replacing the underlying provider outcome. The frozen substantive questions, model,
controls and evidence boundaries remain unchanged and unmeasured.
