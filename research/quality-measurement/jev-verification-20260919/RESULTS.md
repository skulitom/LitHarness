# OpenJev verification screen: observed, not qualified

OpenJev is worth further testing as an optional factual-support checker with abstention.
This run does not justify making it an automatic continuity judge, fact-extraction source,
editorial gate or book-release authority. TypeSafe's hosted Jev was not measured.

The exact checkpoint is `AlexWortega/openjev/qwen3.5-4b-nli-v2`, pinned to revision
`4b5f9a67fa2ebe77466bce0656ce350effc3148c`. Collection followed registration commit
`8045c104cb86b99f433c417bd84135a7462f13c9`; no model output was observed before that
registration. The earlier registration's Windows line-ending correction is recorded in
[RUNBOOK.md](RUNBOOK.md). Fixtures, model, threshold and analysis stayed frozen during collection.

## Results

| Condition | Correct / pairs | Accuracy | Incorrect answers with score >= 0.90 |
|---|---:|---:|---:|
| Base | 64 / 72 | 88.9% | 0 |
| Entity renaming | 64 / 72 | 88.9% | 0 |
| Whitespace reflow | 68 / 72 | 94.4% | 0 |
| Irrelevant context | 66 / 72 | 91.7% | 1 |
| Decisive evidence removed | 57 / 72 | 79.2% | 0 |

These are dependent synthetic cases, not estimates over books. There are 12 families,
two surface arrangements, 360 scored rows and 276 distinct inputs. In particular, the
evidence-removal condition contains 24 distinct inputs repeated three times: 19 of 24
distinct inputs received the correct neutral answer. The two arrangements change names
and sentence order together and cannot isolate an order effect.

Across all rows, 319 / 360 were correct. Of 219 answers whose maximum softmax score
reached the preregistered 0.90 cutoff, 218 were correct. That is 60.8% coverage after
abstention and one remaining error, not proof of calibrated confidence. No false entailment
reached that cutoff in this sample; the registered confident-false-entailment kill condition
therefore did not fire. There were 13 false entailments below the cutoff, including repeated
inputs. Absence of a high-scoring false entailment in this small screen does not establish
an acceptable production error rate.

Two renamings, four whitespace changes and two distractor additions changed the predicted
class relative to the paired base input. Several flips repaired a mistake, but either
direction violates the expected invariance. Aggregate improvement under formatting or
distractors is not evidence that those transformations improve verification.

## What went wrong

- **Old possession became current possession.** Both base surfaces of
  `possession_transfer.*.neutral.base` were incorrectly called entailment. A fact established
  at an earlier time does not by itself establish the current state under this experiment's
  explicit-evidence convention. Their entailment scores were about 0.47 and 0.53.
- **Unreported execution became non-execution.** Both base neutral intention cases were
  called contradiction: the premise supplies a plan but does not establish whether it was
  carried out. Their contradiction scores were about 0.64 and 0.74.
- **An explicit state change was missed.** `location_change.0.contradiction.distractor`
  was classified neutral with score 0.9166 despite the premise explicitly placing the
  character outside the previously occupied location. This is the one error above 0.90;
  it is a missed contradiction, not a false entailment.

These observations come from [raw.jsonl](raw.jsonl) and are traceable to the frozen
synthetic cases in [jev_fixtures.py](jev_fixtures.py). The interpretation is limited to the
registered task definition. Natural-language inference conventions can differ from a strict
evidence checker, which is itself a reason to validate the intended application separately.

## Operational result

All 360 calls completed on the RTX 4090 with no inference retries, token truncation or
hosted API calls. Collection took 226.7 seconds; including model loading, 231.4 seconds.
Forward passes accounted for 86.0 seconds, with the remainder including resting, tokenization,
temperature reads and output handling. Peak observed temperature was 55 C, below the 72 C
hold threshold. Peak PyTorch allocation was 9,395,270,144 bytes. The largest input was only
903 tokens: no chapter-length, full-context or book-length capability was tested.

The initial weight download was interrupted and recovered using byte-range requests;
the resulting complete file matched the pinned published SHA-256 before model loading.
Download logs remain under ignored `runs/jev-verification-20260919/`. This transport repair
did not produce any model observations. The final 360-row collection succeeded once.

## Consequence for LitHarness

Keep this checkpoint in research. A later, separately registered comparison could test
strict evidence-supported claims from generated books, with explicit temporal scope,
missing-evidence controls and independent reference construction. If hosted Jev is available,
evaluate it on the same frozen substrate as a separate model; these results cannot stand in
for it. Do not select a new confidence threshold from this run or use its outputs in drafting.

This trial does not remove the book's reader-evidence or release-readiness blockers. It
neither extracts facts nor demonstrates that a checker can resolve the existing lack of
eligible ecological evidence. No production code, model routing or release policy changed.

## Evidence and reproduction

- [registration.json](registration.json): model/runtime hashes and frozen source hashes.
- [manifest.json](manifest.json): case IDs, labels, input hashes and duplicate count.
- [raw.jsonl](raw.jsonl): numeric probabilities and per-pair telemetry, without input prose.
- [runtime.json](runtime.json): hardware, collection time and exact registration commit.
- [results.json](results.json): deterministic confusion counts, control flips and mistakes.
- [claim.json](claim.json): content-addressed claim, retained as `OBSERVED`.

```powershell
uv run python research/quality-measurement/jev-verification-20260919/benchmark.py analyse --raw research/quality-measurement/jev-verification-20260919/raw.jsonl --output runs/jev-verification-20260919/rebuilt-results.json
uv run python research/quality-measurement/epistemic_governance.py research/quality-measurement/jev-verification-20260919/claim.json
uv run python tools/check.py handoff
```

The report's percentages are display rounding of the numeric artifacts. Rebuilding
`results.json` requires no GPU, model download, network access or API key.
