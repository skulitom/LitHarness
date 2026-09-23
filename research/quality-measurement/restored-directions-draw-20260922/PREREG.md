# Restored-directions draw: registration

**Status: REGISTERED once `run.py prepare` has written `registration.json` and that commit is
pushed; nothing is bought before.** Drafted 2026-09-22 and revised 2026-09-23 after review,
both times while another arm held the box: no test, runner or model call was made to write
it. The runner is [run.py](run.py), the procedure [RUNBOOK.md](RUNBOOK.md), the tests
`tests/test_restored_directions_draw.py`. Read [BRIEF.md](../BRIEF.md) §5 and §6 and
[EPISTEMIC_GOVERNANCE.md](../EPISTEMIC_GOVERNANCE.md) first.

## Question

Stage-0 §255 restored the operator's standing directions where our own changes had dropped
them: the exception that belongs to one person and works for them in chapter one, counted ranks
with a starting rank, a world people live in with costs that fall on a person, a protagonist
the shelf's reader could have been, the first-use placement in chapter one's outline, and the
seed's counted place for the protagonist. §255 shipped them as delivery and round-trip
contracts and says so: "No live generation was run on either route or provider, and delivering
an instruction is not evidence that a model follows it."

This draw asks two things of one fresh book on the production default path, stopped after
chapter one:

1. **Delivery, end to end.** Does every production request each restored direction is written
   for carry it, from the first invention call to chapter one's outline? Checked in code on the
   recorded requests.
2. **One gated draw.** What do the concept, the listing, the seeded world and chapter one look
   like, read by a person at four checkpoints against the operator's enumerated items?

## What the draw can and cannot establish

It **can** establish:

- that each registered direction text reached every request of its profile, verbatim (the
  delivery table below), and that the first live invention request was the one the offline
  preflight registered (the recorder refuses it before dispatch otherwise);
- that the default path on Codex ran from a fresh store to an accepted chapter one under these
  directions with its transport controls intact, or exactly where and why it stopped;
- deterministic, located observations at each checkpoint (counts, never verdicts);
- the coordinator's gate read at each checkpoint, recorded item by item and held to the
  registered pass rule.

It **cannot** establish:

- **Compliance as a rate.** One draw is one sample. A pass shows the pipeline delivered these
  directions and a person found them honoured once; a fail locates one instance.
- **Reader evidence, quality, enjoyment or release readiness.** No reader instrument is run.
  The listing loop's browsing readers are production's and run as production runs them; their
  answers are model outputs, the runner never reads them, and no gate may use them. The gate
  read is a diagnostic harvest, not measurement, and none of it enters a prompt.
- **Premise novelty or invention diversity.** The brief supplies the premise on purpose.
- **The other routes.** §255's evidence boundary asked for a smoke on both routes. This is the
  default route only: no `--planning-material`, no Claude transport, no candidate tier routing.
- **Cause.** There is no arm without the restoration, so nothing here attributes a behaviour to
  §255. Draws are never compared, so a later pass is not evidence that a fix between draws
  worked. With up to three draws a pass somewhere is likelier than a pass in one (BRIEF.md §6,
  question 6: three attempts at an even chance pass seven times in eight), so the result is
  reported per draw, every draw with its fix, and never as "the pipeline passes".

## Why a hook-template brief

The author brief is fixed now. It is the operator's standing hook direction (an ability nobody
else awakens), chosen by the coordinator:

> System apocalypse. When the System arrives, every person on Earth receives exactly one Slot for
> one skill. The protagonist, a man in his twenties, receives a Slot that can hold as many
> skills as he can take. Invent the rest.

SHA-256 `20fef8c91570140f79f83ec5031e5300fc1515d8745044406127dc984e55a54e` over its UTF-8 bytes.

It sidesteps open invention deliberately. The invention-diversity experiments recorded in
[RESEARCH.md](../../../RESEARCH.md) §4.5.2 (seventeen, by the coordinator's count) found the
repeated premise in the first invention call, and no input tested there removed it in its
registered test. An empty brief would confound this draw with that known, unsolved failure. So
the draw tests the restored directions **downstream of a supplied hook**, not premise novelty.

What the brief already supplies, and so what the gate cannot credit to §255: the one-person
exception's premise (C1 is largely given; its working in chapter one and its pulling ahead are
not) and the protagonist's age (half of the reader-life direction; the prior life is left to
invention). What it leaves to the pipeline: the counted ranks and the starting rank, the
threat, the System's look, whether the world is administrative, the first use in chapter one,
the protagonist's prior life, the seed's placement on the ladder, and chapter one itself.

## Fixed inputs

- **Path.** The README's "Start a serial": `concept` (discovery, development and the precision
  edit), `listing --concept … --scenes 24` (which stands the book up), `architect seed`, `world
  check`, `world accept`, then `tick`. Production defaults stay off: no `--planning-material`,
  no exemplar shelf, no director, no reviser, no reader checkpoints.
- **Three disclosed deviations from that recipe.**
  1. `listing --no-title-check`, as the 2026-09-12 fresh chapter did; the lookup is a web
     search over an unpublished working title and bears on no §255 item.
  2. `concept --person third`. The README passes `--person third` to `listing` and no person
     to `concept`; the draw passes it to both, so the invention request is asked for the person
     the book is told in.
  3. `--max-invocations-per-day 60 --max-tokens-per-day 2000000` on every verb, against the
     CLI defaults of 500 and 5,000,000. They can refuse a call production would make; a
     refusal is an operational stop (below), never a retry.
- **Layout.** A 24-scene opening arc of six chapters of four scenes (the CLI defaults, passed
  explicitly to every verb so invention and the book share one layout), the CLI's default target
  words, third person. Chapter one is the first four scenes in reading order.
- **Provider.** `LITHARNESS_PROVIDER=codex`, the native binary
  `C:/Users/artem/AppData/Local/OpenAI/Codex/bin/247581e40ee272fb/codex.exe` pinned at prepare by
  path, SHA-256, size, mtime and `--version` (which makes no model call); the adapter's default
  model `gpt-6-astra` at its default `medium` effort, both checked in the frozen source by the
  preflight. The child environment inherits no `LITHARNESS_` variable, so
  `LITHARNESS_MODEL_TIERS`, `LITHARNESS_CODEX_EFFORTS` and `LITHARNESS_CODEX_MODELS` are unset
  and every role is strong; the recorder refuses any request that names a model.
- **Revision.** HEAD at prepare, which must carry `619c697` (§255), `fd77145` (§256),
  `1c16fe7` (the plural-decade precision rule), `60b1d56` (§257) and `d146504` (§258); HEAD was
  `5269441` when this was revised. The commits after `d146504` (`f131809`, `935b383`,
  `5269441`) change research folders, `RESEARCH.md`, `plan/` and tests only, nothing the
  archive holds. What each production commit after `fd77145` means for this draw:
  - `1c16fe7` committed the `application/precision.py` edit that was uncommitted on 2026-09-22,
    so the plural-decade rule ("1890s" is a digit quantity) is inside the archived source and
    inside this draw's precision pass.
  - §257 records a packed promise line's derivation beside the drafting request: job input
    digests move, and no request byte, packet or sample does.
  - §258 moves every Claude transport out of the repository (`providers/cli.py`, the research
    transports) and pins `recruit`'s roster path. This draw makes no Claude call and no
    recruit, and the Codex adapter already ran each call in a temporary working directory
    with `--skip-git-repo-check`; the audit checks both on every receipt.

  HEAD is archived with `git archive` (src, migrations, pyproject.toml, uv.lock) into a runtime
  of its own, which is what every step and every world-tool child imports. Its third-party
  dependencies, `litharness-contracts` among them, come from the shared `.venv` site-packages:
  the contracts package's files and dist-info are frozen by hash, every installed distribution's
  version is recorded, and both are checked before every stage and every step. A change found
  before a stage starts refuses it with nothing bought, and restoring the environment clears
  the refusal; one found by a step inside a stage is an operational stop. Stage commands run
  under `uv run --no-sync`, so the runner never re-syncs the environment it froze. Any
  working-tree change under the archived paths at prepare is listed in the registration and
  left out.
- **Invention seed.** The production prefix seed (`invention-seed.v3`, 2048 random bits), drawn
  once per draw at prepare the way the CLI draws it, kept locally, hashed in the registration and
  passed as `--seed`. The invention request is therefore fixed before spend: the offline
  preflight records its digest, and the recorder refuses the first non-probe concept call,
  before dispatch, unless its request has that digest.

## Writer

**The rule, stated before the draw.** Draw 1's writer is the first accepted, never-cast writer
in the recruiter's slate order (`application/recruiter.py` `SLATE`, then `SUPPLEMENTARY`) whose
shelf is one of the operator's default genres for new books (portal fantasy, isekai, system
apocalypse; commit `446638f`, 2026-09-08). As the roster's exact shelf slugs those are
`isekai`, `portal-fantasy` and `progression-fantasy`: the roster has no system-apocalypse
shelf, and the coordinator reads system apocalypse as progression. Casts were read from the
pilot records (`plan/serial-pilot-13.md` to `-25.md`), stage-0 §242-§247 and the run folders
under `runs/`.

**Taking the slate in order.** Accepted writers already cast: larkin (light-fantasy, pilots 13
and 14), penhale (cozy-fantasy, 15), brannigan (litrpg-comedy, 17), sandoval (sci-fi, 18), and
on the default shelves marsh, barlow, carver and hollis (progression-fantasy) and tanaka
(portal-fantasy). Uncast, in slate order: draycott (dark-fantasy, slate position 5), mabry
(supernatural, 6), **rowntree (isekai, 11)**, calloway (mystery, supplementary 1), trevelyan
(historical-portal-fantasy, supplementary 3). The first uncast writer on a default shelf is
**rowntree**: writer id `wtr-43f373dd421c86f46c622872`, dossier SHA-256
`b97a225325e883c55c5fe18a04fa6cd48ba6ce638e1d98a48efcf33d9221ffa8` over its UTF-8 bytes, read
from `runs/roster/roster.db` through a `mode=ro` connection on 2026-09-23. Trevelyan's shelf
("historical, paired with portal fantasy") is not the `portal-fantasy` slug, and it comes after
rowntree's in slate order in any case.

**draycott, passed over for a located reason.** The earlier draft cast draycott, the first
uncast writer in slate order. His dossier's prose, which rides discovery, the listing and every
scene call, loves "a price that gets paid" and "a bargain nobody walks away from clean", and his
interests list "bargains and what they cost": the frame §255 removes. A concept, listing, world
or chapter failure on a bargain, price or debt under him could not be attributed to the pipeline
rather than to him, so he is not a writer this draw can read.

**Redraw writers.** A `writer` amendment moves exactly one place along `rowntree, barlow,
carver, hollis, tanaka, marsh`: the default-genre writers already cast, least recently cast
first. They are exempt from "never cast"; mabry, draycott, trevelyan and calloway are never
redraw writers. The order, from the last recorded cast of each:

| Writer | Shelf | Last recorded cast |
| --- | --- | --- |
| barlow | progression-fantasy | pilot 21 draw 3, 2026-09-02 (`plan/serial-pilot-21.md` §5) |
| carver | progression-fantasy | pilot 22, 2026-09-02, after pilot 21's draw 4 |
| hollis | progression-fantasy | pilot 23, 2026-09-02 |
| tanaka | portal-fantasy | *One Clean Want*, 2026-09-08 about 11:53 UTC (§247; `runs/fresh-chapter-20260908`) |
| marsh | progression-fantasy | *Five Notes Under Kittle Street*, 2026-09-08 about 16:48 UTC (`runs/fresh-chapter-marsh-20260908`) |

Pilots 21 to 24 all ran on 2026-09-02, so pilot order breaks the tie. The committed record
alone would put marsh (last committed at pilot 24) before tanaka; the ignored run folder
`runs/fresh-chapter-marsh-20260908/` (its `run.json` and `commands.log` name `--writer marsh`)
records a later cast, so marsh is last. With at most three draws only rowntree, barlow and
carver can be reached. Every writer in the sequence is pinned in `run.py`'s `WRITERS` by writer
id and dossier hash from the same read; a writer amendment must carry that pair and prepare
checks it against the draw's roster copy. A fix or transport redraw keeps the previous draw's
writer and is checked against that draw's recorded pair. The roster also holds a refused
historical recruit named hollis; resolution reads accepted rows only, so the progression-fantasy
hollis is the one cast.

Each draw resolves its writer from a copy of the installation roster taken through a read-only
connection at prepare; the draw never opens the installation roster.

## The writer's dossier: risks named before the draw

The dossier's prose rides discovery's system message, the listing's and its title's requests,
and every scene call. Development, the precision edit, the Architect's seed (a concept with a
treatment drops it: `world_agent.render_seed_request`) and the outline do not carry it. A
writer's interests never reach a request (`Writer.render` sends the dossier prose only), so an
interest is read here as the taste the prose already carries, not as a second channel. Three
things in rowntree's are watched, each against the items it could fail:

- **"a summons that came with obligations nobody mentioned"**: an obligation owed to whoever
  called him, which is administrative pressure and a debt frame by another name. Watched at
  W1, H2 and C4.
- **A caller who issues the power**: the dossier's "a summons" and "wish they had been called
  too", with the interest "summoned heroes and the kingdoms that called them" naming the same
  taste. An institution that issues the exception would make it no longer one person's.
  Watched at L2, L3 and W1.
- **The isekai pull**, "a person wakes on grass that is not their grass" and "small knowledge
  from home": a second world, against the brief's Earth. Watched at C1 and H1, beside the
  concept observation that the author brief was retained.

Fixed now: a failure on an obligation, summons, institution-issued power, debt or ledger frame,
or a premise moved off Earth, is read against the dossier first, as pilot 17 read brannigan's
(two draws, one engine, the dossier), before any cause in `src/` is claimed. The remedy for a
dossier cause is a `writer` amendment to the next writer in the sequence (barlow), never an
edit of the dossier or a prompt. That amendment names the new writer's own watched risks from
his dossier before his draw.

## Stages and checkpoints

Each stage is one command; each ends at a checkpoint where the runner exits and waits for a
person. A stage runs once per draw and only after a recorded pass at the previous checkpoint.

| Stage | CLI steps | Checkpoint | Items the gate read answers |
| --- | --- | --- | --- |
| `concept` | `concept` | concept | C1 the exception belongs to one person and works for them in chapter one; C2 counted ranks with `system.start_rank`; C3 a physical threat; C4 no debt, ledger, court or tenancy frame in the premise, the threat or the System's look |
| `listing` | `listing` | listing | L1 it promises LitRPG (pilot 18); L2 the exception it sells is one person's; L3 no institution-issued engine and no debt, ledger, court, tenancy or licence frame (pilot 17, §116); L4 no internal schema word in the title or listing (read 11) |
| `seed` | `architect seed`, `world check` | world, before `world accept` | W1 no administrative pressure; W2 the protagonist placed on the ladder at the concept's start rank (not placed for an unranked start); W3 world check reports no snapshot fault and no would-breach |
| `chapter` | `world accept`, then `tick` until chapter one's four scenes are accepted | chapter | H1 the exception is one person's and works on the page; H2 no debt, ledger, licence or administration register; H3 system numbers present and the sheet renders; H4 progression felt; H5 a man in his twenties with a prior life the reader has lived; H6 attention on the pursuit, not one procedure; H7 tone matches the popcorn shelf; H8 third person throughout |

The concept and chapter items are the task's and the coordinator's A1 gate table's; the listing
and world items are the operator's recorded refusals and §255's seed sentence. "Fresh premise",
an A1 gate item, is not asked: the brief fixes the premise.

**What the gate reads is bound.** When a stage ends, a no-provider child records the
checkpoint's files by hash (the concept or listing folder, the stage's step records, and at
chapter one the reading copy and the exported library) and a digest of the store (every state
record, the scenes' ids and accepted texts). The gate refuses if any of it changed. The next
stage re-checks the files before it starts, and its first step re-reads the store before it
runs: the listing acts on the concept the C gate read, and `world accept` accepts only the world
the W gate read. A binding that cannot be written is an operational stop.

## The gate

A person's read at each checkpoint, the coordinator's under the operator's sanctioned loop,
decided only on structure, mechanics and the operator's enumerated items. Sentence-level notes
are residuals and never decide. The read is a file under the ignored run folder that gives each
item exactly one verdict line: the id at the start of a line (a list bullet is allowed), a
colon, then `PASS`, `FAIL` or `PARTIAL` and a location.

**The rule.** A checkpoint passes only when every item is `PASS`. `PARTIAL` counts as `FAIL`.
The runner parses the verdict lines and refuses a read that misses an item or answers one
twice, a `pass` over any item that is not `PASS`, and a `fail` over a read whose items are all
`PASS`. It stores each item's verdict in the gate record and in `evidence.json`, hashes the
read, and checks nothing else about it.

Transport failures are read before any verdict: the gate refuses while any call of the draw
failed or never finished. One verdict per checkpoint. A fail ends the draw. A pass at chapter
one ends the series.

## Observations printed beside each gate (inert)

Counts and flags, computed by code, printed beside the gate and never deciding it. No threshold
is registered on any of them. An observation that fails to run is recorded as failed (its exit
code and a log hash) and the gate proceeds without it: observations decide nothing, so they
can block nothing.

- **Administrative lexicon: the same ten words the coordinator's A1 gate read counted**
  (ledger, debt, claim, tenancy, contract, permission, certify, inspect, compensation,
  account). That read states the words and not its counting patterns, so the patterns are this
  runner's (`ADMIN_LEXICON` in run.py) and its numbers are not comparable to that read's.
  Counts and a rate per thousand words. Reported separately, never added: court, licence,
  permit, registry, clerk, fee, tax, owe (`FRAME_LEXICON`). "Account" also counts ordinary use;
  the lexicon is kept as stated rather than tuned.
- Words, numbers (digit runs) and digit characters; status lines and their cells
  (`application/statusline.py`); the tells families of `domain/tells.py` per thousand words
  (the long family needs a shelf threshold and counts nothing here); schema words
  (`domain/schema_words.py`).
- Concept: the author brief retained, the discovery version, `steps`, `start_rank` present and
  in range, whether the precision edit kept `steps`, `start_rank` and `strongest_known` (§255's
  residual), the number of open questions, and the lexicon per field and over the premise,
  threat and look together.
- World, over the records in force (`integrity.in_force`, as the world views and `world
  accept` read them; the count they replaced is reported): records and proposals,
  protagonists, the protagonist's `stands_at` records, the rank their un-keyed standing
  declares counted from one (read off the declared records, since `world_brief.ladder_for`
  reads canon and nothing is canon before `world accept`) against the concept's start rank
  (§255's residual: nothing checks it), roles including institutions, schema-word complaints,
  the lexicon over the world's text, and world check's `ok` with the length of each list it
  reports.
- Chapter: words per scene, the prose counts above, declared cast and how many of their given
  names appear, library shelves, and per request profile the promise lines (the open-threads
  heading, the `open, not yet established:` prefix, any old `owes:`).

## Delivery checks

Profiles and texts are read from the frozen source at prepare, never typed here; the preflight
refuses to register if a literal needle no longer occurs in its module.

| Direction | Request profile at HEAD | Must carry |
| --- | --- | --- |
| discovery | `writer.discovery.v14` | `discovery.DIRECTION` (the v7 power sentence), `discovery.WORLD_DIRECTION` (with `READER_LIFE`) |
| development | `writer.concept.discovery.v9` | `WORLD_DIRECTION`, the one-power exception ask, the `start_rank` ask, and a schema requiring `system.start_rank` |
| Architect seed | `architect.seed.v9` | `discovery.LIVED_WORLD`, the seed's `stands_at` sentence |
| first-arc outline | `planner.outline.v8` | `concept.FIRST_USE_RULE`, `concept.EARLY_MAGIC_RULE`, this draw's concept's `first_use` text, and, when the concept has a start rank, its label in the projection's words ("rank 3 of 12", or "unranked") |

Delivered means every request of that profile carries every text, verbatim or JSON-escaped.
An absent profile is not delivered. The placement rule without the first use it places delivers
nothing, which is why the outline row carries the concept's own text. "unranked" is a weak
needle, a common word, and is reported as such.

## Redraw rule

- At most three draws. A draw ends at a failed gate or an operational stop; a stopped draw
  never resumes and a stage never runs twice.
- Every draw is shown to the operator whether it passes or fails, and `shown` records it. The
  next draw cannot be prepared until the previous one is recorded as shown.
- A redraw needs a committed amendment, `AMENDMENT-N.md` and `amendment-N.json`, naming a
  located cause and one of three remedies:
  - `fix`: new commits on HEAD, after the previous draw's revision. Production fixes
    (`fix_commits`) touch `src/` or `migrations/`. A runner fix (`runner_fix_commits`) changes
    this folder's `run.py` and nothing but it and its test, for a defect in the runner itself:
    an observer, the binding or the scheduler, which are frozen per draw.
  - `writer`: the dossier located as the cause; the next writer in the sequence, with his
    pinned writer id and dossier hash.
  - `transport`: the previous draw's failed call receipt, cited by path and SHA-256.
- **The registration cannot move silently between draws.** Every registered file (run.py,
  PREREG.md, RUNBOOK.md, the test, earlier amendments) whose bytes differ from the previous
  draw's registration must be listed in the amendment's `registration_changes` with its SHA-256
  now and the commit that changed it, and committed as it stands; prepare refuses otherwise.
- The new draw pins HEAD again, with a new seed. Every draw's writer is checked against its
  roster copy: draw 1 against the pair above, a writer redraw against its amendment's pair, a
  fix or transport redraw against the previous draw's.
- No model selects, ranks or compares draws, and the runner compares none. The gate reads each
  draw on its own. No automatic world repair.

## Ceilings

Per draw: **60 provider calls including health probes, 2,000,000 recorded `Usage.total`
tokens, 7,200 seconds** of stage time (time waiting at a checkpoint does not count). Series:
180 calls, 6,000,000 tokens, 21,600 seconds. At most 24 ticks and 3 consecutive failed ticks in
the chapter stage. The CLI's own daily ceilings are passed explicitly on every verb (disclosed
above): `--max-invocations-per-day 60 --max-tokens-per-day 2000000`.

Derivation, from the recorded costs: the 2026-09-12 fresh chapter on the same provider and
layout ([past-action-continuity-20260912/REPORT.md](../past-action-continuity-20260912/REPORT.md))
recorded 19 generation invocations and 401,794 tokens in its store; its transport folder holds 33
attempts with health probes; it ran about 25 minutes of wall time. The coordinator's range is 0.4
to 1M tokens per attempt. The ceilings are about 1.8 times the calls with probes, twice the top of
the token range and about five times the wall time. Admission is checked before every call; a
call admitted below a ceiling may cross it, and the next is refused. These are subscription usage
records, not dollars.

## Stop conditions

A failed or unfinished call (usage unknown; the receipt kept, never replayed as an answer), a
billed call reporting no usage, a first invention request whose digest is not the preflight's, a
changed binary, frozen input or installed dependency found inside a stage, a ceiling (one
crossed by a stage's last call ends the draw before the next stage starts), a request for tools
outside the world bridge or naming a model, an operational exit, a verb's failure exit (world
check's exit 1 is a result, not a stop), a parked or poisoned unit or open exception, a changed
accepted scene or scene count, a scene past chapter one, an idle tick before chapter one is
accepted, three consecutive failed ticks, 24 ticks, a refused `world accept`, a checkpoint that
could not be bound, and a store that changed after its checkpoint was bound.

## Outputs

Under the ignored `runs/restored-directions-draw-20260922/draw-N/`: the store, the frozen source
and runtime, the roster copy, `concept/`, `listing/`, `views/`, `checkpoints/` (each
checkpoint's binding, its observation or recorded observation failure, and the observer's log),
`calls/`, `steps/`, `transport/`, the library and `chapter-one.md`. On a chapter pass, `publish`
copies the reading edition into the ignored `book-library/<slug>/`. Committed: the registration
of each draw, each amendment, `claim.json`, and after the audit `evidence.json` and
`RESULTS.md`. `evidence.json` carries counts, flags, codes and hashes only: a stop or stage
reason is a code and the hash of its text, the operator's closing reason a hash, and each gate
its item verdicts.

## Analysis fixed before collection

Report in this order: transport and operational controls (calls, tokens, time, failures, receipt
chain, isolation including the working directory outside the repository, the preflight digest
match), then delivery per draw, then each checkpoint's gate result by item beside its
observations, then the chapter-one reading's located residuals. No pooled rate, no p-value, no
threshold on an observation. Each draw is reported with its revision, writer, amendment and
whether it was shown. The claim is `REGISTERED` before the first call and at most `OBSERVED`
after.
