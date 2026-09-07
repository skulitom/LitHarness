"""The `litharness-mcp` skill and `.mcp.json` name only tools, verbs and profiles that exist.

The skill is how a session in this repository is told the server exists and what it holds
(stage-0 §241.1); `.mcp.json` is how the session finds the server without being told. Prose
drifts (the `debug-book` skill taught three dead verbs for weeks), so both are walked against
the server module and the real parser.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from litharness.cli import build_parser
from litharness.mcp_server import FENCE, PROFILES, PROPOSE_TOOLS, READ_TOOLS, WORLD_VIEWS

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / ".claude" / "skills" / "litharness-mcp" / "SKILL.md"
MCP_JSON = ROOT / ".mcp.json"

ALL_TOOLS = set(READ_TOOLS) | set(PROPOSE_TOOLS)

#: The verbs the skill says are deliberately not tools, each of which must still be a real
#: verb: an absence explained by a name the parser lacks would be an explanation of nothing.
NAMED_ABSENT = (
    "world accept",
    "roster accept",
    "release approve",
    "dismiss",
    "resolve",
    "revive",
    "enqueue",
    "ingest",
    "replan",
    "revert",
    "revert-plan",
    "tick",
    "architect seed",
    "readers",
    "listing",
    "concept",
    "recruit",
    "revoice",
    "cover",
    "prompts",
    "world declare-batch",
)


def _skill() -> str:
    """The skill with its line wraps folded, so a sentence is searchable across a break."""
    return " ".join(SKILL.read_text(encoding="utf-8").split())


def _leaf_paths() -> set[tuple[str, ...]]:
    found: set[tuple[str, ...]] = set()

    def walk(parser: argparse.ArgumentParser, path: tuple[str, ...]) -> None:
        subs = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
        if not subs:
            found.add(path)
            return
        for sub in subs:
            for name, child in sub.choices.items():
                walk(child, (*path, name))

    walk(build_parser(), ())
    return found


def test_the_skill_names_every_tool_and_no_tool_that_does_not_exist() -> None:
    text = _skill()
    for tool in ALL_TOOLS:
        assert f"`{tool}`" in text, f"the skill does not mention {tool}"
    for prefixed in re.findall(r"mcp__litharness__(\w+)", text):
        assert prefixed in ALL_TOOLS, prefixed
    for view in WORLD_VIEWS:
        assert f"`{view}`" in text, view
    for profile in PROFILES:
        assert f"`{profile}`" in text, profile


def test_the_skill_names_only_verbs_the_parser_has() -> None:
    """Every `litharness <verb> [<subverb>] ...` the skill sets in backticks is a real leaf or
    the prefix of one, and every verb it lists as deliberately absent is a real verb too; a
    verb renamed or removed surfaces here rather than as a failed command."""
    text = _skill()
    leaves = _leaf_paths()
    prefixes = {path[:n] for path in leaves for n in range(1, len(path) + 1)}
    for match in re.finditer(r"`litharness ([a-z][a-z-]*(?: [a-z][a-z-]*)?)[^`]*`", text):
        words = tuple(match.group(1).split())
        assert words in prefixes, match.group(0)
    for verb in NAMED_ABSENT:
        pattern = rf"`(?:litharness )?{re.escape(verb)}(?: [^`]*)?`"
        assert re.search(pattern, text), f"the skill no longer names {verb}"
        assert tuple(verb.split()) in prefixes, verb


def test_the_skill_carries_the_fence_in_the_servers_words() -> None:
    sentence = "Nothing a dossier tells you may become a prompt, directive, finding or plan item"
    assert sentence in _skill()
    assert sentence in FENCE


def test_the_repository_registers_the_server_for_a_session() -> None:
    """`.mcp.json` is the project-scope registration a Claude Code session reads without being
    told; it must launch the console script, name the server the tools are prefixed with, and
    carry no absolute path (the store comes from the environment, with the CLI's default)."""
    config = json.loads(MCP_JSON.read_text(encoding="utf-8"))
    server = config["mcpServers"]["litharness"]
    assert server["type"] == "stdio"
    argv = [server["command"], *server["args"]]
    assert "litharness-mcp" in argv
    assert "--database" in argv
    database = argv[argv.index("--database") + 1]
    assert "${LITHARNESS_DATABASE" in database, "the store is named by the session's environment"
    assert "litharness.db" in database, "with the CLI's own default when it is not"
    profile = argv[argv.index("--profile") + 1]
    assert profile.endswith(":-read}"), "read is the profile a session gets unless it asks"
    for piece in argv:
        absolute = re.match(r"^([A-Za-z]:[\\/]|/)", piece)
        assert not absolute, f"an absolute path was committed: {piece}"
