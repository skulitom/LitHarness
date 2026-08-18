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

#: Horizontal whitespace: any space character that is **not** a newline. Written out because the
#: obvious `\s` is what broke `em_dash_strip` — a transform that tidies the spacing it disturbed
#: must not be able to reach a line boundary while doing it, or it silently reformats the passage
#: and every length-based guard reports that nothing happened. See `em_dash_strip`'s docstring.
_HSPACE = r"[^\S\n]"

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

    def mid_sentence(index: int) -> bool:
        """Whether the match at `index` sits after something other than a sentence break."""
        cursor = index - 1
        while cursor >= 0 and text[cursor] in " \t\n\"'“”\u2018\u2019":
            cursor -= 1
        return cursor >= 0 and text[cursor] not in ".!?…:—"

    # Two checks, because the frequency floor alone does not find names — it *selects*
    # function words, since nothing starts sentences more often than they do. Measured on
    # Mother of Learning chapter 1 before the checks existed, the top-12 "entities" were
    # Zorian, The, You, Mother, Cyoria, Fortov, She, Kirielle, Ilsa, What, There, His — so at
    # every dose the sham rewrote articles and pronouns into names ("Corwin door opened"),
    # which is grammatical damage, the one thing a sham must not inflict. The first CDG
    # battery ran against that version and its rename control moved further than any real
    # degrader. So: a token that also occurs lowercase in this text is sentence
    # capitalisation, not a name ("The", "She"); and a token never seen mid-sentence is a
    # sentence-starter, not a name ("Apparently", a dialogue "Yes") — names get used
    # mid-sentence. The cost is losing a name that doubles as a common noun ("Ash" in a text
    # that mentions ash), which only makes the sham gentler — the safe direction for a
    # control whose contract is "changes no craft".
    counts: dict[str, int] = {}
    seen_mid_sentence: set[str] = set()
    for match in re.finditer(r"\b[A-Z][a-z]{2,}\b", text):
        word = match.group(0)
        counts[word] = counts.get(word, 0) + 1
        if mid_sentence(match.start()):
            seen_mid_sentence.add(word)
    lowercase_forms = {match.group(0) for match in re.finditer(r"\b[a-z]{3,}\b", text)}
    candidates = [
        w
        for w, n in sorted(counts.items(), key=lambda kv: -kv[1])
        if n >= 3 and w in seen_mid_sentence and w.lower() not in lowercase_forms
    ][:12]
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


# ------------------------------------------------- stakes (the persona-reader extension)

#: Words that name a cost. The core of the stake lexicon: what failure would take.
#:
#: **Pruned once already, by inspection, and the pruning is the interesting part.** The first
#: version also carried `break`/`broke`/`broken`, `shatter`, `burn`, `hang`, `collapse` and
#: `hurt`. Printed against Mother of Learning chapter 10, its top-scoring "stake" sentence was
#: *"the shrill whistle of the incoming train broke him out of his concentration"* — `broke`
#: matching a figurative use, in a sentence about nothing being at risk. Those words are too
#: polysemous to carry a cost claim ("broke into a run", "burned with shame", "collapsed into a
#: chair"), and this is the same defect class as `rename_entities`'s stopword bug one function
#: over: a frequency-or-membership selector quietly selecting the wrong grammatical category.
#: The cost of pruning is missing a genuine figurative stake, which only makes the transform
#: gentler — the safe direction for something whose effect is the claim.
_STAKE_COST = frozenset({
    "die", "dies", "died", "dying", "death", "deaths", "dead", "kill", "kills", "killed",
    "killing", "murder", "murdered", "perish", "perished", "execute", "executed",
    "lose", "loses", "lost", "losing", "loss", "ruin", "ruined", "ruins",
    "destroy", "destroyed", "destroys", "destruction", "doomed", "doom",
    "fail", "fails", "failed", "failing", "failure", "starve", "starved", "starving",
    "drown", "drowned", "bleed", "bleeding", "bled", "wound", "wounded", "maimed",
    "debt", "debts", "owe", "owes", "owed", "forfeit", "forfeited",
    "sacrifice", "sacrificed", "betray", "betrayed", "trapped",
    "cost", "costs", "price", "harm", "harmed", "danger", "dangerous",
    "threat", "threatened", "threatens", "risk", "risks", "risked", "risking",
})
#: Words that name irreversibility — but only as an **amplifier**, never a source. A cost that
#: can be undone is a smaller stake than one that cannot, so finality raises a score that
#: already exists; it cannot create one.
#:
#: This too was learned by inspection. The first version treated finality as a source and
#: included `finally`, `always`, `last`, `only` and `final`, which are discourse adverbs and
#: ordinals far more often than they are claims about permanence. Three of the four
#: top-scoring sentences on the chapter above were selected purely by `finally` and `last`.
#: Requiring a cost word before finality counts is what stops the transform from being "delete
#: sentences containing common adverbs".
_STAKE_FINAL = frozenset({
    "never", "forever", "permanent", "permanently", "irreversible", "irrevocably",
    "irreparably", "gone", "unrecoverable",
})
#: The "if X then something bad" shape. Scored as a bonus for co-occurrence rather than on
#: either half alone: `if` is one of the most common words in English and a bare modal says
#: nothing, but the two together in one sentence is the syntax consequence is written in.
_STAKE_CONDITIONAL = frozenset({"if", "unless", "otherwise", "else", "lest", "when"})
_STAKE_MODAL = frozenset({"would", "will", "could", "might", "must", "shall", "may"})


def stake_score(sentence: str) -> int:
    """How much this sentence asserts about the cost of failure. A lexical proxy, and named
    as one.

    **This cannot identify stakes; it identifies stake vocabulary.** Real stakes are semantic
    and often global — a scene can be unbearably tense without a single word from the lists
    above, and "the last light left the window" scores two on pure imagery. A model could do
    better and is disqualified: `dialogue_flatten`'s docstring already refused to put a
    generator inside this module's ground truth, and the same refusal binds here.

    What makes the proxy usable anyway is that it ships with `deplete_matched`, a control that
    deletes the same *number of words* of zero-scoring sentences. If this lexicon is really
    selecting arbitrary sentences, the two transforms move a metric identically and the pair
    reports itself dead. The control is what carries the claim, not the lexicon.

    **A cost word is necessary.** Finality and the conditional-consequence shape only amplify a
    score that a cost word already opened, which is what keeps the transform from degenerating
    into "delete sentences containing `if` or `never`" — see the two lexicon comments above for
    the inspection that forced this structure.
    """
    tokens = [match.group(0).lower() for match in _WORD.finditer(sentence)]
    if not tokens:
        return 0
    cost = sum(1 for token in tokens if token in _STAKE_COST)
    if cost == 0:
        return 0
    present = set(tokens)
    score = cost
    score += min(sum(1 for token in tokens if token in _STAKE_FINAL), 2)
    if present & _STAKE_CONDITIONAL and present & _STAKE_MODAL:
        score += 1
    return score


def _sentences(text: str) -> list[list[str]]:
    return [_SENT.split(block) for block in paragraphs(text)]


def _rebuild(pieces: list[list[str]], drop: set[tuple[int, int]]) -> str:
    kept_blocks = []
    for block_index, sentences in enumerate(pieces):
        kept = [
            sentence
            for sentence_index, sentence in enumerate(sentences)
            if (block_index, sentence_index) not in drop
        ]
        joined = " ".join(piece for piece in kept if piece.strip())
        if joined.strip():
            kept_blocks.append(joined)
    return _join(kept_blocks)


def _stake_plan(text: str, strength: float) -> tuple[set[tuple[int, int]], int]:
    """Which sentences `destake` removes at this dose, and how many words that is.

    Factored out so `deplete_matched` can match the word count exactly rather than
    approximately — a control matched on "roughly as much text" would leave length as the
    difference between the two arms, and length is §1a.1's shallow incumbent.
    """
    if strength <= 0:
        return set(), 0
    pieces = _sentences(text)
    scored = [
        (block_index, sentence_index, stake_score(sentence), len(sentence.split()))
        for block_index, sentences in enumerate(pieces)
        for sentence_index, sentence in enumerate(sentences)
    ]
    staked = [entry for entry in scored if entry[2] > 0]
    if not staked:
        return set(), 0
    budget = strength * sum(entry[3] for entry in staked)
    rng = _rng(text, "destake")
    # Highest-scoring first; the random second key breaks ties deterministically rather than
    # by position, so the transform is not secretly "delete the earliest sentences".
    staked.sort(key=lambda entry: (-entry[2], rng.random()))
    drop: set[tuple[int, int]] = set()
    removed = 0
    for block_index, sentence_index, _score, words in staked:
        if removed >= budget:
            break
        drop.add((block_index, sentence_index))
        removed += words
    return drop, removed


def destake(text: str, strength: float) -> str:
    """Delete the sentences that assert what failure costs. §1a.3 item 1, aimed at stakes.

    The manipulation `plan/persona-reader-validity.md` §5 names first, and the one a persona
    reader is supposed to be uniquely sensitive to: a passage where nothing is at risk should
    read differently to somebody reading *for* risk, and identically to somebody reading for
    prose texture. That per-persona asymmetry is a prediction this transform makes and the
    structural degraders do not.

    Length-changing, and marked so. Its control is `deplete_matched`, which removes the same
    number of words from sentences that scored zero — read the two `per_ablation` rows against
    each other, because the difference between them is the entire claim.
    """
    drop, _removed = _stake_plan(text, strength)
    if not drop:
        return text
    return _rebuild(_sentences(text), drop)


def deplete_matched(text: str, strength: float) -> str:
    """Delete the same word count as `destake`, from sentences that name no cost.

    The control that makes `destake` a claim about stakes rather than about deletion. If a
    metric responds to this as strongly as to `destake`, then `destake`'s effect is the effect
    of removing text, the stake lexicon selected nothing, and the reader-specific reading is
    unsupported — exactly the shape of the `tricolon_rate` failure, where the headline survived
    only until its control was read beside it.

    Selection among zero-scoring sentences is seeded-random rather than positional, so this arm
    does not become "delete the opening" while `destake` deletes from wherever stakes happen to
    sit. Returns the text unchanged when there is not enough zero-scoring material to match the
    budget — `variants` drops an unchanged text rather than emitting a mislabelled pair, so the
    comparison is simply absent for that passage instead of being made against a short measure.
    """
    _drop, target = _stake_plan(text, strength)
    if target <= 0:
        return text
    pieces = _sentences(text)
    neutral = [
        (block_index, sentence_index, len(sentence.split()))
        for block_index, sentences in enumerate(pieces)
        for sentence_index, sentence in enumerate(sentences)
        if stake_score(sentence) == 0 and sentence.strip()
    ]
    if sum(entry[2] for entry in neutral) < target:
        return text
    rng = _rng(text, "deplete")
    rng.shuffle(neutral)
    # Fill under the target in shuffled order, then close the residual with the one remaining
    # sentence nearest to it. A plain "add until `removed >= target`" overshot by 40% at low
    # dose — measured, not feared: stake sentences are sparse (under 3% of sentences on the
    # chapter this was inspected against), so the budget is small and one long neutral sentence
    # blows past it. Length is §1a.1's shallow incumbent, and an arm that deletes half again as
    # much as the arm it controls for differs from it in length as well as in content.
    drop: set[tuple[int, int]] = set()
    removed = 0
    remaining: list[tuple[int, int, int]] = []
    for entry in neutral:
        if removed + entry[2] <= target:
            drop.add((entry[0], entry[1]))
            removed += entry[2]
        else:
            remaining.append(entry)
    if removed < target and remaining:
        residual = target - removed
        best = min(remaining, key=lambda entry: abs(entry[2] - residual))
        drop.add((best[0], best[1]))
    return _rebuild(pieces, drop)


#: Filler clauses for `filler_inject`. Chosen to be grammatical, genre-neutral, and to assert
#: nothing a later sentence could contradict — a filler that introduced a fact would be a
#: continuity edit rather than padding, and the integrity gates would have opinions about it.
_FILLER = (
    "It was not a small thing.",
    "He considered that for a moment.",
    "There was nothing else to say about it.",
    "That was how it went, more or less.",
    "It took a moment to settle.",
    "Nothing about that was simple.",
    "He let the thought finish itself.",
    "It amounted to much the same thing.",
)


def filler_inject(text: str, strength: float) -> str:
    """Pad paragraphs with content-free sentences. §1a.3 item 1, from the opposite direction.

    The protocol's §5 names this and it is the **only manipulation in the set that adds rather
    than removes, reorders or substitutes**, which is the reason to have it: every other degrader
    here takes something away, so a panel that responds to all of them might simply be responding
    to damage-shaped absence. Bloat is the failure mode a serial reader complains about most and
    the one nothing else in this module can produce.

    Length-changing, and in the *opposite* direction from `sentence_deletion` — which is useful,
    because §1a.1's word-count incumbent then has to separate two arms that move length opposite
    ways for the same declared damage direction. A metric riding on length alone cannot do that.

    **The confound this ships with, named rather than controlled away.** Canned sentences are not
    in the passage's voice, so a reader may be responding to "these lines do not belong here"
    rather than to "this is padded" — a style intrusion masquerading as bloat. There is no
    deterministic way to write in-voice filler without a generator, and `dialogue_flatten`'s
    docstring already refused that trade. What makes the confound *checkable* instead is the
    reason codes: padding is the intended response and `flat-voice` is the confound's signature,
    so the interventional test is whether filler-injected variants draw `padding` specifically.
    A run where they draw `flat-voice` has measured the intrusion, not the padding.
    """
    if strength <= 0:
        return text
    blocks = paragraphs(text)
    if not blocks:
        return text
    rng = _rng(text, "filler")
    # One filler sentence per selected paragraph, appended rather than inserted mid-paragraph:
    # a sentence dropped between two others can sever a pronoun from its referent, which is a
    # continuity defect and not the padding this claims to be.
    out = []
    for block in blocks:
        out.append(block)
        if rng.random() <= strength:
            out[-1] = f"{block.rstrip()} {_FILLER[rng.randrange(len(_FILLER))]}"
    return _join(out)


def rewhitespace(text: str, strength: float) -> str:
    """Re-flow whitespace and nothing else. Should change no quality.

    The protocol's second placebo, and a different footprint again from the two existing shams:
    `rename_entities` changes tokens, `respell` changes spellings, this changes not one
    character of any word. A metric that moves on this is responding to layout.
    """
    if strength <= 0:
        return text
    rng = _rng(text, "space")
    blocks = []
    for block in paragraphs(text):
        if rng.random() <= strength:
            block = re.sub(r"[ \t]{2,}", " ", block)
            block = re.sub(r"(?<=[.!?]) (?=[A-Z\"'“])", "  ", block)
        blocks.append(block)
    # Paragraph separator convention is itself whitespace, and `paragraphs` adapts to either.
    separator = "\n\n" if rng.random() <= strength else "\n"
    return separator.join(blocks)


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

#: The stakes extension, kept out of `ALL` on purpose. Adding these to the default set would
#: change the variant schedule every existing caller iterates — `cdg_battery.py`'s recorded
#: numbers are pooled over a particular set of variants, and silently widening it would make a
#: re-run of that battery incomparable with the summary §58 already published. Callers who want
#: these pass `ablations=PERSONA_SET`; everyone else is unaffected.
PERSONA_DEGRADERS = (
    Ablation("destake", 1, -1, False, destake,
             "removes the sentences that assert what failure costs; length-changing"),
    Ablation("deplete_matched", 1, -1, False, deplete_matched,
             "removes the same word count from zero-stake sentences — destake's control"),
    Ablation("filler_inject", 1, -1, False, filler_inject,
             "the only arm that adds words; length-changing upward, unlike every other"),
)
PERSONA_SHAMS = (
    Ablation("rewhitespace", None, 0, True, rewhitespace,
             "layout only; not one character of any word changes"),
)

ALL = DEGRADERS + SHAMS
#: `ALL` plus the stakes extension. The set `persona_battery.py` runs.
PERSONA_SET = DEGRADERS + PERSONA_DEGRADERS + SHAMS + PERSONA_SHAMS
BY_KEY = {ablation.key: ablation for ablation in PERSONA_SET}

#: The dose ladder. Monotonicity across these is the claim a candidate metric has to support;
#: detection at 1.0 alone is detection of vandalism.
DOSES = (0.0, 0.15, 0.35, 0.65, 1.0)


def variants(
    text: str,
    *,
    donor: str = "",
    doses: tuple[float, ...] = DOSES,
    ablations: tuple[Ablation, ...] = ALL,
):
    """Every (ablation, dose) variant of one text, including the untouched original at 0.0.

    `ablations` defaults to `ALL` so every existing caller's schedule is byte-for-byte what it
    was; `PERSONA_SET` adds the stakes extension. It is a parameter rather than a module-level
    switch because two batteries with different sets have to be able to run in one process
    without one of them silently rescheduling the other.

    Yields `(key, sign, item, dose, text)`. The original is emitted once rather than once per
    ablation, because a caller scoring it repeatedly would weight it six-fold in any pooled
    statistic — a small bookkeeping error that would look exactly like a real effect.

    **Distinct texts only, and this was measured rather than assumed.** Two doses of the same
    ablation can produce byte-identical output — `respell` runs out of British spellings to
    swap, `connective_scramble` runs out of connectives — and over 30 Mother of Learning
    chapters that happened 31 times in 987 variants. Emitting both would be worse than
    wasteful: `evaluate` counts one paired comparison per variant, so a duplicate is the same
    evidence counted twice, and the interval it reports would be narrower than the evidence
    supports. Deduplicating is the difference between an honest interval and a confident one.
    """
    yield ("original", 0, None, 0.0, text)
    emitted = {text}
    for ablation in ablations:
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


# ---------------------------------------------- reader-named defects (human read, 2026-08-18)
#
# The first human read of a fully generated book named three defects, and measurement confirmed
# all three: 61 em dashes (5.9 per 1k words), a body-part-to-interiority-verb ratio of 4.56:1,
# and ten `[STATUS]` lines that never move off `Level 2 | HP x/22 | MP ?/? | Gold ?`.
#
# **None of them is a degradation of the text — they are the text.** Every arm above manufactures
# damage by spoiling something good, and the battery validates a panel on telling the spoiled copy
# from the original. A defect present in *both* copies is invisible to that design no matter how
# well the panel scores. These arms exist so the three named defects can at least be manufactured,
# which is the precondition for asking whether any instrument here can see them.
#
# The dual — a transform that *removes* a named defect — is deliberately not an `Ablation`. See
# `em_dash_strip`.

#: The mark itself. Named rather than inlined because the ASCII source of this file is easier to
#: read than a bare glyph, and because the strip and inject arms have to agree exactly.
_EM = "—"

#: Spans where an em dash is structure rather than punctuation: bolded system-voice headers
#: (`**FERROUS GATE — POSTED TOLL**`) and `[STATUS]` lines. Both em-dash arms skip these, and
#: that exclusion is not fastidiousness — it was measured. Without it, stripping turned
#: `**TOLL PAID — 9 days**` into `**TOLL PAID, 9 days**` and `[STATUS] wren — Level 2` into
#: `[STATUS] wren, Level 2`, so a panel preferring the original would have been telling us it
#: liked em dashes *or* that it liked unmangled stat blocks, with no way to separate the two.
#: The human named a prose tell; these lines are not prose.
_PROTECTED = re.compile(r"\*\*[^*\n]*\*\*|^.*\[STATUS\].*$", re.MULTILINE)


def _protected_spans(text: str) -> list[tuple[int, int]]:
    return [(match.start(), match.end()) for match in _PROTECTED.finditer(text)]


def _is_protected(position: int, spans: list[tuple[int, int]]) -> bool:
    return any(start <= position < end for start, end in spans)


#: Verbs that report an inner state rather than an observable one. Same list the read-defect
#: measurement used, so the arm removes exactly what was counted.
_INTERIOR = re.compile(
    r"\b(?:thought|realised|realized|wondered|remembered|felt|knew|hoped|feared|wanted|"
    r"decided|understood|noticed|hated|loved|regretted)\b",
    re.IGNORECASE,
)


def em_dash_inject(text: str, strength: float) -> str:
    """Replace a fraction of comma joins with spaced em dashes. The named tell, manufactured.

    Word-count-changing by exactly one token per replacement, which is why `preserves_length` is
    False on its `Ablation` — a spaced em dash is its own `split()` token and an unspaced one
    welds two tokens into one, so there is no substitution that leaves the count alone. On a
    ~1,000-word scene at full dose this is well under one percent, and the arm reports its own
    delta rather than asking anyone to assume that.

    Only comma joins are targeted. Replacing a period would change sentence count, which is a
    different manipulation wearing this one's name.
    """
    if strength <= 0 or ", " not in text:
        return text
    spans = _protected_spans(text)
    spots = [
        match.start() for match in re.finditer(r", ", text)
        if not _is_protected(match.start(), spans)
    ]
    if not spots:
        return text
    rng = _rng(text, "emdash-in")
    count = max(1, round(strength * len(spots)))
    chosen = set(rng.sample(spots, min(count, len(spots))))
    out = []
    index = 0
    while index < len(text):
        if index in chosen and text.startswith(", ", index):
            out.append(f" {_EM} ")
            index += 2
        else:
            out.append(text[index])
            index += 1
    return "".join(out)


def em_dash_strip(text: str, strength: float) -> str:
    """Replace em dashes with the comma they are standing in for. **Not an `Ablation`.**

    This is the dual of `em_dash_inject` and it is deliberately kept out of every registry in
    this module, because the `Ablation` contract says `sign` is -1 for a degrader and 0 for a
    sham with *no* +1 — nothing here claims to improve prose, on §1a.2's measured finding that
    models asked to improve prose make it worse. That prohibition is right and this function does
    not challenge it: it makes no claim about quality at all. It applies one mechanical
    substitution in the direction a named human said they wanted, and whether a panel agrees with
    that human is the question, not the assumption.

    Keeping it out of the registries is load-bearing rather than tidy. `evaluate.evaluate`
    partitions arms into degraders and shams by `sign` and multiplies every per-arm delta by the
    metric's expected `direction`; an arm whose expected direction is the opposite would report
    `hit_rate` and `dose_rho` backwards while looking exactly like every other row. So the repair
    direction is read through an explicit pairwise comparison where the orientation is written
    down, and never through machinery that assumes damage.

    A spaced em dash is doing a comma's work with more emphasis, so a comma is grammatical
    wherever it sat — except where the dash joined two independent clauses, which yields a comma
    splice. `em_dash_report` counts those rather than this docstring waving them away.

    **This function reformatted the whole passage until 2026-08-18, and that defect produced
    §74's headline number.** The tail was `re.sub(r"\\s+", " ", ...)`, and `\\s` matches newlines,
    so every blank line in the text collapsed to a single space: on the ten drafted scenes it took
    the newline count from 858 to 90 — the 90 being scene 7, which contains no em dash and returns
    early — and the paragraph count from 420 to 45. Nine of ten "em-dash-stripped" variants were
    the entire scene run together as one block. All 72 cached `em_dash_strip` comparisons were
    verified to carry that flattened text by rebuilding their request digests, so the panel's
    0.0417 was a preference for a paragraphed text over an unparagraphed one and never a verdict
    about the mark. Both whitespace patterns are now horizontal-only (`[^\\S\\n]`), which is why
    the match cannot cross a line boundary either: a dash sitting at a line start used to consume
    the newline before it and replace it with ", ".

    **The reason no guard caught it is worth keeping.** `em_dash_report` counts em dashes, words
    and comma splices, and `str.split()` treats "\\n\\n" and " " identically, so `word_delta_pct`
    read -0.30% while all the paragraphing was gone. A length invariant cannot see a layout
    change, so it needs an invariant of its own. `tests/test_ablate_structure.py` is that
    invariant: `test_em_dash_strip_preserves_paragraph_structure` asserts this function's layout
    exactly, and `test_no_transform_collapses_a_passage_to_one_block` bans the class across every
    registered arm.
    """
    if strength <= 0 or _EM not in text:
        return text
    spans = _protected_spans(text)
    pattern = rf"{_HSPACE}*{_EM}{_HSPACE}*"
    spots = [
        match.start() for match in re.finditer(pattern, text)
        if not _is_protected(match.start(), spans)
    ]
    if not spots:
        return text
    rng = _rng(text, "emdash-out")
    count = max(1, round(strength * len(spots)))
    chosen = set(rng.sample(spots, min(count, len(spots))))
    out: list[str] = []
    last = 0
    for match in re.finditer(pattern, text):
        if match.start() not in chosen:
            continue
        out.append(text[last : match.start()])
        # A dash that already follows punctuation needs no comma of its own, and a dash that ends
        # a line is a cut-off rather than a join — neither takes the substitution.
        preceding = text[: match.start()].rstrip()
        out.append(" " if preceding.endswith((",", ";", ":", ".", "!", "?")) else ", ")
        last = match.end()
    out.append(text[last:])
    return re.sub(rf"{_HSPACE}+", " ", "".join(out)).replace(" ,", ",").strip()


def em_dash_report(original: str, stripped: str) -> dict[str, float]:
    """What the substitution actually did, including the grammar it may have broken.

    Reported beside any result that uses `em_dash_strip`, because "the panel preferred the
    repaired text" and "the panel preferred the text with fewer comma splices in it" are
    different findings and only one of them is about em dashes.
    """
    splices = len(re.findall(r",\s+(?:he|she|they|it|the|there|that)\s+\w+ed\b", stripped))
    before = len(re.findall(_EM, original))
    return {
        "em_dashes_before": before,
        "em_dashes_after": len(re.findall(_EM, stripped)),
        "words_before": len(original.split()),
        "words_after": len(stripped.split()),
        "word_delta_pct": round(
            100.0 * (len(stripped.split()) - len(original.split())) / max(len(original.split()), 1),
            3,
        ),
        "possible_comma_splices": splices,
    }


def _interiority_plan(text: str, strength: float) -> tuple[set[tuple[int, int]], int]:
    """Which sentences report an inner state, and how many words removing them costs.

    Factored out for the same reason `_stake_plan` is: `deplete_matched` can then match this
    arm's word count exactly, so "the panel noticed the interiority went" is separable from
    "the panel noticed text went".
    """
    if strength <= 0:
        return set(), 0
    pieces = _sentences(text)
    inner = [
        (block_index, sentence_index, len(_INTERIOR.findall(sentence)), len(sentence.split()))
        for block_index, sentences in enumerate(pieces)
        for sentence_index, sentence in enumerate(sentences)
        if _INTERIOR.search(sentence)
    ]
    if not inner:
        return set(), 0
    budget = strength * sum(entry[3] for entry in inner)
    rng = _rng(text, "interior")
    inner.sort(key=lambda entry: (-entry[2], rng.random()))
    drop: set[tuple[int, int]] = set()
    removed = 0
    for block_index, sentence_index, _hits, words in inner:
        if removed >= budget:
            break
        drop.add((block_index, sentence_index))
        removed += words
    return drop, removed


def interiority_strip(text: str, strength: float) -> str:
    """Delete the sentences that report what a character thought, knew, or felt.

    The second named defect, manufactured: prose that describes a body instead of inhabiting a
    mind. Its control is `deplete_matched`, exactly as `destake`'s is — read the two rows against
    each other, because a panel that responds to this as hard as to matched deletion has
    responded to deletion.

    Aimed at the same measurement that found the defect: 82 body-part nouns against 18
    interiority verbs in the drafted book, a 4.56:1 ratio. At full dose this arm drives that
    ratio to infinity, which is the extreme the real text is already most of the way toward.
    """
    drop, _removed = _interiority_plan(text, strength)
    if not drop:
        return text
    return _rebuild(_sentences(text), drop)


def stat_flatten(text: str, strength: float) -> str:
    """Blank the varying values in system-voice stat blocks. Near-null on the book that named it.

    Kept, and kept honest about being nearly a no-op here: the drafted book's stat lines are
    *already* flat — `Level 2 | HP x/22 | MP ?/? | Gold ?` in all ten, with only HP moving — so
    this arm has almost nothing left to flatten. It manufactures the defect in text that does not
    already have it, which is what makes it usable against published LitRPG, and against this
    book it is expected to read as a near-null for a reason that is a finding rather than a bug.
    """
    if strength <= 0:
        return text
    rng = _rng(text, "statflat")
    def blank(match: re.Match[str]) -> str:
        return match.group(0) if rng.random() > strength else f"{match.group(1)} ?"
    return re.sub(r"\b(HP|MP|Gold|Level|XP|Stamina)\s+[\d/?]+", blank, text)


#: The reader-named arms, kept out of `ALL` and out of `PERSONA_SET` for the reason
#: `PERSONA_DEGRADERS` gives: widening a set that recorded batteries pooled over would make a
#: re-run incomparable with the summary already published. Callers who want these pass
#: `ablations=READER_DEFECT_SET`.
READER_DEFECT_DEGRADERS = (
    Ablation("em_dash_inject", None, -1, False, em_dash_inject,
             "the named surface tell, manufactured; one token per replacement"),
    Ablation("interiority_strip", None, -1, False, interiority_strip,
             "removes the sentences that report an inner state; deplete_matched is its control"),
    Ablation("stat_flatten", None, -1, True, stat_flatten,
             "blanks varying stat values; near-null on a book whose stats are already flat"),
)

#: The reader-defect battery: the three new degraders, the matched-deletion control that makes
#: `interiority_strip` a claim about interiority, and the layout sham that bounds every arm.
READER_DEFECT_SET = (
    *READER_DEFECT_DEGRADERS,
    BY_KEY["deplete_matched"],
    BY_KEY["rewhitespace"],
)
