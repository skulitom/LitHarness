"""Whether a title is free to use, which is a lookup with an answer and never a judgment.

**Operator direction, 2026-08-25:** *"for titles especially we need some sort of search agent
to make sure the title is permissable to be used"*. A serial platform will not take a title
that collides with a running book, and a title colliding with a well-known one is worse than a
bad title — a reader searching for it finds somebody else's.

**The shape is `world_agent`'s with a different tool.** That module is the pattern this project
already has for a model that acts rather than answers: a `CompletionRequest` carrying a narrow
`allowed_tools` allowance and nothing else. The Architect holds `Bash(litharness world:*)`; this
holds `WebSearch`, and no file access, no shell, no other command.

**What this must never become: a model asked whether a title is good.** §61(5) and §105.1 —
no model ranks or selects among candidates unless the containment for it exists — and
`research/quality-measurement/BRIEF.md` is twenty dead proxies long. The model here is asked one
question of fact: *what published works carry this title*. The word "free" is never in its
answer. `read` derives it in code from exact title matches, so the boolean is arithmetic over
what came back rather than an opinion that came back.

**And the lookup has to have happened.** The one thing that could quietly turn this into
theatre is a model that answers "nothing found" without searching, which reads exactly like a
free title. `searches_reported` counts the transport's own record of web-search calls out of
the raw envelope: a `FREE` verdict is licensed only where the environment says a search was
actually made, and `UNKNOWN` is what an unsearched call gets. That is the same asymmetry
`domain/failures.py` keeps everywhere else — the environment refusing is not a fact about the
work.

**What it does not do, stated so nobody discovers it as a defect.** It does not establish that
a title is legally usable: titles are not copyrightable and this is a discovery-collision check,
not trademark clearance. It matches exactly (case, punctuation and spacing normalised) and
nothing looser, because "close enough to confuse a reader" is a judgment and this module holds
none. And a model can invent a collision that does not exist — which costs a rename, where the
opposite error costs a book published under somebody else's name.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from litharness.domain.generation import CompletionRequest
from litharness.domain.writers import Writer

#: Frozen profile, so the lookup's spend is separable from the writing on the decision rows.
CHECK_PROFILE = "title.availability.v0"

#: The whole allowance. One tool, read-only, and no shell: this role looks things up.
ALLOWED_TOOLS: tuple[str, ...] = ("WebSearch",)

MAX_OUTPUT_TOKENS = 2000

#: Verdicts. Three rather than two, because "nobody looked" must not print as "nothing found".
FREE = "free"
TAKEN = "taken"
UNKNOWN = "unknown"

#: What a lookup is asked to bring back. **No slot for an opinion**: there is no `available`,
#: no `recommended`, no `score`, and no alternative title. A field a model can fill with a
#: verdict is a verdict channel, and §89 measured one of those running 4,676x position over
#: text.
FINDINGS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["searched", "works"],
    "properties": {
        "searched": {
            "type": "array",
            "items": {"type": "string"},
            "description": "The search queries you actually ran, verbatim.",
        },
        "works": {
            "type": "array",
            "description": "Every published work you found carrying this title. Empty if none.",
            "items": {
                "type": "object",
                "required": ["title", "kind", "where"],
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "The work's title exactly as it is published.",
                    },
                    "kind": {
                        "type": "string",
                        "description": "book, web serial, film, game, album, or other.",
                    },
                    "where": {
                        "type": "string",
                        "description": "Author or publisher and where it is published.",
                    },
                    "url": {"type": "string", "description": "A link, if you have one."},
                },
            },
        },
    },
}

#: **Written as a question of fact and checked against every way it could become a judgment.**
#: It asks what exists, never what is advisable; it forbids the two answers that would smuggle
#: an opinion back in (a recommendation, a substitute title); and it says what a near miss is
#: for — reported, so a person can see it, and not counted, because `read` matches exactly.
_TASK = (
    "You are checking whether a title is already in use, for a serial about to be published "
    "on a web-fiction platform.\n"
    "Search the web. Report every published work you find carrying this title — books, web "
    "serials, films, games — with where it is published and a link.\n"
    "Report a title that is nearly the same as a separate entry, with its own title as "
    "published, rather than as this one.\n"
    "Do not say whether the title is good, whether it should be used, or what to call it "
    "instead. You are reporting what exists."
)


def render_check_request(title: str, writer: Writer | None = None) -> CompletionRequest:
    """One lookup for one title.

    **No writer by default, and the parameter exists to be left alone.** A dossier is who is
    writing; this role writes nothing. It is accepted only so that a caller threading one
    writer through a whole loop does not have to special-case this call, and passing one adds
    a novelist's biography to a search — which is why nothing in this package does.
    """
    return CompletionRequest(
        prompt=f"The title to check:\n\n{title.strip()}",
        system=f"{writer.render()}\n\n{_TASK}" if writer is not None else _TASK,
        schema=FINDINGS_SCHEMA,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        profile=CHECK_PROFILE,
        call_class="generation",
        timeout_seconds=600.0,
        allowed_tools=ALLOWED_TOOLS,
    )


_PUNCTUATION = re.compile(r"[^\w\s]", re.UNICODE)
_SPACES = re.compile(r"\s+")


def normalise(title: str) -> str:
    """A title reduced to what a collision is about: the words, in order, and nothing else.

    Case, punctuation and spacing are dropped because `The Cinder Road`, `the cinder road` and
    `The Cinder Road!` are one title on a shelf. Word order and the words themselves are kept,
    because anything past that is a similarity judgment and this module makes none.

    Unicode is folded to NFKD first so a curly apostrophe and a straight one are the same
    title — `clean_title` strips a quotation mark that wraps a title and has no business
    touching one inside it.
    """
    folded = unicodedata.normalize("NFKD", title).casefold()
    return _SPACES.sub(" ", _PUNCTUATION.sub(" ", folded)).strip()


_SEARCH_KEYS = ("websearchrequests", "web_search_requests")


def searches_reported(raw: Any) -> int:
    """How many web searches the transport says were made, from anywhere in its envelope.

    **Deliberately shape-tolerant, and that is the decoupling rather than sloppiness.** The
    number lives in two places in `claude -p`'s JSON — `usage.server_tool_use` and each entry
    of `modelUsage` — and a caller in `application` may not know a provider's envelope layout
    at all (CONTRIBUTING's dependency direction). So this walks whatever it is handed and sums
    every integer under a key with either name, which is true of any envelope that reports the
    fact and returns zero for every envelope that does not.

    Zero therefore means *nobody could see a search happen*, which covers a provider that does
    not report it as well as a model that did not search. Both are `UNKNOWN`, and neither is
    `FREE`.
    """
    total = 0
    if isinstance(raw, Mapping):
        for key, value in raw.items():
            if str(key).lower() in _SEARCH_KEYS and isinstance(value, int):
                total += value
            else:
                total += searches_reported(value)
    elif isinstance(raw, list | tuple):
        for item in raw:
            total += searches_reported(item)
    return total


@dataclass(frozen=True, slots=True)
class Collision:
    """One published work carrying the title, as reported."""

    title: str
    kind: str
    where: str
    url: str

    def render(self) -> str:
        parts = [self.title]
        if self.kind:
            parts.append(f"({self.kind})")
        if self.where:
            parts.append(f"- {self.where}")
        if self.url:
            parts.append(self.url)
        return " ".join(parts)

    def to_jsonable(self) -> dict[str, str]:
        return {"title": self.title, "kind": self.kind, "where": self.where, "url": self.url}


@dataclass(frozen=True, slots=True)
class Availability:
    """What the lookup found, and the verdict code derived from it.

    `verdict` is the only field anything branches on and it is computed in `read`, never read
    off an answer. `near` is everything the lookup returned that is not an exact match: shown
    to a person, counted by nothing.
    """

    title: str
    verdict: str
    collisions: tuple[Collision, ...] = ()
    near: tuple[Collision, ...] = ()
    searched: tuple[str, ...] = ()
    searches: int = 0
    note: str = ""

    @property
    def free(self) -> bool:
        """True only for `FREE`. `UNKNOWN` is not free, which is the whole point of three."""
        return self.verdict == FREE

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "verdict": self.verdict,
            "collisions": [item.to_jsonable() for item in self.collisions],
            "near": [item.to_jsonable() for item in self.near],
            "searched": list(self.searched),
            "searches": self.searches,
            "note": self.note,
        }

    def render(self) -> str:
        head = f"{self.title!r}: {self.verdict}"
        if self.note:
            head += f" ({self.note})"
        lines = [head]
        lines += [f"    collides with {item.render()}" for item in self.collisions]
        lines += [f"    near: {item.render()}" for item in self.near]
        return "\n".join(lines)


def _works(value: Any) -> Iterable[Mapping[str, Any]]:
    if not isinstance(value, list | tuple):
        return ()
    return [item for item in value if isinstance(item, Mapping)]


def _strings(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list | tuple):
        return ()
    return tuple(text for item in value if isinstance(item, str) and (text := item.strip()))


def read(
    title: str, parsed: Mapping[str, Any] | None, *, searches: int = 0, refusal: str = ""
) -> Availability:
    """The verdict, in code, from what a lookup brought back.

    Three ways to land, and the order they are checked in is the safety argument:

    1. **No answer** — the call was refused, or came back malformed. `UNKNOWN`.
    2. **An answer with no search behind it** — `UNKNOWN`, carrying the reason. This is the
       branch that keeps the check honest: a model that says "nothing found" without looking
       is indistinguishable from a free title on the text alone, and the transport's own count
       is what tells them apart.
    3. **An answer with a search behind it** — `TAKEN` when any reported work normalises to
       this title, `FREE` otherwise.

    Everything reported that is *not* an exact match rides along in `near` and changes nothing,
    because deciding that `The Cinder Road` is too close to `Cinder Roads` is a judgment.
    """
    if parsed is None:
        return Availability(title=title, verdict=UNKNOWN, note=refusal or "no answer")

    searched = _strings(parsed.get("searched"))
    found = [
        Collision(
            title=str(item.get("title") or "").strip(),
            kind=str(item.get("kind") or "").strip(),
            where=str(item.get("where") or "").strip(),
            url=str(item.get("url") or "").strip(),
        )
        for item in _works(parsed.get("works"))
    ]
    found = [item for item in found if item.title]
    wanted = normalise(title)
    collisions = tuple(item for item in found if normalise(item.title) == wanted)
    near = tuple(item for item in found if normalise(item.title) != wanted)

    if searches <= 0:
        return Availability(
            title=title,
            verdict=UNKNOWN,
            collisions=collisions,
            near=near,
            searched=searched,
            searches=searches,
            note="no web search was reported, so nothing here was looked up",
        )
    return Availability(
        title=title,
        verdict=TAKEN if collisions else FREE,
        collisions=collisions,
        near=near,
        searched=searched,
        searches=searches,
    )


__all__ = [
    "ALLOWED_TOOLS",
    "CHECK_PROFILE",
    "FINDINGS_SCHEMA",
    "FREE",
    "MAX_OUTPUT_TOKENS",
    "TAKEN",
    "UNKNOWN",
    "Availability",
    "Collision",
    "normalise",
    "read",
    "render_check_request",
    "searches_reported",
]
