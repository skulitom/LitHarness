---
name: debug-book
description: Diagnose a LitHarness book or scene from stored provenance through the CLI. Use for prose defects, canon or plan drift, unfinished scenes, unexpected usage, and attribution gaps. Start with the stored views; prefer the MCP read profile when available.
---

# Debugging a LitHarness book

Use the stored views before investigating implementation. They join frozen application
inputs, policy decisions, gates, omissions, plan provenance and events. They do not capture
every provider transport setting or prove why a model wrote a sentence. Do not open the
database directly for this workflow.

## Diagnostic boundary

Nothing a dossier tells you may become a prompt, directive, finding or plan item in the
production loop. Report the evidence and its gaps. Production editorial direction has its
own qualified path in `application/editorial.py`; a diagnostic is not authorization to
bypass it. AGENTS.md defines the separate scope of operator-authorized isolated research.

The commands below inspect records. Commands such as `directive`, `ingest`, `enqueue`,
`replan`, `revert` and `resolve` are outside this diagnostic workflow.

## Choose the store and scene

From the repository root:

```bash
uv run litharness --database book.db status
```

Place `--database` before the verb. It defaults to `LITHARNESS_DATABASE`, then to
`litharness.db` in the working directory. Examples below omit it for brevity.

Check that the intended path exists. Legacy CLI reads, including `status` and `why`,
open the store through a path that can create a missing database and apply migrations.
The MCP read profile and CLI `world` read views instead refuse missing stores and pending
migrations. Prefer MCP when the read must not create or migrate anything.

`litharness-mcp` provides the agent workflow, including `scene_trace`, through
`mcp__litharness__<tool>`. See [the MCP skill](../litharness-mcp/SKILL.md)
for connection, tool paging and trace instructions.

| exit | meaning |
| --- | --- |
| 0 | answered without an attention condition |
| 1 | a result needs attention: a gap, blocking finding or parked unit |
| 2 | operational fault or invalid argument; inspect the error before retrying |

Most branch-scoped commands default to the only book. With multiple books, they name the
`--book` and `--branch` pairs to supply. `plans --json` also returns `book_id` and
`branch_id`. `--scene` accepts a logical id or a 1-based place in reading order; an exact
id wins. An unknown scene exits 1 and lists known scenes.

## Pick the first view

| symptom | first view |
| --- | --- |
| a scene reads badly | `why --scene N`, then the prose through MCP `scene` |
| the book stops adding up across scenes (a column that fell, a debt unpaid, a name that vanished, a sentence said again) | `audit`, then `audit --view status --json` or the view the line names |
| the book drifted from direction | `plans`, then `events --type PlanChanged` |
| a scene contradicts canon | `state`, then the frozen prompt and `context_omitted` |
| a scene was never written | `jobs`, `exceptions`, then `events` |
| usage is unexpected | `status`, then `why --scene N --json` |
| a change has no clear origin | `events --since <cursor>` |
| attribution or store integrity is in doubt | `verify` |

## Read a scene dossier

```bash
uv run litharness why --scene 3
```

1. Read `gates`: PASS/FAIL, rule, verdict source, and `blocking` or `advisory`.
   An advisory failure does not refuse the draft. Read each `detail` and its limitation;
   a passing gate is not a prose-quality verdict.
2. Read `job_plan`, the scene item in the job's recorded plan revision. Missing, invalid
   and unavailable history remain explicit. The `plan item` block (`plan_item`) is the
   current plan. Neither stored item alone proves what was rendered into the prompt.
3. Read `selected by` (`selected_by`): the beat's function, such as `rising` or
   `complication`, its ordinal, template and plan epoch.
4. Read the frozen application strings under `--- system ---` and `--- prompt ---`.
   These are stored inputs, with exemplar material withheld; provider-added instructions
   and an optional revision call's input may be uncaptured.
5. Use MCP `scene_trace` to locate the passage in raw, retained pre-revision and accepted
   text. Its source map pages the recorded input sources of new jobs; old jobs keep their
   provenance gaps. Source matches and changed bytes do not establish model causation.

Add `--json` for the dossier object. A refusal belongs to an attempt; do not substitute
the current accepted scene for text a gate refused.

## Check plan drift and chronology

```bash
uv run litharness plans --json
uv run litharness events --type PlanChanged
uv run litharness directives --status applied
```

Plans are newest first, with the producing proposal and directive. An imported root has no
proposal. `directives` defaults to `--status received`; use `applied`, `interpreted`,
`conflicted` or `superseded` to inspect direction already handled.

Events are in write order and carry sequence cursors. Page with `--limit` and `--since`;
the latter also accepts an ISO-8601 instant. `--type` is repeatable. JSON retains payloads;
the text form truncates long values.

Compare each scene's `job_plan` with its `plan_item`. Different plan items identify plan
drift; prompt differences alone may come from rendering. Equality does not establish that
the plan caused a prose defect.
Attempt numbers can restart after revival; use recorded event chronology.

## Check what the writer could know

```bash
uv run litharness state --subject <character-or-thing>
uv run litharness why --scene 3
```

State marks provenance as `given` for imported declarations or `read` for extraction
from generated prose. This is current recorded state. Its presence or absence does not
establish what an earlier writer request contained.

Inspect `context_omitted` for exclusions and their reasons, such as `budget` or POV
visibility. Inspect `context` for token accounting and section counts, then verify the
relevant instruction in the frozen prompt. An omitted item might also be expressed elsewhere
in that request; a full budget does not prove why a scene contradicted it.

For disclosure conflicts, the MCP skill explains how to compare the trace's recorded story
key with the `world` threads view. Current declarations and planned reveals do not replace
the frozen packet or grant permission to reveal a claim.

## Check unfinished work and usage

```bash
uv run litharness jobs --status parked
uv run litharness exceptions
uv run litharness findings --json
uv run litharness events --type JobFailed
```

Findings are detector reports; exceptions are unresolved conditions awaiting an operator.
The dossier includes `attempts` and their decisions. An unfinished scene reports
`prose` absent and exits 1.

For usage, inspect `decision`: `provider`, `model`, `invocations`, `total_tokens`,
`cost_usd` (null when unreported) and `policy_config_digest`. Compare those records before
attributing a change to the model. `verify` rebuilds revisions from canonical records and
reports attribution gaps; it does not judge the writing.

## Dossier fields

A missing optional row is `null`; an empty list is recorded emptiness. Nested views such
as `job_plan` also carry their own availability status.

| key | meaning |
| --- | --- |
| `scene.accepted_in` | revision that introduced the prose now at head, including a later repair |
| `scene.lineage_depth` | that revision's depth on the branch |
| `decision` | accepting decision, attempt, model, usage, configuration, reason and gates |
| `decision.gates[].blocking` | whether failure refuses the draft |
| `decision.gates[].verdict_source` | `deterministic`, `calibrated_critic`, `uncalibrated_critic` or `human`; a blocking verdict cannot come from the generating model |
| `attempts` | decisions on the attributed job, refusals included, in attempt order |
| `job` | unit kind, status, attempt count and input digest |
| `prompt.system` / `prompt.prompt` | frozen application input strings, subject to shelf withholding |
| `selected_by` | beat function, ordinal, template, epoch and recorded story position |
| `context` / `context_omitted` | packet accounting and excluded items with reasons |
| `plan_item` / `plan_item_scope` | current scene-plan item and its explicit scope |
| `job_plan` | job-bound historical plan item, scope checks and availability |
| `findings` | open and closed detector reports for the scene |
| `draft_before_revision` | retained pre-revision `content` and model attribution when available; absence is not proof that no revision call occurred |
| `absent` | missing top-level dossier evidence |

The `absent` list can include `prose`, `decision`, `prompt` and `plan_item`. The first
three make `why` exit 1; missing current plan text alone does not.

## Report the evidence

Name the scene, job or decision and the rows or stages inspected. Quote only the needed
permitted excerpt, distinguish a recorded fact from an inference, and name uncaptured or
withheld evidence. Do not turn a diagnostic into a literary score or an automatic story edit.
