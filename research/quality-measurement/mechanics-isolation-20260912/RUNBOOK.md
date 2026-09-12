# Design magic separately, with and without the protagonist's pursuit

The operator authorized continued investigation on 2026-09-12. This isolated authoring
experiment changes no production default or stored book and uses no quality score, reader
feedback, model selector, corpus text or authored world palette. New prose stays under
`runs/mechanics-isolation-20260912`.

## Question and prior failures

The invention-order-20260912 outputs retain their newly specified personal goals while
developing familiar connection repair and negotiated travel. Field order and an extra goal
field failed their registered repetition rules. Earlier world seeds and preservation-only
instructions already changed concrete powers/actions without reliably preventing the broader
plot. The new contrast concerns a separate mechanics-design step, not another list of powers
or a demand to preserve a supplied story more emphatically.

Conjecture: designing a magic discipline separately may reduce automatic conversion of a
personal undertaking into a magical version of its practical work. Withholding the goal from
that design step may help further. Neither explanation is established. Test the common
staging procedure and goal withholding separately; favorable staging cannot establish that
withholding caused its effect.

Use all three pursuit fields from the previous experiment's pursuit-1/2/3 receipts, copied
exactly without their opening, world or growth. They concern a mosaic, ferry and pear tree,
with sibling disagreements. They are a biased family of preservation/restoration goals, not
representative fiction prompts. Using all three avoids choosing a favorable goal from that
run, but does not remove this source limitation. Preserving a repair aim is not itself an
error; inspect what supernatural operations and additional dependencies the model invents.

## Arms and lineage

Draw three new 2048-bit integers and use the unchanged v3 Base64 prefix, fixed within each
goal block. Request gpt-6-astra, medium, through the existing subscription-only native
provider. Use fresh ephemeral sessions, no tools, external history, API fallback or retries.

First make two mechanics calls per goal:

- linked: the mechanics designer receives the exact pursuit.
- blind: the same designer is told that no story pursuit is supplied. It receives no goal,
  occupation, person, setting, earlier story, diagnostic or forbidden motif.

The system, schema, seed, limits and all other request fields are identical within each pair.
Only the user message differs. The common task requests a novice effect, limitation,
advancement condition and later extension, 250–350 words total, with no invented protagonist,
setting or plot. The word range is an instruction, not a quality gate. The model invents every
mechanic; there is no palette or selection step. Goal availability and prompt length change
together. A shared seed is not proof of identical backend randomness.

Then make three discovery calls per goal, all with unchanged production render_request:

- direct: the exact pursuit alone as the brief.
- linked: the exact pursuit plus its first linked mechanics object.
- blind: the exact pursuit plus its first blind mechanics object.

The latter two share all request fields except the supplied mechanics. They receive neither
arm labels nor other variants. No critique, summary, edited mechanic or chosen candidate is
inserted. The direct comparison changes the availability of a separate mechanics object and
its generation cost, not just wording. It is a procedure comparison, not an isolated proof
about any particular mechanics instruction.

Mechanics order: linked-1, blind-1, blind-2, linked-2, linked-3, blind-3.
Discovery order: direct-1, linked-1, blind-1, linked-2, blind-2, direct-2, blind-3, direct-3,
linked-3. All mechanics finish before discovery. Freeze sources, goal extractions, seeds,
static requests, renderer, tests and binary before dispatch and commit registration first.
Derived discovery requests are constructed from their designated first parent by the frozen
renderer, saved before dispatch and audited against that receipt's hash. No new registration
choice occurs after outputs. A structurally invalid mechanics parent skips its single
descendant without replacement; other independent slots continue.

## Reading and predeclared decisions

Read no new generated prose until the fifteen-slot sequence finishes or an operational stop
occurs. Then read all mechanics and plans in full, including invalid outputs. Locate each
observation by slot, field and paragraph, with text and receipt hashes in the derived record.

Compare the novice operation, learning condition and later extension across mechanics arms.
Trace each into its discovery: what action earns the first power, what it accomplishes for
the exact goal, what later capability is sought, and what new social/material access is
required. Record changed or discarded rules, lost personal conflicts and retained departures
as well as recurrence. Repairs, water or names alone do not define the target. The recurring
engine is helpful practical work earning structural/transport magic and passage, followed by
further maintenance, nursery/kinship duties or negotiated network access governing progression.
Restoring the source's ferry or tree without those extra dependencies is not automatically
recurrence. A materially different first use must be retained as a counterexample even if
later growth returns to familiar obligations.

Two separate local-feasibility claims have separate rules:

1. Shared staging is a lead if at least two direct controls reproduce the target engine and
   all six staged plans avoid it, retain their exact goal/conflict and supplied mechanics,
   and have different causal means of pursuit across goals rather than one renamed replacement
   template. Recurrence in any staged plan kills this exact consistent-staging claim.
2. Goal withholding is a lead if at least two direct and two linked plans reproduce the engine,
   while all three blind plans avoid it and retain their goal/conflict and mechanics without
   converging on one replacement template. Recurrence in any blind plan kills this claim.

Missing controls, invalid outputs, source loss or convergence prevent a positive conclusion.
If both staged arms depart, credit neither specifically to withholding. If mechanics differ
but plans restore the engine, locate that transition rather than calling new skill names a
fix. A surviving case does not replace a failing case. No numerical creativity score, ranking
or literary-quality bar is inferred from these located, unblinded model-reading observations.

Three source/seed blocks, one draw per condition and related goals severely limit transfer.
Even a positive result needs fresh-goal repeats and downstream preservation evidence before
a production change. No chapter, conditional extra call or promotion is assigned in this run.

## Operations

Check processes and take the shared box lock atomically. Announce ownership and release.
One call or sustained check at a time; cap math/test workers at one. At most fifteen attempts,
no new call after 120000 recorded tokens, 600 seconds per call. That token ceiling is a
pre-call stop and can be exceeded by the last call. Save started/completed/failed receipts,
parent hashes and progress atomically. Unknown usage, provider failure, frozen-file drift or
lock loss stops the run. No automatic resume, replacement, model switch or usage reset.

```powershell
uv run python research/quality-measurement/mechanics-isolation-20260912/run.py prepare
uv run python tools/check.py handoff
# Commit registration before any dispatch.
uv run python research/quality-measurement/mechanics-isolation-20260912/run.py run
uv run python research/quality-measurement/mechanics-isolation-20260912/run.py audit
```
