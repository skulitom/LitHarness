"""The critic roster: what the parser drops, what the verifier can establish, and containment.

The spine of this file is the rule that makes a rejection-optimized roster safe to run at all —
agent prose is not evidence. So the tests that matter most here are the negative ones: a claim
with no verbatim span evaporates in the parser, a claim that promised a counter and cannot pay
is refuted in code and recorded against the critic, and a claim about prose that quotes a status
block is thrown out as mis-cited. A critic that asserts well and quotes badly scores nothing.

Also pinned: that the asymmetry between a mechanical verification and a taxonomy verification is
carried in the record rather than smoothed away, that no operator quotation from the
read-recurrence map appears in any prompt (§97.1, scanned against the map itself), that no field
is named score or verdict, and that the roster's tally is not pooled across prompt versions.

No model is called anywhere in this file: every critic answer below is written here.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "research" / "loop"))

critics = pytest.importorskip("critics", reason="research module; imported by path")
prompts = pytest.importorskip("critic_prompts", reason="research module; imported by path")

# --------------------------------------------------------------------------------- fixtures

CHAPTER = (
    "The lantern still cost twenty crowns, and Rook counted his coins twice, and the keeper "
    "wanted five more, and he paid.\n"
    "He felt a kind of dull certainty settle over him, the way anyone would.\n"
    "Nobody in the Ward trimmed a lamp the way Marrow did.\n"
    "He stopped at the sill — the rain had turned — and waited for the bells.\n"
    # Every line of this block classifies as furniture on its own, which is what makes it
    # usable as the mis-citation fixture: "[STATUS] Rook" would NOT, because the bracketed
    # pattern matches a whole line and that one carries a name after the bracket.
    "[STATUS]\n"
    "Tier: Bronze 2\n"
    "Vigor: 14\n"
)

#: The status block as a span, all-furniture and over `MIN_SPAN_WORDS`.
FURNITURE_SPAN = "[STATUS]\nTier: Bronze 2\nVigor: 14"

FABRIC = critics.ROSTER[0]


def claim(**over: Any) -> dict[str, Any]:
    """One well-formed claim, overridable field by field."""
    return {
        "family": "D1",
        "quote_span": {
            "text": "Rook counted his coins twice, and the keeper wanted five more, and he paid",
            "location": "line 1",
        },
        "claim": "The clauses are strung together rather than built.",
        "cashable_as": "mechanical",
        **over,
    }


def answer(*entries: dict[str, Any]) -> str:
    return json.dumps({"claims": list(entries)})


def parse_one(entry: dict[str, Any], critic: critics.Critic = FABRIC):
    claims, drops = critics.parse_claims(answer(entry), critic)
    return claims, drops


def verify_one(entry: dict[str, Any], chapter: str = CHAPTER) -> critics.Judged:
    claims, _ = parse_one(entry)
    assert claims, "fixture should parse; use parse_one for the drop cases"
    return critics.verify(claims[0], chapter, critic_id=FABRIC.critic_id, chapter_id="ch1")


class FakeAsker:
    """`ask_raw`'s seam, answering from a script. Records every call it was given."""

    def __init__(self, script: dict[str, str] | None = None, default: str = '{"claims": []}'):
        self.script = script or {}
        self.default = default
        self.calls: list[dict[str, Any]] = []

    def ask_raw(self, system, turns, *, schema, max_tokens, tag, sample=0, model=None):
        self.calls.append({"system": system, "turns": turns, "tag": tag, "sample": sample,
                           "schema": schema})
        return {"text": self.script.get(tag["critic_id"], self.default), "refused": False}


# ---------------------------------------------------------------- the parser's one hard rule


def test_a_claim_without_a_span_evaporates_in_the_parser():
    """The headline rule: structurally uncashable, gone before anything reads it."""
    claims, drops = parse_one({k: v for k, v in claim().items() if k != "quote_span"})
    assert claims == []
    assert drops[0]["reason"] == "no-span"


def test_a_span_that_is_not_a_string_is_also_no_span():
    claims, drops = parse_one(claim(quote_span={"location": "line 1"}))
    assert claims == []
    assert drops[0]["reason"] == "no-span"


def test_the_parser_drops_a_family_outside_the_critics_own_lens():
    """A critic that may claim anything produces a scattergun; the menu is per lens."""
    claims, drops = parse_one(claim(family="B5"))
    assert claims == [] and drops[0]["reason"] == "family-outside-lens"


def test_the_parser_drops_a_cash_out_outside_the_closed_set():
    claims, drops = parse_one(claim(cashable_as="obvious"))
    assert claims == [] and drops[0]["reason"] == "cashable-outside-set"


def test_the_parser_drops_a_claim_with_no_sentence():
    claims, drops = parse_one(claim(claim="   "))
    assert claims == [] and drops[0]["reason"] == "no-claim-sentence"


@pytest.mark.parametrize(
    ("raw", "reason"),
    [("not json at all", "unparseable-json"), ('{"other": []}', "no-claims-list"),
     ("[1, 2, 3]", "no-claims-list")],
)
def test_a_malformed_answer_yields_no_claims_and_one_recorded_drop(raw: str, reason: str):
    claims, drops = critics.parse_claims(raw, FABRIC)
    assert claims == []
    assert drops[0]["reason"] == reason


def test_a_fenced_answer_still_parses():
    claims, _ = critics.parse_claims(f"```json\n{answer(claim())}\n```", FABRIC)
    assert len(claims) == 1


def test_the_parser_enforces_the_claim_ceiling():
    """A roster tallied on verified kills has an obvious incentive to flood."""
    claims, _ = critics.parse_claims(answer(*[claim()] * 20), FABRIC)
    assert len(claims) == prompts.MAX_CLAIMS


# ------------------------------------------------------------------------------ verification


def test_an_invented_span_is_dropped_even_though_it_parsed():
    judged = verify_one(claim(quote_span={"text": "no such words anywhere", "location": "x"}))
    assert judged.status == "dropped:no-verbatim-span"
    assert not judged.blocking


def test_a_span_too_short_to_carry_a_claim_is_dropped():
    judged = verify_one(claim(quote_span={"text": "the rain", "location": "x"}))
    assert judged.status == "dropped:span-too-short"


def test_line_wrapping_is_forgiven_but_characters_are_not_folded():
    """Whitespace-tolerant matching, deliberately not character-folding.

    Folding the em dash — as the instrument modules' `normalise` does — would erase the
    evidence for the one family whose entire subject is the em dash, so the match is exact on
    every character and forgiving only of how the model rewrapped the line.
    """
    wrapped = claim(
        family="D4",
        quote_span={"text": "He stopped at the sill —\n   the rain had turned — and waited",
                    "location": "line 4"},
    )
    assert verify_one(wrapped).status == "verified:mechanical"
    folded = claim(
        family="D4",
        quote_span={"text": "He stopped at the sill - the rain had turned - and waited",
                    "location": "line 4"},
    )
    assert verify_one(folded).status == "dropped:no-verbatim-span"


def test_a_mechanical_claim_its_counter_confirms_is_verified():
    judged = verify_one(claim())
    assert judged.status == "verified:mechanical"
    assert judged.counter == "_and_chains" and judged.counter_value >= 2
    assert judged.blocking


def test_a_mechanical_claim_its_counter_refutes_is_recorded_against_the_critic():
    """The falsification that makes the roster honest: the span is real, the defect is not."""
    judged = verify_one(
        claim(family="D4",
              quote_span={"text": "Nobody in the Ward trimmed a lamp the way Marrow did",
                          "location": "line 3"})
    )
    assert judged.status == "refuted:counter-empty"
    assert judged.counter_value == 0
    assert not judged.blocking


def test_a_mechanical_claim_on_a_family_with_no_counter_is_not_waved_through():
    """An unbacked mechanical claim must not be cheaper than a backed one."""
    judged = verify_one(
        claim(family="E2",
              quote_span={"text": "Nobody in the Ward trimmed a lamp the way Marrow did",
                          "location": "line 3"})
    )
    assert judged.status == "unverified:no-counter"
    assert not judged.blocking


def test_a_taxonomy_claim_records_that_it_established_a_citation_not_a_finding():
    """The asymmetry is carried in the record rather than smoothed away."""
    judged = verify_one(claim(cashable_as="taxonomy-item"))
    assert judged.status == "verified:taxonomy"
    assert "the defect itself is not shown" in judged.note
    assert judged.blocking


def test_a_gate_checkable_claim_is_left_for_the_coordinator():
    judged = verify_one(claim(cashable_as="gate-checkable"))
    assert judged.status == "gate-read"
    assert not judged.blocking


def test_a_prose_claim_quoting_only_furniture_is_refuted_as_miscited():
    """A status block is not prose, and a sentence-fabric claim about one is a mis-citation."""
    judged = verify_one(
        claim(family="D2", cashable_as="taxonomy-item",
              quote_span={"text": FURNITURE_SPAN, "location": "line 5"})
    )
    assert judged.status == "refuted:miscited-furniture"


def test_a_system_family_may_quote_furniture(monkeypatch):
    """A4, L1 and M1 are shown BY quoting furniture, so they are not in `PROSE_FAMILIES`."""
    assert not critics.PROSE_FAMILIES & {"A4", "L1", "M1"}
    diegesis = next(c for c in critics.ROSTER if c.critic_id == "diegesis-integrity")
    parsed, _ = critics.parse_claims(
        answer(claim(family="M1", cashable_as="taxonomy-item",
                     quote_span={"text": FURNITURE_SPAN, "location": "l5"})),
        diegesis,
    )
    judged = critics.verify(parsed[0], CHAPTER, critic_id=diegesis.critic_id, chapter_id="ch1")
    assert judged.status == "verified:taxonomy"


def test_every_status_the_module_can_produce_is_declared():
    """A status assigned but not listed would vanish from every split and every tally."""
    produced = {
        verify_one(claim()).status,
        verify_one(claim(cashable_as="taxonomy-item")).status,
        verify_one(claim(cashable_as="gate-checkable")).status,
        verify_one(claim(quote_span={"text": "no such words here", "location": "x"})).status,
    }
    assert produced <= set(critics.STATUSES)
    assert set(critics.BLOCKING_STATUSES) <= set(critics.STATUSES)


# ---------------------------------------------------------------------------------- the runner


def test_the_runner_asks_every_critic_about_every_chapter():
    asker = FakeAsker()
    report = critics.run_critics("v1", [("ch1", CHAPTER), ("ch2", CHAPTER)], asker)
    assert len(asker.calls) == len(critics.ROSTER) * 2
    assert report.roster_version == prompts.ROSTER_VERSION
    assert {call["tag"]["variant"] for call in asker.calls} == {"v1"}


def test_each_cell_gets_its_own_sample_index():
    """Two critics reading one chapter must not collapse into a single cached answer."""
    asker = FakeAsker()
    critics.run_critics("v1", [("ch1", CHAPTER), ("ch2", CHAPTER)], asker)
    samples = [call["sample"] for call in asker.calls]
    assert len(set(samples)) == len(samples)


def test_a_cell_that_answered_nothing_is_counted_not_guessed_at():
    """A roster reporting no kills beside failures is reporting on the cells that answered."""
    class Silent:
        def ask_raw(self, system, turns, *, schema, max_tokens, tag, sample=0, model=None):
            return {"text": "", "refused": False}

    report = critics.run_critics("v1", [("ch1", CHAPTER)], Silent())
    assert report.transport_failures == len(critics.ROSTER)
    assert report.judged == ()


def test_the_report_splits_claims_by_what_the_code_established():
    asker = FakeAsker({
        FABRIC.critic_id: answer(
            claim(),
            claim(family="D4", quote_span={"text": "Nobody in the Ward trimmed a lamp the way "
                                                   "Marrow did", "location": "l3"}),
            claim(quote_span={"text": "invented entirely by the critic", "location": "l9"}),
        )
    })
    report = critics.run_critics("v1", [("ch1", CHAPTER)], asker)
    split = report.split()
    assert split["verified:mechanical"] == 1
    assert split["refuted:counter-empty"] == 1
    assert split["dropped:no-verbatim-span"] == 1
    assert set(split) == set(critics.STATUSES)
    assert [j.family for j in report.blocking] == ["D1"]
    assert report.table().startswith("critic")


# ------------------------------------------------------------------------------- the tally file


def test_the_tally_accumulates_per_critic_across_runs(tmp_path: Path):
    """The rejection pressure the direction asked for, kept as bookkeeping."""
    path = tmp_path / "roster.json"
    asker = FakeAsker({FABRIC.critic_id: answer(claim())})
    report = critics.run_critics("v1", [("ch1", CHAPTER)], asker)
    critics.record_run(path, report)
    tally = critics.record_run(path, report)
    assert tally["runs"] == 2
    assert tally["critics"][FABRIC.critic_id]["verified:mechanical"] == 2
    assert tally["critics"]["premise-freshness"]["claims"] == 0


def test_a_tally_from_another_prompt_version_is_not_pooled(tmp_path: Path):
    """A reworded prompt is a different instrument; its record is not this one's."""
    path = tmp_path / "roster.json"
    path.write_text(json.dumps({"roster_version": "critics.vOLD", "critics": {}}), "utf-8")
    with pytest.raises(ValueError, match="not pooled"):
        critics.load_tally(path)


def test_the_tally_file_is_the_only_write(tmp_path: Path):
    """Containment: the runner returns a record and touches nothing else on disk."""
    before = sorted(tmp_path.rglob("*"))
    critics.run_critics("v1", [("ch1", CHAPTER)], FakeAsker())
    assert sorted(tmp_path.rglob("*")) == before


# -------------------------------------------------------------------------------- containment


def test_no_operator_quotation_from_the_recurrence_map_reaches_a_prompt():
    """§97.1, scanned against the map itself rather than asserted in a comment.

    The map's header says the family names are ours and the quoted phrases are the operator's,
    given once and not to become prompt text. This lifts every such quotation out of the map
    and checks that none of them appears in any string a critic is shown.
    """
    text = (REPO / "plan" / "agent-impact" / "read-recurrence-map.md").read_text("utf-8")
    quoted = {
        match.strip().strip('."').lower()
        for match in re.findall(r'\*"([^"]{12,})"\*', text)
    }
    assert len(quoted) >= 8, "the map's operator quotations should have been found"
    rendered = " ".join(
        [prompts.SYSTEM, prompts.TASK, *prompts.FAMILIES.values()]
        + [c.lens_note for c in critics.ROSTER]
    ).lower()
    for phrase in quoted:
        assert phrase not in rendered


def test_the_prompts_carry_no_approval_vocabulary():
    """A critic has no way to say a chapter is good, and no field in which to say it."""
    rendered = json.dumps(prompts.CLAIM_SCHEMA) + prompts.SYSTEM + prompts.TASK
    for word in ("score", "verdict", "rating", "rate the", "quality of"):
        assert word not in rendered.lower()
    fields = prompts.CLAIM_SCHEMA["properties"]["claims"]["items"]["properties"]
    assert set(fields) == {"family", "quote_span", "claim", "cashable_as"}


def test_the_claim_schema_is_closed_at_every_level():
    """An open schema is how an unfalsifiable field arrives through a side door."""
    items = prompts.CLAIM_SCHEMA["properties"]["claims"]["items"]
    assert prompts.CLAIM_SCHEMA["additionalProperties"] is False
    assert items["additionalProperties"] is False
    assert items["properties"]["quote_span"]["additionalProperties"] is False
    assert items["required"] == ["family", "quote_span", "claim", "cashable_as"]


def test_a_stated_preference_is_not_offered_as_a_defect():
    """The map records I2 as a preference, not a defect; offering it would return it as one."""
    assert "I2" not in prompts.FAMILIES
    assert all("I2" not in critic.families for critic in critics.ROSTER)


def test_the_roster_lenses_partition_their_families():
    """Overlapping menus would let one defect be claimed twice and tallied twice."""
    seen: set[str] = set()
    for critic in critics.ROSTER:
        assert set(critic.families) <= set(prompts.FAMILIES)
        assert not seen & set(critic.families)
        seen |= set(critic.families)
    assert len({c.critic_id for c in critics.ROSTER}) == len(critics.ROSTER)
    assert 3 <= len(critics.ROSTER) <= 5


def test_every_counter_is_for_a_family_on_the_map():
    assert set(critics.SPAN_COUNTERS) <= set(prompts.FAMILIES)
    assert set(critics.PROSE_FAMILIES) <= set(prompts.FAMILIES)


def test_the_report_has_no_field_named_score_or_verdict():
    asker = FakeAsker({FABRIC.critic_id: answer(claim())})
    rendered = critics.run_critics("v1", [("ch1", CHAPTER)], asker).to_json().lower()
    for forbidden in ("score", "verdict", "rating", "overall"):
        assert f'"{forbidden}"' not in rendered


def test_nothing_under_src_imports_the_loop_modules():
    """The dependency direction, checked rather than trusted."""
    offenders = [
        path
        for path in (REPO / "src").rglob("*.py")
        if re.search(r"\b(?:import|from)\s+(?:research|adversarial|critics|critic_prompts|"
                     r"measures_adapter)\b", path.read_text("utf-8"))
    ]
    assert offenders == []
