# LitHarness Lite

A fresh, small fiction drafting tool: **brief → compact plan → whole chapter**.
Python 3.11+ standard library only, with a signed-in native Codex CLI. It imports no
LitHarness code and requires no database, queue, roster, contracts package, or server.

```powershell
python lite.py --brief examples/slot-apocalypse.txt --out runs/my-chapter --words 4000
```

Optionally provide `--context author-notes.md`, `--model`, `--effort`, or `--binary`.
The defaults match this pilot's historical baseline, not a claim about the best model.
Both calls use the same model and effort. No automatic model fallback or literary
scoring loop. The output folder must be new. Calls consume the signed-in subscription.

Each run saves `brief.txt`, `context.txt`, `plan.md`, `chapter.md`, and `run.json`.
`calls/` retains exact requests, responses, provider events, time and token receipts.
Input, source, binary and artifact hashes bind a run. `--resume` with the same arguments
skips completed stages and refuses changed inputs/artifacts. Failed attempts remain;
resume explicitly retries an unfinished stage. A stale `.running` file after a hard
kill must be removed only after verifying its recorded process is dead.

Generation runs in an empty temporary working directory with user configuration,
project instructions, skills and tools disabled. API keys are not inherited. Provider
tool activity, a failed turn, or a mismatched final output causes a failure. There is
no automatic retry. Length deviations are reported, not silently resampled.

This is an opening-chapter prototype. It does not yet maintain a serial's evolving
canon, provide transactional recovery after a crash between saving the response and
manifest, or perform verified continuity repair. Those are capabilities to evaluate
before replacing LitHarness for long books.

Run deterministic checks with `python -m unittest discover -s tests -v`.
The comparison's frozen method, outputs, receipts and assessment live under
`experiments/2026-09-27-opening/`. They are local research artifacts; no publication
or upstream LitHarness changes are made by this tool.
