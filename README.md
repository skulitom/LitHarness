# LitHarness

LitHarness drafts LitRPG serial chapters from a short brief: two Codex calls per opening chapter,
plain files for everything, and nothing to install beyond Python and a signed-in Codex CLI.

This is the lightweight rebuild (2026-09-27). The previous implementation is kept, unchanged, at the
tag `legacy/incumbent-2026-09-27` and the branch `legacy/main`; the prototype it grew from is at
`legacy/lite-2026-09-27`. The rebuild plan is frozen in
[experiments/2026-09-27-rebuild-plan/PLAN.md](experiments/2026-09-27-rebuild-plan/PLAN.md).

## Requirements

- Python 3.11 or later. The package uses the standard library only.
- The Codex CLI, signed in with a ChatGPT subscription. Calls spend that subscription.

## Use

```powershell
python -m litharness opening --brief briefs/slot.txt --words 1500
```

`opening` plans and drafts one opening chapter in two calls (Lite's behaviour, unchanged). It writes
to `$LITHARNESS_HOME/openings/<brief>-<words>/` (default `~/LitHarness-data`). Re-run with
`--resume` to finish an interrupted run; changed inputs or artifacts are refused.

```powershell
python -m litharness check chapter.md [--stage pitch|plan|chapter] [--serial SLUG]
```

`check` runs every deterministic check on any text without a call: the hard checks that will
redraw a stage (`money`, `leak`, `person`, `rise`, `fields`, `pitch-shape`, `plan-shape`, `length`)
and the inert reports. Without `--serial` the file is treated as chapter 1 with no plan or bible.

Exit codes: 0 done, 1 needs a person (a failing check, a held lock, an existing run), 2 fault.

Every call keeps its request, system prompt, events, stderr, `final.md` and `receipt.json`
(model, effort, token usage, seconds, sha256 of every input and of the output).

## Tests

```powershell
python -m unittest -q
```

Serial, stdlib only, about a second. No test spawns a model CLI.
