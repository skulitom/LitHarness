# Causal-reader admission: no state-continuity substrate

The call-free census opened isolated backup copies of 24 available stores and audited every
branch, covering 25 stored book IDs. The third baseline store was missing because generation
stopped before creating it. [results.json](results.json) owns the source/backup identities,
branch enumeration, manuscript revision IDs, candidate counts, and rejection reasons.
Every original database hash was unchanged. No model calls were made.

The census admitted zero state-continuity candidates and generated zero controlled ecological
items. Every exported ecological manifest therefore reports `eligible_for_model_run: false`.
The proposed subtler costed-reader arm stops at this precondition; the result says nothing
about reader sensitivity or literary quality. Admission was not weakened to obtain a sample.

There are 51 promise/payoff candidate relations across three stored book IDs: two in baseline
Book 1, forty in the current volume store, and nine in the current draw-6 store. These are
located relation candidates, not validated interventions. That family has no implemented
ecological transformation with matched damage/sham controls, and multiple relations in a book
do not create independent books. The other admitted relation families were empty. The result
does not license swapping families into an unregistered model run.

The fitness stores provide enough intact chunks for feed seating, and baseline Book 1 has
twelve intact chunks; neither fact supplies a mechanically certified defect. Baseline Book 2
has six intact chunks. No shuffled or damaged variant floor was tested here. Present-day
historical stores are explicitly not substituted for the missing historical screen inputs.

The existing replicated order-sensitivity finding is recorded narrowly in
[order-sensitivity-claim.json](order-sensitivity-claim.json). It cannot turn these candidate
relations into a qualification claim. A future promise/payoff manipulation would need its own
verified transformation, matched controls, book-level independence and attainability checks,
held-out implementation, and committed registration before reader calls.

One implementation error preceded the completed census: the driver passed a path to the
connection-taking `SqliteStore` constructor. It failed on the first disposable backup before
any audit. The driver was corrected to `SqliteStore.open`; the failed backup and driver remain
under `runs/causal-reader-admission-20260910-failed-attempt-1/`, and the two invocation logs are
retained beside the baseline. This was a call-free API correction, with no manuscript edits or
selection among observed reader outcomes.

The completed snapshots and private answer-key material remain under ignored
`runs/causal-reader-admission-20260910/`. The [runbook](RUNBOOK.md) names every source and the
stop rule. The driver refuses to overwrite that directory.
