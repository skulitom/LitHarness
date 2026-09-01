"""Frozen prompt text and the claim schema for the rejection-optimized critic roster.

Separated from the runner so the bytes a critic sees are readable in one place and a reworded
prompt is visibly a new instrument rather than a silent edit to an old one.

**Two containment rules govern every string in this file.**

1. **No operator quotes (§97.1).** The defect families come from the read-recurrence map, whose
   own header says the family names are ours and the quoted phrases are the operator's, given
   once and not to become prompt text. Only the codes and our own one-line glosses appear
   below. Nothing an operator said about a book is in this file, and nothing may be added.
2. **Critic prose never reaches generation.** These prompts are read by critics and by nothing
   else. No string here is, or may become, an input to drafting, revision, planning or any
   store the writer reads. The runner enforces the same rule structurally by returning a
   record and writing only to the roster file.

The task is the one the direction's amendment named: the strongest case for REJECTION. A
critic is not asked what it thinks of the chapter, is not asked to rate it, and has no way to
express approval — the schema has one field list and it is a list of accusations. That is
deliberate, and it is why a critic's output is not evidence on its own: an agent instructed to
find fault will find fault, so the runner verifies in code what can be verified and lets the
rest evaporate.
"""

from __future__ import annotations

from typing import Any

#: Bump on any change to the bytes below. A roster tally accumulated under one version says
#: nothing about a critic running under another, and `critics.py` refuses to pool them.
ROSTER_VERSION = "critics.v0"

#: The claimable defect families: every code on the read-recurrence map's taxonomy, with our
#: own gloss. `I2` is on the map and is deliberately NOT here — the map records it as a stated
#: preference rather than a defect, and a preference offered to an agent told to reject would
#: come back as a defect every time.
FAMILIES: dict[str, str] = {
    "A1": "system numbers are flat, monotone or absent where the page needs them to move",
    "A2": "no inventory of named abilities the reader can hold in mind",
    "A3": "numbers attached to the wrong referent, counting something that does not matter",
    "A4": "the system is not part of the world; it arrives as noise nobody interacts with",
    "B1": "the opening does not grip, or the hook is somewhere other than the opening",
    "B2": "the protagonist has no exception of their own, and is neither relatable "
          "nor aspirational",
    "B3": "which character the chapter belongs to is unclear",
    "B4": "the premise is one this writer has already written; it converges on itself",
    "B5": "the premise is the genre's default rather than this book's",
    "B6": "the chapter is not the genre it claims",
    "C1": "minutiae and irrelevant detail; the world described onto the page rather than used",
    "C2": "nothing happens; the chapter is stagnant",
    "C3": "narrated rather than present; an observation nobody voices",
    "C4": "too many names and characters for the reader to carry",
    "C5": "information the reader already has, re-established as if new",
    "D1": "paratactic and-chains; clauses strung rather than built",
    "D2": "punctuation and connective tissue failing at the sentence level",
    "D4": "em dashes",
    "E1": "words reaching for an effect the sentence has not earned",
    "E2": "niche, trade or archaic vocabulary with no reason to be on this page",
    "E3": "institutional register: licences, ledgers, charters, taxes",
    "F1": "a figure that fails a literal read; the image does not survive being pictured",
    "G1": "the inference narrated for the reader, or a generic-manner gloss doing the work",
    "G2": "the negative-space tell: describing what a thing is not, or what nobody does",
    "G3": "a tell in the listing, standing on nothing",
    "H1": "the reader's offer is skimped; options presented without deliberation over them",
    "I1": "no interiority",
    "J1": "the chapter does not stand alone; it cannot be understood as read",
    "J2": "a device the reader cannot tell from confusion",
    "K1": "the palette is grey; the light fantasy the genre promises is absent",
    "L1": "internal or schema vocabulary printed on the page",
    "M1": "reading-copy presentation: status line rendering, column width",
}

#: How a claim may cash out, from the direction note's amendment. These three and no others.
CASHABLE = ("mechanical", "gate-checkable", "taxonomy-item")

#: The claim schema, verbatim. Closed on every level: an open schema is how an unfalsifiable
#: field arrives through a side door, and `additionalProperties: false` at both depths is the
#: §69 lesson applied twice.
CLAIM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "family": {"enum": sorted(FAMILIES)},
                    "quote_span": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"},
                            "location": {"type": "string"},
                        },
                        "required": ["text", "location"],
                        "additionalProperties": False,
                    },
                    "claim": {"type": "string"},
                    "cashable_as": {"enum": list(CASHABLE)},
                },
                "required": ["family", "quote_span", "claim", "cashable_as"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["claims"],
    "additionalProperties": False,
}

#: The system block. `{lens}`, `{lens_note}` and `{families}` are the only slots; everything
#: else is fixed across the roster so two critics differ in their lens and in nothing else.
SYSTEM = """You are a hostile reader on a rejection panel for serialised web fiction.

Your lens is {lens}: {lens_note}

You have one job: build the STRONGEST CASE FOR REJECTION of the chapter you are given, from \
your lens and no other. You are not asked whether the chapter is good, you are not asked what \
works, and there is no field in which to say so. Another critic covers every other lens; \
duplicating their ground weakens your case rather than strengthening it.

Every claim you make must be anchored to text you can quote EXACTLY. A claim without a \
verbatim quotation from the chapter is discarded before anyone reads it, so an accusation you \
cannot quote is worse than one you do not make. Quote enough to carry the claim - a full \
clause or sentence, not one or two words.

You may claim only these defect families:

{families}

Each claim declares how it cashes out, and this is checked mechanically afterwards:
  "mechanical"     - a counter run over your quoted span will find the thing you name. Choose \
this only when the span itself contains it; a counter that comes back empty refutes your claim \
and is recorded against you.
  "gate-checkable" - the quotation itself shows the problem to anyone who reads the line.
  "taxonomy-item"  - the span is an instance of the family, argued rather than counted.

Answer with JSON only."""

#: The user turn. `{chapter_id}` and `{chapter}` are its slots; the ceiling on claims is stated
#: in the prompt as well as enforced in parsing, because a roster paid by verified kills has an
#: obvious incentive to flood.
TASK = """Chapter under review ({chapter_id}):

{chapter}

Make the strongest case for rejecting this chapter, from your lens only. At most {max_claims} \
claims, ordered strongest first. Each claim: one family code, one verbatim span quoted exactly \
from the chapter above with its location, one sentence stating the defect, and how it cashes \
out.

Respond with a single JSON object: {{"claims": [...]}}"""

#: Claims accepted per critic per chapter. A ceiling rather than a target: the tally rewards
#: verified kills, so the incentive runs toward volume, and the ceiling is where that stops.
MAX_CLAIMS = 6

#: Tokens for one critic's answer. Six claims with spans is the sizing case.
MAX_TOKENS = 1600


def families_block(codes: tuple[str, ...]) -> str:
    """The family menu for one lens, as the prompt's `{families}` slot."""
    return "\n".join(f"  {code}  {FAMILIES[code]}" for code in codes)


def system_for(lens: str, lens_note: str, codes: tuple[str, ...]) -> str:
    """One critic's system block, fully rendered."""
    return SYSTEM.format(lens=lens, lens_note=lens_note, families=families_block(codes))


def task_for(chapter_id: str, chapter: str, max_claims: int = MAX_CLAIMS) -> str:
    """One critic's user turn over one chapter."""
    return TASK.format(chapter_id=chapter_id, chapter=chapter, max_claims=max_claims)
