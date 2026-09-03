"""The register the scene packet states world facts in: what is so, never what to write.

**The defect this file pins was declared away three times and rendered anyway.**
`worlds.MANIFESTS_PREDICATE`'s docstring calls the field *"how a feature shows on the page"*
and the one predicate that exists *"purely for the register"*; `worlds.EDGE_PREDICATE`'s calls
its neighbour *"a fact about the world, exactly as a rule is — never an instruction about how
to write them"*; and `gamesystem.Ability` says `costs` and `manifests_as` are *"facts about the
world in the register `worlds._record_sentence` already uses — what is so, never an instruction
about how to write it"*. The renderer said `shows on the page as:`, which names the writer's
output. Stage-0 §168.5 found the contradiction and left it; §182 is the correction.

**Why it went unnoticed for the life of the field: nothing asserted either frame.** A
repo-wide search for the rendered phrase found one production line and no test, and the cast
sheet's label was unpinned too — so both strings could be changed, or changed back, with a
green suite. That is what this file exists to end.

**The property, and it is deliberately not a string echo.** A test that asserted the new
wording would pin a phrasing and catch nothing; the invariant is that **a line stating a world
fact never names the page**. It is asserted over the packed items of the sections that carry
facts, so it holds at any render site that feeds them — `worlds.project` today, and anything
a later track adds.

**The one place the page may be named is a section frame, and that distinction is the point.**
`context.render`'s hidden block says *"never put it on the page"*, which is a signed
prohibition on a section (§138's shape) rather than an instruction attached to a fact. So the
assertions below run over item text, never over the rendered document, and
`test_the_hidden_sections_prohibition_is_not_collateral_damage` states that in the suite so a
later reader does not silently widen the rule into the frame that must keep it.

No model call, no network, no store: three renderers and one pure `assemble`.
"""

from __future__ import annotations

from litharness.domain import characters as characters_mod
from litharness.domain import worlds
from litharness.domain.context import CAST, FACTS, assemble
from litharness.domain.revision import new_book
from tests.helpers import canon

#: What a fact line may not contain. The writer's output is the page; a fact is about the
#: world. Both spellings, because the two renderers that carried the defect used both.
PAGE_WORDS = ("on the page", "shows on the page")


#: A rule, a person and a thing, each with a declared form. Three subjects because the
#: manifestation of a rule, of a cast member and of a carrier reach the packet by three
#: different paths and the register has to hold on all of them.
FORM_OF_THE_RULE = "A queue at a folding table, and the reading read out where it is heard."
FORM_OF_THE_PERSON = "Sleeves pushed back before she is asked anything."
FORM_OF_THE_THING = "A cracked handset in a left hand, registered to nobody."

WORLD = [
    canon("payout_rule", worlds.WORLD_RULE_PREDICATE, value="the print settles who was owed"),
    canon("payout_rule", worlds.MANIFESTS_PREDICATE, value=FORM_OF_THE_RULE),
    canon("priya", worlds.ENTITY_ROLE_PREDICATE, value="protagonist"),
    canon("priya", worlds.MANIFESTS_PREDICATE, value=FORM_OF_THE_PERSON),
    canon("handset", worlds.ENTITY_ROLE_PREDICATE, value="carrier"),
    canon("handset", worlds.MANIFESTS_PREDICATE, value=FORM_OF_THE_THING),
]


def _packet_fact_lines() -> list[str]:
    """Every packed line of the two sections that state facts, at one scene."""
    revision = new_book("book-register", "main", title="Register", scenes=2)
    packet = assemble(revision, "scene-1", state_records=WORLD)
    return [
        item.text
        for section in (FACTS, CAST)
        for item in packet.sections.get(section, ())
    ]


def test_no_line_of_the_packet_tells_the_writer_what_to_put_on_the_page() -> None:
    """The §182 property, over items rather than over one renderer's output string.

    This is the assertion that was missing while the defect was live: it fails on
    `worlds._record_sentence`, on `characters.Character.render`, and on any third site a
    later track routes into the fact sections, without naming any of them.
    """
    lines = _packet_fact_lines()
    assert lines, "the fixture packed nothing, so the assertion below would be vacuous"
    offending = [line for line in lines if any(word in line.lower() for word in PAGE_WORDS)]
    assert offending == [], (
        "a packet line states a world fact by naming the writer's output: " f"{offending}"
    )


def test_the_declared_form_still_reaches_the_writer_word_for_word() -> None:
    """**The register changed and the knowledge did not**, which is the whole of §182.

    The counterpart to the test above and the reason it cannot be satisfied by deletion: a
    later track that cut the manifestations instead of reframing them would pass the register
    assertion and fail this one. §168.1 measured the packet handing the writer a world it
    then wrote out; the answer taken was to stop the packet *instructing*, never to stop it
    *knowing*.
    """
    joined = "\n".join(_packet_fact_lines())
    for form in (FORM_OF_THE_RULE, FORM_OF_THE_PERSON, FORM_OF_THE_THING):
        assert form in joined, f"a declared form stopped reaching the packet: {form!r}"


def test_a_manifestation_is_stated_the_way_the_rule_beside_it_is() -> None:
    """One sentence, read directly, in the register `_record_sentence` documents.

    `project` is the seam every packet consumer goes through, so this grades the sentence
    itself rather than the packet built from it — and it names the world, which is the
    positive half of the change. The negative half is asserted above, where a regression at
    any other site is also caught.
    """
    sentences = set(worlds.project(WORLD).values())
    manifestation = [line for line in sentences if FORM_OF_THE_RULE in line]
    assert len(manifestation) == 1
    [line] = manifestation
    assert "in the world" in line
    assert "page" not in line.lower()
    assert line.startswith("The form payout_rule takes in the world:")


def test_the_cast_sheet_says_what_a_person_looks_like_not_what_to_write() -> None:
    """The second renderer, and the label's siblings are why `looks like` is the right word.

    Every other line of a sheet names something the person *is* — is, wants, sounds, can do
    what nobody else can, and it costs. `on the page` was the one label that named the
    writer's output instead, and it carried the same field as the sentence above.
    """
    person = characters_mod.cast(WORLD)
    [priya] = [character for character in person if character.subject == "priya"]
    sheet = priya.render()
    assert FORM_OF_THE_PERSON in sheet
    assert "looks like:" in sheet
    assert "on the page" not in sheet.lower()


def test_the_hidden_sections_prohibition_is_not_collateral_damage() -> None:
    """**A section frame may name the page; a fact line may not.** Named so it stays true.

    `context.render`'s hidden block is a signed prohibition — *"never put it on the page"* —
    and it is the one instruction in the packet actively holding material back, which makes
    it the iceberg's ally rather than its cause. A later reader widening §182's rule from
    item text to the rendered document would delete it, so the distinction is asserted rather
    than left to the docstring.
    """
    revision = new_book("book-register", "main", title="Register", scenes=2)
    hidden = canon(
        "payout_rule",
        worlds.CLAIM_CONTENT,
        value="the print has been wrong once and was never corrected",
    )
    packet = assemble(revision, "scene-1", state_records=[*WORLD, hidden])
    document = packet.render()
    assert "never" in document and "on the page" in document
