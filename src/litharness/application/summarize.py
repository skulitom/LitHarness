"""The producer for `domain/context.py`'s evicted-context slot.

**Why this exists at all, and why it did not before.** The context packet drops the oldest
prose when the budget binds, records the omission, and hands the generator nothing about the
scenes it dropped. That was invisible for as long as this system wrote 172-word scenes:
`plan/stage-0-decisions.md` §47 measured the 6,000-token budget binding at scene 24 at that
length and recorded the eviction counter staying "at zero for every six-scene fixture, which
is exactly why this limit went unnoticed". At the lengths a capable generator writes it binds
around scene five, so a book of any real size was about to be written by a model that could
not see most of it.

**Fielded rather than free-form, and each field written fresh.** The fields are the four
things the packet's other sections cannot carry for an evicted scene — where it happened, who
was in it, what changed, what it left open — and asking for them by name is what stops the
answer being a paragraph of atmosphere. `OPEN` is the field with a ground truth: this project
records `open_threads` as state, so what a summary claims the book still owes can be checked
against what the book *records* it owes rather than taken on trust. `check_open_threads` is
that check.

**Per scene, never a rolling digest of the book.** A rolling summary has to be recomputed
whenever any covered scene is repaired, and it accumulates drift with nothing to compare
against. A per-scene summary is idempotent, addressed by that scene's own content hash, and a
repair invalidates exactly one.

**It is a mechanical call and routes to a local model** (§15): at ~1,000 invocations for a
draft, the CLI adapters' 15-24k-token per-invocation harness tax would dwarf the payload, and
this is the highest-count job class in the system.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from litharness.application.conductor import JobHandler
from litharness.application.ports import SummaryStore, TextGenerator
from litharness.application.repair import SCENE_SUMMARY
from litharness.domain import state as state_mod
from litharness.domain.events import Event
from litharness.domain.generation import PROFILES, CompletionRequest
from litharness.domain.jobs import Job
from litharness.domain.nodes import NodeKind
from litharness.domain.text import content_hash

#: The call class, which is what routes this to a non-billing provider even in production.
CALL_CLASS = "mechanical"

#: Resolves to a greedy sampler: a summary of fixed prose is an extraction, and the same scene
#: should compress the same way twice.
PROFILE = "mechanical"

#: Words. Small on purpose — the whole value of the slot is that a scene costs a fraction of
#: its prose to keep, and a summary that ran long would evict the prose it was meant to spare.
TARGET_WORDS = 60

SUMMARY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["setting", "characters", "events", "open"],
    "properties": {
        "setting": {"type": "string"},
        "characters": {"type": "string"},
        "events": {"type": "string"},
        "open": {"type": "string"},
    },
}


class SummaryInputError(Exception):
    """The job payload does not describe a scene this handler can summarise."""


def _timestamp(now: float) -> str:
    return datetime.fromtimestamp(now, tz=UTC).isoformat().replace("+00:00", "Z")


def render_summary_prompt(text: str, *, open_threads: Sequence[str] = ()) -> tuple[str, str]:
    """(system, prompt) for one scene.

    The fields are asked for by name so the answer is four short statements rather than one
    paragraph of tone, and each is asked for *fresh from the scene* — the instruction that
    keeps the model from treating them as a running log it continues.

    The book's own open threads go in the prompt so the OPEN field has something to notice
    rather than to invent. They are shown, never asserted: a scene that touches none of them
    should say so, and `check_open_threads` reads the answer rather than assuming it.
    """
    system = (
        "You are compressing one scene of a novel so a writer who cannot re-read it still "
        f"knows what it contained. Answer in about {TARGET_WORDS} words in total, as four "
        "fields. State what is on the page and nothing else: no interpretation, no praise, "
        "no guesses about what happens next. Write each field fresh from this scene rather "
        "than continuing anything.\n"
        "SETTING: where and when.\n"
        "CHARACTERS: who was present, by the names the prose uses.\n"
        "EVENTS: what changed. Concrete actions and outcomes, not atmosphere.\n"
        "OPEN: what the scene left unresolved — promises made, questions raised, debts "
        "owed. Say so plainly if it left nothing open."
    )
    owed = ""
    if open_threads:
        owed = "\n\nThe book records these as still owed; note any this scene touches:\n" + (
            "\n".join(f"- {thread}" for thread in open_threads)
        )
    return system, f"The scene:\n\n{text}{owed}"


def flatten(payload: dict[str, object]) -> str:
    """The four fields as the one line the packet renders.

    Flattened at write time rather than at render time, so the stored artifact is the thing
    that goes into the prompt: a summary reassembled differently by each reader is one whose
    effect on the book nobody can reconstruct from the record.
    """
    parts = [
        f"{label} {str(payload.get(key, '')).strip()}"
        for key, label in (
            ("setting", "Setting:"),
            ("characters", "Characters:"),
            ("events", "Events:"),
            ("open", "Left open:"),
        )
        if str(payload.get(key, "")).strip()
    ]
    return " ".join(parts)


def check_open_threads(summary_open: str, threads: Sequence[str]) -> tuple[int, int]:
    """(threads the OPEN field mentions, threads the book records). Advisory.

    **The one field in this artifact with a ground truth**, and the reason a summarizer is
    worth more in this system than in one without a state layer: the book already records
    what it owes, so "did the compression keep the promises" is checkable rather than a
    matter of taste.

    **A majority of the thread's distinctive words, not any one of them.** The first version
    of this asked for a single word over four letters and counted a thread as kept — which
    matched "the sealed letter must be read aloud at the will reading" against a summary
    whose only overlap was the word *aloud*. One shared word between two sentences about a
    book with a consistent register is not evidence of anything, and a coverage number
    inflated that way would be this project's own §2 lesson repeated at a smaller scale: a
    measurement that reports the vocabulary rather than the thing.

    Still crude, and deliberately: a stricter match would need the model to quote the record
    back, which is asking it to copy a string rather than to notice a promise. Advisory and
    never a gate. A scene may legitimately leave open something the extractor never recorded,
    and a thread the book owes that *this scene* did not touch is not an error at all. This
    reports coverage for instrumentation, which is what Stage 3 is for.
    """
    lowered = summary_open.lower()
    mentioned = 0
    for thread in threads:
        distinctive = [word for word in thread.lower().split() if len(word) > 4]
        if not distinctive:
            continue
        hits = sum(1 for word in distinctive if word in lowered)
        if hits * 2 >= len(distinctive):
            mentioned += 1
    return mentioned, len(threads)


def make_summary_handler(
    registry: TextGenerator,
    store: SummaryStore,
    project_id: str,
    *,
    call_class: str = CALL_CLASS,
) -> JobHandler:
    """Build a `JobHandler` that records what one accepted scene contained.

    Returns no events, and that is a decision rather than an omission. A summary is a derived
    read-side artifact: it mutates no manuscript, accepts no candidate, and §19's attribution
    clause — every mutation traceable to a recorded policy decision — does not reach it, so
    minting a decision here would put a row on the record that decided nothing. The store
    write is idempotent on the scene's content hash, which is what makes returning no events
    safe under the replay the Conductor's two-transaction commit allows.
    """

    def handle(job: Job, now: float) -> Sequence[Event]:
        payload = job.payload
        try:
            book_id = str(payload["book_id"])
            branch_id = str(payload["branch_id"])
            revision_id = str(payload["revision_id"])
            logical_id = str(payload["logical_id"])
            expected_hash = str(payload["content_hash"])
        except (KeyError, TypeError) as error:
            raise SummaryInputError(
                f"job {job.job_id} payload lacks book/branch/revision/logical/content_hash: "
                f"{error}"
            ) from error

        revision = store.load_revision(revision_id)
        try:
            node = revision.node(logical_id)
        except KeyError as error:
            raise SummaryInputError(
                f"job {job.job_id} names {logical_id}, which is not in {revision_id[:12]}"
            ) from error
        if node.kind is not NodeKind.SCENE or not node.content:
            raise SummaryInputError(
                f"job {job.job_id} names {logical_id}, which carries no prose to summarise"
            )

        # **The prose has to still be the prose the job was minted for.** A repair landing
        # between the enqueue and the claim leaves a job whose content hash names text that
        # no longer exists, and summarising what is there *now* under that hash would file a
        # new summary at the old scene's address — a summary silently describing different
        # prose than the packet believes it describes. Returning nothing is correct: the
        # repair minted its own summary job for the text it wrote.
        actual = content_hash(node.content)
        if actual != expected_hash:
            return ()

        threads = [
            state_mod.describe(record)
            for record in state_mod.open_threads(store.state_records(book_id, branch_id))
        ]
        system, prompt = render_summary_prompt(node.content, open_threads=threads)
        result, _ = registry.complete(
            CompletionRequest(
                prompt=prompt,
                system=system,
                schema=SUMMARY_SCHEMA,
                profile=PROFILE,
                call_class=call_class,
                sampler=PROFILES[PROFILE],
                max_output_tokens=512,
            )
        )
        if result.parsed is None:
            # A malformed answer is a shape result and earns the ordinary bounded retry. It
            # is not a crisis: a scene with no summary is an eviction with nothing left
            # behind, which is exactly where the packet started.
            raise SummaryInputError(
                f"job {job.job_id}: {result.provider} returned no conforming summary"
            )

        store.record_scene_summary(
            book_id,
            branch_id,
            logical_id,
            content_hash=actual,
            summary=flatten(result.parsed),
            model=result.model,
            profile=PROFILE,
            created_at=_timestamp(now),
        )
        return ()

    return handle


__all__ = [
    "CALL_CLASS",
    "PROFILE",
    "SCENE_SUMMARY",
    "SUMMARY_SCHEMA",
    "TARGET_WORDS",
    "SummaryInputError",
    "check_open_threads",
    "flatten",
    "make_summary_handler",
    "render_summary_prompt",
]
