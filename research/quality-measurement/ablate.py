"""Manufactured ground truth: transformations of published prose whose sign is known.

The refutation ledger's shape is that every label available is contaminated — engagement
tracks cover art, comment counts track archive capture date, declared-AI tracks the year. This
module sidesteps the label problem instead of solving it: take prose that is already published
and already human, damage it in a way whose direction nobody disputes, and ask whether a
candidate metric notices. The pair is **attributed by construction** — you know which of
§1a.3's items you broke — which `plan/craft-corpus.md` §4.5 lists as "genuinely blocked" for
selected pairs and true for it.

**The validity gap, stated first because it is the reason this could be another tricolon.**
A shuffled chapter is not mediocre prose; it is off the distribution of anything a generator
would produce. Sensitivity to an ablation is therefore evidence of sensitivity *in the
direction of* an item, and not evidence that the item's natural variation is detected. Three
things are built in to keep that honest:

- **Dose.** Every degrader takes `strength` in [0,1] and the test is *monotonicity across
  dose*, not detection at strength 1.0. A metric that only fires on a fully-shuffled chapter
  has shown it can detect vandalism.
- **Shams.** `SHAMS` change the text about as much as the degraders and should not move a
  craft metric. A metric that separates sham-from-original as strongly as it separates
  degraded-from-original is detecting *edited-ness*, not damage. This is the direct analogue
  of the era control that killed `tricolon_rate`, and it is the control this module exists to
  make cheap.
- **Length preservation.** Every degrader here is exactly length-preserving in words except
  `sentence_deletion`, which is marked `preserves_length=False` so a caller cannot forget.
  Length is the shallow incumbent that correlates with everything (§1a.1).

Deterministic given a seed, and the seed is derived from the text so the same chapter always
receives the same damage — a re-run that re-rolls its own ablations cannot be compared with
its predecessor.
"""

from __future__ import annotations

import hashlib
import random
import re
from collections.abc import Callable
from dataclasses import dataclass

_SENT = re.compile(r"(?<=[.!?])[\"'”\u2019]*\s+")
_QUOTED = re.compile("[\"“][^\"“”]*[\"”]")
_WORD = re.compile(r"[\w'\u2019-]+", re.UNICODE)

#: Discourse connectives, mapped to one that inverts or flattens the logical relation. Used by
#: `connective_scramble`, the one degrader that changes almost no tokens: it is here to answer
#: "is the metric just noticing that many words moved?" with a damage that moves nine.
_CONNECTIVE_FLIP = {
    "but": "and", "however": "therefore", "although": "because", "though": "since",
    "yet": "so", "instead": "likewise", "despite": "given", "unless": "if",
    "nevertheless": "consequently", "whereas": "while",
}


def paragraphs(text: str) -> list[str]:
    """Split into paragraphs, adapting to which convention the source uses.

    **Written as a function after the naive version silently produced a no-op corpus.** A
    fixed blank-line split is the obvious choice and it is wrong for the largest prose source
    on this machine: Mother of Learning's Wayback export separates paragraphs with a single
    newline, so `\\n\\s*\\n` returned one 6,492-word "paragraph" and every paragraph-level
    ablation became the identity transform. They were then *dropped* by `variants`, which
    correctly refuses to emit an unchanged text as a labelled pair — so the failure showed up
    as two ablations quietly missing from the output rather than as an error. That is the
    shape of bug this whole directory exists to catch, and it is worth a comment that it
    happened here first.
    """
    blocks = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
    if len(blocks) > 1:
        return blocks
    return [line.strip() for line in text.split("\n") if line.strip()]


def _join(blocks: list[str]) -> str:
    return "\n".join(blocks)


def _rng(text: str, salt: str) -> random.Random:
    """Seeded from the text, so damage is a function of the chapter and not of the run."""
    digest = hashlib.sha256(f"{salt}\x00{text}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def _derange(items: list, rng: random.Random) -> list:
    """A permutation with no element left in place, in one pass and without a retry loop.

    **This replaced a `while ...: rng.shuffle(...)` that hung.** "Reshuffle until nothing is
    in its original position" terminates with probability 1 only when the elements are
    distinguishable by position; it does not terminate at all when every candidate reordering
    compares equal to the original. Mother of Learning contains paragraphs that the sentence
    splitter turns into runs of identical pieces — an ellipsis line like ". . . ." splits into
    four copies of "." — and the loop spun forever on the first chapter, producing no output
    and no error. Rotating by a random non-zero offset is a derangement by construction, costs
    one pass, and is deterministic given the seed.

    When `items` has fewer than two entries no derangement exists, and the original is
    returned; `variants` drops an ablation that changed nothing, so the pair is simply not
    emitted rather than being emitted mislabelled.
    """
    if len(items) < 2:
        return list(items)
    offset = rng.randrange(1, len(items))
    return items[offset:] + items[:offset]


def words_of(text: str) -> int:
    return len(text.split())


@dataclass(frozen=True, slots=True)
class Ablation:
    """One transformation, with the claim it licenses.

    `item` is the §1a.3 item this damages, and it is the whole reason to prefer manufactured
    pairs over selected ones: a selected top-decile/bottom-decile pair says "readers converted
    on one and not the other" and is silent about why.

    `sign` is -1 for a degrader and 0 for a sham. There is deliberately no +1: nothing here
    claims to *improve* prose, because §1a.2's measured finding is that models asked to
    improve prose make it worse, and a transformation asserted to be an improvement would be
    exactly the unvalidated claim this module is built to avoid making.
    """

    key: str
    item: int | None
    sign: int
    preserves_length: bool
    apply: Callable[[str, float], str]
    note: str


# ------------------------------------------------------------------ degraders (sign = -1)


def paragraph_shuffle(text: str, strength: float) -> str:
    """Displace a fraction of paragraphs. §1a.3 item 3 — escalation and payoff, destroyed.

    Setup lands after its payoff. Exactly length-preserving: the same paragraphs, reordered.
    """
    blocks = paragraphs(text)
    if len(blocks) < 4 or strength <= 0:
        return text
    rng = _rng(text, "para")
    count = max(2, round(strength * len(blocks)))
    picked = sorted(rng.sample(range(len(blocks)), min(count, len(blocks))))
    # A derangement rather than a shuffle: `random.shuffle` can return the identity on a small
    # selection, which would silently emit an *unablated* text labelled as damaged. Built by
    # rotation rather than by resampling until one appears — a rotation is a derangement by
    # construction, costs one pass, and cannot loop. `_derange` explains why that matters.
    shuffled = _derange(picked, rng)
    out = list(blocks)
    for target, source in zip(picked, shuffled, strict=True):
        out[target] = blocks[source]
    return _join(out)


def sentence_shuffle(text: str, strength: float) -> str:
    """Reorder sentences inside their own paragraph. §1a.3 item 5 — local logic and rhythm.

    Kept inside the paragraph so it damages a different level from `paragraph_shuffle`: a
    metric that responds identically to both is measuring disorder, not narrative structure.
    """
    rng = _rng(text, "sent")
    out = []
    for paragraph in paragraphs(text):
        pieces = _SENT.split(paragraph)
        if len(pieces) < 3 or rng.random() > strength:
            out.append(paragraph)
            continue
        order = _derange(pieces, rng)
        out.append(" ".join(order))
    return _join(out)


def connective_scramble(text: str, strength: float) -> str:
    """Invert discourse connectives. §1a.3 item 5, and the smallest possible edit.

    "but" becomes "and", "however" becomes "therefore". Argument structure is destroyed while
    the token count is unchanged and typically fewer than a dozen words differ. This is the
    degrader that answers the obvious objection to all the others — that a metric is simply
    responding to how much of the text moved.
    """
    rng = _rng(text, "conn")

    def swap(match: re.Match[str]) -> str:
        word = match.group(0)
        replacement = _CONNECTIVE_FLIP.get(word.lower())
        if replacement is None or rng.random() > strength:
            return word
        return replacement.capitalize() if word[:1].isupper() else replacement

    pattern = re.compile(r"\b(" + "|".join(_CONNECTIVE_FLIP) + r")\b", re.IGNORECASE)
    return pattern.sub(swap, text)


def dialogue_flatten(text: str, strength: float) -> str:
    """Strip the quotation marks off dialogue. §1a.3 item 4 — voice, and speaker distinction.

    The words survive; the *rendering* as spoken becomes indirect. Chosen over deleting
    dialogue because deletion changes length, and over model-rewriting it into reported speech
    because that would put a generator inside the ground truth this module is meant to supply.
    """
    rng = _rng(text, "dial")

    def strip(match: re.Match[str]) -> str:
        if rng.random() > strength:
            return match.group(0)
        return match.group(0)[1:-1]

    return _QUOTED.sub(strip, text)


def transplant(text: str, strength: float, *, donor: str = "") -> str:
    """Replace a run of paragraphs with a length-matched run from a different story.

    §1a.3 items 1 and 3 at once — the scene neither belongs to this story nor pays anything
    it set up. The strongest available degrader and the least subtle; it is here mainly as the
    upper anchor of the dose ladder, so a metric that fails to detect *this* is dead.

    Needs a donor and returns the text unchanged without one, rather than raising: a batch that
    runs out of donors should lose this ablation, not the run.
    """
    if not donor or strength <= 0:
        return text
    host = paragraphs(text)
    graft = paragraphs(donor)
    if len(host) < 4 or len(graft) < 2:
        return text
    rng = _rng(text, "graft")
    span = max(1, round(strength * len(host)))
    start = rng.randrange(0, max(1, len(host) - span))
    # Match on words, not on paragraph count, so length stays comparable.
    target_words = sum(words_of(p) for p in host[start : start + span])
    chosen: list[str] = []
    cursor = rng.randrange(len(graft))
    while sum(words_of(p) for p in chosen) < target_words and len(chosen) < len(graft):
        chosen.append(graft[cursor % len(graft)])
        cursor += 1
    return _join(host[:start] + chosen + host[start + span :])


def sentence_deletion(text: str, strength: float) -> str:
    """Delete a fraction of sentences. §1a.3 item 1 — the scene stops doing what it did.

    **The only degrader here that changes length**, which is why it is marked and why a caller
    comparing it against the original owes a length control. Kept because deletion is the
    damage closest to what a summarising generator actually does.
    """
    rng = _rng(text, "del")
    out = []
    for paragraph in paragraphs(text):
        pieces = _SENT.split(paragraph)
        kept = [piece for piece in pieces if rng.random() > strength] or pieces[:1]
        out.append(" ".join(kept))
    return _join(out)


# ---------------------------------------------------------------------- shams (sign = 0)


def rename_entities(text: str, strength: float) -> str:
    """Consistently rename the most frequent capitalised tokens. Should change no quality.

    The primary sham, and the sharpest one for a model-based metric: it moves a large number
    of tokens, wrecks the model's familiarity with a *memorised* published text, and changes
    nothing a reader would call craft. A surprisal-based metric that responds to this as
    strongly as to `paragraph_shuffle` is measuring recall of the training set.
    """
    if strength <= 0:
        return text
    counts: dict[str, int] = {}
    for match in re.finditer(r"\b[A-Z][a-z]{2,}\b", text):
        counts[match.group(0)] = counts.get(match.group(0), 0) + 1
    # Sentence-initial words masquerade as names; requiring several occurrences and skipping
    # the very common ones is crude and adequate for a control.
    candidates = [w for w, n in sorted(counts.items(), key=lambda kv: -kv[1]) if n >= 3][:12]
    if not candidates:
        return text
    rng = _rng(text, "rename")
    pool = [
        "Corwin", "Halvard", "Ysolde", "Bram", "Neriah", "Tolliver", "Ash", "Pell",
        "Vance", "Ottoline", "Ruy", "Sabra", "Emrys", "Talia", "Grieve", "Wren",
    ]
    rng.shuffle(pool)
    count = max(1, round(strength * len(candidates)))
    out = text
    for name, replacement in zip(candidates[:count], pool, strict=False):
        out = re.sub(rf"\b{re.escape(name)}\b", replacement, out)
    return out


def respell(text: str, strength: float) -> str:
    """British/American spelling and quote-style swaps. Should change no quality.

    A second sham with a different footprint from `rename_entities`: it touches many words
    lightly rather than a few words heavily, which separates "responds to token novelty" from
    "responds to entity identity".
    """
    swaps = {
        "colour": "color", "honour": "honor", "armour": "armor", "realise": "realize",
        "realised": "realized", "grey": "gray", "travelled": "traveled", "defence": "defense",
        "practise": "practice", "towards": "toward", "amongst": "among", "learnt": "learned",
        "neighbour": "neighbor", "favourite": "favorite", "recognise": "recognize",
    }
    rng = _rng(text, "spell")

    def swap(match: re.Match[str]) -> str:
        word = match.group(0)
        replacement = swaps.get(word.lower())
        if replacement is None or rng.random() > strength:
            return word
        return replacement.capitalize() if word[:1].isupper() else replacement

    pattern = re.compile(r"\b(" + "|".join(swaps) + r")\b", re.IGNORECASE)
    return pattern.sub(swap, text).replace("“", '"').replace("”", '"')


DEGRADERS = (
    Ablation("paragraph_shuffle", 3, -1, True, paragraph_shuffle,
             "setup lands after payoff; same paragraphs, reordered"),
    Ablation("sentence_shuffle", 5, -1, True, sentence_shuffle,
             "local logic and rhythm destroyed inside each paragraph"),
    Ablation("connective_scramble", 5, -1, True, connective_scramble,
             "argument structure inverted; typically under a dozen tokens differ"),
    Ablation("dialogue_flatten", 4, -1, True, dialogue_flatten,
             "spoken rendering removed; the words survive"),
    Ablation("transplant", 1, -1, True, transplant,
             "a length-matched run from another story; needs a donor"),
    Ablation("sentence_deletion", 1, -1, False, sentence_deletion,
             "the only length-changing degrader; owes a length control"),
)

SHAMS = (
    Ablation("rename_entities", None, 0, True, rename_entities,
             "consistent rename; also the training-set-memorisation control"),
    Ablation("respell", None, 0, True, respell,
             "spelling and quote-style variants; many words touched lightly"),
)

ALL = DEGRADERS + SHAMS
BY_KEY = {ablation.key: ablation for ablation in ALL}

#: The dose ladder. Monotonicity across these is the claim a candidate metric has to support;
#: detection at 1.0 alone is detection of vandalism.
DOSES = (0.0, 0.15, 0.35, 0.65, 1.0)


def variants(text: str, *, donor: str = "", doses: tuple[float, ...] = DOSES):
    """Every (ablation, dose) variant of one text, including the untouched original at 0.0.

    Yields `(key, sign, item, dose, text)`. The original is emitted once rather than once per
    ablation, because a caller scoring it repeatedly would weight it six-fold in any pooled
    statistic — a small bookkeeping error that would look exactly like a real effect.

    **Distinct texts only, and this was measured rather than assumed.** Two doses of the same
    ablation can produce byte-identical output — `respell` runs out of British spellings to
    swap, `connective_scramble` runs out of connectives — and over 30 Mother of Learning
    chapters that happened 31 times in 987 variants. Emitting both would be worse than
    wasteful: `evaluate` counts one paired comparison per variant, so a duplicate is the same
    evidence counted twice, and the Wilson interval it computes would be narrower than the
    evidence supports. Deduplicating is the difference between an honest interval and a
    confident one.
    """
    yield ("original", 0, None, 0.0, text)
    emitted = {text}
    for ablation in ALL:
        for dose in doses:
            if dose == 0.0:
                continue
            if ablation.key == "transplant":
                damaged = transplant(text, dose, donor=donor)
            else:
                damaged = ablation.apply(text, dose)
            if damaged in emitted:
                # Either a no-op at this dose — which is not a labelled pair, and emitting it
                # would put identical texts on both sides of the comparison — or a repeat of a
                # lower dose, which is the same evidence twice.
                continue
            emitted.add(damaged)
            yield (ablation.key, ablation.sign, ablation.item, dose, damaged)


if __name__ == "__main__":
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from corpus_io import mol_chapters

    chapters = mol_chapters()
    host, donor = chapters[10].text, chapters[60].text
    print(f"host: {words_of(host)} words, {len(paragraphs(host))} paragraphs\n")
    print(f"{'ablation':<22} {'dose':>5} {'words':>7} {'Δwords':>7} {'%tokens moved':>14}")
    original_tokens = host.split()
    for key, sign, item, dose, damaged in variants(host, donor=donor):
        delta = words_of(damaged) - words_of(host)
        # Positional token disagreement, not character diff: a single displaced paragraph
        # shifts every later character and makes a character diff saturate at ~100% for every
        # ablation, which is what the first version of this printout reported.
        pairs = list(zip(original_tokens, damaged.split(), strict=False))
        changed = round(
            100.0 * sum(1 for a, b in pairs if a != b) / max(1, len(pairs)), 1
        )
        tag = (
            "sham"
            if sign == 0 and key != "original"
            else ("orig" if key == "original" else f"i{item}")
        )
        print(f"{key:<22} {dose:>5.2f} {words_of(damaged):>7} {delta:>+7} {changed:>8}  {tag}")
