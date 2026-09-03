"""Declare every shape in `shapes.jsonl` into a fresh store and record what the house says.

Deliverable 1's second half (`plan/handoff-market-fit.md`; `PREREG.md` fixes every clause
below before the sample was read). For each shape: the `world declare` sequence that
expresses it in the house vocabulary, run in-process through `litharness.cli.main` against a
fresh store, `world check` and `world accept` around it, a second round where more than
eight grants need growth (§211), every declared owner's line rendered, and the outcome of
every feature by the table in `PREREG.md`. Writes `census.json` and prints the tables
`FINDINGS.md` carries. No model, no bar, no corpus text: every label is one of the shared
eighty or a class, and every id is minted here.

    uv run python research/quality-measurement/system-fit/census.py
"""

from __future__ import annotations

import argparse
import contextlib
import io
import itertools
import json
import os
import re
import tempfile
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

os.environ.setdefault("LITHARNESS_ENV", "test")

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application import export as export_module
from litharness.cli import main as cli_main
from litharness.domain import extraction, gamesystem, genre

HERE = Path(__file__).resolve().parent

#: The house's own line-width ceiling: the rung and eight grants (`gamesystem.MAX_ABILITIES`,
#: "the number of columns a status line can print"). A window wider than this is a box.
LINE_WIDTH = gamesystem.MAX_ABILITIES + 1
SYSTEM_MOVES = frozenset(
    {"gain", "deepen", "rise", "choose", "spend", "growth", "change_kind", "loss"}
)
ORDER = {"missing": 3, "refused": 2, "workaround": 1, "clean": 0}
LETTERS = "abcdefghijklmnopqrstuvwxyz"

#: What each gap is, in one sentence, for the ranked list. The tag is the key; the kind is
#: the outcome the clause in PREREG.md gives it.
GAP_TEXT: dict[str, tuple[str, str]] = {
    "mixed_columns": (
        "refused",
        "a plain column (a pool, a currency, a class) beside a system's grants on one line: "
        "accept leaves the system unfinished on purpose and no beat speaks it",
    ),
    "scale_ceiling": ("refused", "a grant held past 99: the drawn scale runs to 2..99"),
    "draw_count": ("refused", "fewer than five grants in a system"),
    "list_not_graph": ("refused", "grants with no prerequisite among them: a list, not a graph"),
    "no_depth": ("refused", "grants held or not, with no depth anywhere: no scale can be minted"),
    "fork_options": ("refused", "a choice screen with one way, or more than four"),
    "stock_priced": ("refused", "a column both handed out per rung and allocated by points"),
    "growth_floor": (
        "refused",
        "after growth the floor and the line disagree with the grown system: the snapshot "
        "lacks the new columns and the line prints ? for them",
    ),
    "second_system_line": ("refused", "two systems with a sheet each: the second never prints"),
    "snapshot_fault": (
        "refused",
        "a status line the arithmetic cannot read (§213.1): an id in a numeric column, or a "
        "held grant on the opening line with no edge behind it",
    ),
    "other_refusal": ("refused", "a refusal outside the clauses, kept in the house's words"),
    "member_rank": ("missing", "a list whose members carry a rank or rarity each"),
    "party_display": ("missing", "several subjects' sheets on one screen"),
    "notice_other": (
        "missing",
        "a notice for anything but a gain or a rise: a welcome, a warning, a quest, a title, "
        "a zone, the System speaking",
    ),
    "quest_display": ("missing", "a quest card: objective, progress, reward"),
    "other_screen": ("missing", "a menu, a map, a shop, an inventory screen"),
    "pool_refill": ("missing", "a pool's refill rule"),
    "derived_rule": ("missing", "a figure derived from other columns"),
    "exp_accrual": ("missing", "a rise by accumulation (experience to next level)"),
    "class_effect": ("missing", "a class, title or race that moves a number"),
    "direction_down": ("missing", "a number that improves by falling"),
    "box_view": ("workaround", "a window wider than nine fields, printed on one line"),
    "item_box": ("workaround", "an item's box, printed as a [STATUS] line nothing asks for"),
    "readout_on_request": (
        "workaround",
        "another subject's sheet where the protagonist reads it: declared, never asked for",
    ),
    "description_text": ("workaround", "a paragraph on a screen, carried as one line"),
    "percent_as_number": ("workaround", "a percentage as a number with the unit in the label"),
    "rate_as_two_columns": ("workaround", "a pool's regeneration as a second column"),
    "blank_hidden": ("workaround", "a field shown blank, standing at nothing and hidden"),
    "growth_two_rounds": (
        "workaround",
        "more than eight grants: eight at the seed, the rest after",
    ),
    "stock_source": ("workaround", "a point stock credited by something other than a rung"),
    "ladder_assumed": (
        "workaround",
        "a system with no ladder shown: a three-rung ladder declared for it",
    ),
    "opening_without_display": (
        "workaround",
        "no display in the sampled chapters; this house prints from chapter one",
    ),
}

REFUSAL_TAGS: tuple[tuple[str, str], ...] = (
    ("a fork offers", "fork_options"),
    ("a drawn system carries", "draw_count"),
    ("a list rather than a graph", "list_not_graph"),
    ("declares no depth", "no_depth"),
    ("a drawn scale runs to", "scale_ceiling"),
    ("left unfinished on purpose", "mixed_columns"),
    ("is handed out by the rungs and is priced", "stock_priced"),
    ("describing different books", "growth_floor"),
    ("canon status_sheet records", "second_system_line"),
    ("takes a whole number", "snapshot_fault"),
    ("is also a can_do edge", "snapshot_fault"),
    ("no can_do", "snapshot_fault"),
)

#: The complaints `records_for` joins with `; ` each begin with an id or one of these words.
_REASON_SPLIT = re.compile(
    r";\s+(?=(?:[a-z_]+ (?:is|needs|opens|declares|says)|the (?:fork|ability|way|option|"
    r"prerequisites|rung|system|scale)|this system|no ability|two |an ability)\b)"
)


@dataclass
class Feature:
    name: str
    outcome: str
    gap: str | None = None
    said: str | None = None


@dataclass
class Book:
    """One shape's declarations, as rounds of argv lists, and what the store said to them."""

    rounds: list[list[list[str]]] = field(default_factory=lambda: [[]])
    warnings: list[str] = field(default_factory=list)
    accepts: list[str] = field(default_factory=list)
    checks: list[dict[str, Any]] = field(default_factory=list)
    subjects: list[str] = field(default_factory=list)

    def declare(
        self,
        subject: str,
        predicate: str,
        value: object = None,
        obj: str | None = None,
        key: str | None = None,
    ) -> None:
        args = ["world", "declare", subject, predicate]
        if value is not None:
            args += ["--value", value if isinstance(value, str) else json.dumps(value)]
        if obj is not None:
            args += ["--object", obj]
        if key is not None:
            args += ["--order-key", key]
        self.rounds[-1].append(args)

    def new_round(self) -> None:
        self.rounds.append([])


def _run(db: Path, args: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli_main(["--database", str(db), *args])
    return code, out.getvalue(), err.getvalue()


def run_book(book: Book, db: Path) -> dict[str, Any]:
    _run(db, ["init"])
    _run(
        db,
        [
            "new",
            "Census probe",
            "--premise",
            "A shape from the market's furniture.",
            "--scenes",
            "6",
        ],
    )
    for declarations in book.rounds:
        for args in declarations:
            _code, _out, err = _run(db, args)
            for line in err.splitlines():
                if "will not resolve" in line:
                    book.warnings.append(line.strip())
        _code, out, err = _run(db, ["world", "accept"])
        # A refusal prints to stderr (§200, §213.1) and is kept beside the acceptance.
        book.accepts.append((out.strip() + chr(10) + err.strip()).strip())
        _code, out, _err = _run(db, ["world", "check"])
        book.checks.append(json.loads(out))
    store = SqliteStore.open(str(db))
    try:
        book_id, branch_id = export_module.resolve_branch(store, None, None)
        records = store.state_records(book_id, branch_id)
    finally:
        store.close()
    rendered: dict[str, str] = {}
    for record in records:
        if record.predicate == "status_snapshot" and record.subject in book.subjects:
            rendered[record.subject] = extraction.render_status_line(
                record.subject, record.value, records=records
            )
    return {
        "rendered": rendered,
        "floor": {
            "has_starting_sheet": genre.has_starting_sheet(records),
            "system_gap": genre.system_gap(records),
            "standing_example": extraction.standing_example(records),
        },
    }


# --------------------------------------------------------------------------- the translator


def slug(text: str) -> str:
    out = re.sub(r"[^a-z0-9]+", "_", text.strip().lower()).strip("_")
    if not out or out[0].isdigit():
        out = f"c_{out}"
    return out


def printable(text: str) -> str:
    """A label the house prints: title case, letters, no digit, at most 24 characters."""
    words = re.sub(r"\d+", "", text).split()
    label = " ".join(word.capitalize() for word in words) or "Field"
    return label[:24].strip()


class Namer:
    """Ids and labels for one owner's columns; a label used twice gets a letter, and an id
    another namer already minted (a grant's) is skipped rather than reused."""

    def __init__(self, taken: set[str] | None = None) -> None:
        self.seen: Counter[str] = Counter()
        self.taken = taken or set()

    def __call__(self, label: str) -> tuple[str, str]:
        base = slug(label)
        while True:
            n = self.seen[base]
            self.seen[base] += 1
            if n == 0:
                candidate, printed = base, printable(label)
            else:
                suffix = (
                    LETTERS[n - 1]
                    if n <= 26
                    else f"{LETTERS[(n - 1) // 26]}{LETTERS[(n - 1) % 26]}"
                )
                candidate, printed = f"{base}_{suffix}", printable(f"{label} {suffix.upper()}")
            if candidate not in self.taken:
                return candidate, printed


OWNER_SUBJECTS = {
    "protagonist": ("hero", "cast"),
    "person": ("ally", "cast"),
    "creature": ("beast", "creature"),
    "place": ("site", "place"),
    "item": ("relic", "carrier"),
    "institution": ("guild", "institution"),
    "party": ("party_member", "cast"),
}


class Translator:
    """One shape into one `Book`, with the features the translation decides on its own."""

    def __init__(self, shape: dict[str, Any]) -> None:
        self.shape = shape
        self.book = Book()
        self.features: list[Feature] = []
        self.ladders: dict[str, tuple[str, list[str]]] = {}
        self.grant_ids: list[str] = []
        self.system_id: str | None = None
        self.system_needed = False
        self.two_rounds = False
        self.fork_pending = False
        self.moves = set(shape.get("moves") or [])
        self.displays = set(shape.get("displays") or [])

    # --- pieces

    def feature(
        self, name: str, outcome: str, gap: str | None = None, said: str | None = None
    ) -> None:
        self.features.append(Feature(name, outcome, gap, said))

    def ladder(self, label: str, *, governed_by: str | None = None) -> tuple[str, list[str]]:
        key = slug(label)
        if key in self.ladders:
            return self.ladders[key]
        crit = f"{key}_ladder"
        names = ("First", "Second", "Third")
        # A rung's name normalises back to its id, so `display_name` prints the name and
        # not the id (the guard in `extraction.display_name`).
        rungs = [slug(f"{label} {name}") for name in names]
        self.book.declare(crit, "type", "criterion")
        self.book.declare(crit, "comparator", "ordinal")
        self.book.declare(crit, "is_a", printable(label))
        for lower, higher in itertools.pairwise(rungs):
            self.book.declare(lower, "precedes", value=crit, obj=higher)
        for rung, name in zip(rungs, names, strict=True):
            self.book.declare(rung, "is_a", printable(f"{label} {name}"))
        if governed_by:
            self.book.declare(crit, "governed_by", obj=governed_by)
        self.ladders[key] = (crit, rungs)
        return crit, rungs

    def capability(self, entity_id: str, label: str, *, governed: bool) -> None:
        self.book.declare(entity_id, "entity_role", "capability")
        self.book.declare(entity_id, "is_a", label)
        if governed and self.system_id:
            self.book.declare(entity_id, "governed_by", obj=self.system_id)

    def declare_grant(self, grant_id: str, label: str, spec: dict[str, Any]) -> None:
        """One grant of the system, with its stock, its price and how far the hero holds it."""
        self.capability(grant_id, label, governed=True)
        self.grant_ids.append(grant_id)
        if spec.get("stock"):
            self.book.declare(grant_id, "per_rung", "1")
        elif spec.get("moves") in ("per_rung", "both"):
            self.book.declare(grant_id, "per_rung", "1")
            if spec["moves"] == "both":
                self.book.declare(grant_id, "costs", "1", obj="points")
                self.feature(
                    f"a column both per rung and allocated ({label})", "refused", "stock_priced"
                )
            else:
                self.feature(f"a column the rungs hand out ({label})", "clean")
        elif spec.get("moves") == "allocate":
            self.book.declare(grant_id, "costs", "1", obj="points")
        if spec["depth"] > 0 and not spec.get("stock"):
            self.book.declare("hero", "can_do", str(spec["depth"]), obj=grant_id)

    # --- the translation

    def translate(self) -> Book:
        shape = self.shape
        sheets = shape.get("sheets") or []
        grants = shape.get("grants")
        fork = shape.get("fork")
        moving_fields = [
            f
            for sheet in sheets
            if sheet["owner"] == "protagonist"
            for f in sheet["fields"]
            if f.get("moves")
        ]
        self.system_needed = bool(fork) or (
            grants is not None and (bool(self.moves & SYSTEM_MOVES) or bool(moving_fields))
        )
        if not sheets and not self.displays and not shape.get("ladder"):
            self.feature("no display seen", "workaround", "opening_without_display")

        # The protagonist: every shape has one, since the sheet, the ladder and the system
        # all need somebody to stand in them.
        self.book.declare("hero", "entity_role", "cast")
        self.book.declare("hero", "entity_role", "protagonist")
        self.book.declare("hero", "is_a", "Hero")

        ladder = shape.get("ladder")
        main_ladder: tuple[str, list[str]] | None = None
        if self.system_needed:
            self.system_id = "the_system"
            self.book.declare(self.system_id, "entity_role", "system")
            self.book.declare(self.system_id, "is_a", "The System")
        if ladder:
            main_ladder = self.ladder(ladder["label"], governed_by=self.system_id)
            self.feature("a ladder", "clean")
            if ladder.get("direction") == "down":
                self.feature("a number that improves by falling", "missing", "direction_down")
        elif self.system_needed or "notice_rise" in self.displays:
            main_ladder = self.ladder("level", governed_by=self.system_id)
            self.feature("a ladder the furniture never shows", "workaround", "ladder_assumed")
        if main_ladder:
            crit, rungs = main_ladder
            self.book.declare("hero", "stands_at", value=crit, obj=rungs[0])

        plain_columns: list[dict[str, Any]] = []
        snapshot: dict[str, Any] = {}
        system_columns: list[dict[str, Any]] = []
        grown: list[tuple[str, str, dict[str, Any]]] = []

        if self.system_needed:
            system_columns, snapshot, grown = self.system(grants, moving_fields, fork)

        # The sheets. The protagonist's is built once, with the system's columns first
        # where there is a system and the plain columns the window also prints after them.
        for sheet in sheets:
            owner = sheet["owner"]
            if owner == "protagonist":
                columns, values = self.columns(
                    sheet["fields"],
                    skip_moving=self.system_needed,
                    taken=set(self.grant_ids) | ({"rank"} if self.system_needed else set()),
                )
                plain_columns.extend(columns)
                snapshot.update(values)
            else:
                self.owner_sheet(sheet)
        if "readout_other" in self.displays:
            if not any(s["owner"] == "creature" for s in sheets):
                self.owner_sheet(
                    {
                        "owner": "creature",
                        "fields": [{"label": "level", "kind": "number", "max": 24}],
                    }
                )
            self.feature("a readout of another's sheet", "workaround", "readout_on_request")

        fields: list[dict[str, Any]] = []
        if self.system_needed:
            fields.append(
                {"name": "rank", "label": printable((ladder or {}).get("label", "level"))}
            )
            snapshot.setdefault("rank", 1)
        fields.extend(system_columns)
        fields.extend(plain_columns)
        if fields:
            declaration: dict[str, Any] = {"fields": fields, "show_unheld": False}
            if self.system_needed and not plain_columns:
                declaration["system"] = self.system_id
            # Until §219 the translator tagged a plain column beside a system's grants as
            # refused from its own clause, since the store refused every such shape on an
            # earlier clause first (FINDINGS); since §219 the store accepts it, so the store
            # answers and the clause tags nothing. `census.json` is §217's record and keeps
            # the clause's count.
            self.book.declare("hero", "status_sheet", declaration)
            self.book.declare("hero", "status_snapshot", snapshot)
            self.book.subjects.append("hero")
            self.feature("a window as the status line", "clean")
            widest = int(shape.get("widest_window") or 0)
            if widest > LINE_WIDTH:
                self.feature(f"a window of {widest} fields on one line", "workaround", "box_view")

        # The graph line, for the notices the house prints.
        edges = []
        if "notice_rise" in self.displays:
            edges.append({"predicate": "stands_at", "phrase": "has reached"})
            self.feature("a notice on a rise", "clean")
        if "notice_gain" in self.displays:
            edges.append({"predicate": "can_do", "phrase": "has learned"})
            self.feature("a notice on a gain", "clean")
        if edges:
            holder = self.system_id or (main_ladder[0] if main_ladder else "hero")
            self.book.declare(holder, "graph_line", {"label": "SYSTEM", "edges": edges})

        for display, tag in (
            ("notice_other", "notice_other"),
            ("quest", "quest_display"),
            ("other_screen", "other_screen"),
            ("party_display", "party_display"),
        ):
            if display in self.displays:
                self.feature(f"a display: {display}", "missing", tag)
        if "description_text" in self.displays:
            target = self.grant_ids[0] if self.grant_ids else "hero"
            self.book.declare(target, "manifests_as", "a paragraph the screen shows, as one line")
            self.feature("a paragraph on a screen", "workaround", "description_text")
        rules = ("exp_accrual", "class_effect", "direction_down", "pool_refill", "derived_rule")
        for rule in shape.get("rules") or []:
            if rule in rules and not any(
                f.gap == rule and f.outcome == "missing" for f in self.features
            ):
                self.feature(f"a rule: {rule}", "missing", rule)

        # Growth: the grants past eight are declared after the first accept (§211).
        if grown:
            self.book.new_round()
            for grant_id, label, spec in grown:
                self.declare_grant(grant_id, label, spec)
            self.feature("more than eight grants", "workaround", "growth_two_rounds")
            self.two_rounds = True
            if fork and self.fork_pending:
                self.fork_declare(fork)
        return self.book

    def columns(
        self, fields: list[dict[str, Any]], *, skip_moving: bool, taken: set[str] | None = None
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        namer = Namer(taken)
        columns: list[dict[str, Any]] = []
        values: dict[str, Any] = {}
        for f in fields:
            if skip_moving and f.get("moves"):
                continue
            if f.get("stock") and self.system_needed:
                continue
            kind = f["kind"]
            key, label = namer(f["label"])
            top = int(f.get("max") or 1)
            if kind == "number":
                columns.append({"name": key, "label": label})
                values[key] = top
                self.feature(f"a number column ({f['label']})", "clean")
            elif kind == "paired":
                columns.append({"name": key, "label": label, "paired": True})
                values[key] = top
                values[f"{key}_max"] = top
                self.feature(f"a paired column ({f['label']})", "clean")
            elif kind == "percent":
                columns.append({"name": key, "label": f"{label} %"})
                values[key] = top
                self.feature(f"a percentage ({f['label']})", "workaround", "percent_as_number")
            elif kind == "rate":
                columns.append({"name": key, "label": label})
                columns.append({"name": f"{key}_regen", "label": f"{label} Regen"})
                values[key] = top
                values[f"{key}_regen"] = 1
                self.feature(
                    f"a pool with a rate ({f['label']})", "workaround", "rate_as_two_columns"
                )
                if not any(x.gap == "pool_refill" for x in self.features):
                    self.feature("a pool's refill rule", "missing", "pool_refill")
            elif kind == "ordinal":
                crit, rungs = self.ladder(f["label"])
                if not self.shape.get("ladder") or slug(self.shape["ladder"]["label"]) != slug(
                    f["label"]
                ):
                    self.book.declare("hero", "stands_at", value=crit, obj=rungs[0])
                columns.append({"name": key, "label": label, "kind": "ordinal"})
                values[key] = rungs[0]
                self.feature(f"an ordinal column ({f['label']})", "clean")
            elif kind == "name":
                entity = f"{key}_value"
                self.book.declare(entity, "is_a", f"{label} Value")
                columns.append({"name": key, "label": label, "kind": "name"})
                values[key] = entity
                self.feature(f"a name column ({f['label']})", "clean")
            elif kind == "text":
                columns.append({"name": key, "label": label, "kind": "text"})
                values[key] = "as written"
                self.feature(f"a text column ({f['label']})", "clean")
            elif kind in ("set", "set_depth", "set_rank"):
                members = self.members(f)
                columns.append({"name": key, "label": label, "kind": "set"})
                values[key] = [[m, 2] if kind == "set_depth" else [m] for m in members]
                if kind == "set_rank":
                    self.feature(
                        f"a list with a rank per member ({f['label']})", "missing", "member_rank"
                    )
                else:
                    self.feature(f"a list column ({f['label']})", "clean")
            elif kind == "blank":
                columns.append({"name": key, "label": label})
                values[key] = 0
                self.feature(f"a blank field ({f['label']})", "workaround", "blank_hidden")
            elif kind == "derived":
                columns.append({"name": key, "label": label})
                values[key] = top
                self.feature(f"a derived figure ({f['label']})", "workaround", "derived_rule")
                if not any(
                    x.gap == "derived_rule" and x.outcome == "missing" for x in self.features
                ):
                    self.feature("a derivation rule", "missing", "derived_rule")
            elif kind == "change":
                columns.append({"name": key, "label": label})
                values[key] = top
                self.feature(f"a change written with an arrow ({f['label']})", "clean")
            else:
                raise ValueError(f"unknown kind {kind!r} in {self.shape['story']}")
        return columns, values

    def members(self, f: dict[str, Any]) -> list[str]:
        if self.grant_ids:
            return self.grant_ids[: max(1, min(len(self.grant_ids), int(f.get("count") or 3)))]
        count = max(1, int(f.get("count") or 2))
        ids = []
        for i in range(count):
            member = f"member_{LETTERS[i % 26]}{'' if i < 26 else i // 26}"
            self.capability(member, f"Member {LETTERS[i % 26].upper()}", governed=False)
            ids.append(member)
        return ids

    def owner_sheet(self, sheet: dict[str, Any]) -> None:
        owner = sheet["owner"]
        subject, role = OWNER_SUBJECTS[owner]
        n = sum(1 for s in self.book.subjects if s == subject or s.startswith(f"{subject}_"))
        if n:
            subject = f"{subject}_{LETTERS[n]}"
        self.book.declare(subject, "entity_role", role)
        self.book.declare(subject, "is_a", printable(subject.replace("_", " ")))
        columns, values = self.columns(sheet["fields"], skip_moving=False)
        if not columns:
            return
        self.book.declare(
            subject, "status_sheet", {"fields": columns, "show_unheld": False, "owner": subject}
        )
        self.book.declare(subject, "status_snapshot", values)
        self.book.subjects.append(subject)
        if owner == "item":
            self.feature("an item's box", "workaround", "item_box")
        elif owner == "party":
            self.feature("a party member's sheet", "clean")
        else:
            self.feature(f"an owner's sheet ({owner})", "clean")

    def system(
        self,
        grants: dict[str, Any] | None,
        moving: list[dict[str, Any]],
        fork: dict[str, Any] | None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any], list[tuple[str, str, dict[str, Any]]]]:
        """The grants, in the order the seed takes them: the stock, the attributes that move,
        the skills, then a fork's way grants. Returns the sheet columns, the snapshot values
        and the grants left for a second round."""
        assert self.system_id
        stock = self.shape.get("stock") or {}
        planned: list[tuple[str, str, dict[str, Any]]] = []
        allocate = any(f.get("moves") in ("allocate", "both") for f in moving)
        if allocate:
            planned.append(("points", "Free Points", {"depth": 0, "stock": True}))
            self.feature("points allocated into attributes", "clean")
            if stock.get("source") == "other":
                self.feature(
                    "a point stock credited by something other than a rung",
                    "workaround",
                    "stock_source",
                )
        namer = Namer({"points", "rank"})
        for f in moving:
            key, label = namer(f["label"])
            planned.append((key, label, {"depth": int(f.get("max") or 1), "moves": f["moves"]}))
        count = int((grants or {}).get("count") or 0)
        depth = int((grants or {}).get("max_depth") or 1)
        for i in range(count):
            suffix = f"{LETTERS[i % 26]}{'' if i < 26 else i // 26}"
            planned.append(
                (f"skill_{suffix}", f"Skill {suffix.upper()}", {"depth": depth if i == 0 else 1})
            )
        if "change_kind" in self.moves and count < 2:
            planned.append(("skill_evolved", "Skill Evolved", {"depth": 0}))
        way_grants: list[tuple[str, str, dict[str, Any]]] = []
        if fork:
            for i in range(int(fork.get("options") or 2)):
                way_grants.append(
                    (
                        f"way_grant_{LETTERS[i % 26]}",
                        f"Way Grant {LETTERS[i % 26].upper()}",
                        {"depth": 0},
                    )
                )
        everything = planned + way_grants
        if "growth" in self.moves and len(everything) <= gamesystem.MAX_ABILITIES:
            everything.append(("skill_grown", "Skill Grown", {"depth": 0}))
        first = everything[: gamesystem.MAX_ABILITIES]
        rest = everything[gamesystem.MAX_ABILITIES :]
        self.fork_pending = bool(fork) and any(p in rest for p in way_grants)

        columns: list[dict[str, Any]] = []
        snapshot: dict[str, Any] = {}
        for grant_id, label, spec in first:
            self.declare_grant(grant_id, label, spec)
            columns.append({"name": grant_id, "label": label})
            snapshot[grant_id] = spec["depth"]
        skills = [g for g in self.grant_ids if g.startswith("skill_")]
        if (grants or {}).get("prerequisites") and len(skills) >= 2:
            self.book.declare(skills[1], "requires", value="1", obj=skills[0])
            self.feature("a prerequisite between grants", "clean")
        for move in sorted(self.moves & SYSTEM_MOVES):
            if move in ("gain", "deepen", "rise", "spend", "choose", "growth"):
                self.feature(f"a move: {move}", "clean")
        if "change_kind" in self.moves:
            old = skills[0] if skills else self.grant_ids[0]
            new = skills[1] if len(skills) >= 2 else "skill_evolved"
            if new not in self.grant_ids:
                new = self.grant_ids[-1]
            self.book.declare("shift", "type", "change", key="0300")
            self.book.declare("shift", "participant", obj="hero")
            self.book.declare("shift", "effect", "0", obj=old)
            self.book.declare("shift", "effect", "1", obj=new)
            self.feature("a change of kind", "clean")
        if "loss" in self.moves:
            self.book.declare("drain", "type", "change", key="0400")
            self.book.declare("drain", "participant", obj="hero")
            self.book.declare("drain", "effect", "0", obj=self.grant_ids[0])
            self.feature("a loss", "clean")
        if fork and not self.fork_pending:
            self.fork_declare(fork)
        self.feature(f"a system of {len(everything)} grants", "clean")
        if len(everything) < gamesystem.MIN_ABILITIES:
            self.feature(
                f"a system of {len(everything)} grants, below the draw's floor",
                "refused",
                "draw_count",
            )
        return columns, snapshot, rest

    def fork_declare(self, fork: dict[str, Any]) -> None:
        assert self.system_id
        options = int(fork.get("options") or 2)
        rungs = next(iter(self.ladders.values()))[1]
        self.book.declare("path", "governed_by", obj=self.system_id)
        self.book.declare("path", "is_a", "Path")
        self.book.declare("path", "requires", obj=rungs[1])
        for i in range(options):
            way = f"way_{LETTERS[i % 26]}"
            self.book.declare("path", "offers", obj=way)
            self.book.declare(way, "is_a", f"Way {LETTERS[i % 26].upper()}")
            self.book.declare(way, "grants", obj=f"way_grant_{LETTERS[i % 26]}")
            if fork.get("text"):
                self.book.declare(way, "manifests_as", "a mark that shows on the hand")
            if fork.get("conditional") and i == 0 and self.grant_ids:
                self.book.declare(way, "requires", value="1", obj=self.grant_ids[0])
        outcome = (
            "clean" if gamesystem.MIN_OPTIONS <= options <= gamesystem.MAX_OPTIONS else "refused"
        )
        self.feature(
            f"a choice screen of {options} ways",
            outcome,
            None if outcome == "clean" else "fork_options",
        )


# --------------------------------------------------------------------------- the reading


def tag_for(sentence: str) -> str:
    for needle, tag in REFUSAL_TAGS:
        if needle in sentence:
            return tag
    return "other_refusal"


def reasons_in(accept: str) -> list[str]:
    if "not finished:" not in accept:
        return []
    reason = accept.split("not finished:", 1)[1].strip()
    return [part.strip() for part in _REASON_SPLIT.split(reason) if part.strip()]


def read_store(translator: Translator, book: Book) -> list[Feature]:
    """What the store said, attached to the features the clauses name.

    The first round's completion sentence is read whole. The second round's is read only
    when the first minted the system, since a seed the store refused makes every later
    sentence about the same refusal; the final `check` is read for the growth clause and
    for anything that moved `ok`.
    """
    found: list[Feature] = []
    seen: set[str] = set()
    minted_first = bool(book.accepts) and "minted to finish" in book.accepts[0]
    rounds = book.accepts[:1] + (book.accepts[1:] if minted_first else [])
    for accept in rounds:
        if "not accepted" in accept:
            for line in accept.splitlines():
                if line.startswith("litharness:") and "not accepted" not in line:
                    sentence = line.removeprefix("litharness:").strip()
                    found.append(
                        Feature("the world, at accept", "refused", tag_for(sentence), sentence)
                    )
        for part in reasons_in(accept):
            tag = tag_for(part)
            key = tag if tag != "other_refusal" else re.sub(r"^\S+", "", part)[:60]
            if key in seen:
                continue
            seen.add(key)
            found.append(Feature("the system, at accept", "refused", tag, part))
    final = book.checks[-1] if book.checks else {}
    for gap in final.get("gaps", []):
        if "describing different books" in gap and translator.two_rounds and minted_first:
            found.append(
                Feature("the grown system against the floor", "refused", "growth_floor", gap)
            )
        elif "canon status_sheet records" in gap:
            found.append(Feature("two book sheets", "refused", "second_system_line", gap))
    for complaint in final.get("complaints", []) + final.get("would_breach", []):
        found.append(
            Feature("a complaint the check makes", "refused", tag_for(complaint), complaint)
        )
    # The translator's own refused clauses take the store's sentence where the store said
    # it, and say so where an earlier refusal masked it.
    said_by_tag = {f.gap: f.said for f in found if f.said}
    for feature in translator.features:
        if feature.outcome == "refused" and feature.said is None:
            feature.said = said_by_tag.get(feature.gap) or (
                "masked: the store refused the system on an earlier clause, see the accept sentence"
            )
    return found


def worst(features: list[Feature]) -> str:
    return max((f.outcome for f in features), key=lambda o: ORDER[o], default="clean")


def census(shapes: list[dict[str, Any]], workdir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, shape in enumerate(shapes):
        translator = Translator(shape)
        book = translator.translate()
        db = workdir / f"shape_{index:03d}.db"
        seen = run_book(book, db)
        found = read_store(translator, book)
        features = translator.features + found
        refused_tags = {f.gap for f in found}
        # A fork the store refused is not also a clean fork; a store refusal the translator
        # already tagged from its own clause is not counted twice.
        if "fork_options" in refused_tags:
            features = [
                f
                for f in features
                if not (f.name.startswith("a choice screen") and f.outcome == "clean")
            ]
        own = {f.gap for f in translator.features if f.outcome == "refused"}
        features = [
            f for f in features if not (f in found and f.gap in own and f.gap != "other_refusal")
        ]
        rows.append(
            {
                "story": shape["story"],
                "source": shape["source"],
                "outcome": worst(features),
                "tags": sorted({f.gap for f in features if f.gap}),
                "features": [asdict(f) for f in features],
                "declarations": book.rounds,
                "warnings": book.warnings,
                "accept": book.accepts,
                "check": {
                    key: book.checks[-1].get(key)
                    for key in (
                        "ok",
                        "complaints",
                        "gaps",
                        "would_not_finish",
                        "grown",
                        "would_breach",
                        "snapshot_faults",
                    )
                }
                if book.checks
                else {},
                "rendered": seen["rendered"],
                "floor": seen["floor"],
                "widest_window": shape.get("widest_window"),
                "note": shape.get("note", ""),
            }
        )
        print(
            f"  {shape['story']:22} {rows[-1]['outcome']:10} {', '.join(rows[-1]['tags'])}",
            flush=True,
        )
    return rows


#: How much of one of *our own* sentences this record keeps. The house's refusals run long —
#: `genre.system_gap`'s unfinished-system complaint is 133 words and every blocked shape
#: records it — and `corpus_leak_audit.py` fails a committed string of 120 words or more,
#: because a length rule is the only rule that catches an excerpt of somebody else's novel
#: before it is public. Sixty-four of these landed in this record and thirty-five tripped
#: that rule, on two distinct sentences repeated per shape.
#:
#: **The repair is here rather than in the audit** (2026-09-03, correcting §217's artifact).
#: The audit's exemption set is pinned exactly by `tests/test_corpus_leak_audit.py`, whose
#: first line calls an exemption in a leak audit a dangerous thing to add; a path exemption
#: would also let a future census that recorded a market chapter's line pass unseen. What the
#: census needs from a refusal is which refusal it was, so the record keeps the sentence that
#: names it and the code keeps the rest.
SHORT_WORDS = 40


def shorten(text: str) -> str:
    """One of our sentences, cut to its first clause where that identifies it."""
    words = text.split()
    if len(words) <= SHORT_WORDS:
        return text
    head = text.split(". ")[0]
    if head and len(head.split()) <= SHORT_WORDS:
        return f"{head}. …"
    return " ".join(words[:SHORT_WORDS]) + " …"


def shortened(value: Any) -> Any:
    """`shorten` over every string in a payload, leaving its shape alone."""
    if isinstance(value, str):
        return shorten(value)
    if isinstance(value, list):
        return [shortened(item) for item in value]
    if isinstance(value, dict):
        return {key: shortened(item) for key, item in value.items()}
    return value


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    market = [r for r in rows if r["source"] == "royalroad"]
    shelf = [r for r in rows if r["source"] == "shelf"]
    outcomes = {
        group: dict(Counter(r["outcome"] for r in items))
        for group, items in (("market", market), ("shelf", shelf))
    }
    gaps: list[dict[str, Any]] = []
    for tag, (kind, text) in GAP_TEXT.items():
        n = sum(1 for r in market if tag in r["tags"])
        s = sum(1 for r in shelf if tag in r["tags"])
        if n or s:
            gaps.append(
                {
                    "tag": tag,
                    "kind": kind,
                    "market": n,
                    "share": round(n / len(market), 3) if market else None,
                    "shelf": s,
                    "what": text,
                }
            )
    gaps.sort(key=lambda g: (-g["market"], -g["shelf"], g["tag"]))
    widths = [int(r.get("widest_window") or 0) for r in market]
    width_bands = {
        "<=4": sum(1 for w in widths if w <= 4),
        "5-9": sum(1 for w in widths if 5 <= w <= 9),
        "10-14": sum(1 for w in widths if 10 <= w <= 14),
        ">=15": sum(1 for w in widths if w >= 15),
    }
    return {
        "market_shapes": len(market),
        "shelf_shapes": len(shelf),
        "outcomes": outcomes,
        "share_clean_market": round(outcomes["market"].get("clean", 0) / len(market), 3)
        if market
        else None,
        "widest_window_bands": width_bands,
        "share_wider_than_line": round(sum(1 for w in widths if w > LINE_WIDTH) / len(market), 3)
        if market
        else None,
        "gaps": gaps,
    }


def tables(summary: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    out: list[str] = []
    out.append("| group | shapes | clean | workaround | refused | not expressible |")
    out.append("| --- | --- | --- | --- | --- | --- |")
    for group in ("market", "shelf"):
        o = summary["outcomes"][group]
        n = summary[f"{group}_shapes"]
        cells = [
            group,
            n,
            o.get("clean", 0),
            o.get("workaround", 0),
            o.get("refused", 0),
            o.get("missing", 0),
        ]
        out.append("| " + " | ".join(str(cell) for cell in cells) + " |")
    out.append("")
    out.append("| rank | gap | kind | market shapes | share | shelf | what is missing |")
    out.append("| --- | --- | --- | --- | --- | --- | --- |")
    for i, gap in enumerate(summary["gaps"], start=1):
        cells = [
            i,
            f"`{gap['tag']}`",
            gap["kind"],
            gap["market"],
            gap["share"],
            gap["shelf"],
            gap["what"],
        ]
        out.append("| " + " | ".join(str(cell) for cell in cells) + " |")
    out.append("")
    out.append("| shape | outcome | gaps |")
    out.append("| --- | --- | --- |")
    for r in rows:
        tags = ", ".join(f"`{t}`" for t in r["tags"]) or "—"
        out.append(f"| {r['story']} | {r['outcome']} | {tags} |")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--shapes", type=Path, default=HERE / "shapes.jsonl")
    parser.add_argument("--out", type=Path, default=HERE / "census.json")
    parser.add_argument("--only", help="one story id, for a dry run")
    args = parser.parse_args(argv)
    shapes = [
        json.loads(line)
        for line in args.shapes.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if args.only:
        shapes = [s for s in shapes if s["story"] == args.only]
    with tempfile.TemporaryDirectory(prefix="system-fit-") as tmp:
        rows = census(shapes, Path(tmp))
    summary = summarise(rows)
    payload = {
        "registered": sha256((HERE / "PREREG.md").read_bytes()).hexdigest(),
        "run_at": datetime.now(tz=UTC).isoformat(),
        "line_width": LINE_WIDTH,
        "summary": summary,
        "shapes": rows,
    }
    args.out.write_text(
        json.dumps(shortened(payload), indent=2, ensure_ascii=False),
        encoding="utf-8",
        newline="\n",
    )
    print()
    print(tables(summary, rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
