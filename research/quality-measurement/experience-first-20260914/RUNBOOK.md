# Experience before discovery: feasibility pilot

Status: registration, not evidence of reader enjoyment or commercial success.

## Question and authorization

The operator approved trying the approach developed in the local reader-pleasure study:
invent an intended reader experience in prose before the ordinary discovery treatment.
This isolated research task asks whether that representation changes what survives through
discovery, mechanical concept development, an outline, and an opening chapter. It does not
change production prompts, select a book, or qualify an editorial intervention.

Read the parent [RUNBOOK](../RUNBOOK.md), [BRIEF](../BRIEF.md), and
[epistemic governance](../EPISTEMIC_GOVERNANCE.md) before execution.

## Fixed design

Six independently authored, general creative briefs: two about competence, two about
discovery, two about belonging. Each has one independently drawn 2048-bit opaque invention
prefix. Three arms share that brief and prefix:

- A: the committed discovery request unchanged.
- B: an additional 450-650-word planning-language proposal, then discovery.
- C: an additional 450-650-word prospective fictional scene, then discovery.

B and C have identical creative requirements, schema, output allowance, downstream wrapper,
and provider settings; their representation instruction differs. C versus B is the primary
contrast. A measures what adding either preliminary step changes. These are total effects of
the different proposal routes: neither extra-call duration nor actual returned length is
forced equal. A common prefix does not make native generation deterministic.

The six blocks use all six permutations of A/B/C, fixed in the runner. Stage order is all
preliminary proposals, all discoveries, all concepts, all outlines, all opening chapters.
Every valid designated first output advances; no aesthetic filter, alternative draw, ranking,
or substitution is permitted. A malformed parent skips only its descendants. A transport,
containment, missing-usage, or frozen-input error stops new calls for the entire run.

## Inputs and isolation

The production source is archived from committed revision 78dfe30 before registration.
The archive excludes unrelated working-tree changes. Imports use that archive. All source
files, the lockfile, native executable, runner, tests, runbook, seeds, and static requests are
content-addressed before dispatch. Registration must be committed and present in origin/main
before the runner starts. No production stores are opened and no manuscript is accepted.

No favorite-book prose, review, digest, title list, or research report enters any generation
request. The six briefs and common instructions are original general creative intentions.
The native provider runs isolated, ephemeral, tool-free sessions with project instructions,
user config, and memory disabled. The model and effort are the current provider defaults:
gpt-6-astra and medium. No model switching, usage reset, or fallback is part of this run.

The extra proposal is explicitly revisable future material. It creates neither author locks
nor accepted history, and is supplied once, to discovery. The concept is developed with the
unchanged production renderer. Its parser mechanically retains discovery.opening as
first_arc.opens; that equality cannot be reported as model preservation.
The existing Concept.for_outline projection then omits discovery.opening, first_use, and
first_arc.opens. Thus exact opening choreography is intentionally unavailable to the planner;
this pilot examines transfer through the remaining foundations and commitments. That omission
is a source-code fact, not a model defect or a result of this experiment.

The production outline renderer receives the concept, original brief as premise, six ordinary
beats, a plan base containing only that locked premise, and 1,400 target words per scene.
There is no generated
world, state ledger, promise schedule, or accepted history. Each scene is one proposed chapter.
The chapter adapter receives only the original brief and the first structured scene handoff.
It does not receive the prototype, discovery, or full concept again. This is an isolated
drafting adapter, not the complete production conductor/Architect/writer packet.

## Limits and execution

Maximum 84 application calls: 12 preliminary + 18 discovery + 18 concept + 18 outline +
18 draft. Calls are sequential under runs/box.lock. Before a new call, stop at 2,500,000
recorded tokens or 180 minutes since dispatch began. An admitted call can take the total
beyond either ceiling. Existing renderers retain their timeouts (outline: 1,800 seconds;
discovery/concept: 600); the two research adapters use 600 seconds. There is no shell timeout.
Native transport may consume resources beyond its reported usage; this is an admission bound,
not a guaranteed financial cap. The native subscription transport is used, not a billed API.

Run from the repository root:

```powershell
uv run python research/quality-measurement/experience-first-20260914/run.py prepare
uv run python research/quality-measurement/epistemic_governance.py research/quality-measurement/experience-first-20260914/claim.json
```

After offline tests and `tools/check.py handoff` (set PYTEST_XDIST_AUTO_NUM_WORKERS=1),
commit and push the exact registration files. Then:

```powershell
uv run python research/quality-measurement/experience-first-20260914/run.py run
uv run python research/quality-measurement/experience-first-20260914/run.py audit
```

Preparation and dispatch refuse existing state. There is no implicit resume or retry. Keep
failed receipts. A new draw requires a new registration. Release only this task's lock after
the run and sustained checks finish.

## Observation, not an enjoyment instrument

Do not inspect generated content until generation finishes or stops. Then read every reached
output, including all three arms, before describing individual cases. Audit request bytes,
parent lineage, schema validity, transport containment, session independence, source hashes,
and lengths. Record omissions and unreachable stages, not just completed pairs.

The descriptive reading follows these questions, without scores or pass thresholds:

1. What does this person want to be able to do, discover, or share?
2. Which proposed event makes that experience concrete?
3. At each handoff, what is retained, changed, postponed, or lost? Cite field or paragraph.
4. What does the chapter actually dramatize, and what only remains in the outline?
5. Is a future event accidentally treated as past history or present capability?
6. What contrary example or alternative explanation limits the interpretation?

Repeated agreement, prose enthusiasm, requested keywords, and numerical progression are not
evidence of pleasure. Do not aggregate these descriptions into a quality score or rank arms.
No reader model, human panel, winner selection, or adaptive editorial feedback is licensed.
Two blocks per intention are not a population estimate; one chapter cannot establish retained
capability, long-arc payoff, retention, or popularity. If the first scene defers the relevant
event, record that coverage limit rather than forcing the whole arc into the opener.

Raw outputs and reading copies stay under ignored runs/experience-first-20260914. Tracked
evidence contains identifiers, hashes, derived counts, and methodological conclusions; prose
reading notes remain local. Any follow-on intervention needs its own evidence and scope.
