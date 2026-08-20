"""The Writer record's rails, and the wiring G0 reads.

`plan/writer-roster.md`. Four properties are load-bearing and every one of them fails silently —
by minting a writer, rendering a prompt, or returning an id, none of which raises:

1. **The content address cannot collide.** A roster whose ids collide is a roster that cannot
   answer "which writer drafted this book", which is the only reason the address exists. The
   first version of `writer_id_for` returned equal ids for `("a", "b")` and `("a\\x1fb",)`.
2. **`exemplar_digest` is addressed from the first mint.** Populating it later must mint a new
   writer; adding the field later would have re-addressed every writer that already existed.
3. **R1 is inherited, not restated.** A dossier that names a registered prose axis must be
   unrepresentable rather than discouraged, by the same guard and the same exception type the
   Director's brief uses.
4. **The dossier reaches the system message and never the packet.** A parameter accepted and not
   read is a defect this repo has paid for once already, in `render_prompt`'s own `target_words`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from litharness.application.planner import render_prompt
from litharness.domain import writers
from litharness.domain.beats import SIX_BEAT, Beat
from litharness.domain.context import ContextPacket
from litharness.domain.directors import IllegalBrief

RESEARCH = Path(__file__).resolve().parents[1] / "research" / "quality-measurement"
sys.path.insert(0, str(RESEARCH))


def _beat() -> Beat:
    return Beat(
        logical_id="s1",
        ordinal=1,
        of_total=30,
        title="The Archive",
        function="setup",
        template_id=SIX_BEAT.template_id,
        story_order_key="s1",
    )


def _packet() -> ContextPacket:
    return ContextPacket(
        query_id="beat:s1",
        target_logical_id="s1",
        book_id="bk",
        branch_id="br",
        base_revision_id="rev",
    )


def _render(writer: writers.Writer | None) -> tuple[str, str]:
    return render_prompt(
        _beat(), book_title="Test Book", packet=_packet(), target_words=900, writer=writer
    )


# ------------------------------------------------------------------- the content address


def test_the_interest_separator_cannot_be_forged():
    """`("a", "b")` and `("a\\x1fb",)` are different rosters and must be different writers.

    Joining alone is forgeable: without the length prefix both join to the same bytes and address
    to the same id. Measured rather than reasoned about — the first version of this function
    returned equal ids for exactly this pair.
    """
    joined = writers.writer_id_for(name="x", dossier="knows tides", interests=("a", "b"))
    forged = writers.writer_id_for(name="x", dossier="knows tides", interests=("a\x1fb",))
    assert joined != forged


def test_interest_order_is_part_of_identity():
    first = writers.writer_id_for(name="x", dossier="knows tides", interests=("a", "b"))
    second = writers.writer_id_for(name="x", dossier="knows tides", interests=("b", "a"))
    assert first != second


def test_editing_one_word_of_a_dossier_mints_a_different_writer():
    """The whole reason for a content address: a roster cannot drift under the books it wrote."""
    before = writers.build("x", "You spent eleven seasons mapping ground nobody had mapped.")
    after = writers.build("x", "You spent twelve seasons mapping ground nobody had mapped.")
    assert before.writer_id != after.writer_id


def test_the_note_is_not_addressed():
    """An operator annotation that minted a new writer would make note-keeping a version event."""
    plain = writers.build("x", "knows tides", interests=("marine",))
    annotated = writers.build("x", "knows tides", interests=("marine",), note="reconsider this")
    assert plain.writer_id == annotated.writer_id


def test_the_exemplar_socket_is_addressed_from_the_first_mint():
    """Two id changes that must stay distinguishable.

    Populating an exemplar later *should* mint a new writer — it changes what the writer drafts,
    which is identity, not drift. Adding the *field* later would instead re-address every writer
    that already existed without changing what any of them does, which is a schema re-mint and is
    pure loss. The field participating from the first mint buys the first and avoids the second.
    """
    unset = writers.writer_id_for(name="x", dossier="knows tides", interests=("marine",))
    populated = writers.writer_id_for(
        name="x", dossier="knows tides", interests=("marine",), exemplar_digest="deadbeef"
    )
    assert unset != populated
    assert writers.Writer(
        writer_id=populated,
        name="x",
        dossier="knows tides",
        interests=("marine",),
        exemplar_digest="deadbeef",
    ).exemplar_digest == "deadbeef"


def test_a_writer_id_that_does_not_address_its_writer_is_unrepresentable():
    with pytest.raises(writers.IllegalDossier):
        writers.Writer(writer_id="wtr-nonsense", name="x", dossier="knows tides")


# ----------------------------------------------------------------------------------- R1


def test_a_dossier_may_not_name_a_registered_prose_axis():
    """R1, inherited from the Director's rail rather than restated.

    A brief reaches the narrative planner; a dossier rides in the system message of *every* scene
    call, beside `feedback` — the one channel `plan/reader-judge-loop.md` §2.1 guards with a
    four-step admission path.
    """
    for illegal in (
        "avoid em dashes",
        "keep the status-line vague",
        "use short punchy sentences",
        "she writes with a great deal of interiority",
    ):
        with pytest.raises(writers.IllegalDossier):
            writers.build("x", illegal)


def test_illegal_dossier_is_caught_by_an_illegal_brief_handler():
    """One rule, one `except`. Two exception types would let R1 drift into two rules."""
    assert issubclass(writers.IllegalDossier, IllegalBrief)
    with pytest.raises(IllegalBrief):
        writers.build("x", "avoid em dashes")


def test_an_empty_dossier_is_not_a_writer():
    with pytest.raises(writers.IllegalDossier):
        writers.build("x", "   ")


def test_no_shipped_dossier_uses_an_em_dash():
    """Every dossier is a small exemplar, whether anyone intended one or not.

    The guard refused four of the ten example dossiers on the `em_dash` axis — not because any of
    them *said* anything about punctuation, but because the prose contained the mark. That is not
    a false positive: a dossier rides in every scene call, so one written with em dashes
    *demonstrates* the mark on every draft, and §83's finding is that demonstration moves register
    where description does not. §78's em-dash hypothesis is still VOID and under test.
    """
    for writer in writers.BUILTIN.values():
        assert "—" not in writer.dossier, writer.name
        writers.legal_dossier(writer.dossier)


def test_the_shipped_roster_is_ten_writers_with_two_adjacent_pairs():
    """Adjacency is what lets G2 read *graded* binding. A far-pair pass has fooled us before."""
    roster = writers.BUILTIN
    assert len(roster) == 10
    assert len({w.writer_id for w in roster.values()}) == len(roster)
    for anchor, neighbour in (("geology", "volcanology"), ("marine", "estuarine")):
        assert anchor in roster and neighbour in roster
        assert roster[anchor].interests != roster[neighbour].interests


# ------------------------------------------------------------------------------ wiring


def test_the_dossier_reaches_the_system_message_and_changes_its_bytes():
    """`target_words` was accepted and never read, and a commit reported a 47% effect from
    byte-identical prompts. G0 exists so that cannot happen twice."""
    anonymous, _ = _render(None)
    for writer in writers.BUILTIN.values():
        system, _ = _render(writer)
        assert writer.render() in system
        assert system != anonymous


def test_the_dossier_never_reaches_the_packet_side():
    """§3.2 and R5. The packet's contract is "established and may be relied on; do not contradict
    it", and a novelist's career is not a fact about the story."""
    _, anonymous_prompt = _render(None)
    for writer in writers.BUILTIN.values():
        _, prompt = _render(writer)
        assert prompt == anonymous_prompt
        assert writer.render() not in prompt


def test_no_writer_is_the_control_and_it_is_unchanged():
    system, _ = _render(None)
    assert system.startswith("You are drafting one scene of a novel.")


def test_two_writers_differ_and_one_writer_repeats():
    """The byte-identity floor §89.1 earned: four personas, one answer vector, byte-identical."""
    systems = {name: _render(w)[0] for name, w in writers.BUILTIN.items()}
    assert len(set(systems.values())) == len(systems)
    for name, writer in writers.BUILTIN.items():
        assert _render(writer)[0] == systems[name]


def test_g0_selftest_passes():
    writer_g0 = pytest.importorskip("writer_g0")
    assert writer_g0.selftest() == 0
