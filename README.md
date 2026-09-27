<p align="center">
  <img src="docs/banner.png" width="100%" alt="LitHarness — a constellation dragon rising from an open book in a workshop of one-eyed archive creatures">
</p>

# LitHarness

[![CI](https://github.com/skulitom/LitHarness/actions/workflows/ci.yml/badge.svg?branch=main&event=push)](https://github.com/skulitom/LitHarness/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

LitHarness is an open-source Python system for autonomous, open-ended serial fiction.
Specialised LLM agents invent a concept, build its world, plan and draft scenes, check
continuity, repair located defects, and prepare books and covers for release. Manuscript
revisions and story state retain their history in SQLite.

The goal is fiction a defined audience voluntarily continues and recommends, with no human
in the production loop. The operator can direct a book and accept or reject it as a whole.

**The generation loop works; literary quality remains an open research problem.** No
simulated reader mechanism has yet earned the right to certify it. The project is working
toward an LLM-based system that can perceive quality well enough to behave as a readership;
[RESEARCH.md](RESEARCH.md) records what the evidence supports so far.

[Operator guide](docs/operator-guide.md) · [Contributing](CONTRIBUTING.md) ·
[Research](RESEARCH.md)

## Install

You need Python 3.11+, [uv](https://docs.astral.sh/uv/), and a signed-in local Claude Code CLI
for generation. The contracts package and fixtures are pinned in `uv.lock`; one checkout
is enough.

```bash
git clone https://github.com/skulitom/LitHarness
cd LitHarness
uv sync --extra dev
uv run python tools/check.py smoke
```

To use a signed-in Codex subscription, set `LITHARNESS_PROVIDER=codex`. Both providers run
the same `litharness` pipeline, with no automatic fallback. For a model-free local run,
set `LITHARNESS_FAKE_PAD_CHARS=400`. See
[provider setup](docs/operator-guide.md#generation-providers) for executable overrides,
tracing, and usage limits. Tests cannot select a billing provider.

## Start a serial

Create a serial from a brief and write to a chapter target with one command:

```bash
uv run python tools/produce.py start runs/serials/my-book --brief "A courier can cross a gate that has sealed his city." --writer halloran --chapters 6
```

The runner invents the concept, creates its listing and book, seeds and accepts the world,
then uses the ordinary production loop. It saves progress in the new directory and exports
`book.html` after reaching the target and finishing queued work. The default chapter has four
scenes. Supply `--brief-file` for a longer brief, or omit the brief to invent freely within the
house's default subgenres.

Interrupt with Ctrl+C, inspect progress, and resume using the saved settings:

```bash
uv run python tools/produce.py status runs/serials/my-book
uv run python tools/produce.py resume runs/serials/my-book
uv run python tools/produce.py resume runs/serials/my-book --chapters 12
```

Failures stop with the reason and an attempt log; accepted work remains in the book database.
See [the saved production workflow](docs/operator-guide.md#saved-production-workflow) for
usage limits and recovery, or [starting a serial](docs/operator-guide.md#start-a-serial) for
individual commands, existing premises, imports, and experimental generation options.

## Run the production loop

One `tick` performs one bounded, restart-safe unit of work. Repeat it to plan, draft, and
process the book. Global options go **before** the command; this example bounds daily usage:

```bash
uv run litharness --database book.db --max-invocations-per-day 40 --max-tokens-per-day 500000 tick
```

For a continuous foreground loop in PowerShell, stop with Ctrl+C:

```powershell
.\tools\run-loop.ps1 -Database book.db -DelaySeconds 15 -TickArgs '--max-invocations-per-day','40','--max-tokens-per-day','500000'
```

Accepted work survives interruption. `tick` exits `0` after work or ordinary idleness,
`1` when a unit fails or parks, and `2` for an operational fault. See
[loop operation](docs/operator-guide.md#run-the-production-loop) and
[recovery](docs/operator-guide.md#direct-and-recover) for details.

## Inspect and export

```bash
uv run litharness --database book.db status
uv run litharness --database book.db jobs --status parked
uv run litharness --database book.db why --scene 1
uv run litharness --database book.db export book.html
```

The library refreshes after each tick and provides a reading copy, chapter files, and
release volumes. [Covers and publication workflows](docs/operator-guide.md#covers-library-and-export)
prepare files for manual posting; LitHarness does not publish them automatically.

Agents reading stored book evidence should use the
[MCP read guide](.claude/skills/litharness-mcp/SKILL.md). Diagnostic observations cannot
become production prompts, findings, or plan items.

## Find the right context

| Task | Start here |
| --- | --- |
| Operate or troubleshoot a book | [Operator guide](docs/operator-guide.md) |
| Change code | [AGENTS.md](AGENTS.md) and [CONTRIBUTING.md](CONTRIBUTING.md) |
| Understand code and state ownership | [System model](docs/system-model.md) |
| See research results and open questions | [RESEARCH.md](RESEARCH.md) |
| Work on reader perception | [Reader architecture](plan/reader-architecture-program.md) and [research navigation](research/quality-measurement/README.md) |
| Consult the roadmap or a past decision | [PLAN.md](PLAN.md) and [decision history](plan/stage-0-decisions.md) |

Read the relevant workflow first. The full plans and decision archive are reference material.

## Development

Use the repository checker for local feedback and before handing off a change:

```bash
uv run python tools/check.py changed
uv run python tools/check.py handoff
```

[CONTRIBUTING.md](CONTRIBUTING.md#set-up-and-verify) explains the check modes and validation
requirements. [AGENTS.md](AGENTS.md#current-code-map) maps the repository and its boundaries.
