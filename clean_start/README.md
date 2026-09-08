# Clean start

A standalone first-chapter generator. Python 3.11+, standard library only, and a native
Claude Code or Codex installation signed in with a subscription. Neither launcher imports
the old engine.

[First-run record](FIRST_RUN.md): the initial complete chapter still exhibits the reported
problems. This prototype establishes a baseline, not a demonstrated quality fix.

The same brief can run through Codex, pinned to `gpt-6-astra` with medium reasoning:

```powershell
python -m clean_start.codex_chapter --codex C:/path/to/codex.exe --out runs/clean-start-codex
```

Codex must report a ChatGPT login. It runs in an empty temporary directory with user
configuration, project documents, rules, memory, plugins and hooks disabled. Supported
unused built-in tool and skill controls are disabled explicitly; a response containing
tool activity is refused. This is not a claim to have inspected the complete live inventory. The
recorded Codex comparisons used the Claude baseline's replacement system and brief. The launcher
records the requested model; Codex's JSONL does not independently identify the resolved model. CLI/platform context
is not fully captured. A paired local marker test confirmed that the document setting
suppressed an `AGENTS.md` instruction which appeared with document loading enabled.
Disabling additional built-in features subsequently reduced the same greeting request's
reported input from 5,356 to 3,754 tokens; residual CLI/platform context is still present.

The [Codex comparison record](CODEX_COMPARISON.md) records complete chapters, remaining
defects and transport failures. No API credentials, model fallback or application retry is used.

```powershell
python clean_start/chapter.py --out runs/clean-start-first
```

Both launchers default to a magical-adventure LitRPG for Royal Road readers in portal fantasy,
isekai, or system apocalypse, with combinations allowed. Use `--brief-file path/to/brief.txt`
to replace that default completely, including choosing another subgenre. Saved experiment
requests retain the brief used for their run. The code contains no
story, premise, writer persona, scene outline, example prose or rules about numbers.

One new, tool-free Claude session receives a short replacement system prompt and the brief.
It runs in an empty temporary directory with `--safe-mode`. Only normal operating-system
and connection environment settings survive. Before generation, the CLI must report a
`claude.ai` login. No API client, API credentials, fallback model, application retry,
critic, candidate selection or revision pass is used. Managed Claude policies can still
apply; this is not a claim to remove the model's training or every provider-side instruction.

The first response is the experiment. The runner saves its exact request before starting,
then the raw response, errors, completion metadata and unchanged chapter. Existing output
directories are refused. A failed call stays failed; partial output is retained. `--dry-run`
records a request without authenticating or generating. A finished response is not proof
of a good chapter: refusals or other unsuitable text can still be returned by a model.

```powershell
python -m unittest discover -s clean_start/tests -v
```

These small tests cover transport and preservation, not prose quality. Read the complete
chapter as a chapter: what draws attention, whether the action makes sense, whether magic
and progression create an adventure, and whether the prose keeps interrupting itself to
explain. Record concrete passages and limitations alongside the output. Do not edit the
first response or silently generate until a preferred result appears.

This first experiment tests the removal of the accumulated pipeline as a bundle. It does
not isolate an individual cause or establish Royal Road appeal or serial endurance. The
next architecture decision follows reading the result. Before removing the legacy system,
preserve access to saved books and protect local state and concurrent changes. Git history
can retain retired source; it need not be copied into a second archive tree.
