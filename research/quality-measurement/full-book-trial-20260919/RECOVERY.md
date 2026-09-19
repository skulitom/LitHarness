# Explicit recovery of the second-arc outline contract failure

The preserved trial stopped with six accepted chapters (14,204 words), twelve planned
scenes, 41 completed calls and 1,014,525 recorded tokens. The first second-arc outline
scheduled a promise after its deadline. Two retries used book-wide chapter numbers where
the validator requires response-local scene ordinals. The poisoned job and exception are
recorded in recovery.json. This is an observed operational failure, not a quality verdict.

Preserve the stopped database, progress, manifest, original audit, runner and step receipts
under runs/full-book-trial-20260919/arc2-stop before changing the book. The production fix
must touch only application/outline.py: expose the domain validator's feasible local
positions per open promise, retain all obligations and deadlines, clarify scene versus
chapter coordinates, and constrain response scene numbers. Synthetic regression tests must
cover an accepted second arc, unchanged accepted prose and overdue debt, and refusal of
late or book-wide windows. No generated narrative has been read while making this fix.

Archive the committed fixed production source in a separate subdirectory of sources/A;
retain and verify the original source too. Freeze a separate runtime and this recovery's
files in recovery.json. After committing the amendment, recover through ordinary resolve
and replan CLI commands with providers disabled. Preserve the old poisoned job and all
decisions. Only that exact three-attempt job may be classified as historical after the plan
epoch advances; any other terminal job or open exception still stops the trial.

Continue the same store at chapter7 iteration4, retaining the existing twenty-tick phase
ceiling, original first-dispatch clock, all usage, author brief, concept, accepted chapters,
model and transport controls. Do not rerequest the first six chapters, rerun world growth,
extend an incomplete arc or raise any ceiling. No implicit second recovery. Verify frozen
files and unchanged stopped state before operations; record every recovery operation.

The first recovery preflight refused before any book operation or provider call because
the generic admission check also rejects stopped books. Its error incorrectly said budget
exhaustion. Preserve that attempt under recovery-preflight. After stopped() validates the
exact registered state, mark the in-memory candidate running before checking admission;
persist nothing until all original ceilings pass. Freeze this correction before dispatch.

This is a mixed-revision continuation after a failed run, never an uninterrupted completion
or a controlled quality comparison. The original run's failed step controls remain visible.
Final audit and located narrative readout follow the original RUNBOOK. No diagnostic
story notes enter generation. The reader qualification blocker remains open.

Commands, in order:

```powershell
uv run python tools/check.py handoff
# Commit the production fix first, then:
uv run python research/quality-measurement/full-book-trial-20260919/recover.py prepare
# Commit the frozen recovery registration and code, then:
uv run python research/quality-measurement/full-book-trial-20260919/recover.py run
uv run python research/quality-measurement/full-book-trial-20260919/recover.py audit
```
