"""The agent surface: `litharness-mcp` (stage-0 §241).

Every containment claim the server module makes is pinned here by code rather than by its
docstring: the tier table equals the parser; the paid verbs are the ones whose handlers build
a provider registry, found by `ast`; no profile registers an operator or paid verb; there is
no accept tool; the module imports no provider and no CLI; a read tool changes no byte of the
store; a write tool reports a locked store once and never retries; a marker shelf never
leaves a tool result. The handlers are driven in-process, so none of this needs the SDK; the
one stdio round trip at the end skips when the `mcp` extra is absent.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import inspect
import json
import os
import re
import sqlite3
import sys
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from litharness import cli, mcp_server
from litharness.adapters import sqlite_store
from litharness.adapters.sqlite_store import SqliteStore
from litharness.application import dossier as dossier_mod
from litharness.application import exemplars as exemplars_mod
from litharness.application import world_agent
from litharness.application.handlers import SCENE_DRAFT
from litharness.cli import EXIT_ATTENTION, EXIT_OK, build_parser, main
from litharness.domain.jobs import Job, input_digest_for
from litharness.mcp_server import (
    DESCRIPTIONS,
    FENCE,
    PROFILES,
    PROMPTS,
    PROPOSE_TOOLS,
    READ_TOOLS,
    RESOURCES,
    RESULT_KEYS,
    SURFACE_ONLY_TOOLS,
    TIERS,
    VERB_HELP,
    WORLD_VIEWS,
    Binding,
    make_tools,
    prompt_names,
    prompt_text,
)

REPO = Path(__file__).resolve().parent.parent


def run(db: Path, *args: str) -> int:
    return main(["--database", str(db), *args])


@pytest.fixture
def db(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> Path:
    path = tmp_path / "book.db"
    assert run(path, "init") == EXIT_OK
    assert run(path, "import", "--fixture", "litrpg") == EXIT_OK
    capsys.readouterr()
    return path


@pytest.fixture
def db_fd(tmp_path: Path, capfd: pytest.CaptureFixture[str]) -> Path:
    """The same store, under fd-level capture: the stdio round trip hands the child a
    real stderr, which `capsys` cannot provide and cannot be combined with."""
    path = tmp_path / "book.db"
    assert run(path, "init") == EXIT_OK
    assert run(path, "import", "--fixture", "litrpg") == EXIT_OK
    capfd.readouterr()
    return path


def binding(db: Path, profile: str = "read") -> Binding:
    return Binding(database=db, roster_database=db, profile=profile, client="test")


def _leaf_paths() -> dict[tuple[str, ...], argparse.ArgumentParser]:
    """Every leaf verb of the real parser, the way `test_cli.py` derives the allowance."""
    found: dict[tuple[str, ...], argparse.ArgumentParser] = {}

    def walk(parser: argparse.ArgumentParser, path: tuple[str, ...]) -> None:
        subs = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
        if not subs:
            found[path] = parser
            return
        for sub in subs:
            for name, child in sub.choices.items():
                walk(child, (*path, name))

    walk(build_parser(), ())
    return found


def _leaf_help() -> dict[tuple[str, ...], str]:
    helps: dict[tuple[str, ...], str] = {}

    def walk(parser: argparse.ArgumentParser, path: tuple[str, ...]) -> None:
        for sub in (a for a in parser._actions if isinstance(a, argparse._SubParsersAction)):
            for choice in sub._choices_actions:
                helps[(*path, choice.dest)] = choice.help or ""
            for name, child in sub.choices.items():
                walk(child, (*path, name))

    walk(build_parser(), ())
    return helps


#: The server's own keys on a result: the contract's two, and the paging four (§241.2).
SERVER_KEYS = {"attention", "next", "total", "offset", "limit", "truncated"}


def _payload(result: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in result.items() if key not in SERVER_KEYS}


# --- the tier table against the parser ------------------------------------------------


def test_every_parser_verb_has_exactly_one_tier() -> None:
    """A verb that arrives unclassified would be neither offered nor named as excluded: the
    silent kind of gap. Equality in both directions, from the real parser."""
    assert set(TIERS) == set(_leaf_paths())


def test_the_tier_table_names_every_verb_that_builds_a_registry_as_excluded() -> None:
    """Which verbs spend is read off `cli.py` by `ast` — a handler that builds the provider
    registry, runs the conductor, or finds the Codex binary — and held equal to the tiers
    that say `spends`. Nobody's memory of what is paid is the source."""
    tree = ast.parse(Path(inspect.getsourcefile(cli) or "").read_text(encoding="utf-8"))
    functions = {node.name: node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    spending_names = {"build_default_registry", "_conductor", "_codex_executable"}

    def spends(function: ast.FunctionDef) -> bool:
        return any(
            isinstance(node, ast.Name) and node.id in spending_names
            for node in ast.walk(function)
        )

    paid = set()
    for path, parser in _leaf_paths().items():
        handler = parser._defaults["func"]
        if spends(functions[handler.__name__]):
            paid.add(path)
    assert paid == {path for path, tier in TIERS.items() if tier.reason.startswith("spends")}
    assert paid, "the litrpg pipeline spends somewhere"


def test_no_profile_registers_an_operator_or_paid_verb() -> None:
    by_tool: dict[str, set[str]] = {}
    for tier in TIERS.values():
        if tier.tool is not None:
            by_tool.setdefault(tier.tool, set()).add(tier.kind)
    for profile, tools in PROFILES.items():
        for tool in tools:
            kinds = by_tool.get(tool, set())
            assert kinds <= {"read", "propose"}, (profile, tool, kinds)
    assert set(PROPOSE_TOOLS) - set(READ_TOOLS) == {"world_declare", "world_declare_batch"}
    assert "why" not in PROPOSE_TOOLS and "export_markdown" not in PROPOSE_TOOLS
    # The surface's own tools wrap no single verb; every other read tool wraps one.
    wrapped = {tier.tool for tier in TIERS.values() if tier.kind == "read"}
    assert wrapped == set(READ_TOOLS) - set(SURFACE_ONLY_TOOLS)
    assert set(SURFACE_ONLY_TOOLS) <= set(READ_TOOLS)


def test_the_server_exposes_no_accept_tool() -> None:
    """The omission is the containment (§146.9): `world accept` is in no profile, and the
    world tool's views are the parser's subtree minus the writes and that gate."""
    world_sub = {path[1] for path in _leaf_paths() if path[0] == "world"}
    assert set(WORLD_VIEWS) == world_sub - {"accept", "declare", "declare-batch"}
    assert "accept" not in WORLD_VIEWS
    for tools in PROFILES.values():
        assert not any("accept" in tool for tool in tools)
    assert TIERS[("world", "accept")].kind == "operator"


def test_the_tier_tables_architect_members_are_the_architects_allowance() -> None:
    """Two renderings of one omission: the Bash allowance the Architect holds and the world
    tools the server registers name the same subcommands."""
    rendered = {
        f"Bash(litharness world {path[1]}:*)"
        for path, tier in TIERS.items()
        if path[0] == "world" and tier.kind in {"read", "propose"}
    }
    assert rendered == set(world_agent.ALLOWED_TOOLS)


def test_the_server_module_imports_no_provider_no_cli_and_opens_no_socket() -> None:
    source = Path(inspect.getsourcefile(mcp_server) or "").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
            imported.update(f"{node.module}.{alias.name}" for alias in node.names)
    forbidden = ("litharness.providers", "litharness.cli", "urllib", "http", "socket", "httpx")
    for name in imported:
        assert not any(name == f or name.startswith(f + ".") for f in forbidden), name
    strings = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert not any("EXEMPLARS" in text for text in strings)
    for tools in PROFILES.values():
        assert not any("post" in tool or "publish" in tool for tool in tools)


def test_the_server_and_the_cli_name_the_same_environment_variables_and_project() -> None:
    assert mcp_server.DATABASE_ENV == cli.DATABASE_ENV
    assert mcp_server.ROSTER_DATABASE_ENV == cli.ROSTER_DATABASE_ENV
    assert build_parser().get_default("project") == mcp_server.DEFAULT_PROJECT_ID


def test_every_tool_description_carries_the_parsers_help() -> None:
    """The factual half of a description is the parser's help, pinned so it cannot drift the
    way the skill's prose did; the fence is on every read and never on a write."""
    helps = _leaf_help()
    for path, text in VERB_HELP.items():
        assert helps[path] == text, path
    for name in READ_TOOLS:
        assert DESCRIPTIONS[name].endswith(FENCE), name
        assert DESCRIPTIONS[name].startswith("READ.")
    for name in ("world_declare", "world_declare_batch"):
        assert DESCRIPTIONS[name].startswith("PROPOSE.")
        assert "PROPOSED" in DESCRIPTIONS[name]
        assert FENCE not in DESCRIPTIONS[name]
    for view in WORLD_VIEWS:
        assert VERB_HELP[("world", view)] in DESCRIPTIONS["world"]
    for view in ("show", "check", "vocabulary"):
        assert VERB_HELP[("roster", view)] in DESCRIPTIONS["roster"]
    assert set(DESCRIPTIONS) == set(READ_TOOLS) | set(PROPOSE_TOOLS)


# --- binding and the store ------------------------------------------------------------


def test_the_server_refuses_to_start_on_an_absent_database_and_creates_no_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "nope.db"
    with pytest.raises(SystemExit) as raised:
        Binding.resolve(["--database", str(missing)])
    assert raised.value.code == 2
    assert "does not exist" in capsys.readouterr().err
    assert not missing.exists()
    with pytest.raises(SystemExit):
        Binding.resolve([])


def test_the_binding_reads_the_environment_the_cli_reads(
    db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(mcp_server.DATABASE_ENV, str(db))
    monkeypatch.delenv(mcp_server.ROSTER_DATABASE_ENV, raising=False)
    bound = Binding.resolve(["--client", "probe"])
    assert bound.database == db.resolve() and bound.roster_database == db.resolve()
    assert bound.actor == "mcp:read:probe"


def test_a_relative_database_is_anchored_on_the_project_directory_the_host_names(
    db: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`.mcp.json` names the store relatively (`litharness.db` unless `LITHARNESS_DATABASE`
    says otherwise) and the host does not document the working directory a project server
    gets; it does set `CLAUDE_PROJECT_DIR`, so a relative path is anchored there (§241.1). An
    absolute path is untouched, and with the variable unset the working directory is the
    anchor, as for any command."""
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    monkeypatch.setenv(mcp_server.PROJECT_DIR_ENV, str(db.parent))
    bound = Binding.resolve(["--database", db.name])
    assert bound.database == db.resolve()
    assert Binding.resolve(["--database", str(db)]).database == db.resolve()
    monkeypatch.delenv(mcp_server.PROJECT_DIR_ENV)
    with pytest.raises(SystemExit):
        Binding.resolve(["--database", db.name])


def test_a_read_tool_opens_the_store_read_only_and_leaves_no_file_behind(db: Path) -> None:
    before = hashlib.sha256(db.read_bytes()).hexdigest()
    siblings = sorted(
        p for p in db.parent.iterdir() if not p.name.endswith(("-wal", "-shm"))
    )
    tools = make_tools(binding(db))
    calls: dict[str, dict[str, Any]] = {
        "store_info": {},
        "guide": {},
        "book": {},
        "scene": {"scene": "1"},
        "status": {},
        "why": {"scene": "1"},
        "findings": {},
        "events": {},
        "plans": {},
        "state": {},
        "queue": {},
        "world": {"view": "summary"},
        "characters": {},
        "roster": {"view": "show"},
        "release_show": {},
        "verify": {},
        "export_markdown": {},
    }
    assert set(calls) == set(READ_TOOLS)
    for name, arguments in calls.items():
        result = tools[name](**arguments)
        assert isinstance(result, dict) and "attention" in result, name
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before
    # SQLite's own WAL sidecars (`-wal`, `-shm`) may appear for a reader; no store does.
    after = sorted(
        p for p in db.parent.iterdir() if not p.name.endswith(("-wal", "-shm"))
    )
    assert after == siblings
    for view in WORLD_VIEWS:
        assert tools["world"](view=view)["view"] == view


def test_a_read_tool_answers_while_another_connection_holds_begin_immediate(db: Path) -> None:
    holder = sqlite3.connect(str(db), isolation_level=None)
    holder.execute("BEGIN IMMEDIATE")
    try:
        started = time.monotonic()
        assert make_tools(binding(db))["status"]()["attention"] is False
        assert time.monotonic() - started < 1.0
    finally:
        holder.execute("ROLLBACK")
        holder.close()


def test_a_write_tool_reports_a_locked_database_as_retryable_and_does_not_loop(
    db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One fault, one sentence, no retry: the operator's own contract at `cli.main`.

    The store's busy timeout is shortened for the test: `open_existing` reads the constant
    when it opens, so the wait is 300 ms here rather than five seconds, and the bound below
    is then several waits wide — a retry loop of any length fails it, while a loaded box
    under coverage tracing (where the five-second version failed once) does not."""
    monkeypatch.setattr(sqlite_store, "BUSY_TIMEOUT_MS", 300)
    holder = sqlite3.connect(str(db), isolation_level=None)
    holder.execute("BEGIN IMMEDIATE")
    tools = make_tools(binding(db, "propose"))
    try:
        started = time.monotonic()
        with pytest.raises(Exception, match="locked by the ticking session") as raised:
            tools["world_declare"](subject="x", predicate="is_a", value="Thing")
        assert time.monotonic() - started < 5 * sqlite_store.BUSY_TIMEOUT_MS / 1000 + 2
        assert type(raised.value).__name__ in {"ToolError", "ServerFault"}
    finally:
        holder.execute("ROLLBACK")
        holder.close()


def test_a_tool_handler_runs_on_a_worker_thread_and_still_transacts(db: Path) -> None:
    """The SDK runs a sync handler on an anyio worker thread; the store's transactions run only
    on the thread that opened it — so a tool opens its own store inside the call."""
    tools = make_tools(binding(db, "propose"))
    outcome: dict[str, Any] = {}

    def work() -> None:
        outcome["result"] = tools["world_declare"](subject="probe", predicate="is_a", value="Thing")

    worker = threading.Thread(target=work)
    worker.start()
    worker.join()
    assert outcome["result"]["new"] is True and outcome["result"]["authority"] == "proposed"
    with SqliteStore.open_read_only(db) as store:
        book_id, branch_id, _ = store.branches()[0]
        assert any(r.subject == "probe" for r in store.state_records(book_id, branch_id))


def test_a_tool_call_writes_nothing_to_stdout(db: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """stdout is the transport. A stray print would corrupt the JSON-RPC stream."""
    tools = make_tools(binding(db, "propose"))
    tools["world"](view="check")
    tools["store_info"]()
    tools["world_declare"](subject="quiet", predicate="is_a", value="Thing")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "litharness-mcp mcp:propose:test world_declare" in captured.err


# --- results, not exits ---------------------------------------------------------------


def test_the_why_tool_carries_attention_instead_of_exit_one(db: Path) -> None:
    result = make_tools(binding(db))["why"](scene="1")
    assert result["attention"] is True
    assert "prose" in result["absent"] and result["next"] == ["queue"]
    assert tuple(_payload(result)) == dossier_mod.DOSSIER_KEYS


def test_an_unknown_scene_and_an_ambiguous_store_are_results_not_faults(
    db: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    tools = make_tools(binding(db))
    unknown = tools["why"](scene="99")
    assert unknown["error_kind"] == "unknown_scene" and unknown["attention"] is True
    assert "scene-1" in unknown["known_scenes"]
    assert run(db, "import", "--fixture", "mystery") == EXIT_OK
    capsys.readouterr()
    ambiguous = tools["state"]()
    assert ambiguous["error_kind"] == "ambiguous_branch"
    assert len(ambiguous["known"]) == 2 and ambiguous["next"] == ["store_info"]
    named = tools["state"](**ambiguous["known"][0])
    assert "records" in named


def test_the_views_the_server_returns_are_the_dicts_the_cli_prints(
    db: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """One source: the CLI prints a view, the server returns it. Only `attention` and
    `next` are the server's own, and `now` is the clock's."""
    tools = make_tools(binding(db))

    def cli_json(*args: str) -> Any:
        code = run(db, *args)
        assert code in (EXIT_OK, EXIT_ATTENTION)
        return json.loads(capsys.readouterr().out)

    for name, args, kwargs in (
        ("findings", ("findings", "--json"), {}),
        ("events", ("events", "--json", "--limit", "100"), {}),
        ("plans", ("plans", "--json"), {}),
        ("state", ("state", "--json"), {}),
        ("characters", ("characters", "--json"), {}),
        ("verify", ("verify", "--json"), {}),
    ):
        assert _payload(tools[name](**kwargs)) == cli_json(*args), name
    status = _payload(tools["status"]())
    printed = cli_json("status", "--json")
    status.pop("now", None)
    printed.pop("now", None)
    assert status == printed
    queue = tools["queue"]()
    assert queue["counts"] == cli_json("jobs", "--json")["counts"]
    assert queue["exceptions"] == cli_json("exceptions", "--json")["exceptions"]
    assert queue["directives"] == cli_json("directives", "--json")["directives"]
    for view in WORLD_VIEWS:
        assert tools["world"](view=view)["result"] == cli_json("world", view), view


def test_the_dossier_the_server_returns_is_the_dict_the_cli_prints_unless_a_shelf_was_shown(
    db: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(db, "why", "--scene", "1", "--json") == EXIT_ATTENTION
    printed = json.loads(capsys.readouterr().out)
    assert _payload(make_tools(binding(db))["why"](scene="1")) == printed


def test_a_marker_shelf_never_appears_in_a_tool_result(db: Path) -> None:
    """The shelf is other writers' text, shown to the writer and never quoted (§196). It is
    spliced whole into the frozen prompt `why` prints, so the server withholds it by count.
    Built with the same render the planner uses (`planner.render_prompt` joins
    `render_openings(shelf)` and the packet with one blank line) so a heading rename fails
    here rather than leaking."""
    marker = "Zebulon Quandary polished the seventeenth brass owl."
    shelf = exemplars_mod.Shelf(
        root=Path("shelf"),
        exemplars=(
            exemplars_mod.Exemplar(
                name="Marker",
                title="Marker Book",
                chapter=f"{marker}\n\nHe polished it again.",
                blurb=None,
                digest="0" * 16,
                words=12,
            ),
        ),
    )
    packet = "Premise: a person climbs.\n\nNow write scene-1."
    prompt = f"{exemplars_mod.render_openings(shelf)}\n\n{packet}"
    system = f"You write scenes.\n{exemplars_mod.SHELF_SYSTEM}"
    with SqliteStore.open_existing(db) as store:
        book_id, branch_id, _ = store.branches()[0]
        payload = {
            "prompt": prompt,
            "system": system,
            "logical_id": "scene-1",
            "book_id": book_id,
            "branch_id": branch_id,
            "exemplars": shelf.record(),
        }
        store.enqueue(
            Job(
                job_id="shelf-probe",
                job_kind=SCENE_DRAFT,
                payload=payload,
                input_digest=input_digest_for(payload),
            )
        )
    result = make_tools(binding(db))["why"](scene="scene-1")
    rendered = json.dumps(result)
    assert marker not in rendered
    assert exemplars_mod.SHELF_SYSTEM not in rendered
    assert exemplars_mod.OPENINGS_HEADING not in rendered
    assert result["prompt"]["prompt"].startswith("[exemplar shelf withheld: ")
    assert result["prompt"]["prompt"].endswith("Premise: a person climbs.\n\nNow write scene-1.")
    assert result["prompt"]["system"] == "You write scenes."
    # The operator's own `why` still prints the shelf: that is the diagnostic channel.
    with SqliteStore.open_read_only(db) as store:
        head = store.head(book_id, branch_id)
        assert head is not None
        node = dossier_mod.scene_node(head, "scene-1")
        assert node is not None
        raw = dossier_mod.scene_dossier(store, book_id, branch_id, node, head)
    assert marker in raw["prompt"]["prompt"]


def test_a_shelf_whose_end_cannot_be_found_withholds_the_whole_prompt() -> None:
    dossier = {
        "prompt": {"system": None, "prompt": f"{exemplars_mod.OPENINGS_HEADING}\n\nsecret text"},
        "draft_before_revision": None,
    }
    redacted = dossier_mod.redact_shelf(dossier)
    assert redacted["prompt"]["prompt"] == dossier_mod.PROMPT_WITHHELD
    assert "secret" not in json.dumps(redacted)
    untouched = {
        "prompt": {"system": "s", "prompt": "Premise: plain"},
        "draft_before_revision": None,
    }
    assert dossier_mod.redact_shelf(untouched) == untouched


# --- the propose profile --------------------------------------------------------------


def test_world_declare_through_the_server_mints_proposed_only_and_carries_the_machine_actor(
    db: Path,
) -> None:
    tools = make_tools(binding(db, "propose"))
    first = tools["world_declare"](subject="Sera", predicate="is_a", value="Person")
    assert first["authority"] == "proposed" and first["new"] is True and first["attention"] is False
    second = tools["world_declare"](subject="Sera", predicate="is_a", value="Climber")
    assert second["supersedes"] == [first["record_id"]]
    with SqliteStore.open_read_only(db) as store:
        book_id, branch_id, _ = store.branches()[0]
        records = store.state_records(book_id, branch_id, subject="sera")
        assert {record.authority.value for record in records} == {"proposed"}
        actors = {
            item.event.actor
            for item in store.read_log()
            if item.event.payload.get("via") == "mcp world_declare"
        }
    assert actors == {"mcp:propose:test"}


def test_world_declare_batch_reports_each_item_and_stops_only_when_asked(db: Path) -> None:
    tools = make_tools(binding(db, "propose"))
    items = [
        {"subject": "a", "predicate": "is_a", "value": "A"},
        {"subject": "b", "predicate": "is_a", "value": "B", "order-key": "0100"},
        {"subject": "c", "predicate": "is_a", "value": "C"},
    ]
    batch = tools["world_declare_batch"](items=items)
    assert (batch["declared"], batch["refused"], batch["not_attempted"]) == (2, 1, 0)
    assert batch["results"][1] == {"index": 1, "refused": batch["results"][1]["refused"]}
    assert "check" in batch and batch["attention"] is True
    stopping = tools["world_declare_batch"](
        items=[
            {
                "subject": "sera",
                "predicate": "status_sheet",
                "value": {
                    "fields": [
                        {"name": "mp", "label": "MP", "paired": True},
                        {"name": "mp_max", "label": "Ceiling"},
                    ]
                },
            },
            {"subject": "f", "predicate": "is_a", "value": "F"},
        ],
        stop_on_incoherent=True,
    )
    assert stopping["declared"] == 1 and stopping["not_attempted"] == 1
    assert stopping["results"][0]["cannot_be_read"]


def test_the_propose_profile_holds_the_architects_shape_and_no_dossier(db: Path) -> None:
    tools = make_tools(binding(db, "propose"))
    assert set(PROFILES["propose"]) <= set(tools)
    assert tools["store_info"]()["tools"] == list(PROPOSE_TOOLS)
    assert tools["guide"]()["verbs"]
    named = {row["verb"]: row["tool"] for row in tools["guide"]()["verbs"]}
    assert named["why"] is None, "a read tool the propose profile does not register reads as absent"
    assert named["world declare"] == "world_declare"


# --- store_info, guide, and the absent extra ------------------------------------------


def test_store_info_still_answers_with_pending_migrations(db: Path, tmp_path: Path) -> None:
    copy = tmp_path / "lagging.db"
    copy.write_bytes(db.read_bytes())
    connection = sqlite3.connect(str(copy))
    connection.execute(
        "DELETE FROM schema_migrations WHERE name = (SELECT max(name) FROM schema_migrations)"
    )
    connection.commit()
    connection.close()
    tools = make_tools(binding(copy))
    info = tools["store_info"]()
    assert info["migrations_pending"] == 1 and info["attention"] is True
    with pytest.raises(Exception, match=r"MigrationsPending: 1 migration\(s\) pending"):
        tools["status"]()


def test_the_guide_names_every_excluded_verb_with_its_reason_and_cli_form(db: Path) -> None:
    guide = make_tools(binding(db))["guide"]()
    rows = {row["verb"]: row for row in guide["verbs"]}
    assert set(rows) == {" ".join(path) for path in TIERS}
    for verb in guide["spends"]:
        assert rows[verb]["tier"] == "excluded"
        assert rows[verb]["reason"].startswith("spends")
        assert rows[verb]["cli_form"].startswith("litharness ")
    named = {"tick", "architect seed", "readers", "listing", "concept", "cover"}
    assert named <= set(guide["spends"])
    assert rows["world accept"]["tier"] == "operator" and rows["world accept"]["tool"] is None
    assert guide["fence"] == FENCE
    one = make_tools(binding(db))["guide"](verb="world")
    assert {row["verb"].split(" ")[0] for row in one["verbs"]} == {"world"}


def test_a_missing_mcp_extra_is_one_line_and_exit_2(
    db: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setitem(sys.modules, "mcp", None)
    monkeypatch.setitem(sys.modules, "mcp.server", None)
    assert mcp_server.main(["--database", str(db)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.strip().splitlines() == [
        "litharness: the mcp extra is not installed; run `uv sync --extra mcp`"
    ]


def test_the_stdio_server_lists_exactly_the_profile_tools(db_fd: Path) -> None:
    """The one transport round trip: the installed SDK's client launches the console
    script's module, lists the profile's tools with their annotations, and calls two.
    Under `db_fd`: the SDK hands the child its own stderr, which needs a real descriptor."""
    db = db_fd
    pytest.importorskip("mcp")
    import anyio
    from mcp import Client, StdioServerParameters
    from mcp.client.stdio import stdio_client

    async def probe(profile: str) -> tuple[list[Any], dict[str, Any], dict[str, Any]]:
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "litharness.mcp_server", "--database", str(db), "--profile", profile],
            env={**os.environ, "LITHARNESS_ENV": "test"},
            cwd=str(REPO),
        )
        # The SDK binds its default `errlog` to `sys.stderr` at import, which under pytest's
        # capture is an object with no file descriptor; the child gets the real one.
        async with Client(stdio_client(params, errlog=sys.__stderr__)) as client:
            listed = await client.list_tools()
            info = await client.call_tool("store_info", {})
            why = await client.call_tool("why", {"scene": "1"}) if profile == "read" else None
            prompts = await client.list_prompts()
            resources = await client.list_resources()
            templates = await client.list_resource_templates()
            guide = await client.read_resource("litharness://guide")
            extras = {
                "prompts": [item.name for item in prompts.prompts],
                "resources": [str(item.uri) for item in resources.resources],
                "templates": [item.uri_template for item in templates.resource_templates],
                "guide": json.loads(guide.contents[0].text),
            }
            return (
                list(listed.tools),
                json.loads(info.content[0].text),
                {} if why is None else json.loads(why.content[0].text),
                extras,
            )

    tools, info, why, extras = anyio.run(probe, "read")
    assert [tool.name for tool in tools] == list(READ_TOOLS)
    assert extras["prompts"] == list(PROMPTS["read"])
    assert set(extras["resources"]) == {"litharness://store", "litharness://guide"}
    assert set(extras["templates"]) == {
        "litharness://book/{book_id}",
        "litharness://export/{book_id}",
    }
    assert extras["guide"]["fence"] == FENCE
    for tool in tools:
        assert tool.annotations is not None and tool.annotations.read_only_hint is True
        assert tool.description == DESCRIPTIONS[tool.name]
    assert info["profile"] == "read" and len(info["books"]) == 1
    assert why["attention"] is True and "prose" in why["absent"]

    proposed, info, _, extras = anyio.run(probe, "propose")
    assert extras["prompts"] == list(PROMPTS["propose"]) and extras["templates"] == []
    assert [tool.name for tool in proposed] == list(PROPOSE_TOOLS)
    assert info["tools"] == list(PROPOSE_TOOLS)


# --- §241.2: the book and scene tools, paging, the prompt switch, the access log -----------


def test_the_book_and_scene_tools_answer_the_reading_state(db: Path) -> None:
    tools = make_tools(binding(db))
    book = tools["book"]()
    assert book["total"] == 6 and book["drafted"] == 0 and book["attention"] is True
    assert book["title"] and book["premise"]
    assert [row["ordinal"] for row in book["scenes"]] == [1, 2, 3, 4, 5, 6]
    assert {row["chapter"] for row in book["scenes"]} == {1, 2}
    assert book["next"] == ["status", "queue"]
    one = tools["scene"](scene="2")
    assert one["logical_id"] == book["scenes"][1]["logical_id"]
    assert one["text"] is None and one["drafted"] is False and one["next"] == ["why"]
    assert tools["scene"](scene="99")["error_kind"] == "unknown_scene"


def test_state_and_findings_page_with_a_visible_bound(db: Path) -> None:
    tools = make_tools(binding(db))
    everything = tools["state"](limit=0)
    assert everything["total"] == len(everything["records"]) > 3
    assert everything["truncated"] is False
    first = tools["state"](limit=2)
    assert len(first["records"]) == 2 and first["truncated"] is True and first["offset"] == 0
    second = tools["state"](limit=2, offset=2)
    assert second["records"][0] == everything["records"][2]
    last = tools["state"](limit=2, offset=everything["total"] - 1)
    assert len(last["records"]) == 1 and last["truncated"] is False
    paged = tools["findings"](limit=1)
    assert paged["total"] == paged["shown"] and paged["truncated"] is (paged["total"] > 1)


def test_the_why_tool_can_withhold_the_prompt_and_keep_its_sizes(db: Path) -> None:
    tools = make_tools(binding(db))
    with SqliteStore.open_existing(db) as store:
        book_id, branch_id, _ = store.branches()[0]
        payload = {
            "prompt": "Write the scene.",
            "system": "You write.",
            "logical_id": "scene-1",
            "book_id": book_id,
            "branch_id": branch_id,
        }
        store.enqueue(
            Job(
                job_id="prompt-probe",
                job_kind=SCENE_DRAFT,
                payload=payload,
                input_digest=input_digest_for(payload),
            )
        )
    full = tools["why"](scene="scene-1")
    assert full["prompt"]["prompt"] == "Write the scene."
    slim = tools["why"](scene="scene-1", include_prompt=False)
    assert slim["prompt"]["prompt"] is None
    assert slim["prompt"]["prompt_chars"] == len("Write the scene.")
    assert slim["prompt"]["system_chars"] == len("You write.")
    assert tuple(_payload(slim)) == dossier_mod.DOSSIER_KEYS


def test_export_markdown_cuts_at_max_chars_and_says_so(db: Path) -> None:
    tools = make_tools(binding(db))
    whole = tools["export_markdown"]()
    assert whole["truncated"] is False and whole["chars"] == len(whole["markdown"])
    cut = tools["export_markdown"](max_chars=50)
    assert len(cut["markdown"]) == 50 and cut["truncated"] is True
    assert cut["chars"] == whole["chars"]


def test_every_result_carries_the_keys_the_tool_list_documents(db: Path) -> None:
    """The shape is taught rather than typed (module docstring): every tool's result on the
    fixture holds every key its `RESULT_KEYS` row names, and every description names them."""
    calls: dict[str, dict[str, Any]] = {
        "store_info": {},
        "guide": {},
        "book": {},
        "scene": {"scene": "1"},
        "status": {},
        "why": {"scene": "1"},
        "findings": {},
        "events": {},
        "plans": {},
        "state": {},
        "queue": {},
        "world": {"view": "summary"},
        "characters": {},
        "roster": {"view": "vocabulary"},
        "release_show": {},
        "verify": {},
        "export_markdown": {},
        "world_declare": {"subject": "keys", "predicate": "is_a", "value": "Probe"},
        "world_declare_batch": {"items": [{"subject": "k2", "predicate": "is_a", "value": "P"}]},
    }
    assert set(calls) == set(RESULT_KEYS) == set(READ_TOOLS) | set(PROPOSE_TOOLS)
    read = make_tools(binding(db))
    propose = make_tools(binding(db, "propose"))
    for name, arguments in calls.items():
        tools = propose if name.startswith("world_declare") else read
        result = tools[name](**arguments)
        missing = set(RESULT_KEYS[name]) - set(result)
        assert not missing, (name, missing)
        assert "attention" in result
        for key in RESULT_KEYS[name]:
            assert key in DESCRIPTIONS[name], (name, key)
    described = read["guide"](tool="why")["tool"]
    assert described["result_keys"] == list(dossier_mod.DOSSIER_KEYS)
    assert described["registered"] is True
    with pytest.raises(Exception, match="no tool named"):
        read["guide"](tool="post")


def test_every_call_leaves_one_access_log_line(
    db: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The operator's measurement of what agents ask (§241.2): actor, tool, an argument
    digest (never the arguments), elapsed, outcome — on stderr, and in the file the
    environment names, so a host that swallows a child's stderr still leaves a record."""
    log = tmp_path / "access.log"
    monkeypatch.setenv(mcp_server.ACCESS_LOG_ENV, str(log))
    tools = make_tools(binding(db))
    tools["status"]()
    tools["why"](scene="1")
    tools["why"](scene="99")
    with pytest.raises(Exception, match="no tool named"):
        tools["guide"](tool="nope")
    err = capsys.readouterr().err
    lines = [line for line in err.splitlines() if line.startswith("litharness-mcp")]
    assert len(lines) == 4
    assert lines[0].startswith("litharness-mcp mcp:read:test status ") and lines[0].endswith(" ok")
    assert lines[1].endswith(" attention")
    assert lines[2].endswith(" result:unknown_scene")
    assert lines[3].endswith(" fault:ValueError")
    assert "99" not in lines[2] and "nope" not in lines[3], "arguments never reach the log"
    assert len(log.read_text(encoding="utf-8").splitlines()) == 4


def test_the_prompts_walk_the_tools_they_name_and_end_with_the_fence() -> None:
    for name in prompt_names():
        text = prompt_text(name, scene="scene-3")
        for tool in re.findall(r"`([a-z_]+)`", text):
            if tool in RESULT_KEYS:
                profile = "propose" if name == "propose_world" else "read"
                assert tool in PROFILES[profile], (name, tool)
    assert prompt_text("debug_scene", scene="scene-3").endswith(FENCE)
    assert prompt_text("book_health").endswith(FENCE)
    assert "world accept" in prompt_text("propose_world")
    with pytest.raises(ValueError, match="no prompt named"):
        prompt_text("post")
    assert set(prompt_names()) == set(PROMPTS["read"]) | set(PROMPTS["propose"])
    for profile, uris in RESOURCES.items():
        assert "litharness://store" in uris and "litharness://guide" in uris, profile
