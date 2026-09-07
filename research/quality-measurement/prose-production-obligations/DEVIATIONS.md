# Execution qualifications

2026-09-07. All four registered slots completed in the fixed order. There were no manual
redraws, replacements, prompt edits, model/API fallbacks or reported internal sampling
retries. Every request and raw response remains retained, including stderr.

Each call emitted the same category of warning: PowerShell shell snapshots are unsupported.
The outputs parsed as one completed turn and one final message; the warning does not by
itself establish a sampling failure. Raw stderr hashes and warning categories are retained
in execution.json. Absence of a reported retry is not proof of an internal attempt count.

The source recorded timeout 300 seconds; the reused subprocess transport allowed 900
seconds, as preregistered. Historical production used Claude Code, whereas both fresh
conditions use the same subscription Codex CLI. Requested model and CLI are known;
resolved model and the complete upstream prompt stack are not captured.

The four local results reported 70163 input-plus-output tokens. No call crossed the
100000 stop. Cached input and reasoning remain subsets of the corresponding totals;
reported tokens are not a measurement of account-window quota consumption.

All generation-affecting files remained frozen. Reading notes, the comparison builder and
execution summarizer were produced after registration; they did not enter any writer
request. The comparison retains literal raw output and exposes all four draws without
ranking, selection, repair or cleanup. All inspected source omissions and staging changes
remain visible.

The registration was completed as designed. Its limitations are one original scene
fixture, two draws per condition, the combined duplication/placement/length change, and
shared source-authority tensions. No full chapter continuation was attempted.
