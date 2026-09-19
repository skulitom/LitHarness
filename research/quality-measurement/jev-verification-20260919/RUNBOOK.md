# OpenJev factual verification screen

Registered before inference, 2026-09-19. The user authorized this isolated trial after
discussing Jev for LitHarness. It tests supplied passage/claim pairs, not claim extraction,
literary quality, manuscript readiness, or editorial interventions.

## Target and boundary

Can this exact OpenJev checkpoint discriminate entailed, contradicted and unspecified facts
on explicitly constructed factual traps, including withholding the decisive evidence?
This is a synthetic capability/falsification screen. Labels follow authored positive,
negative and unspecified assertions; their construction is an assumption of the experiment.
Code verifies the transformations and metadata, not the semantics of natural language.
There are no independent reader labels, actual books or ecological transfer observations.
No outcome qualifies a production reader or changes the book-release decision.

## Frozen mechanism and substrate

- `AlexWortega/openjev`, revision `4b5f9a67fa2ebe77466bce0656ce350effc3148c`,
  `qwen3.5-4b-nli-v2`. OpenJev is a separate model from TypeSafe's hosted Jev.
- Local CUDA, BF16, eager attention, batch size one, no generation or sampling. Built-in
  Transformers backbone plus last non-padding token and classifier head, matching the
  model author's wrapper. Remote Python code is not executed. Runtime and file hashes
  are recorded in `registration.json`; a mismatch prevents collection.
- Input: `Premise: {premise}\nHypothesis: {hypothesis}`. Class order: contradiction,
  entailment, neutral. No role prompt, examples, gold label, case ID or confidence tuning.
- `jev_fixtures.py` constructs 12 families, two dependent surface arrangements per family,
  three truth states and five variants: 360 pairs. Surface arrangements change sentence
  order and names; they are not independent paraphrases or stories. Each truth-state
  triple shares an identical hypothesis to prevent hypothesis-only label leakage.
- Base positives explicitly establish the fact; base negatives explicitly refute it;
  neutral backgrounds leave it unspecified. Missing evidence never means contradiction.
- Label-preserving controls rename entities, reflow whitespace and add 48 irrelevant
  archive sentences. Evidence location within distractors is early/middle/late, balanced
  across families and fixed independently of labels. This is modest context stress,
  not a full-context or book-length test.
- The destructive control removes the decisive assertion and expects neutral in all
  cases. Duplicated inputs are retained and disclosed in `manifest.json`; they do not
  increase the independent sample size. All prompts are reconstructed from the frozen
  synthetic fixture code; no third-party prose or manuscript enters this experiment.
- Fixed seed 20260919 shuffles execution order. Inputs above 4096 tokens abort; there
  is no truncation, selection based on results, threshold fit, or automatic retry.

## Analysis and decision rule

Run once, analyse the complete frozen case set. Report confusion counts, accuracy,
constant-neutral baseline, multiclass Brier sum (range 0 to 2, lower is better), base
family/surface breakdowns, and paired class/probability shifts under each harmless
transformation. Report all mistakes and high-confidence mistakes at the fixed 0.90
maximum softmax cutoff. This cutoff is a diagnostic, not a calibrated acceptance policy.
The Brier statistic is also descriptive; this small dependent sample cannot establish
general calibration. No significance claim or confidence interval over dependent rows.

Any confident false entailment falsifies unconditional use of this checkpoint at the
registered cutoff on this fixture scope. Any class flip under renaming or reflow is an
observed invariance failure. Neither no such error nor high aggregate accuracy constitutes
production qualification. A clean run permits considering a separately registered book
transfer study; failures must shape the scope of any such study. Keep the empirical claim
`OBSERVED` pending interpretation of controls. Do not generalize findings to hosted Jev.
This trial is an engineering screen, not a new literary mechanism or quality bar.

## Operation and stop conditions

Take the workstation lock and check for competing jobs as the parent research runbook
requires. Use the existing MirrorBench interpreter; do not modify its packages. The cap is
360 pairs, 45 minutes including loading and rests, zero hosted API calls. No TypeSafe key
was available at preflight, so hosted Jev is unmeasured. Download is outside the runtime cap.
Rest one second per inference second. Hold at 72 C until below 66 C. Temperature read
failure, OOM, invalid probabilities, changed artifacts or token overflow stops collection.
Preserve partial output and register any repair before a further inference attempt; do not
interpret incomplete data as a complete benchmark. No full test suite during inference.

```powershell
uv run python research/quality-measurement/jev-verification-20260919/benchmark.py manifest
uv run pytest tests/test_jev_verification.py -n 0
uv run python tools/check.py handoff
# Freeze registration and commit it before the following command.
& C:/DEV/MirrorBench/.venv/Scripts/python.exe research/quality-measurement/jev-verification-20260919/benchmark.py run --model-dir runs/jev-verification-20260919/model/qwen3.5-4b-nli-v2 --output runs/jev-verification-20260919/raw.jsonl
uv run python research/quality-measurement/jev-verification-20260919/benchmark.py analyse --raw runs/jev-verification-20260919/raw.jsonl --output research/quality-measurement/jev-verification-20260919/results.json
```

Commit raw numeric observations and runtime metadata, derived report and hashed claim
references. Model files and logs stay under ignored `runs/`. Record local failures even if
no complete result is obtained. No production transport, prompt, evaluator or policy changes.

## Sources inspected before registration

- [OpenJev model card](https://huggingface.co/AlexWortega/openjev): checkpoint description;
  published benchmark claims are not observations from this trial.
- [Pinned inference wrapper](https://huggingface.co/AlexWortega/openjev/blob/4b5f9a67fa2ebe77466bce0656ce350effc3148c/modeling_openjev.py):
  template, pooling and probability calculation. The wrapper's silent truncation is disabled.
- [TypeSafe introduction](https://typesafe.ai/blog/introducing-system-one-models-and-jev):
  motivation for bounded classification; not evidence of local OpenJev capability.
