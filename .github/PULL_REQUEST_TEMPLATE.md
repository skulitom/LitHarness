# PR

## What this changes

<!-- One or two sentences: the behavior change, not the file list. -->

## Checklist

- [ ] `uv run python tools/check.py handoff` passes (lint, types, coverage,
      diff and lock validation, wheel build, corpus-history audit)
- [ ] A focused regression test covers the behavior being changed
- [ ] Patch is narrow; unrelated work in the tree is left uncommitted
- [ ] No applied SQL migration was edited (new behavior = next numbered migration)
- [ ] Architecture boundaries hold — `application` imports neither `adapters`
      nor `providers` (`tests/test_architecture.py`)
- [ ] Nothing under `src/litharness/` references a corpus (RS1;
      `tests/test_corpus_leak_audit.py`)
- [ ] Counts and findings are pointed to, not restated — no number copied into
      a second home
- [ ] If `plan/stage-0-decisions.md` is touched: append-only, corrections in
      place, and the section number was checked against `main` and every
      worktree
- [ ] Any new `claude -p` call site carries `--setting-sources user` and the
      `claudeMdExcludes` setting (stage-0 §109)
