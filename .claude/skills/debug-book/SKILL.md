---
name: debug-book
description: Answer "why did this book or scene come out the way it did" from LitHarness's stored provenance. Use when a scene reads badly, a book drifted from its direction, a scene contradicts canon, a unit never produced prose, or a run cost more than expected. Read-only — start here before reading source or opening the database.
---

# Debugging a LitHarness book

LitHarness drafts books by running an LLM pipeline one bounded unit of work at a time. Every
unit leaves a durable record in a **single SQLite file**: the exact prompt that was sent, the
policy decision that accepted or refused what came back, the gates it passed, what the
context packet could not fit, the plan statement that steered it, and an event log written in
the same transaction as every state change.

This skill is how you read that record. **You do not need to read the source, and you must
not open the database directly** — every verb below prints stored rows, and the joins that
matter are already done for you.

## Before anything else: the one rule

**These verbs are read-only and they are fenced.** Nothing you learn here may be turned into
input for generation. `plan/serial-pilot-1.md` §6 and stage-0 §97.1 keep diagnostics on the
operator's side of the loop: a rejection carries no explanation back into the system, and a
located defect does not become a note in the next prompt. Diagnose, report to the human, and
stop. Writing a finding, a directive, or a plan item because of something a dossier told you
is the one thing this workflow forbids — the feedback that reaches a prompt has its own
gated path (`feedback`), and routing around it destroys the measurement it exists to protect.

No verb in this skill writes a row. If you find yourself reaching for `directive`, `ingest`,
`enqueue`, `replan`, `revert`, or `resolve`, you have left the workflow.

## Setup

Everything runs through one command. From the repo root:

```bash
uv run litharness --database book.db status
```

`--database` names the store; it defaults to `litharness.db` in the working directory. Every
verb below takes it in the same position, **before** the verb. Examples here omit it for
brevity — add it if the store is not at the default path.

**Exit codes are the contract**, and they are the same on every verb:

| code | meaning |
|---|---|
| `0` | the verb answered, and nothing needs a human |
| `1` | needs attention — a gap, a blocking finding, a parked unit. Not an error |
| `2` | operational fault — database locked or missing, bad argument. Retry or fix the path |

A `1` from a diagnostic verb is a *result*, not a failure. Read the output.

**Book and branch ids.** Most verbs default to the only book in the store, so you usually
pass nothing. When a store holds more than one, the verb lists the ids and asks. To get them
directly:

```bash
uv run litharness plans --json
```

The first two keys are `book_id` and `branch_id`.

**Naming a scene.** `--scene` takes either a logical id (`scene-3`) or a 1-based place in
reading order (`3`). Both resolve; the id wins if a book names its scenes something else.

---

## Symptom → first command

| symptom | start here |
|---|---|
| a scene reads flat, generic, or wrong | `why --scene N` — read the **feedback set** and the **gate ladder** |
| the book drifted from what the director asked for | `plans`, then `events --type PlanChanged` |
| a scene contradicts established canon | `state`, then the dossier's **`context_omitted`** list |
| a scene was never written | `jobs`, `exceptions`, then `events` |
| a run cost more than expected | `status`, then `why --scene N --json` and read `decision` |
| a tournament picked the wrong draft | `why --scene N` — read **`span_candidates`** |
| something changed and nobody knows when | `events --since <cursor>` |
| the store itself may be damaged | `verify` |

---

## Workflow 1 — a scene reads flat

```bash
uv run litharness why --scene 3
```

This is the scene dossier: every stored row that explains one scene, joined. Read it in this
order.

1. **`feedback`** — what was frozen onto the prompt at enqueue. This is the reader→writer
   loop's one channel into generation.
   - `0 item(s)` with `(an explicit empty set: drafted with no feedback)` means the loop was
     live and had nothing to say. **This is the normal case**, and it means nobody's reading
     shaped this scene. If the prose is flat, the loop is not why.
   - `ABSENT - no scene feedback row` means no row was written for that revision at all —
     usually a scene older than the loop, or prose committed by a path that records none. A
     different fact from an empty set, and the dossier keeps the two apart on purpose.
   - Items present means direction reached the prompt; each reads
     `role:axis_id->preferred_pole`.
2. **`gates`** — the ladder that ran on the returned draft. `PASS`/`FAIL`, the rule id, the
   verdict source, and whether it was `blocking` or `advisory`.
   - An **advisory** gate can fail without stopping anything. A craft gate is advisory until
     calibration evidence promotes it, so a failing advisory gate is information, not the
     cause of an acceptance.
   - The `detail` line under a gate carries the measured number and its caveat. Read the
     caveat: several of these measure something narrower than their name suggests.
3. **`craft`** — advisory measurements recorded against this scene. Numbers only, no verdict.
   Cross-book context: `uv run litharness craft`.
4. **`plan item`** — the per-scene statement that steered the draft, verbatim. `ABSENT` means
   the book has no outline for this scene (normal for a book run with `--no-outline`, and for
   the golden fixture books, which carry only book-wide statements). A scene with no statement
   was told only the premise and its beat function.
5. **`selected by`** — why this beat, from the payload's own record: which beat of how many,
   its function (`rising`, `complication`, …), the template, and the plan epoch.
6. **the prompt itself**, printed last and whole, after `--- system ---` and `--- prompt ---`.
   This is the exact text that was sent, not a re-render. If the prose is flat and the prompt
   asked for something else, the generator is the story. If the prompt is thin, the *packet*
   is the story — go to Workflow 3.

Add `--json` for the same content as one object. See **Fields** below.

For a whole-book view of one measurable trait beside the feedback that was live when each
scene drafted, `blame` reads the same rows across every scene:

```bash
uv run litharness blame --book <id> --branch <id> --axis interiority
```

`--axis` is one of `em_dash`, `interiority`, `stat_flatten`, and `--book`/`--branch` are
required here (this verb does not default to the only book). It prints a counter value and a
provenance shape per scene and **never a score** — there is no aggregate here to read as a
quality number, and nothing it prints can refuse anything.

## Workflow 2 — the book drifted from the directive

```bash
uv run litharness plans
uv run litharness plans --json
```

The plan's lineage, newest first, with the proposal that produced each step and the directive
behind it. A revision reading `imported; no proposal produced it` is the plan the book started
with — the root, not a step with its history missing.

Then find *when*:

```bash
uv run litharness events --type PlanChanged
uv run litharness directives --status applied
```

`directives` defaults to `--status received`, which is the *unread* inbox and is empty on a
book that has already acted on its direction. Ask for `applied` (or `interpreted`, `conflicted`,
`superseded`) to read the text of a directive the book has taken. `plans` prints the directive id behind each
step, so you can match them up.

`events` prints the log in write order with a sequence number on every line. Because plan
changes, job outcomes and policy decisions all land in the same log, this is the one view
that shows the order things actually happened in across tables. Read it in passes:

```bash
uv run litharness events --limit 20
# ...ends with: (20 of 137 matching event(s); next --since 20)
uv run litharness events --since 20 --limit 20
```

`--since` also takes an ISO-8601 instant (`--since 2026-08-13`), and `--type` is repeatable.
`--json` carries each payload whole; the text form truncates long ones to one line.

To close the loop, take a scene drafted after the change and one before it, and compare the
`plan item` and `selected by` blocks of their dossiers.

## Workflow 3 — a scene ignores canon

Canon is objective story state: what the book holds as true, in story order. The integrity
gate refuses drafts that contradict it and the context packet hands it to the generator as
established fact.

```bash
uv run litharness state
uv run litharness state --subject <character-or-thing>
```

Each line marks its provenance: `given` is the author's word (imported), `read` is this
system's own extraction from prose it generated. If canon is missing here, the scene was never
told it and the generator is not at fault.

If the canon **is** on record, the scene was probably not shown it:

```bash
uv run litharness why --scene 3
```

Read **`context_omitted`**. This is the honest half of the context packet — the items the
budget or a visibility rule kept out, each with the reason (`budget`, `not visible to POV`,
…). The packet drops the *oldest* prose rather than the least relevant, so by mid-book a scene
is routinely drafted knowing little of the book before it. A scene that contradicts canon
sitting on this list is explained.

Also read `context`: `N item(s), used/budget token(s)` and the per-section counts. A used
figure at the budget means the packet was full. Raising `--context-budget` on the run is a
human's decision to make, not yours.

## Workflow 4 — a scene was never written

```bash
uv run litharness jobs
uv run litharness jobs --status parked
uv run litharness exceptions
```

A **finding** is something a detector reported and policy usually clears by itself. An
**exception** is something policy could not resolve and is waiting on a human. They are
different queues and they read differently.

```bash
uv run litharness findings --json
uv run litharness events --type JobFailed
```

Then look at what the refusals said. `why` shows the accepting decision plus an `attempts`
line when the job took more than one — refusals are recorded as fully as acceptances, so the
ladder across attempts is readable. For a scene that never landed at all, `why` reports
`prose ABSENT` and exits 1.

## Workflow 5 — the run cost more than expected

```bash
uv run litharness status
uv run litharness why --scene 3 --json
```

The dossier's `decision` block carries `provider`, `model`, `invocations`, `total_tokens`,
`cost_usd` (null where the provider reports no dollars) and `policy_config_digest`. A run that
behaves differently at the same model usually differs in that digest — a threshold change
reads as a different config rather than as unexplained drift.

## Workflow 6 — a tournament picked the wrong draft

When a book is drafted with `--plan-search`, each span produces K alternative plan statements
and K candidate drafts, and exactly one is committed. The losers are kept.

```bash
uv run litharness why --scene 3
```

`candidates` lists every one with its `alternative_index`, its status (`selected` /
`discarded`), its length, and **the statement it was drafted under** — which is what the
tournament was actually selecting between. The prose is only its evidence.

## Workflow 7 — is the store itself sound

```bash
uv run litharness verify
```

Rebuilds every revision from canonical records and reports revisions that no policy decision
explains. Exit 1 with a list means attribution gaps — the same gaps `why` reports per scene as
`decision ABSENT`.

---

## Fields

What the dossier's keys mean, in `--json` order. Absences are always explicit: a missing row
is `null` and is named in `absent`, while an empty list is a recorded emptiness.

| key | meaning |
|---|---|
| `scene.accepted_in` | the revision that introduced the prose now at head — the repair if one rewrote it, not the first draft |
| `scene.lineage_depth` | how far along the branch that revision sits |
| `decision` | the policy decision that accepted it: outcome, attempt, model, spend, config digest, reason, and `gates` |
| `decision.gates[].blocking` | whether failing it would have refused the draft. Advisory gates annotate |
| `decision.gates[].verdict_source` | `deterministic`, `calibrated_critic`, `uncalibrated_critic`, `human`. A blocking gate can never source its verdict from the generating model |
| `attempts` | every decision on the same job, refusals included, in attempt order |
| `job` | the queued unit: kind, status, attempts, input digest |
| `prompt.system` / `prompt.prompt` | the exact strings sent, frozen at enqueue |
| `selected_by` | why this beat was chosen: beat function, ordinal, template, plan epoch, story position |
| `context` | the packet's size against its budget, and per-section counts |
| `context_omitted` | what the packet could not hold, and why. **Read this for anything the scene should have known** |
| `payload_feedback` | the feedback set frozen onto the prompt: `items`, `digest`, `dropped` |
| `scene_feedback` | the same set projected onto the accepted revision. `null` means no row was written |
| `plan_item` | the per-scene statement and whether a director locked it |
| `craft_metrics` | advisory numbers measured against this revision |
| `findings` | what detectors said about this scene, open and closed |
| `draft_before_revision` | the writer's own text, when the §185 reviser replaced it: both models, the mark count §180 took out of it, and `content` — the prose `--no-revise` would have committed. `null` means the accepted prose *is* the writer's, which is not a gap and is not in `absent` |
| `span_candidates` | every tournament draft for this span, winner and losers |
| `absent` | every piece the store does not hold for this scene |

`absent` may contain `prose`, `decision`, `prompt`, `plan_item`, `scene_feedback`. The first
three mean the dossier could not answer its own question and the verb exits 1; the last two
are ordinary facts about some books and exit 0.

## Reporting back

Say which rows you read and what they say. Quote the prompt or the gate detail rather than
paraphrasing — the value of this record is that it is verbatim. If the answer is "the store
does not hold that", say so and name what is absent; the write side does not persist the
context packet's *contents* (only counts and the omission list) or the raw provider envelope,
so some questions genuinely have no stored answer, and guessing at one is worse than the gap.

Then stop. The fix is a human's call.
