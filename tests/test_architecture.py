"""Executable boundaries for the package: its dependencies, and its prose.

The project has a useful inward dependency direction today, but a diagram cannot stop a
convenient import from reversing it. These tests keep the domain independent, keep provider
and adapter implementations from coupling to each other, and reject internal import cycles.

**And they check the docstrings, because in this repo the docstrings are load-bearing.** The
comments here carry the reasons, the refuted alternatives and their measurements, and readers
— human and otherwise — act on them. Nothing type-checked a word of that, and the record says
what happens: `jobs.priority` was documented as inert in four places for two stages after it
stopped being, and a claim that a list of uncalled promises was empty survived exactly one
commit. Prose decays like code and had none of code's guards.

These are the cheapest approximations of a type-check for it — a symbol the prose names in
backticks should be findable, and a test it cites as evidence should exist — and they are the
two failures that actually happened.
"""

from __future__ import annotations

import ast
import enum
import re
from pathlib import Path

import litharness_contracts as lc
import pytest

PACKAGE_ROOT = Path(__file__).parents[1] / "src" / "litharness"
REPO_ROOT = Path(__file__).parents[1]

#: The one page that says where each fact lives, which function reads it, and which test
#: pins it (`docs/system-model.md`). It names symbols and tests in backticks exactly as the
#: docstrings do, so it decays exactly as they do, and the two prose checks below read it
#: beside the package: a map that names a function nobody has any more is worse than none.
SYSTEM_MODEL = REPO_ROOT / "docs" / "system-model.md"

#: The inward direction, and `application` is the row that carries the argument.
#:
#: It reaches persistence through `application/ports.py` and never imports `adapters`, and it
#: now reaches generation the same way. **The half-inverted state is the one this rule
#: replaced**: `application` held a concrete `ProviderRegistry` import in three modules while
#: `conductor.HealthResettable` typed the very same object structurally, with a docstring
#: saying it keeps the dependency "at the handler layer instead of the loop". So the direction
#: was already decided and enforced in one place out of four, which is the worst of both — a
#: reader could not tell whether the concrete import was a decision or an oversight.
#:
#: Dropping `providers` here is what makes `TextGenerator` load-bearing rather than decorative.
#: `cli` is the composition root and still binds the concrete registry, which is the one place
#: that should.
ALLOWED_DEPENDENCIES = {
    "domain": frozenset({"domain"}),
    "providers": frozenset({"domain", "providers"}),
    "adapters": frozenset({"domain", "adapters"}),
    "application": frozenset({"domain", "application"}),
    "entrypoint": frozenset(
        {"domain", "providers", "adapters", "application", "entrypoint"}
    ),
}


def _module_name(path: Path) -> str:
    parts = list(path.relative_to(PACKAGE_ROOT.parent).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _modules() -> dict[str, Path]:
    return {_module_name(path): path for path in PACKAGE_ROOT.rglob("*.py")}


def _layer(module: str) -> str | None:
    parts = module.split(".")
    if len(parts) < 2:
        return None
    if parts[1] in {"cli", "__main__"}:
        return "entrypoint"
    return parts[1] if parts[1] in ALLOWED_DEPENDENCIES else None


def _imports(path: Path, known_modules: set[str]) -> list[tuple[str, int]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(
                (alias.name, node.lineno)
                for alias in node.names
                if alias.name.startswith("litharness")
            )
        elif isinstance(node, ast.ImportFrom) and node.module:
            if not node.module.startswith("litharness"):
                continue
            # ``from litharness.domain import state`` names a module through its alias,
            # while ``from litharness.domain.state import State`` names a symbol. Prefer
            # the former only when it is a module that actually exists.
            candidates = [f"{node.module}.{alias.name}" for alias in node.names]
            imported_modules = [name for name in candidates if name in known_modules]
            found.extend(
                (name, node.lineno)
                for name in (imported_modules or [node.module])
            )
    return found


#: The seams `domain/extraction.py` was split along (stage-0 §215), as the arrows that may not
#: point back. `extraction` re-exports every name the four modules below it define, so any of
#: them importing `extraction` closes a cycle the moment it lands; `sheet` reads only `names`;
#: `graphline` reads the sheet's refusal class and nothing above it; `moves` reads all three;
#: and `gamesystem` sits under all five, for the reason
#: `tests/test_gamesystem.py::test_the_module_hands_out_columns_rather_than_sheet_fields` gives.
EXTRACTION_SEAMS: dict[str, frozenset[str]] = {
    "names": frozenset({"sheet", "graphline", "moves", "extraction", "gamesystem"}),
    "sheet": frozenset({"graphline", "moves", "extraction"}),
    "graphline": frozenset({"moves", "extraction"}),
    "moves": frozenset({"extraction"}),
    "gamesystem": frozenset({"names", "sheet", "graphline", "moves", "extraction"}),
}


def test_dependencies_only_point_outward_to_inward() -> None:
    modules = _modules()
    violations: list[str] = []
    for source, path in sorted(modules.items()):
        source_layer = _layer(source)
        if source_layer is None:
            continue
        allowed = ALLOWED_DEPENDENCIES[source_layer]
        for target, line in _imports(path, set(modules)):
            target_layer = _layer(target)
            if target_layer is not None and target_layer not in allowed:
                violations.append(
                    f"{source}:{line} ({source_layer}) imports {target} ({target_layer})"
                )
    assert not violations, "dependency boundary violations:\n" + "\n".join(violations)


def test_the_extraction_seams_point_one_way() -> None:
    """The cycle test would catch a back-arrow only once it closed a cycle; this names the
    arrows before that, so a convenient `from litharness.domain.extraction import ...` inside
    `sheet` or `moves` is refused with the seam it crosses rather than with a cycle report
    that arrives one import later. The seams and their reasons are `EXTRACTION_SEAMS`'s.
    """
    modules = _modules()
    violations: list[str] = []
    for source, forbidden in EXTRACTION_SEAMS.items():
        path = modules[f"litharness.domain.{source}"]
        for target, line in _imports(path, set(modules)):
            short = target.removeprefix("litharness.domain.")
            if short in forbidden:
                violations.append(f"domain/{source}.py:{line} imports {short}")
    assert not violations, "a seam points the wrong way:\n" + "\n".join(violations)


# --- the prose ------------------------------------------------------------------------

#: Backtick-quoted names in `src/` docstrings that deliberately name nothing here. It should
#: stay short: this project's style is to name a refuted alternative
#: (`plan/stage-0-decisions.md` is full of them), so a genuinely absent name belongs here
#: **with its reason**, not silently outside the check.
#:
#: Four kinds earn a place, and the reason says which: a symbol retired by a named commit and
#: still cited for what it taught; a module that lives in `research/` or `plan/`, which the
#: corpus does not scan; an OS or third-party name that was never ours; and an example value
#: standing in for data, which is not a symbol at all.
PROSE_ALLOWED: dict[str, str] = {
    "AXIS_MATCHERS": "the Judge's frozen matchers, in "
    "research/quality-measurement/elicitation_study.py; the corpus scans src/, tests/, "
    "migrations/ and pyproject.toml, so nothing under research/ resolves here",
    "Chapter3": "an example value, not a symbol: it is what `stem` returns for chapter 3, "
    "quoted so the docstring shows the filename an operator pastes from",
    "CreateProcess": "Win32, and the point of both docstrings is that it is not ours: it "
    "caps a command line at 32,767 characters, which is why the prompt goes down stdin",
    "OllamaProvider": "the retired Ollama adapter's class; domain/generation.py keeps the "
    "sampler measurements taken on it, and the class went with the adapter",
    "_RULES": "the forge's rule tuple, application/architect.py; retired with the legacy "
    "Forge subsystem, and worlds.py cites it for the price rule it already enforced",
    "agency_the_drift": "an example subject id, not a symbol: application/world.py quotes it "
    "to show what splitting ids on `_` contributes to a name count",
    "axes.Pole": "domain/axes.py, cut with the prose-axis channel (530f40e); promises.py "
    "cites it for the one property that survives — a kind carries no valence",
    "comprehension_battery": "research/quality-measurement/comprehension_battery.py, outside "
    "the scanned corpus; house.py cites the four readers it asked and what they quoted",
    "creature_saltmilk_doe": "an example subject id, beside `agency_the_drift`",
    "named_axes": "domain/discrimination.py, cut with the dead cluster (530f40e); "
    "directors.py names it to say what `prose_axes_named` deliberately is not",
    "opening_proper_nouns": "domain/axes.opening_proper_nouns, cut with the prose-axis "
    "channel; kept as this project's cautionary case — a counter nominated for a named "
    "defect put the complained-about chapter at the 68.5th percentile "
    "(research/quality-measurement/opening-counters-results.md)",
    "overall_score": "a column in the cached RoyalRoad shards, never ours; rivals.py cites "
    "it because it is 100% null, which is why followers and views are the evidence instead",
    "preference.MACHINE_READER_PREFIX": "domain/preference.py, cut with the §61 pairwise "
    "stack (530f40e); directors.py restates the prefix and cites it for the reason it gives "
    "against sharing one constant between two tables",
    "promoted_gate": "domain/calibration.py, cut with the calibration programme (530f40e); "
    "integrity.py cites it for the rule that outlived it — a calibration is looked up by "
    "`metric_id`, so changed arithmetic is a new metric",
    "records_for": "application/architect.py, retired with the legacy Forge subsystem; "
    "worlds.py cites it for the byte-identity rail over worlds forged before that",
    "repeated_span": "domain/craft.py, cut with the calibration programme (530f40e); "
    "generation.py and integrity.py both cite the metric it shipped, `craft.repeated_span.v0`",
    "scene_echo": "domain/craft.py, cut with the same commit as `repeated_span`; integrity.py "
    "cites its move to `.v1` as the precedent for changed arithmetic being a new metric id",
    "stamina_max": "deliberately hypothetical: extraction.py's point is that MAX_SUFFIX "
    "covers a sheet that grows one, without an edit",
}

#: A name worth resolving: it has an underscore, a dot, or an initial capital. A single
#: lowercase word in backticks is ordinary emphasis far more often than it is a symbol.
_SYMBOLISH = re.compile(r"`([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)`")


def _repo_corpus() -> str:
    """What a prose reference may resolve against — with every backticked mention stripped
    out first, because a mention is a claim, not evidence. Without the stripping this check
    could not fail: the corpus contains each scanned file, so the reference under test always
    found itself, and a name deleted from the code would still be vouched for by the very
    docstring citing it (or by any other docstring that ever named it)."""
    parts = [path.read_text(encoding="utf-8") for path in PACKAGE_ROOT.rglob("*.py")]
    parts += [path.read_text(encoding="utf-8") for path in (REPO_ROOT / "tests").rglob("*.py")]
    parts += [path.read_text(encoding="utf-8") for path in (REPO_ROOT / "migrations").glob("*.sql")]
    parts.append((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return _SYMBOLISH.sub(" ", "\n".join(parts))


@pytest.mark.intensive
def test_every_symbol_the_prose_names_still_exists() -> None:
    """A docstring naming a function that was renamed is worse than one saying nothing: it
    teaches the wrong thing to whoever reads it next, and reads as current because it is
    sitting beside working code.

    Contract names are skipped — those belong to `litharness_contracts` and are checked by
    its own suite — and the contract's vocabulary reaches one level below `dir`:
    `plan_changed` names `ExtractedChangeKind.PLAN_CHANGED` as surely as the class name
    does, so enum members and their wire values are contract names too. Plain lowercase
    words are also skipped, being emphasis more often than they are symbols.
    """
    contract_names = set(dir(lc))
    for attr in dir(lc):
        obj = getattr(lc, attr)
        if isinstance(obj, type) and issubclass(obj, enum.Enum):
            contract_names.update(member.name for member in obj)
            contract_names.update(
                member.value for member in obj if isinstance(member.value, str)
            )
    corpus = _repo_corpus()
    stale: list[str] = []
    for path in [*sorted(PACKAGE_ROOT.rglob("*.py")), SYSTEM_MODEL]:
        for name in sorted(set(_SYMBOLISH.findall(path.read_text(encoding="utf-8")))):
            head, tail = name.split(".")[0], name.split(".")[-1]
            if "_" not in name and "." not in name and not name[0].isupper():
                continue
            if head in contract_names or tail in contract_names or name in PROSE_ALLOWED:
                continue
            if not re.search(rf"\b{re.escape(tail)}\b", corpus):
                stale.append(f"{path.relative_to(REPO_ROOT).as_posix()}: `{name}`")
    assert not stale, (
        "prose names symbols that no longer exist:\n"
        + "\n".join(stale)
        + "\n(rename the reference, or record it in PROSE_ALLOWED with why it is absent)"
    )


def test_every_test_cited_as_evidence_exists() -> None:
    """The project cites tests by name as proof that a clause holds — `PLAN.md` §17 does it
    for every Stage 0 exit criterion. A citation that no longer resolves is a claim with its
    evidence removed, and it looks exactly like a claim with evidence.

    Checked over `src/`, `plan/stage-0-decisions.md` and `docs/system-model.md`, the three
    places that cite *this* repo's tests; the map's whole purpose is to say which test pins
    a fact, so a name there that resolves to nothing is the map lying. `PLAN.md` and the
    other companion docs also discuss siblings' suites, which this repo cannot resolve and
    should not pretend to.
    """
    tests_dir = REPO_ROOT / "tests"
    suite = "\n".join(path.read_text(encoding="utf-8") for path in tests_dir.rglob("*.py"))
    sources = [
        *PACKAGE_ROOT.rglob("*.py"),
        REPO_ROOT / "plan" / "stage-0-decisions.md",
        SYSTEM_MODEL,
    ]
    stale: list[str] = []
    for path in sources:
        text = path.read_text(encoding="utf-8")
        for name in sorted(set(re.findall(r"`(test_[a-z0-9_]+)`", text))):
            if re.search(rf"def {re.escape(name)}\b", suite):
                continue
            if (tests_dir / f"{name}.py").exists():
                continue  # a module, cited as a whole
            stale.append(f"{path.relative_to(REPO_ROOT).as_posix()}: `{name}`")
    assert not stale, "cited tests that do not exist:\n" + "\n".join(stale)


def test_internal_module_graph_has_no_cycles() -> None:
    modules = _modules()
    known = set(modules)
    graph = {
        source: {
            target
            for target, _ in _imports(path, known)
            if target in known and target != source
        }
        for source, path in modules.items()
    }
    visited: set[str] = set()
    active: list[str] = []
    active_set: set[str] = set()

    def visit(module: str) -> list[str] | None:
        if module in active_set:
            start = active.index(module)
            return [*active[start:], module]
        if module in visited:
            return None
        active.append(module)
        active_set.add(module)
        for dependency in sorted(graph[module]):
            cycle = visit(dependency)
            if cycle is not None:
                return cycle
        active.pop()
        active_set.remove(module)
        visited.add(module)
        return None

    for module in sorted(graph):
        cycle = visit(module)
        assert cycle is None, "internal import cycle: " + " -> ".join(cycle)


def test_the_registry_still_satisfies_the_port_the_application_asks_for() -> None:
    """`application` names `TextGenerator`; `cli` hands it a `ProviderRegistry`. Nothing in
    the application layer can check that, because the rule above forbids it the import.

    mypy checks the fit where `cli` wires them, which is the right place and an easy one to
    lose: the wiring is one keyword argument, and a refactor that routes the registry through
    an `Any`-typed factory would drop the check with no diagnostic anywhere. This asserts the
    contract directly, so the port cannot drift from its only implementation in silence.

    Structural, not nominal — `ProviderRegistry` does not inherit from anything, and the whole
    value of the port is that a future in-memory or remote generator implements it without
    knowing it exists.
    """
    from litharness.application.ports import TextGenerator
    from litharness.providers.fake import FakeProvider
    from litharness.providers.registry import ProviderRegistry

    registry = ProviderRegistry(FakeProvider())
    generator: TextGenerator = registry

    for method in ("resolve", "complete", "reset_health"):
        assert callable(getattr(generator, method)), f"the port names {method}"


def test_every_role_that_writes_for_a_reader_carries_the_house_rules() -> None:
    """One role learning something is not the pipeline learning it, and that is a measured claim.

    On 2026-08-23 five rule changes made a forged premise clear and made its ladder a chain of
    abilities somebody keeps. Measured on premises they worked. Then the first book written on
    that world opened on 1,067 words of a call-centre shift rendered step by step, and the
    operator read chapter one as though none of it had happened \u2014 because none of it had. Every
    change had edited the retired Forge's private rules, and the Writer's whole system prompt was
    three sentences about not writing headings.

    `domain/house` is the single home, and this is the test that a new role cannot quietly skip
    it, which is exactly how the Writer came to be skipped.

    **The roles deliberately absent, so their absence reads as a decision.** `judge_panel` and the
    audit paths judge rather than write; `narrative_planner` proposes plan *edits* as JSON;
    `summarize` writes summaries the packet reads and no reader ever sees. A role that starts
    producing reader-facing prose belongs on this list and its own test failure will say so.

    **`recruiter` joined the absent list on 2026-08-28, and it is the closest call on it.** What
    it writes is a bio nobody reads, so by the criterion above it does not belong here — but that
    bio is rendered into the system message of every scene call the writer it describes ever
    makes, which is the most-repeated text in the system. That is the reason the floor may not
    reach it rather than a reason it may: `house.CLARITY` and `house.READER` are craft doctrine,
    `writers.legal_dossier` refuses a dossier that names what good prose is, and §138 measured a
    rule's affirmative half coming back as a verbal formula in the output. A Recruiter told how
    prose should read is one paraphrase from writing that into a dossier, where
    `prose_axes_named` cannot see it. The floor reaches the drafting call once, through
    `system_for`, where the prose actually is.

    An absence recorded in a docstring is not enough on its own — absence-by-forgetting and
    absence-by-decision look identical, which is the failure this test exists to prevent — so
    `test_the_recruiter_prompt_carries_no_craft_doctrine_of_its_own` asserts it.
    """
    from litharness.application import outline, planner, world_agent
    from litharness.domain import house
    from litharness.domain import writers as writers_domain

    assert house.CLARITY in house.HOUSE_RULES
    assert house.READER in house.HOUSE_RULES

    architect = world_agent.render_seed_request(
        "A listing readers have already seen.", writers_domain.CAST["ferreira"]
    )
    assert house.HOUSE_RULES in (architect.system or "")

    # The writer and the outline are checked at the source rather than by calling them, and the
    # weakness is stated rather than hidden: `planner.render_prompt` needs a beat and a built
    # context packet, and `outline.render_outline_request` needs a premise and a beat sheet, so
    # constructing either here would put a fixture in an architecture test. What is asserted is
    # that each routes its system string through the one function, which is the property that
    # would have failed before today and the one a new role can forget.
    for module in (planner, outline):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "house.with_house_rules(" in source, module.__name__


def test_the_house_rules_are_not_a_judgment_about_a_story() -> None:
    """`planner.point_of_view`'s boundary, applied to the block that now rides in every prompt.

    That docstring refuses an adjective because *how* to handle a protagonist is the director's
    to say and a default here would be "this system's own taste arriving in every prompt it ever
    renders" (\u00a795, \u00a797.1). The two rules pass because neither is about a story: one says a
    reader must be able to follow the words, the other says the words should be spent on what the
    book is selling. Checked against the same forbidden list the protagonist rule is checked
    against, whole words rather than substrings.
    """
    from litharness.domain import house

    lowered = house.HOUSE_RULES.lower()
    for forbidden in (
        "win", "winning", "hero", "likeable", "likable", "sympathetic", "root for",
        "faster", "fastest", "strongest", "best", "succeed", "success", "triumph",
        "interesting", "compelling", "exciting", "gripping",
    ):
        assert not re.search(rf"\b{forbidden}\b", lowered), forbidden
