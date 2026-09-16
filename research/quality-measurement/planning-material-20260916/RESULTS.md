# Planning material: completed result

Status: **OBSERVED** authoring experiment. Registration was committed and pushed as
`3cdb928` before live calls. Both arms used production revision `80d37ba`.
See [RUNBOOK.md](RUNBOOK.md) for the fixed comparison and limits.

## Observation and decision

The prototype validated all four first-output transformations and preserved the central
source developments in the post-run reading. No missing central arc development or violation
of the supplied absence constraint was identified. Mechanical source-unit coverage does not
establish semantic fidelity: context-derived detail can have only a coarse arc citation.

Case 2 still plans its completed delivery in chapter 5 in both arms. Case 4 advances the
bargain and cost into chapter 1 in treatment, but repayment remains in chapter 3. Fresh
cases 1 and 3 enact their proposed openings in both arms and continue into changed practical
circumstances in chapter 2. These observations do not establish a treatment benefit.
Later planned events are not counted as enacted. Full located readings and prose stay under
`runs/planning-material-20260916/`, bound by [reading-record.json](reading-record.json).

The separation is incomplete. Generated numbered timing remains in untouched concept fields
for fresh cases 1 and 3, and in treatment placement suggestions for all four. No numbered
timing was found in the untouched concept fields for cases 2 and 4 by the recorded lexical
inventory; suggestions still expose their original scene coordinates. All opening requests
have null actual `open_promises`. Do not describe these generated suggestions as enforced
upstream promise deadlines, or infer that duplication caused the observed placements.

Keep the prototype isolated. The next design proposal is a single structured source of
proposed developments with provenance, dependencies and future bounds, separate optional
coordinates, and unchanged authoritative author constraints. First verify its rendered
contract offline; any live comparison needs its own registration. This is not a qualified
reader mechanism, production policy or promise of improved popularity.

## Mechanical results

- Four paired sources, eight outlines, twelve accepted chapters, 18,602 words.
- 88 provider calls, 1,533,344 recorded tokens; elapsed 3,528.697 seconds. Four material calls
  used 36,382 tokens. Shared fresh-source costs are charged to A, so book totals are not an
  equal-cost A/B comparison. Phase totals are in [readout-controls.json](readout-controls.json).
- No stop, failed provider call or unknown usage; all eight books complete with drained queues.
- All transport, registered outline-input, author-retention and experience-retention controls
  pass. Every store verifies with zero unattributed revisions.
- All 48 chapter coverage entries are retained; all twelve full briefs reach their writers
  and match job-bound plans and originating outlines. One writer and one policy attempt each.
- Five raw drafts equal accepted prose; seven differ only through existing surface cleanup.
  All raw differences were read. No narrative repair, redraw or alternative selection occurred.
- Readout revalidates 382 frozen files, 24 paired source files and 123 handoff source files.

## Evidence and reproduction

[evidence.json](evidence.json) records transport, requests, retention, calls, steps and reached
volumes. [handoff-evidence.json](handoff-evidence.json) records job/outline/writer correspondence.
[readout-controls.json](readout-controls.json) adds mechanical integrity, phase usage, raw
differences and numbered-field locations. That inventory is not a quality metric or a complete
semantic timing detector. Reproduce it with the completed local artifacts:

```powershell
uv run python research/quality-measurement/planning-material-20260916/summarize.py
uv run python research/quality-measurement/epistemic_governance.py research/quality-measurement/planning-material-20260916/claim.json
```

The reading record attests which artifacts were read and identifies the local report; agent
prose does not promote the claim. Four sources, one draw per arm, two familiar cases, changed
representation plus paraphrase plus guidance, and divergent continuation histories prevent
a causal, quality or generalization claim. No production source or defaults change here.

## Validation

The final canonical `tools/check.py handoff` completed successfully: 5,273 passed, 20 skipped,
89.97% coverage, clean lint/types/diff/lock checks, built wheel and clean corpus-history audit.
The local log is `runs/planning-material-results-handoff.log`, hashed in the reading record.
The check includes unrelated existing checkout changes; those are not part of this result commit.
