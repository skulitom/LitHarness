# Is the unconditional unfamiliar-life sentence causing the added obligations?

The operator asked to investigate and fix the cause on 2026-09-12. This registration tests
one proposed prompt cause before changing the default. It does not create a reader score,
candidate selector or automatic editorial feedback mechanism.

## Fixed sources and intervention

Use both deferred-genre adaptations from the preceding experiment, unchanged:
`adapt-late-1-1` (Salma) and `adapt-late-2-1` (Nico). Their original selection was committed
before any story output. Include both; neither is chosen for apparent quality. Freeze their
receipts, parsed text, parent registration and source lineage. These known cases motivated
the test, so this is not unseen-source transfer evidence.

The prior plans added nursery-related obligations absent from these two adapted premises.
CONJECTURE: the unconditional sentence requiring unfamiliar life's pursuits, relationships
and history invites that addition. An observed correspondence is not yet a causal result.
Use fresh controls and change only that sentence in discovery.render_request's system:

- full: unchanged frozen discovery request.
- omit: delete exactly the sentence identified by ORIGINAL in run.py.
- scoped: replace it with the sentence identified by SCOPED in run.py, requiring that
  elaboration when the author's brief introduces unfamiliar life or intelligence.

Everything else remains fixed: premise, schema, user prompt, profile, output limit, model,
effort and provider. Deletion shortens the request; scoping changes its length and meaning.
The conditional does not prohibit inventing beings or ban any particular story material.
No nursery, family, water or repair prohibition enters a generation prompt. Prior plans,
chapters, critiques, reader answers, corpus and external examples are excluded.

Use the existing frozen d4ebdb5 source, native Codex binary and subscription transport,
requesting gpt-6-astra at medium effort. As with the preceding expansions, supplied-premise
requests have no separate seed prefix. These are controlled expansions of two already seeded
stories, not a test or alteration of the fresh Base64 generation default. Repeats are exactly
the same captured application and transport request in fresh sessions.

The twelve-plan order is full-1-1, omit-1-1, scoped-1-1, scoped-2-1, omit-2-1, full-2-1,
scoped-1-2, omit-1-2, full-1-2, full-2-2, omit-2-2, scoped-2-2. Thus each source reverses
condition order on repeat 2. Keep every first response. No ranking, substitution or reroll.

After all plans, draft the repeat-1 full/scoped sources in order full-2-1, scoped-2-1,
scoped-1-1, full-1-1. Use the preceding experiment's exact standalone drafting renderer,
third person past tense, 1200-1600 words, with only the plan's world/opening/growth object.
Do not call Discovery.render, which would reintroduce the stored original direction.
Invalid plans skip their assigned chapters without substitute. This is not a complete book
run: later mechanical development, production planning and editorial acceptance are absent.

## Reading and decision rule

Read no new prose until all slots finish or an operational stop fires. Then read all retained
plans and chapters, including validation refusals. Record receipt, field/paragraph and text
hash for each observation. Preserve departures in full controls and failures in both modified
arms. Distinguish source inheritance from new plan material and new chapter material.

Inspect added nonhuman households, ancestry, nurseries or breeding sites, maintenance work,
and bargains making the protagonist's pursuit depend on protecting or servicing them. A new
creature alone is not that repeated causal family, and a different noun for the same activity
does not remove it. Also inspect whether the original desire, chosen action, consequence and
power progression survive. Nico's sale investigation and Salma's school/relocation conflict
must remain recognizable; omission of the story itself is not a successful fix.

The registered causal lead requires fresh full controls to reproduce the added family on
each source, while both omitted-sentence repeats remove that addition on both sources without
displacing their central action/progression. A full control lacking the addition is a real
counterexample; mixed repeats weaken the claim. Persistence in both omitted repeats for a
source defeats the claim that this sentence alone is sufficient to remove that source's
addition. No reproduction in full controls leaves the causal attribution unresolved.

The scoped wording is a candidate correction only if it also avoids that added family in
both repeats of both sources, preserves the supplied pursuits and usable progression, and
does not restore the family in either assigned chapter. Missing/invalid required comparisons
cannot count as passing. It need not remove source-inherited administrative action or all
water settings. This is a narrowly located feasibility rule, not a numerical quality bar.

A favorable result would support narrowing this mandatory instruction under the operator's
request; it would not establish general originality, whole-book quality, reader enjoyment,
training-distribution OOD or an automatic finding-to-prompt loop. Any product correction must
preserve prior discovery-version rendering, the author's direction, fresh seed behavior and
existing accepted books, and include focused compatibility checks. A failed or ambiguous
contrast does not justify installing this wording as a demonstrated fix. Record the smallest
claim warranted by artifacts, not the rhetoric of the report.

The independent source unit is two previously observed premises. Repeated calls are sampling
replicates; fields and paragraphs are not additional independent stories. Prompt length,
known-source reuse, single drafts and undisclosed backend behavior remain limitations.
Semantic inspection is unblinded and not a qualified reader instrument. No output is ranked
or selected by a model. No claim about prose superiority follows from a source difference.

## Operation

Read CONTRIBUTING.md, BRIEF.md, EPISTEMIC_GOVERNANCE.md and the shared-box section of the
parent RUNBOOK. Check processes and atomically hold this task's runs/box.lock. Run calls
sequentially, without sustained checks beside them. Every handoff uses one worker plus
OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1 and MKL_NUM_THREADS=1.

Freeze scripts, tests, protocol, source artifacts, requests, provider and binary. Run handoff
and commit registration before dispatch. Record attempts and completions atomically with
flush/fsync, native traces, exact input and usage. No API key, direct billing fallback,
live-provider test flag, reset, retry or implicit resume. Stop on unknown usage, frozen-file
drift, transport/authentication/quota failure. Retain all failures and unattempted slots.

Ceilings are sixteen calls and 120000 recorded tokens, checked before each call; one in-flight
call can overrun the latter. Output limits are 2400 for plans, 4200 for chapters; timeout is
600 seconds per call. Validate plans with the same Discovery.from_invention as production.

```powershell
uv run python research/quality-measurement/discovery-life-scope-20260912/run.py prepare
# One-worker handoff and registration commit precede dispatch.
uv run python research/quality-measurement/discovery-life-scope-20260912/run.py run
uv run python research/quality-measurement/discovery-life-scope-20260912/audit.py
```

The offline audit checks frozen inputs, source lineage, actual effective system including
the schema instruction, native schema, repeat/arm differences, sessions and usage. It keeps
field hashes for structurally readable refused plans too. Keep raw prose under the ignored
run root. Commit derived controls and bounded located observations. Run final one-worker
handoff before commit/push under the operator's existing authorization. Preserve unrelated
edits and release only this task's owned lock.
