"""The Architect's visible text stays out of the administrative family, and the audit that says so.

Stage-0 §116 shipped its prevention as rule text plus tests, because a word list with no receipt
drifts back. This is the same shape one address along: the audit in
`research/quality-measurement/architect_register.py` found the lean is **not** in our text, and the
one thing that was — a §116-family metaphor surviving in a second home — is subtracted here and
pinned so it cannot return quietly.
"""

from __future__ import annotations

import pytest

from litharness.application import world_agent
from litharness.domain import worlds

architect_register = pytest.importorskip(
    "architect_register",
    reason="research module; needs the quality-measurement directory on the path",
)

#: Words §116 named in the family it was removing, restricted to the ones that mean only the one
#: thing. `court` is deliberately absent: §116.8 removed it after a measured false positive on an
#: arena, and this list inherits that narrowing rather than repeating the mistake.
_FAMILY = ("ledger", "debt", "tariff", "writ", "bailiff", "docket", "magistrate", "plaintiff")


def _complaint_text() -> str:
    """Every complaint `validate` can emit, as one lowercase blob.

    Built by running the validator over deliberately broken worlds rather than by reading the
    source, so a complaint added later is covered without anybody remembering this test.
    """
    broken = [
        worlds.world_record("thing", worlds.COMPARATOR_PREDICATE, value="not-a-comparator"),
        worlds.world_record("thing", worlds.ENTITY_ROLE_PREDICATE, value="not-a-role"),
        worlds.world_record("q", worlds.CLAIM_CONTENT, value="an answer nobody reveals"),
        worlds.world_record("q", worlds.QUESTION_PREDICATE, value="who moved the seal"),
    ]
    return " ".join(worlds.validate(tuple(broken))).lower()


def test_no_complaint_the_architect_reads_carries_an_administrative_metaphor() -> None:
    """The subtraction of 2026-08-29, pinned.

    `world check` and `world declare` print these strings straight back to the Architect, so a
    financial metaphor here is ambient register in the one text it reads on every run.
    """
    text = _complaint_text()
    assert text, "the validator produced no complaints; the fixture stopped being broken"
    for word in _FAMILY:
        assert word not in text, f"{word!r} is back in a complaint the Architect reads"


def test_the_mystery_complaint_still_says_what_is_wrong() -> None:
    """A subtraction that cost the sentence its job would be a worse defect than the metaphor."""
    text = _complaint_text()
    assert "no reveal scene" in text
    assert "never comes back to" in text


def test_the_architect_task_text_names_no_institution() -> None:
    """The audit's central finding, as a guard rather than a claim.

    Read 7 §4.2 sent us looking for an institutional lean in the Architect's own prompt. There is
    none, which is why the fix could not be a subtraction there — and that only stays true if
    nobody adds one.
    """
    surface = " ".join(
        (world_agent._SEED, world_agent._GROW, world_agent._TOOLS)
    ).lower()
    for word in ("charter", "licence", "license", "guild", "tribunal", "bailiff", "ledger"):
        assert word not in surface, f"{word!r} entered the Architect's task text"


def test_the_audit_separates_schema_supplied_values_from_what_the_architect_wrote() -> None:
    """§116's exclusion rule at the new address.

    `institution` and `agency` are printed by `world vocabulary` on every run, so a world using
    them used a menu we supplied. Counting them inside the rate would count our own instructions,
    which is exactly why §116 excluded `price`, `cost`, `pay` and `bond` from its own family.
    """
    for value in ("institution", "agency", "law", "economy", "politics", "crime"):
        assert value in architect_register.SCHEMA_SUPPLIED
    assert not (architect_register.SCHEMA_SUPPLIED & architect_register.CORE)


def test_the_audit_word_family_inherits_the_court_narrowing() -> None:
    """§116.8 measured that `court` bought one world in thirty and cost every courtyard."""
    assert "court" not in architect_register.CORE
    assert "courts" not in architect_register.CORE
    # The unambiguous members of the same register are kept, which is the half §116.8 retained.
    for word in ("bailiff", "magistrate", "tribunal", "writ"):
        assert word in architect_register.CORE


def test_ambiguous_words_are_probed_and_never_summed_into_the_rate() -> None:
    """`register` and `office` are ordinary English as often as they are institutions."""
    assert not (architect_register.CORE & architect_register.PROBE)
    for word in ("register", "office", "file", "notice"):
        assert word in architect_register.PROBE
