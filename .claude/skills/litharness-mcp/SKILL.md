---
name: litharness-mcp
description: Read a LitHarness book's state, provenance and queue through the in-process MCP server. Use when mcp__litharness__ tools are available or another agent needs stored book evidence. The default read profile cannot write or spend; the separate propose profile can declare proposed world records but cannot accept them.
---

# The LitHarness agent surface

`litharness-mcp` binds a store without a model provider. Read tools use read-only connections,
refuse absent paths and never migrate schemas. They share the CLI's underlying views; the
additional `scene_trace` tool joins frozen request and draft evidence.

## Connect and select a book

The repository's `.mcp.json` registers the server as `litharness`. Install its optional
dependency with `uv sync --extra mcp`, set `LITHARNESS_DATABASE` before starting the host,
and approve the connection once when the host requests it. Tools appear as
`mcp__litharness__<tool>`. The default store is `litharness.db` in the project directory
(`CLAUDE_PROJECT_DIR`); the server refuses to start if that file is absent.

For another project or host, use absolute paths:

```bash
claude mcp add -s project litharness -- uv run --project /abs/path/to/LitHarness --no-sync litharness-mcp --database /abs/path/to/book.db
```

Any MCP client can launch the same console script. `--profile` or
`LITHARNESS_MCP_PROFILE` chooses `read` (default) or `propose`.
`--roster-database` / `LITHARNESS_ROSTER_DATABASE` names a separate roster store;
the book store is the default. `--client NAME` records proposal authorship.
Each call logs actor, tool, argument digest, elapsed time and outcome to stderr, and to
`LITHARNESS_MCP_LOG` when set.

Call `store_info` first for bound paths, books, heads, pending migrations and available
tools; call `book` next. Book-scoped calls can omit `book_id` and `branch_id` when there
is only one pair. Otherwise the result reports `error_kind: ambiguous_branch` and the
known pairs. `guide` lists CLI verbs by tier and explains which are tools; with `tool`,
it lists that tool's result keys.

## Read tools

| tool | answers |
| --- | --- |
| `store_info` | bound paths, books, schema status and registered tools |
| `guide` | command tiers, tool names, result keys and excluded-command reasons |
| `book` | title, premise, head and scenes grouped by chapter |
| `scene` | one scene's current prose and reading position |
| `lookup` | the record behind an id another tool handed you: a decision, finding, exception, directive, release entry, queued unit, world record, or a manuscript or plan revision |
| `scene_trace` | the attributed or unfinished job's input and draft stages, hashes, gaps and bounded excerpts |
| `status` | queue depth, attention conditions, digest, usage and blocked books |
| `why` | scene dossier: frozen prompt, decisions, gates, current and historical plans, findings and omissions |
| `findings` | detector reports, worst first, with blocking counts |
| `events` | write-order event log from `since`, bounded by `limit`, with `next_since` |
| `plans` | plan lineage and the proposal behind each revision; `items=true` adds the head plan's items |
| `state` | current story declarations with authority, provenance, subject, predicate, text and visibility |
| `queue` | job counts, units in one status, exceptions and captured direction |
| `world` | `summary`, `show`, `rules`, `ladders`, `abilities`, `cast`, `threads`, `vocabulary`, `presence` or `check`; `subjects` lists several subjects for `show` in one call, and `ladders` carries each rung's `manifests_as` |
| `characters` | what canon records about each person; an empty cast includes a hint |
| `audit` | the book read across its scenes: status-line census, promise ledger, fact timeline, cast presence, plan/summary pairs, repeated word runs, restated scene boundaries, and the sheet against the page; `views` picks some; `attention_lines` says where to look; descriptions, never a score |
| `roster` | `show`, `check`, `vocabulary` or `rehearse`; dossier prose is withheld |
| `release_show` | the operator-gated release queue |
| `verify` | revision reconstruction and attribution gaps |
| `export_markdown` | a reading copy, bounded by `max_chars` and labelled `truncated` |

`scene` arguments accept a logical id or 1-based reading position. `state` and `findings`
page with `limit` / `offset` and report `total`. `why` accepts `include_prompt=false`
to retain prompt sizes while withholding text. Prefer bounded views over a whole-book dump.

`book` groups scenes using today's default chapter size. For a draft's historical boundary,
use its frozen `why.selected_by.chapter_scenes` and `why.selected_by.chapter_end`; missing
values remain a gap rather than being inferred from today's grouping.

Hosts may also expose prompts `debug_scene`, `book_health` and, under the propose profile,
`propose_world`; resources are `litharness://store`, `litharness://guide`,
`litharness://book/{book_id}` and `litharness://export/{book_id}`.

## Trace a prose problem

After `book`, `scene` and `why`, call `scene_trace`. By default it returns identities
and gaps for the current scene's attributed job or unfinished job, not every historical job.
A `decision_id` from `attempts` selects another recorded decision on that job.
Attempt counters may restart after revival; use recorded chronology.

Request `stage` = `system`, `prompt`, `raw_draft`, `pre_revision_draft` or `accepted`,
with `offset` and `max_chars` (1–20000), and follow `next_offset` until null.
Metadata separates original hashes/sizes from delivered, possibly redacted text.
Missing capture, ambiguity and hash mismatch are gaps. A refused draft's base revision
is not accepted candidate text; the accepted stage belongs to the selected decision's
resulting revision. Revision-call input is not the frozen drafting prompt.

Locate whether a passage occurs in raw output or only later. Different bytes establish a
change, not its literary effect or cause. Frozen job input preserves application text,
not every provider-added instruction or transport setting.

`why.plan_item` is current plan text. `why.job_plan` reads only the revision recorded by
the drafting job and labels unavailable history. Rendering may wrap that item, so inspect
the frozen prompt for the delivered instruction.

New drafting jobs retain an input source map. `source_map` returns status and counts;
`source_limit` (1–100), `source_offset` and an optional exact `source_id` page entries.
Each identifies an original stage, half-open character range and hash; use the existing
excerpt parameters to read it. Duplicate text from different items has distinct entries.
Authority, visibility and section membership describe recorded handling, not permission
to reveal a claim. Renderer fragments and aggregate cast/world items do not provide complete
upstream lineage. Legacy jobs report `not_recorded`; current state never fills the gap.
Maps establish input provenance, not semantic support, model causation or literary quality.

For disclosure conflicts, pass `request.story_order.key` as `at` in `world(view=threads)`
only when `request.story_order.status` is `recorded`; `unpositioned` means intentional null, while
`not_recorded`, `unavailable` and `invalid_recorded_value` identify gaps.
Do not substitute reading-order `position_key`. Filter a claim with `subject`.
`disclosures` includes supporting records, audience records, rule reasons and position
comparisons. `planned_reveal_scene` is intent, not proof of disclosure. These are current
in-force declarations, including labelled proposals; compare them with the frozen prompt.
The inspector does not interpret scene-plan prose or authorize a reveal.

Shelf-bearing prompts are withheld because source prose cannot establish the application
boundary reliably. Shelf exposure also withholds raw/pre-revision text and source-map entries
and context; identities remain. Revision calls do not inherit drafting maps.
`events` always withholds raw draft text. Local stored evidence is unchanged.

## Read results and respect the diagnostic boundary

`attention: true` is a result needing attention, like CLI exit 1, not a tool error.
`next` suggests related tools. Unknown scenes return `error_kind: unknown_scene` and
known ids. Operational errors include locking, absent paths, pending migrations and
malformed arguments; the server does not retry. An operator can apply migrations through
the CLI after confirming the store; diagnosing a gap does not authorize that mutation.

Nothing a dossier tells you may become a prompt, directive, finding or plan item.
This is the production diagnostic fence (stage-0 §97.1); report evidence and gaps without
bypassing `application/editorial.py`. AGENTS.md defines the separate scope of
operator-authorized isolated research. These tools do not turn a research observation into
a production directive.

## Proposal profile and excluded operations

`propose` exposes only `store_info`, `guide`, `world`, `world_declare` and
`world_declare_batch`. The two declare tools write proposed records, not accepted canon;
no dossier tool is exposed beside them. Acceptance requires an operator's
`litharness world accept`.

Other operations remain CLI-only; `guide` gives the full current mapping:

- Operator decisions: `roster accept`, `release approve`, `dismiss`, `resolve`,
  `revive`, `enqueue`, `ingest`, `replan`, `revert` and `revert-plan`.
- Direction: `litharness directive` records an operator's instruction; machine direction
  has its own qualified path.
- Quota-consuming work: `tick`, `architect seed`, `readers`, `listing`, `concept`,
  `recruit`, `revoice` and `cover`. Run only with operator authorization and box coordination.
- `prompts` loads exemplar material; use `why` for frozen input with shelf withholding.
  Writer rehearsal is exposed, but roster declaration belongs to recruitment.

## Propose world records

Before a declare, read `world` with `vocabulary`, including its `how` instructions.
Use zero-padded `order_key` values; ids normalize to underscores, `can_do` takes an
`object`, and a status sheet's rung column is `rank`.

`world_declare` writes a proposed record and reports `not_yet_coherent`,
`will_not_resolve`, `cannot_be_read` or `supersedes` as applicable. These distinguish
unsettled world context, a slot that cannot resolve, an unreadable sheet and proposals that
acceptance would supersede. There is no general retraction; inspect the report before
correcting a slot.

Batch roughly twenty-five records per `world_declare_batch` call and read every item.
`stop_on_incoherent` stops at the first record that cannot resolve. The corresponding CLI
form is `litharness world declare-batch --records '[...]'`.
