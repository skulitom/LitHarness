"""The debug-book skill names verbs and dossier keys, and the parser owns both.

`.claude/skills/debug-book/SKILL.md` is how an outside agent is told to read a book's
provenance through the CLI. It drifted: on 2026-09-07 it still taught `blame`, `craft` and
`feedback` — verbs 530f40e removed — the `--plan-search` flag that went with them, and four
dossier keys `why --json` had stopped emitting (stage-0 §241). Nothing checked it, because
prose is not code and no test read the skill. This one walks every backticked token in the
skill and asks the real parser, so a verb renamed or a key dropped surfaces here rather than
as an agent's failed command. Struck text (`~~...~~`) is exempt: the house form keeps a
correction's wrong half visible on purpose.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from litharness import mcp_server
from litharness.application import dossier as dossier_mod
from litharness.cli import EXIT_ATTENTION, EXIT_OK, build_parser, main

SKILL = Path(__file__).resolve().parent.parent / ".claude" / "skills" / "debug-book" / "SKILL.md"

#: `why --json`'s keys and the read server's tool names, from their canonical homes: the
#: dossier module builds the dict, and the server registers the tools (stage-0 §241).
DOSSIER_KEYS = dossier_mod.DOSSIER_KEYS
MCP_TOOLS = mcp_server.READ_TOOLS


#: Ordinary words the skill sets in backticks that are neither verbs, keys, tools, nor
#: values the parser admits. Each carries the reason it is prose; the test refuses a member
#: the skill no longer uses, so this cannot quietly become an allowlist.
PROSE_WORDS = {
    "null": "JSON literal: how the dossier spells a missing row",
    "given": "a provenance mark `state` prints: the author's word, imported",
    "read": "a provenance mark `state` prints: this system's own extraction",
    "budget": "an omission reason inside `context_omitted`",
    "rising": "a beat function inside `selected_by`",
    "complication": "a beat function inside `selected_by`",
    "deterministic": "a `verdict_source` value on a gate",
    "calibrated_critic": "a `verdict_source` value on a gate",
    "uncalibrated_critic": "a `verdict_source` value on a gate",
    "human": "a `verdict_source` value on a gate",
    "blocking": "a gate's weight, as the text form prints it",
    "advisory": "a gate's weight, as the text form prints it",
    "gates": "a field of `decision`, and the text form's label for the ladder",
    "detail": "a field of one gate: the measured number and its caveat",
    "plan item": "the text form's label for the `plan_item` key",
    "selected by": "the text form's label for the `selected_by` key",
    "provider": "a field of `decision`",
    "model": "a field of `decision`",
    "invocations": "a field of `decision`",
    "cost_usd": "a field of `decision`",
    "total_tokens": "a field of `decision`",
    "policy_config_digest": "a field of `decision`",
    "content": "a field of `draft_before_revision`: the prose the reviser replaced",
    "prose": "a member of `absent`",
    "litharness-mcp": "the MCP server's console script, which is not a parser verb",
}

#: A name the skill sets in backticks: a verb, a `world check`-style path, a dossier key or
#: a tool. The brief's pattern had no `_`; that would have exempted every dossier key, which
#: is the half of the drift this test exists to catch.
NAME = re.compile(r"[a-z][a-z_-]*(?: [a-z_-]+)*")
OPTION = re.compile(r"--[a-z][a-z-]*")
#: Tokens that are file paths, dotted `key.subkey` paths, placeholders, printed lines or
#: identifiers rather than names: skipped, not checked.
SKIP = re.compile(r"[<(:/.A-Z]")
COMMAND_PREFIX = "uv run litharness "


def _parsers(
    parser: argparse.ArgumentParser, path: tuple[str, ...] = ()
) -> dict[tuple[str, ...], argparse.ArgumentParser]:
    """Every parser reachable from `parser`, keyed by the verb path that reaches it."""
    found = {path: parser}
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, sub in action.choices.items():
                found.update(_parsers(sub, (*path, name)))
    return found


def _subverbs(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return dict(action.choices)
    return {}


def _actions_by_option(
    parsers: dict[tuple[str, ...], argparse.ArgumentParser],
) -> dict[str, argparse.Action]:
    return {
        option: action
        for parser in parsers.values()
        for action in parser._actions
        for option in action.option_strings
    }


def _command_problems(
    words: list[str],
    *,
    where: str,
    parsers: dict[tuple[str, ...], argparse.ArgumentParser],
    require_verb: bool,
) -> list[str]:
    """Walk one command line the way argparse would, and name what it would refuse.

    Options must exist on the top-level parser or on a parser along the verb path (or, for
    an inline fragment with no verb, on any parser at all); a word after a value-taking
    option is its value; a bare word is the verb, then a subverb where one is admitted, and
    otherwise a positional value.
    """
    by_option = _actions_by_option(parsers)
    path: tuple[str, ...] = ()
    problems: list[str] = []
    pending_value = False
    for word in words:
        if word.startswith("-"):
            pending_value = False
            if not OPTION.fullmatch(word):
                continue  # `---`-style printed header, not an option
            action = by_option.get(word)
            if action is None:
                problems.append(f"{where}: no parser has option {word!r}")
                continue
            reachable = {
                option
                for depth in range(len(path) + 1)
                for parser_action in parsers[path[:depth]]._actions
                for option in parser_action.option_strings
            }
            if path and word not in reachable:
                problems.append(f"{where}: {word!r} is not an option of {' '.join(path)!r}")
            pending_value = action.nargs != 0
            continue
        if pending_value:
            pending_value = False
            continue
        choices = _subverbs(parsers[path])
        if word in choices:
            path = (*path, word)
        elif not path:
            problems.append(f"{where}: {word!r} is not a verb")
    if require_verb and not path:
        problems.append(f"{where}: no verb on the line")
    return problems


def test_every_verb_and_key_the_debug_book_skill_names_still_exists(tmp_path, capsys) -> None:
    """Three vocabularies, each derived rather than restated: the parser's verbs, subverb
    paths, option strings and admitted choice values come from `build_parser()`; the dossier
    keys are checked against `why --json` on the litrpg fixture; the MCP tool names wait on
    their module. A prose word is admitted only through `PROSE_WORDS`, and only while the
    skill still uses it."""
    parsers = _parsers(build_parser())
    verbs = {" ".join(path) for path in parsers if path}
    choices = {
        value
        for parser in parsers.values()
        for action in parser._actions
        if not isinstance(action, argparse._SubParsersAction) and action.choices
        for value in action.choices
        if isinstance(value, str)
    }

    db = tmp_path / "skill.db"
    assert main(["--database", str(db), "init"]) == EXIT_OK
    assert main(["--database", str(db), "import", "--fixture", "litrpg"]) == EXIT_OK
    capsys.readouterr()
    assert main(["--database", str(db), "why", "--scene", "1", "--json"]) in (
        EXIT_OK,
        EXIT_ATTENTION,
    )
    assert tuple(json.loads(capsys.readouterr().out)) == DOSSIER_KEYS

    text = SKILL.read_text(encoding="utf-8")
    assert text.count("~~") % 2 == 0, "an unpaired ~~ would exempt everything after it"
    live = re.sub(r"~~.*?~~", "", text, flags=re.S)
    fenced = re.findall(r"```.*?```", live, flags=re.S)
    inline = re.findall(r"`([^`\n]+)`", re.sub(r"```.*?```", "", live, flags=re.S))

    known = verbs | set(DOSSIER_KEYS) | set(MCP_TOOLS) | choices
    problems: list[str] = []
    prose_used: set[str] = set()
    for token in inline:
        if SKIP.search(token):
            continue
        words = token.removeprefix(COMMAND_PREFIX).split()
        if NAME.fullmatch(token) and not any(word.startswith("-") for word in words):
            name = token.removeprefix(COMMAND_PREFIX)
            if name in PROSE_WORDS:
                prose_used.add(name)
            elif name not in known:
                problems.append(f"`{token}` is not a verb, a dossier key, a tool, or prose")
        elif words[0] in verbs or OPTION.fullmatch(words[0]):
            problems.extend(
                _command_problems(words, where=f"`{token}`", parsers=parsers, require_verb=False)
            )
        # Anything else — digits, `scene-3`, a quoted output line — is not a name.

    for block in fenced:
        for line in block.splitlines():
            line = line.strip()
            if line.startswith(COMMAND_PREFIX):
                problems.extend(
                    _command_problems(
                        line.removeprefix(COMMAND_PREFIX).split(),
                        where=line,
                        parsers=parsers,
                        require_verb=True,
                    )
                )

    assert not problems, "\n".join(problems)
    unused = set(PROSE_WORDS) - prose_used
    assert not unused, f"PROSE_WORDS admits words the skill no longer uses: {sorted(unused)}"
