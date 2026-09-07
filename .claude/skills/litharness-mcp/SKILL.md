---
name: litharness-mcp
description: Read a LitHarness book's state, provenance and queue, or propose world records, through the in-process MCP server (`litharness-mcp`) instead of shelling out to the CLI. Use when a session lists mcp__litharness__ tools, when a task needs the store's answers from another agent or process, or when an Architect-shaped agent should declare world records in batches. Read-only by default; nothing here creates, migrates, accepts, spends or posts.
---

# The LitHarness agent surface

LitHarness keeps every book in one SQLite store and answers questions about it through the
`litharness` command line. Since stage-0 §241 the same read verbs are also served in-process
by `litharness-mcp`, a stdio MCP server that binds one store at start and answers from the
same functions the CLI prints from — so a tool result and a `--json` verb never disagree. It
imports no model provider, so nothing behind it can spend; it opens the store read-only for
every read; it refuses an absent path instead of creating one; and it never migrates the
schema, accepts a proposal into canon, or posts anything anywhere.

## Connect

**In this repository, nothing to install.** `.mcp.json` at the repository root registers a
server named `litharness`. A Claude Code session started here offers it once and asks you to
approve it; after that its tools appear as `mcp__litharness__<tool>`. The store it serves is
`LITHARNESS_DATABASE` when that is set in the environment the session started with, else
`litharness.db` in the repository root (a relative path is resolved against the project
directory the host names, `CLAUDE_PROJECT_DIR`). `LITHARNESS_MCP_PROFILE` picks the profile
(`read` unless set) and `LITHARNESS_ROSTER_DATABASE` the roster store. Point it at a real
store before starting the session, or the server refuses to start and the tools are simply
absent — read the session's MCP status rather than guessing. The `mcp` extra has to be
installed in the checkout (`uv sync --extra mcp`); without it the server exits with one line
saying so.

**From another project or agent host:** register it by hand, with absolute paths and the
`mcp` extra installed (`uv sync --extra mcp` in the LitHarness checkout):

```bash
claude mcp add -s project litharness -- uv run --project /abs/path/to/LitHarness --no-sync litharness-mcp --database /abs/path/to/book.db
```

**By hand, for any MCP client:** the command is `uv run --no-sync litharness-mcp --database
<absolute path>` in the checkout. `--roster-database` names the installation's roster store
(`LITHARNESS_ROSTER_DATABASE` also works; the book's own store is the default), `--profile`
picks `read` (the default) or `propose`, and `--client NAME` is recorded on every proposal the
server writes. `litharness-mcp --help` lists them. Every call leaves one line on the server's
stderr — actor, tool, an argument digest, elapsed time, outcome — and, when
`LITHARNESS_MCP_LOG` names a file, appends it there too, because a host swallows a child's
stderr; that file is how the operator sees what agents ask.

## First call

Call `store_info`. It returns the bound paths, every `(book_id, branch_id, head)` the store
holds, how many migrations are pending, and the tools this profile registers. Most stores hold
one book, so `book_id` and `branch_id` can be left off every other tool; a store holding more
returns `error_kind: ambiguous_branch` with the known pairs, and you pass one back.

Call `guide` when you want to know whether something is a tool here: it lists every verb of the
command line with its tier — `read`, `propose`, `operator`, `excluded` — the tool that wraps it,
and for the rest the reason and the CLI form. The verbs that spend money are named as such;
none of them is a tool.

## The tools

Read profile (every one opens the store read-only):

| tool | answers |
| --- | --- |
| `store_info` | what this server is bound to, and the books in it |
| `guide` | every CLI verb with its tier, tool, reason and CLI form; with `tool`, the keys that tool's result always carries |
| `book` | the book at a glance: title, premise, every scene with whether it is drafted and how long, grouped by chapter, the head revision. Call it second |
| `scene` | one scene's prose as it stands, with its place in the book. The dossier withholds prose and sends you here |
| `scene_trace` | one scene's attributed or unfinished job: frozen input, raw draft, retained pre-revision draft and accepted text joined by decision/revision IDs; hashes and gaps by default, one bounded excerpt with `stage` |
| `status` | queue depth, attention counts, digest and spend; blocked books with the sentence the next tick refuses with |
| `why` | one scene's dossier: the frozen prompt, the decision that took it, the gate ladder, the plan item, findings, what the packet omitted. `scene` is a logical id (`scene-3`) or a 1-based place in reading order (`3`); `include_prompt=false` keeps the prompt's sizes and drops its text |
| `findings` | what the evaluators say is wrong, worst first; `blocking` counts what a gate refuses on; `limit`/`offset` page it |
| `events` | the event log in write order from a cursor (`since`), bounded by `limit`, with `next_since` to resume |
| `plans` | the plan's lineage, newest first, and the proposal behind each revision |
| `state` | what the book holds as true, in story order: position, provenance (`read` from its own prose or `given`), authority, subject, predicate, the sentence, the note, who may know it; `limit`/`offset` page it and `total` says how many there are |
| `queue` | job counts by status (always present), the units in one status, open exceptions, and captured direction with its author |
| `world` | one of the world's views by name: `summary`, `show`, `rules`, `ladders`, `abilities`, `cast`, `threads`, `vocabulary`, `presence`, `check` |
| `characters` | everything canon holds about each person; an empty cast carries a `hint` |
| `roster` | the installation's writer roster: `show`, `check`, `vocabulary`, or `rehearse` a candidate dossier; dossier prose is never returned |
| `release_show` | the operator-gated release queue for the book; there is no post anywhere |
| `verify` | rebuild every revision from canonical records; the ones no decision explains |
| `export_markdown` | a reading copy of the book as it stands, gaps and all, cut at `max_chars` with `truncated` saying so; prefer `scene` for one scene |

Large results are paged or cut rather than dropped: `state` and `findings` take `limit` and
`offset` and report `total`; `export_markdown` reports `chars` and `truncated`; `why` takes
`include_prompt`. The server also offers prompts (`debug_scene`, `book_health`, and
`propose_world` under the propose profile), which the host lists as slash commands and which
walk the workflows below, and resources (`litharness://store`, `litharness://guide`,
`litharness://book/{book_id}`, `litharness://export/{book_id}`) a host can attach to context.

### Trace a prose problem

After `book`, `scene` and `why`, call `scene_trace` for the scene. Its default answer gives
stage identities without dumping the chapter and prompts into context. The trace covers
the current scene's attributed job (or its unfinished job), not every job ever aimed at it.
Use a `decision_id` from `attempts` to inspect another recorded decision on that job; attempt
numbers can restart after revival and are not reliable chronology.

Request `stage` = `system`, `prompt`, `raw_draft`, `pre_revision_draft` or `accepted`, with
`offset` and `max_chars` (1 to 20000), to read that stage in chunks. Follow `next_offset`
until it is null. Stage metadata distinguishes original hashes/sizes from delivered,
redacted text. A missing capture, ambiguous event or hash mismatch is a gap to report.
Do not substitute the current manuscript for a refused candidate: its event names a base
revision, not accepted candidate text. The accepted stage belongs to the selected decision's
resulting revision. An optional revision call's input is not the frozen drafting prompt.

Locate whether a passage already appears in raw output or appears only later. Different
bytes establish a change, not its literary effect or cause. Frozen job input preserves
the application's text; it does not capture provider-added instructions or omitted transport
settings. Nothing is reconstructed from today's plan, writer dossier or configuration.

Shelf-bearing prompts are withheld in full because a heading inside source prose cannot
establish where the application's own context resumes; original sizes remain available.
Raw and pre-revision drafts exposed to an exemplar shelf are withheld, including rejected
drafts that might copy it without a heading. Their identities remain visible. The generic
`events` tool always withholds raw draft text; local event storage remains unchanged. These
are diagnostic reads under the same fence below, not a route into automatic story direction.

Propose profile (`--profile propose`): `store_info`, `guide`, `world`, and two writes —
`world_declare` (one record) and `world_declare_batch` (a list of records, reported one by
one, ending with the world's `check`). This is the Architect's shape: the world's read views
and the two declares, and no dossier tool beside a write tool.

## Reading a result

Every result is a JSON object. `attention: true` means what exit code 1 means at the command
line: a result a person should read — a scene with no prose, a blocking finding, an open
exception, a world that contradicts itself. It is never an error. Results may carry `next`, the
tools worth calling after; `why` on an undrafted scene points at `queue`.

A tool error is the exit-2 class only: the store is locked by the ticking session (retry
after the current tick; the server never retries for you), migrations are pending (run
`litharness --database <path> status` at the CLI, which applies them), the path is absent, or an
argument is malformed. An unknown scene comes back as a result with `error_kind:
unknown_scene` and the known scene ids, not as an error.

## The one rule

These tools are read-only and they are fenced (stage-0 §97.1). Nothing a dossier tells you
may become a prompt, directive, finding or plan item. Diagnose, report to the operator, and
stop. Every read tool's description ends with this sentence; the fix is a person's call, and
the paths that reach a prompt have their own gates (`application/editorial.py`).

## What is not here, and where it is

- **Operator acts** — `world accept`, `roster accept`/`refuse`, `release approve`/`record-posted`
  /`withdraw`, `dismiss`, `resolve`, `revive`, `enqueue`, `ingest`, `replan`, `revert`,
  `revert-plan`, `init`, `new`, `extend`, `import`, `backup`, `propagate` — each mints a
  person's judgment as a decision row or selects one item out of a set an agent can see. They
  are command-line verbs a person runs.
- **Direction** — `litharness directive` records a person's direction; a machine's has its own
  gated path. No tool.
- **Anything that spends** — `tick`, `architect seed`/`grow`, `readers`, `listing`, `concept`,
  `recruit`, `revoice`, `cover`. Command-line only, operator-run, one arm at a time on this box.
- **`prompts`** — it loads the exemplar shelf. The frozen scene prompt is in `why`, with any
  shelf withheld by character count.
- **Rehearsing a writer** is here (`roster` with `rehearse`); declaring one is not, because a
  recruit run stamps the shelf and the form.

## Proposing world records

`world_declare` writes a `PROPOSED` record and refuses nothing: `not_yet_coherent` is what
the rest of the world may still settle, `will_not_resolve` is a record in a slot nothing will
ever settle (there is no retraction; a correction fills a different slot, so both survive),
`cannot_be_read` is a sheet the parser refuses (a declaration in the same slot replaces it),
and `supersedes` names the earlier proposals in this slot that acceptance will leave behind.
Canon costs `litharness world accept` at the command line, a person's act.

Before the first declare, read `world` with `vocabulary`: it is the whole of what the world's
language admits, and the lines under `how` are the traps measured on real seeds — write
`order_key` as zero-padded digits, ids are normalised to underscores, `can_do` takes an
`object`, a status sheet's rung column is named `rank`. Batch about twenty-five records per
`world_declare_batch` call and read each item's report; `stop_on_incoherent` stops at the
first record that will not resolve. The command-line form of the batch is
`litharness world declare-batch --records '[...]'`, which is what the internal Architect holds.
