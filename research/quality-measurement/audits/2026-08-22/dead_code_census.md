# Dead-code census: `research/quality-measurement/*.py` — findings

**Method.** Read-only audit of the worktree `claude/ox-maint_audit-7f3a21`. I inventoried every top-level (`column-0`) `def`/`async def`/`class` in the 58 Python modules under `research/quality-measurement/`, then for each name ran word-boundary `git grep -n -w <name>` across the whole tree, bucketing hits into: same module, other research modules / `src/` / `scripts`-type `.py`, `tests/`, markdown docs (`research/quality-measurement/*.md`, `plan/*.md` ×35, `README.md`, `CONTRIBUTING.md`), and committed result data (`.json/.jsonl/.csv` — **not** counted as references). For same-module hits I re-derived references with Python `ast` so that docstrings/comments don't count and each use is attributed to its real enclosing scope (module-level code, a named function, `main()`, or `selftest()`), then computed reachability from roots: external refs, module-level wiring (`if __name__ == "__main__": main()` guards), `main()`/argparse bodies, and separately `selftest()` bodies.

**Verification done.** Each finalist was confirmed by a full-tree `git grep`; spot-checks confirmed claimed-reachable names really are called inside `run()`/`selftest()`/`main()` bodies (e.g., `bcr.kendall_tau` at bcr.py:1318/1453/1455 inside run + `--selftest` branch; `world_lexicon.build_lexicon` called from `main` at line 249). I checked for dynamic dispatch that AST would miss: no `globals()`, `eval()`, `importlib`, or `__import__` in the directory; all `getattr()` uses access data attributes, not module functions.

## Candidates (no reference anywhere outside their own body)

### `compression_progress.py`
- `research/quality-measurement/compression_progress.py:196 Fiction`
  Searched `-w Fiction` over the entire tree: the only occurrence in the repository is the `class Fiction:` statement itself — no imports, no test, no internal use, no doc mention.

### `elicit.py`
- `research/quality-measurement/elicit.py:1289 samples_to_rows`
  Searched `-w samples_to_rows` over the entire tree: only hit is its own `def` line; nothing in any module, `tests/`, `main()`/argparse wiring, or docs references it.

### `surprisal_field.py`
- `research/quality-measurement/surprisal_field.py:217 surprisal_series`
  Searched `-w surprisal_series` over the entire tree: only hit is its own (multi-line) `def` signature at line 217; zero references anywhere else.

## Referenced only from documentation (deleting would orphan a sentence)

- `research/quality-measurement/elicit.py:1335 probe_discrimination` — no code or test references anywhere; sole reference is prose in `plan/stage-0-decisions.md:3799` ("`elicit.probe_discrimination` is the precondition that would have caught it in eight calls").

## Referenced only by a `selftest()`

- None found. Every module's `selftest()` is itself wired into `main()` via a `--selftest` argparse flag (verified, e.g., `bcr.py:1493/1508-1509`), so anything referenced solely from a selftest body still chains to a live root; no name's *only* referencing context is a selftest body in isolation.

## Counts (this audit's tally, not a project property)

- Top-level definitions scanned: **739** across **58** modules (740 raw column-0 matches; 1 excluded as a false positive — a docstring line in `authorship_tells.py:32` beginning with the word "class").
- Candidates (no reference outside own body): **3**
- Doc-only referenced: **1**
- Selftest-only referenced: **0**

**Caveats:** per instructions I did not run the test suite, GPU tooling, or any state-changing command (only `git ls-files`, `git grep`, file reads, and an in-memory Python `ast` pass). String-keyed dispatch tables would evade both grep-by-name and AST analysis; none exist in these modules. Committed result files (`results/*.json|jsonl`) frequently contain metric-name keys coinciding with function names; these were tallied but deliberately not treated as live references. No deletions recommended — the operator decides.