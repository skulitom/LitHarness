# Explicit continuation after the thermal shutdown

This amendment follows the operator's instruction to continue after the computer overheated.
It is recorded before inspecting any new story output or dispatching a further call.
The original registration and frozen runner remain unchanged.

No original experiment process remains. clean-1-1 and preserve-1-1 have valid completed
receipts, with 12,197 recorded tokens in total. The progress file, combined-1-1 receipt,
preserve-2-1 receipt and two transport files contain only zero bytes. The remaining temporary
transport directory has no final response file. Preserve the original files and their hashes
under crash-snapshot; do not infer the missing outputs or their usage from file lengths.

Count all four existing call slots as attempted. Mark combined-1-1 and preserve-2-1 as
lost_after_shutdown, with unknown usage and outcome. Neither is retried or replaced. Resume
only the eight remaining slots, in their original order and with exactly their prepared
requests. Retain each first response, including failures. The twelve-attempt ceiling still
holds. The original 100,000-token ceiling cannot be verified because two usage records were
lost; the explicitly resumed phase has its own 65,000 recorded-token stop before a call.
Unknown usage or failure in a new call stops that phase. There is no implicit second resume.

The original unknown-usage stop fired in practice through loss of the process and records.
This user-authorized amendment permits the separate remaining phase despite those two
unrecoverable records. It does not relabel unknown usage as zero or claim the original
budget control passed. Historical and resumed usage must be reported separately.

Freeze and commit the recovery code, snapshot hashes, remaining requests and amendment before
dispatch. Keep the original inputs and source frozen. Write resumed progress, receipts and
transport traces under recovery/, leaving original files untouched. New receipt/progress
writes flush file data and use atomic replacement; no claim is made about hardware durability.
Provider transport and prompts remain unchanged. Hold the existing task lock. Use one pytest
worker through PYTEST_XDIST_AUTO_NUM_WORKERS=1 for required checks and run no tests beside models.

Keep new prose unread until the remaining phase finishes or stops. Read all recoverable
responses and report every missing slot. The original rule requiring both repeats for both
premises cannot be fully evaluated: one preservation-only repeat and one combined repeat
are missing. Do not claim a balanced completed experiment, replace the registered decision
rule with a more permissive one, or promote a production change from this damaged run.
Concrete counterexamples and limited comparisons remain reportable.
