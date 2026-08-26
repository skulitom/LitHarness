"""The book a reader could read instead of ours, and the rule that admits one.

**The operator's direction, 2026-08-25:** *"the readers have a specific amount of currency they
can spend either reading our text or a tantalizing alternative (new provably good overview)"*,
and then the two things that make *provably* mean anything: *"it should be a real listing that is
rated above 4 stars"*, *"which is in our genre"*, and *"it should be a new listing each time"*.

**Why this module exists rather than a string parameter.** §94 measured continuation saturating
at 195 of 196 because continuing was free, and §134 recorded four more rounds at 13/16, 15/16,
15/16, 16/16 and 16/16. `readers._SLOT` answered that with scarcity in the abstract — *"the rest
of the page is full of other people's books"* — and the page stayed empty, because a competitor
nobody names costs nothing to refuse. This is the competitor, named, on the page.

**What makes it provably good is not ours to say.** The rating is the market's own count of what
people did with the book, which is the one kind of quality evidence this project can use without
a validated instrument behind it: it is external, it is behavioural, and no model produced it.
`admit` refuses anything that does not carry one. That is the whole containment — there is no
call anywhere in which a model decides whether the alternative is any good.

**RS1 is kept by the package not knowing where these come from.** Nothing here reads a corpus,
opens a parquet shard or names a source; a `Rival` is a record an operator hands in and this
module either admits or refuses. `tests/test_corpus_leak_audit.py` checks that nothing under
`src/litharness/` references a corpus, and this module is written to keep passing it.

**And a rival may only ever be shown to the measurement pool.** A steering reader's words reach
the writer (§128, `application/readers.py`), so a rival in front of one would put somebody else's
published prose one hop from a prompt. `readers.render_start_request` and `render_choice_request`
already refuse a steering reader; that refusal is now load-bearing for RS1 as well as for the
pool split.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

#: **Above four stars, and "above" is strict.** The operator's words are *"rated above 4 stars"*;
#: a bar written as `>=` would admit exactly-4.0, which is a different sentence. Nothing here
#: interprets the number beyond the comparison — this is not a quality scale this project owns,
#: it is a threshold on somebody else's published figure.
MIN_RATING = 4.0

#: **Ratings are a mean and a mean over three votes is not a rating.** A book with one five-star
#: review clears any threshold, so the count is admitted alongside the score and checked. Twenty
#: is not derived from anything and is written here as the arbitrary floor it is; what it buys is
#: that a rival cannot be a book nobody read.
MIN_RATINGS = 20

#: **The operator's proxy for the count, for the case where the page shows no count.**
#: 2026-08-26: *"we should look for an imprecise number like 4.36 stars, because that implies a
#: lot of views and ratings"*. It is arithmetic rather than intuition — a mean of `n` votes on a
#: five-point scale lands on a value with at most one decimal place only for small or specially
#: composed `n`, so `4.36` cannot come from four raters and `4.5` very easily can.
#:
#: Used **only where a count is absent**, because it is a proxy and the count is the thing. A
#: rival carrying both is judged on the count; a rival carrying neither is refused, since then
#: nothing about it is established and the whole point of this module is that something is.
MIN_DECIMALS = 2

#: **The other kind of evidence, and it exists because the first kind is not available.** The
#: operator asked for a listing *"rated above 4 stars"*; the cached RoyalRoad shards carry
#: `overall_score` as **100% null** — 0 of 2,202 fictions in one shard hold one, the same way
#: `pages` is null and `corpus_io` already records. What the shards do carry is what people did:
#: followers, favourites, views and a ratings count.
#:
#: A following is the same class of evidence as a star average and arguably the closer one to
#: this project's objective — §126's is *fiction a defined audience voluntarily continues and
#: recommends*, and a follower is a reader who chose to be told about the next chapter. So a
#: rival may prove itself either way, and `admit` requires **one** of them rather than both.
#:
#: A thousand is a floor, not a finding. Among genre-tagged fictions in the cached shards the
#: median has **2** followers and the 90th percentile has 92; a thousand is deep into the tail
#: that anybody would call a successful serial. `research/quality-measurement/rival_pool.py`
#: prints the percentile a run's floor corresponds to, so the number here is checkable against
#: the distribution it was chosen from rather than asserted.
MIN_FOLLOWERS = 1000

#: The genres this project's readership reads, which is the same ground `writers.CAST` covers.
#: Membership is checked rather than inferred, and a refusal names the set so an operator can see
#: what to widen. Deliberately not a taxonomy: it is a list of the labels this market uses for
#: the books these readers read, and it has no meaning outside that.
GENRES: frozenset[str] = frozenset(
    {
        "litrpg",
        "progression fantasy",
        "portal fantasy",
        "isekai",
        "cultivation",
        "system apocalypse",
        "reincarnation",
        "dungeon core",
    }
)


class IllegalRival(ValueError):
    """A book this readership may not be asked to choose instead.

    Raised rather than filtered, for `registry.BillingGuardViolation`'s reason: a rival silently
    dropped for a missing rating would leave the screen measuring our book against fewer
    competitors than the operator believed, and a quieter measurement that reads the same is
    the failure this repository keeps finding.
    """


@dataclass(frozen=True, slots=True)
class Rival:
    """One published book, as the reader meets it: a title, a listing, and what it scored.

    `source` is where the row came from and is carried so a reading can be traced back to the
    competitor it was measured against. Nothing here is shown to the reader except `title` and
    `listing` — the rating is admission evidence and never appears on the page, because a reader
    told a book is rated 4.6 is being told the answer.
    """

    title: str
    listing: str
    genre: str
    #: The star average, where one exists. `None` for every row out of the cached shards.
    rating: float | None = None
    #: How many people rated it. `None` where the page did not say, which is the case
    #: `MIN_DECIMALS` exists for.
    ratings: int | None = None
    #: How many people asked to be told when it updates. The evidence a rival carries when it
    #: carries no rating, and the one closer to §126's objective.
    followers: int | None = None
    source: str = ""

    @property
    def rival_id(self) -> str:
        """Content address over what the reader is shown, so a draw is traceable and stable."""
        material = f"{self.title}\x00{self.listing}".encode()
        return f"rv-{sha256(material).hexdigest()[:16]}"

    def render(self) -> str:
        """The competitor as it sits on the page: a title over a blurb, and nothing else."""
        return f"{self.title.strip()}\n\n{self.listing.strip()}"

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "rival_id": self.rival_id,
            "title": self.title,
            "rating": self.rating,
            "ratings": self.ratings,
            "followers": self.followers,
            "genre": self.genre,
            "source": self.source,
        }


def _number(value: Any) -> float | None:
    """A float, or None for anything absent or unreadable. Never a guess."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _count(value: Any, title: str) -> int | None:
    """A whole count, or None when absent. Unreadable is a refusal rather than a zero.

    Zero and absent must not read the same: a book with no followers recorded and a book with
    none are different claims, and only the first is a gap in the data.
    """
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError) as error:
        raise IllegalRival(f"{title!r} carries an unreadable count: {value!r}") from error


def admit(row: Mapping[str, Any]) -> Rival:
    """One admitted rival, or `IllegalRival` naming exactly what failed.

    **Two ways to prove a book, and a row needs one of them.** A star average above `MIN_RATING`
    (with a count above `MIN_RATINGS`, or a score precise enough to imply one — see
    `MIN_DECIMALS`), or a following above `MIN_FOLLOWERS`. The first is what the operator asked
    for and the second is what the corpus has; both are somebody else's record of what readers
    did, and neither is a judgment made here.

    Every check is arithmetic or membership over a supplied record. There is no call in this
    module and nothing that could become one.
    """
    title = str(row.get("title") or "").strip()
    listing = str(row.get("listing") or "").strip()
    genre = str(row.get("genre") or "").strip().casefold()
    if not title or not listing:
        raise IllegalRival("a rival needs a title and a listing; a blank page tempts nobody")
    if genre not in GENRES:
        raise IllegalRival(
            f"{title!r} is filed as {genre!r}, which is not one of {', '.join(sorted(GENRES))}. "
            "A reader who does not read that genre would pass on it for the wrong reason"
        )

    rating = _number(row.get("rating"))
    ratings = _count(row.get("ratings"), title)
    followers = _count(row.get("followers"), title)

    if rating is not None:
        if rating <= MIN_RATING:
            raise IllegalRival(f"{title!r} is rated {rating}, which is not above {MIN_RATING}")
        if ratings is None:
            # No count, so the score's own precision stands in for it: `4.30` and `4.3` are one
            # float and two different claims about how many people voted, so the *string* is
            # what carries the evidence.
            shown = str(row.get("rating"))
            if len(shown.partition(".")[2].rstrip()) < MIN_DECIMALS:
                raise IllegalRival(
                    f"{title!r} is rated {shown} with no count given. A score landing on "
                    f"{MIN_DECIMALS - 1} decimal or fewer is what a handful of votes averages "
                    "to; give the count, or find one rated to two places"
                )
        elif ratings < MIN_RATINGS:
            raise IllegalRival(
                f"{title!r} has {ratings} rating(s) against a floor of {MIN_RATINGS}; a mean "
                "over a handful of votes is not a rating"
            )
    elif followers is None or followers < MIN_FOLLOWERS:
        raise IllegalRival(
            f"{title!r} carries neither a rating above {MIN_RATING} nor {MIN_FOLLOWERS}+ "
            f"followers, so nothing about it is established. A competitor we merely believe "
            "in is one we chose"
        )

    return Rival(
        title=title,
        listing=listing,
        genre=genre,
        rating=rating,
        ratings=ratings,
        followers=followers,
        source=str(row.get("source") or "").strip(),
    )


def admit_all(rows: Sequence[Mapping[str, Any]]) -> tuple[Rival, ...]:
    """Every row, admitted in order. One bad row refuses the pool rather than shrinking it."""
    return tuple(admit(row) for row in rows)


def draw(pool: Sequence[Rival], key: str) -> Rival:
    """One rival for one call, chosen by content rather than by chance.

    **A different competitor every time, which is the operator's direction and is a sampling
    argument rather than a boredom one.** *"it should be a new listing each time, so readers
    don't get bored by reading the same one over and over"* — and these readers cannot be bored,
    because every call is a fresh `claude -p` process with no session persistence and no memory
    of the last one. The reason to rotate anyway is better than the reason given: one fixed
    competitor makes every reading a measurement of our book against **that** book, and its
    particular appeal is then inside every number. Rotating makes it our book against the
    market, which is the comparison worth having.

    **Content-derived rather than random**, for the reason every job id in this system is:
    replays must converge rather than draw again. `key` is expected to carry the reader and the
    passage, so one screen puts several different competitors in front of one book while a
    re-run of that screen puts back the same ones.
    """
    if not pool:
        raise IllegalRival("no rival was admitted, so there is nothing to spend the slot on")
    index = int(sha256(key.encode()).hexdigest(), 16) % len(pool)
    return pool[index]


def ours_first(key: str) -> bool:
    """Which of the two goes on the page first, derived from the same key.

    **Position, not preference, is what an unblinded pairwise choice measures**: §89 clocked the
    verdict channel running 4,676x position over text. Swapping deterministically means the
    order varies across readers and passages, is recorded on the decision, and can be read back
    as a covariate — which is the difference between controlling a confound and hoping it is
    absent.
    """
    return int(sha256(f"order\x00{key}".encode()).hexdigest(), 16) % 2 == 0


__all__ = [
    "GENRES",
    "MIN_DECIMALS",
    "MIN_FOLLOWERS",
    "MIN_RATING",
    "MIN_RATINGS",
    "IllegalRival",
    "Rival",
    "admit",
    "admit_all",
    "draw",
    "ours_first",
]
