# Promise/payoff challenge: collection stopped at authentication

The full-book challenge is implemented and registered in commit `0bbcd1b`. Collection stopped
on its first isolation probe because the installed Claude CLI reported that its Anthropic
profile login had expired. **No extraction check or book request ran.** This is an operational
failure, not evidence for or against any promise/payoff interpretation.

[observations.json](observations.json) owns the machine-readable outcome: zero completed calls,
zero of eight extraction checks observed, incomplete collection, and no semantic admission.
[failure.json](failure.json) preserves the provider error. Raw attempt and task hashes connect
the report to local artifacts. The run recorded no token usage or cost; this is not an assertion
that failed calls always consume zero resources. The isolation flag is false because its probe
did not complete, not because instruction leakage was observed.

## What is ready

The [registered protocol](RUNBOOK.md) fixes eight authored extraction traps, twelve independent
fulfilment searches and six paragraph-dependency searches, plus the isolation check. The book
requests retain all 24 scenes, including text after the ledger's recorded payment. Each of the
three cases has unchanged, payment-withheld, control-withheld and whitespace-only contexts.
The earlier construction used opening-to-payment windows; those alone could not search for
later evidence. Requests, identities, executable and code are content-addressed before collection.

Exact-location checking rejects invented or ambiguous quotations and evidence before the
relevant event. One failed quotation invalidates its entire proposed chain. Empty results never
certify absence, and a located chain never certifies the model's proposed semantic connection.
Separate dependency requests explicitly expose the proposed deleted paragraph, while independent
fulfilment requests receive no condition label, registered payment or ledger interpretation.

All existing manuscript snapshots are unchanged. No production reader or admission rule changed.
The focused [regression suite](../../../tests/test_promise_payoff_challenge.py) passed; the full
repository handoff passed with 5,449 tests passed and 20 skipped, a successful wheel build, and
a clean corpus-history audit before registration.

## Required continuation

Re-authenticate the existing Claude profile. Preserve the stopped run and its zero-observation
report. Before another live attempt, commit an explicit recovery amendment with a fresh output
directory, the original frozen questions and inputs, and bounded remaining resources. The
original runner intentionally refuses to overwrite or implicitly resume `raw.jsonl`.

Do not treat this stop as a reason to change models, weaken controls, use a different book or
promote the three constructed cases. The semantic questions remain unmeasured. Once collection
works, inspect the located hypotheses and extraction failures before deciding which narrowly
controlled transformation is worth building next.
