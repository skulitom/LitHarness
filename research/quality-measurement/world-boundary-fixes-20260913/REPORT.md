# The source boundaries improved; retrieval and reconciliation timing still fail

**State: OBSERVED.** Both assigned cases completed, with first outputs retained and all
provenance/containment controls passing. Source-preservation observations below are narrow:
they do not qualify literary quality, establish a creativity rate or isolate the causal
effect of one prompt sentence. Engineering was committed as `ebff771`; registration was
pushed as `a7b8e49` before generation. The source snapshot excludes the other session's
precision changes. Neither prior Wren database nor its three chapter exports changed.

The run used nine native calls and 740,661 reported tokens over 1,005.1 seconds. Wren used
seven calls / 570,075 tokens; the opposing world used two / 170,586. All calls used the
registered native executable and requested repository-default model/reasoning. Requested
model attribution is not independent backend resolution. `evidence.json` identifies the
requests, sessions, usage, declaration locators, tool reads and checkpoints.

## Source-preservation observations

- Wren's development (`book-1/calls/002.json`, `want`) retains water, structural inquiry and
  false-condemnation investigation without adding the prior return-home motive.
- The seeded world has Wren's `status_snapshot` at rank zero and no `can_do` edges. Its
  `wren manifests_as` explicitly places her before the collapse, assessment and acquisition.
  Split and Articulated each require Loadstitch and their supplied rank, with no `offers`
  records or permanent exclusion. There is no Mara in this world's declarations.
- The outline (`book-1/calls/004.json`, scene 1) schedules the assessment rather than
  treating it as completed. The new chapter shows the prompt at line 71, the twenty-joint
  requirement at line 97, completed assessment at line 137 and the first load-bearing
  application before the rank reward at line 195. Errors receive demonstrated corrections;
  the seed explicitly makes perfection unnecessary. This closes the located elision in
  this first output; the source's detailed joint-by-joint choreography remains revisable.
- In the opposing case, development keeps Mara's return-home motive. Seeded `mara can_do`
  retains Fold and Anchor; `stands_at` and `status_snapshot` retain Rank Two. Step remains
  unowned. The fixed two-trial quota and permanent Mirror/Echo fork remain. The seed also
  elaborates automatic Step depth at Rank Five while saying it adds no extra access test;
  preservation of these selected boundaries is not evidence of zero added world detail.

The new Wren chapter was read in full: 1,990 whitespace words, including status lines.
Its SHA-256 is `ee61eaacfeed20853de650f6bef8c047fd78d4d43675f6867da3be7478d90815`.
Reading copy: `runs/world-boundary-fixes-20260913/book-1/library/world-boundary-probe-1/`.
The chapter contains a useful sequence from mistaken prediction to a restrained-load
solution and an experienced reward. This is an assistant's located reading observation,
not an audience label or a comparison qualified against Mother of Learning.

## Retrieval guidance did not solve repeated whole-world reads

The seed used one scoped `show` response of 15,098 bytes. Reconciliation did not consistently
use the advertised scope: `book-1/calls/007.json` requested `world show --current` twice,
returning the same 87,209-byte stdout, then again after declarations for 102,814 bytes.
It also tried a comma-joined subject string, got an empty match, then corrected the request
to separate subject arguments and obtained 5,772 bytes. The three full reads dominate the
283,080 bytes returned by its five `show` calls.

The seed cost 237,140 tokens and reconciliation cost 278,735. These are aggregate native
usage, including repeated/cached context, not per-read token measurements. Different
worlds, initial inputs and dispatch paths prevent a causal savings comparison with the
earlier continuation. Guidance alone has not removed this operational failure.

## A separate timing fault was exposed

The reconciliation's `world check` reports twenty unplaceable records using `0100`/`0110`,
which are schedule-space keys. The final world contains twenty accepted canon records
and two proposals at these keys. These story facts cannot be placed by scene cutoffs.
The engine's `ok` remains true because this list is advisory; attribution verification
does not test usable story timing. The grow report recognizes the warnings, but changing
only a record's position cannot replace its existing content-derived identity.

This warrants supplying the actual scene key to reconciliation and refusing newly
declared story facts at unusable positions before persistence. It does not authorize
silently moving the retained records or declaring this book's continuity fixed. A bounded
generation-facing retrieval surface is the separate response to the repeated full reads.
These next changes require their own frozen run; this experiment remains unchanged.

## Validation

`tools/check.py handoff` passed with 5,018 tests and 20 skips, 89.81% coverage, lint, types,
wheel build and corpus-history audit. The added CLI/MCP regression verifies exact filtering,
retained proposals, unchanged history and no store mutation. Opposing-source request tests
verify routing and immutable source retention, not model compliance. All saved checkpoints
have attributable revisions. System voice remains unchecked as a quality mechanism.

Rebuild the deterministic evidence with:

```powershell
runs/world-boundary-fixes-20260913/runtime/Scripts/python.exe research/quality-measurement/world-boundary-fixes-20260913/audit.py
```
