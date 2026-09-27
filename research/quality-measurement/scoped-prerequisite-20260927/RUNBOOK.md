# A prerequisite with an explicit instant

This is the next call-free construction step authorized on 2026-09-27. It replaces the
unsupported persistence inference found by the state-admission audit with an explicit necessary
condition at one instant. It is engineering of a synthetic logical probe, not a registered reader
arm. No model call, production change or quality claim is licensed by this runbook.

## Exact semantics and source boundary

`prerequisite_certificate.py` defines a closed language. A rule for a named trial states that a
particular hatch is open only while a particular lamp is lit. Observations name the trial and
instant explicitly. Hatch states are the exclusive pair open/shut, lamp states lit/dark.
The rule is necessary, not sufficient: lit does not imply open. An unobserved state is unknown;
the same entity at another instant or in another trial is a different atom. No persistence or
identity resolution is inferred.

This is an ongoing state prerequisite. A rule that only constrains the *opening event* is
refused: it does not imply the lamp must stay lit after the hatch opens. The two accepted
renderers both state the ongoing restriction explicitly.

Every sentence must parse in full. Dialogue, pronouns, modality, negation outside the declared
state pair, arbitrary narrative and appended exceptions are unsupported. A caller cannot supply
annotations to override parsing. A proof certifies only this grammar's semantics. Rejecting a
natural passage means the grammar does not interpret it, never that the passage is defective.

The synthetic source carries two rules, two lamp observations and two shut-hatch observations.
One lamp is lit, the other dark. A single `shut` -> `open` edit at each hatch produces a
contradiction and a consistent control, identified by code after editing. The control's own
prerequisite must be explicitly satisfied. The three-clause contradiction has its rule, dark
lamp and open hatch in the public text. Both full-source siblings are retained.

The two edits have equal character, token, sentence, punctuation, whitespace, uppercase and line
counts, exactly equal token multisets, and the same position decile. Fixed other-trial rules keep
both final edits in that decile; this artificial layout is a declared limitation. Hatch/lamp
links and rule/observation order are crossed under two renderers. These are variations of one
synthetic family, not independent books or held-out ecological transformations.

## Attacks and checks

- Verify the solver against independent exhaustive Boolean enumeration on the active four atoms.
- Require intact/control consistency, damaged inconsistency, and a minimal three-clause proof.
- Delete the relevant rule or move the dark-lamp observation to another trial/instant: the
  damaged text must have a consistent witness. Removing context must not count as contradiction.
- A lit lamp with a shut hatch must remain consistent. This kills reversing necessity.
- Reject unsupported narration, quoted rules, forged state types, a contradictory source,
  missing control prerequisites, or an unmatched edit fingerprint.
- Keep public packets flat, opaque and complete. Proof spans, sibling links and condition labels
  remain private; no sentence or paragraph from a real book is committed.

## Natural-text boundary check

The Last Anchorage's already-inspected frozen development snapshot is available at
`runs/full-book-trial-20260919/readout-frozen/book.db`. Its head is
`0c1b306d3d401eda38cec60067d131ec6ab4a313367fdcf95c719baf303892a8`.
The read-only MCP profile confirmed the source identity and absence of pending migrations before
design work. The selected book is development material, never a holdout.

Read a consistent backup with `corpus_io.generated_scenes`, with `min_words=0`, using the current
export representation. Refuse an absent source or pending migrations, and never migrate the
original. Check every reached scene against the *whole-source* grammar; report refusal offsets
and hashes without treating arbitrary non-parsing prose as negative labels. This checks that
the prototype does not silently admit natural prose by throwing away context. It is not a
prevalence estimate, a search for all possible causal relations, or an informative test of a
reader. Preserve full local inputs and the original database hash.

## Operation and output

Use `runs/box.lock` for sustained validation, after checking other jobs. No provider, GPU or
network is needed. Keep generated packets and source snapshots under ignored `runs/`. Refuse
existing output paths. Commit only the derived report with its source identities and control
outcomes, plus implementation and tests. This implementation fact receives no research claim
record. Any later reader experiment needs its own committed registration.

```powershell
uv run pytest tests/test_prerequisite_certificate.py -n 0
uv run python research/quality-measurement/scoped-prerequisite-20260927/run.py --out runs/scoped-prerequisite-20260927 --database runs/full-book-trial-20260919/readout-frozen/book.db
uv run python tools/check.py handoff
```

The result must separate `logic_certified` from `ecological_admission`. The latter remains false;
the grammar is not a semantic certificate for an unrestricted generated manuscript. A later
natural-language grounding contract cannot be obtained by loosening this parser or trusting a
model's interpretation. No reader eligibility or production authority changes here.
