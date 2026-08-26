"""blurb_rewrite.v0 — make the reader produce, not judge, and measure the diff in code.

`plan/blurb-rewrite-validity.md` is the registration; this module carries the frozen bytes and
every registered definition. Read that first.

**The idea, from the handoff's task 1.** A model's *generative* fluency is reliable where its
*critical* judgment is blind: it will rarely write "a patch of notes", even though it cannot
reliably flag one. So the reader is never asked to judge. It is given a listing and one of that
listing's sentences, and asked to **write that sentence as it would be written**. Where the
rewrite silently repairs a phrase, the phrase was off; where it echoes, it was not. The
measurement is the diff, computed in code — no verdict slot, nothing rated, nothing ranked,
which is what makes it admissible where every verdict channel died (§89, §97.4).

**The reader is never told anything is wrong.** The ask is *"write this the way it would be
written"*, not *"fix this"*; the system prompt and the ask are byte-frozen below and neither
contains fix/improve/polish/wrong/judge vocabulary. The reply is a bare sentence — no schema —
and is consumed by the scorers only; nothing a model wrote here reaches a prompt (§97.1).

**Results carry no third-party prose.** For pool texts the committed record carries digests,
token offsets and counts only — never a market sentence or span text. Span TEXT is stored only
for our own listings (`--texts`). This is enforced in code, not by care: prose fields exist
only behind `allow_prose=True`, and every pool-sourced row is built with the default.

Free legs first; the paid run is refused twice over (once without `--yes`, and even with it
until the operator's gate flag is passed, because the first paid run is the operator's gate):

    uv run python research/quality-measurement/blurb_rewrite.py --selftest
    uv run python research/quality-measurement/blurb_rewrite.py --dry-run
    uv run python research/quality-measurement/blurb_rewrite.py --run --yes
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import random
import re
import statistics
import sys
from itertools import chain, combinations
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent / "src"))

import blurb_gradient  # noqa: E402
import listing_arena  # noqa: E402
import reader_transport  # noqa: E402

from litharness.domain.generation import CompletionRequest  # noqa: E402
from litharness.providers import build_default_registry  # noqa: E402

RESULTS = HERE / "results"
DERIVED = HERE / "derived"

# ---------------------------------------------------------------- the registration, frozen

BLURB_REWRITE_VERSION = "blurb_rewrite.v0"

#: **Byte-frozen.** The reader is a writer here, and is told nothing about any sentence being
#: right, wrong or improvable. No verdict word appears anywhere in these bytes.
SYSTEM = (
    "You write listings for serial fiction on this market. "
    "Reply with a single sentence and nothing else."
)

#: **Byte-frozen.** The title, a blank line, the full listing, then the sentence and the ask.
#: "Write that sentence as it would be written" — never fix, improve or polish.
ASK = (
    "{title}\n\n{listing}\n---\nSentence {k} of this listing:\n{sentence}\n\n"
    "Write that sentence as it would be written in a listing in this market."
)

#: Draws per sentence. The comic-beat census measured a one-draw locator at 0.54 reliability;
#: four draws is §124's lesson applied, inherited byte for byte in spirit from anticipation.
K_DRAWS = 4

#: A sentence fits comfortably; nothing here needs room to explain itself.
MAX_OUTPUT_TOKENS = 256

REWRITE_PROFILE = "reader.rewrite.v0"
CALL_CLASS = "generation"

#: **Stable repairs**: original-side spans changed in at least this many of the K draws. Three
#: of four is the registered vote; fewer is paraphrase jitter, not a located diagnostic.
STABLE_THRESHOLD = 3

#: Refuse above this many calls without --yes.
CALL_GUARD = 1_000

#: The pair-bootstrap behind KG's interval. Seeded, so the interval is reproducible.
BOOTSTRAP_DRAWS = 2_000
BOOTSTRAP_SEED = 20260826

PRE_REGISTRATION: dict[str, Any] = {
    "version": BLURB_REWRITE_VERSION,
    "system": SYSTEM,
    "ask": ASK,
    "k_draws": K_DRAWS,
    "max_output_tokens": MAX_OUTPUT_TOKENS,
    "profile": REWRITE_PROFILE,
    "call_class": CALL_CLASS,
    "stable_threshold": STABLE_THRESHOLD,
    "call_guard": CALL_GUARD,
    "bootstrap_draws": BOOTSTRAP_DRAWS,
}


def registration_digest() -> str:
    material = json.dumps(PRE_REGISTRATION, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def render_ask(title: str, listing: str, k: int, sentence: str) -> str:
    """The frozen ask, rendered. Nothing may be appended, softened or explained."""
    return ASK.format(title=title.strip(), listing=listing.strip(), k=k, sentence=sentence)


def build_request(prompt: str) -> CompletionRequest:
    """One measurement call: no schema — the reply is a sentence, not a record.

    Handed to `reader_transport.completer` as the registry reader's request constructor, so
    the seam cannot rebuild (and so drift from) these bytes: `--reader registry` sends
    exactly this and nothing else.
    """
    return CompletionRequest(
        prompt=prompt,
        system=SYSTEM,
        schema=None,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        profile=REWRITE_PROFILE,
        call_class=CALL_CLASS,
        timeout_seconds=300.0,
    )


# ------------------------------------------------------------------------------- the scorers


#: An ender (. ! ?) followed by a space or newline is a sentence boundary. Abbreviation
#: false-splits stay false-splits — blurbs are 40-146 words and simplicity beats cleverness;
#: the limitation is documented in the registration rather than patched with a clever list.
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def sentences(text: str) -> list[str]:
    """The listing's sentences, whitespace-collapsed, in order.

    Deliberately naive: any `.`, `!` or `?` followed by whitespace ends a sentence, so
    "Mr. Wu" splits and an ellipsis that touches the next word splits. Keeping the
    false-splits as they fall is registered behaviour, not an oversight.
    """
    stripped = text.strip()
    if not stripped:
        return []
    return [" ".join(piece.split()) for piece in _SENTENCE_END.split(stripped) if piece.strip()]


_QUOTES = "\"“”‘’«»'"  # noqa: RUF001 — the curly quotes are the point; they get stripped
_ECHO = re.compile(r"^\s*sentence\s*\d+\s*[:.\-—]*\s*", re.IGNORECASE)


def normalise(reply: str) -> str:
    """Collapse whitespace, strip surrounding quotes, drop a leading "Sentence k:" echo."""
    text = " ".join(reply.split()).strip()
    while len(text) >= 2 and text[0] in _QUOTES and text[-1] in _QUOTES:
        text = text[1:-1].strip()
    return _ECHO.sub("", text).strip()


_WORD = re.compile(r"[a-z0-9']+")


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens; the unit every span offset counts."""
    return _WORD.findall(text.lower())


def span_diff(original: str, rewrite: str) -> tuple[float, list[tuple[int, int]]]:
    """`(change_rate, changed_spans)` on lowercase word tokens.

    `change_rate = 1 - (matched original tokens / original tokens)`; `changed_spans` are the
    original-side token-offset half-open spans of the replace/delete opcodes. Deterministic,
    in code — no model ever says how much changed.
    """
    left, right = tokenize(original), tokenize(rewrite)
    matcher = difflib.SequenceMatcher(None, left, right, autojunk=False)
    matched = sum(block.size for block in matcher.get_matching_blocks())
    rate = 1.0 - matched / len(left) if left else 0.0
    changed = [
        (a1, a2)
        for tag, a1, a2, _b1, _b2 in matcher.get_opcodes()
        if tag in ("replace", "delete")
    ]
    return rate, changed


def merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Sort and merge overlapping-or-touching half-open spans."""
    merged: list[list[int]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(start, end) for start, end in merged]


def stable_repairs(
    draws_spans: list[list[tuple[int, int]]],
    n_tokens: int,
    threshold: int = STABLE_THRESHOLD,
) -> list[tuple[int, int]]:
    """Original-side token positions changed in >= threshold draws, merged into spans.

    Voting is per token: a position counts every draw whose changed spans cover it, positions
    reaching the threshold are kept, and contiguous kept positions merge — so overlapping
    spans from different draws coalesce into the one located repair.
    """
    hits = [0] * n_tokens
    for spans in draws_spans:
        for start, end in set(spans):
            for position in range(start, min(end, n_tokens)):
                hits[position] += 1
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for position, count in enumerate([*hits, 0]):
        if count >= threshold and start is None:
            start = position
        elif count < threshold and start is not None:
            runs.append((start, position))
            start = None
    return runs


def _changed_token_set(spans: list[tuple[int, int]]) -> frozenset[int]:
    return frozenset(chain.from_iterable(range(start, end) for start, end in spans))


def _jaccard(left: frozenset[int], right: frozenset[int]) -> float:
    if not left and not right:
        return 1.0  # both draws echoed the sentence: perfect agreement, trivially
    union = left | right
    return len(left & right) / len(union) if union else 1.0


def draw_agreement(draws_spans: list[list[tuple[int, int]]]) -> float | None:
    """KP's within-sentence number: mean pairwise Jaccard of the draws' changed-token sets."""
    sets = [_changed_token_set(spans) for spans in draws_spans]
    if len(sets) < 2:
        return None
    pairs = list(combinations(sets, 2))
    return statistics.fmean(_jaccard(a, b) for a, b in pairs)


# ------------------------------------------------------------------------ the report builders


def sentence_report(
    index: int, original: str, replies: list[str | None], *, allow_prose: bool = False
) -> dict[str, Any]:
    """One sentence over its K draws.

    **`allow_prose` defaults to False and stays False for every pool-sourced row** — the
    committed record then carries offsets and numbers and no market sentence, no span text.
    Our own listings (`--texts`) pass True, because their prose is ours to commit.

    **A failed draw is excluded, never scored** (the registration's transport rule): an empty
    reply diffed against the original would read as maximal repair, so a `None` or empty
    reply leaves every rate and is counted in `failed_draws` instead.
    """
    normed = [normalise(reply) for reply in replies if reply]
    failed = len(replies) - len(normed)
    diffs = [span_diff(original, reply) for reply in normed]
    rates = [diff[0] for diff in diffs]
    spans = [diff[1] for diff in diffs]
    tokens = tokenize(original)
    row: dict[str, Any] = {
        "sentence": index,
        "tokens": len(tokens),
        "draws": len(normed),
        "failed_draws": failed,
        "rates": rates,
        "mean_change_rate": statistics.fmean(rates) if rates else 0.0,
        "changed_spans": spans,
        "stable_repairs": stable_repairs(spans, len(tokens)),
    }
    if allow_prose:
        row["original"] = original
        row["rewrites"] = normed
        row["stable_text"] = [
            " ".join(tokens[start:end]) for start, end in row["stable_repairs"]
        ]
    return row


def listing_report(
    name: str,
    title: str,
    body: str,
    replies_by_sentence: list[list[str]],
    *,
    source_kind: str,
    followers: int | None = None,
    allow_prose: bool = False,
) -> dict[str, Any]:
    """One listing: per-sentence rows plus the mean of the sentences' mean change rates."""
    bodies = sentences(body)
    rows = [
        sentence_report(k, sent, replies_by_sentence[k - 1], allow_prose=allow_prose)
        for k, sent in enumerate(bodies, start=1)
    ]
    report: dict[str, Any] = {
        "name": name,
        "kind": source_kind,
        "digest": listing_arena.digest_of(body),
        "words": len(body.split()),
        "sentence_count": len(rows),
        "mean_change_rate": (
            statistics.fmean(row["mean_change_rate"] for row in rows) if rows else 0.0
        ),
        "sentences": rows,
    }
    if followers is not None:
        report["followers"] = followers
    if allow_prose:
        report["title"] = title
        report["listing"] = body
    return report


# ------------------------------------------------------- the controls: each one is a kill


def fixed_point_summary(round1: list[float], round2: list[float]) -> dict[str, Any]:
    """KF, reported as distributions and never as a bar.

    Direction: round 2 — the model asked to rewrite its own rewrite — should sit materially
    below round 1 on the same sentences. If it does not, the diff is paraphrase noise rather
    than repair and the instrument is dead. "Materially" is a direction plus these
    distributions; the registration refuses to fit it to a number.
    """
    paired = [
        (first, second)
        for first, second in zip(round1, round2, strict=True)
        if second == second  # a refused round-2 ask is missing, not zero
    ]
    if not paired:
        return {"pairs": 0}
    return {
        "pairs": len(paired),
        "round1_mean": statistics.fmean(first for first, _ in paired),
        "round2_mean": statistics.fmean(second for _, second in paired),
        "deltas": [second - first for first, second in paired],
        "share_round2_below": sum(second < first for first, second in paired) / len(paired),
    }


def gradient_stat(
    pairs_low_high: list[tuple[float, float]],
    *,
    draws: int = BOOTSTRAP_DRAWS,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    """KG: the share of length-matched pairs where the LOW listing needed more repair.

    Statistic and interval only — the direction (LOW above HIGH) is the registration's, the
    pair-bootstrap interval is the uncertainty, and nothing here is a bar. Until LOW sits
    clearly above HIGH, nothing this instrument says about our own listings is believed.
    """
    if not pairs_low_high:
        return {"pairs": 0}
    wins = sum(low > high for low, high in pairs_low_high)
    rng = random.Random(seed)
    n = len(pairs_low_high)
    boots: list[float] = []
    for _ in range(draws):
        sample = (pairs_low_high[rng.randrange(n)] for _ in range(n))
        boots.append(sum(low > high for low, high in sample) / n)
    boots.sort()
    lo = boots[int(0.025 * draws)]
    hi = boots[min(int(0.975 * draws), draws - 1)]
    return {
        "pairs": n,
        "wins": wins,
        "share": wins / n,
        "bootstrap_interval": [lo, hi],
        "per_pair_delta": [low - high for low, high in pairs_low_high],
    }


def length_correlation(rates: list[float], lengths: list[int]) -> float | None:
    """KL: Pearson's r between a sentence's change_rate and its token length.

    Reported whatever its size; a strong dependence is named in the results, because a
    gradient that is really about sentence length has been seen here before — §141's reason
    for matching pairs by word count.
    """
    if len(rates) != len(lengths) or len(rates) < 3:
        return None
    try:
        return statistics.correlation(rates, lengths)
    except statistics.StatisticsError:
        return None


def draw_reliability(within: list[float], between: list[float]) -> dict[str, Any]:
    """KP in the gate-0 shape: within-sentence across-draw agreement against the between
    contrast, because reliability without the between contrast is the trap a constant
    scorer passes perfectly."""
    return {
        "within_mean": statistics.fmean(within) if within else None,
        "between_mean": statistics.fmean(between) if between else None,
        "sentences": len(within),
    }


# --------------------------------------------------------------------------------- selftest


def selftest() -> int:
    """The scorers against built-in fixtures whose values were derived by hand."""
    failures: list[str] = []

    blurb = "Renn counted the seals twice. The tower was empty. He climbed anyway."
    if sentences(blurb) != [
        "Renn counted the seals twice.",
        "The tower was empty.",
        "He climbed anyway.",
    ]:
        failures.append("three-sentence blurb did not split into its three sentences")
    if sentences("Only one sentence lives here.") != ["Only one sentence lives here."]:
        failures.append("a single sentence must come back alone")
    if sentences("It kept falling...") != ["It kept falling..."]:
        failures.append("a trailing ellipsis must stay one sentence")
    if sentences("It kept falling... Then silence.") != ["It kept falling...", "Then silence."]:
        failures.append("an ellipsis followed by space must split")
    if sentences("") != []:
        failures.append("empty text must yield no sentences")

    if normalise('  "A patch of notes lined the shelf."  ') != (
        "A patch of notes lined the shelf."
    ):
        failures.append("surrounding quotes must be stripped")
    if normalise("Sentence 12: He took the stairs.") != "He took the stairs.":
        failures.append("a leading Sentence-k echo must be dropped")

    echo = "He found a patch of notes on the desk."
    if span_diff(echo, echo) != (0.0, []):
        failures.append("an exact echo must diff to rate 0.0 with no changed spans")

    rate, spans = span_diff("the ward held firm", "the ward gave way")
    if abs(rate - 1 / 2) > 1e-9 or spans != [(2, 4)]:
        failures.append("two-token replace must give rate 1/2 and the span (2, 4)")

    merged = stable_repairs([[(2, 6)], [(2, 6)], [(4, 8)], []], 10)
    if merged != [(4, 6)]:
        failures.append("overlapping spans from three draws must merge to one stable repair")
    if stable_repairs([[(0, 2)], [(0, 2)]], 10) != []:
        failures.append("two of four draws must not reach the stability threshold")

    row = sentence_report(1, "A patch of notes lined the desk.", ["A ledger filled the desk."])
    blob = json.dumps(row)
    if "patch" in blob or "notes" in blob or "ledger" in blob:
        failures.append("a pool-sourced row leaked prose")

    dropped = sentence_report(1, "The ward held firm.", ["The ward gave way.", None, ""])
    if dropped["draws"] != 1 or dropped["failed_draws"] != 2:
        failures.append("a None or empty draw must be excluded and counted, never scored")
    if dropped["rates"] != [0.5]:
        failures.append("the surviving draw must score alone (rate 1/2)")

    if gradient_stat([(0.6, 0.2)])["share"] != 1.0:
        failures.append("one LOW-above-HIGH pair must share 1.0")
    if registration_digest() != registration_digest():
        failures.append("registration digest unstable")

    for line in failures:
        print(f"FAIL {line}", file=sys.stderr)
    print("selftest: " + ("FAILED" if failures else "passed"), file=sys.stderr)
    return 1 if failures else 0


# ---------------------------------------------------------------------------------- the run


def _pool_entries(
    high: list[dict[str, Any]], low: list[dict[str, Any]], count: int
) -> tuple[list[dict[str, Any]], list[tuple[dict[str, Any], dict[str, Any]]]]:
    """The gradient pairing, imported from blurb_gradient — never duplicated here."""
    pairs = blurb_gradient.matched_pairs(high, low, count)
    entries: list[dict[str, Any]] = []
    for side, rows in (
        ("high", [pair[0] for pair in pairs]),
        ("low", [pair[1] for pair in pairs]),
    ):
        for row in rows:
            entries.append(
                {
                    "kind": side,
                    "name": str(row["source"]),
                    "title": str(row.get("title") or ""),
                    "body": str(row["listing"]),
                    "followers": int(row.get("followers") or 0),
                }
            )
    return entries, pairs


def _text_entries(texts: list[dict[str, str]]) -> list[dict[str, Any]]:
    return [
        {
            "kind": "ours",
            "name": entry["name"],
            "title": entry.get("title") or "",
            "body": entry["listing"],
            "followers": None,
        }
        for entry in texts
    ]


def call_plan(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Exact call arithmetic, shared by --dry-run and the guard.

    Round 1 asks K draws per sentence of every listing; the KF fixed point feeds draw 1 back
    once per sentence; there are no other calls.
    """
    per: list[dict[str, Any]] = []
    total_sentences = 0
    for entry in entries:
        n = len(sentences(entry["body"]))
        total_sentences += n
        per.append({"kind": entry["kind"], "name": entry["name"], "sentences": n})
    round1 = total_sentences * K_DRAWS
    fixed_point = total_sentences
    return {
        "listings": per,
        "sentences": total_sentences,
        "round1_calls": round1,
        "fixed_point_calls": fixed_point,
        "total": round1 + fixed_point,
    }


def _ask_once(complete: Any, prompt: str, sample: int = 0) -> tuple[str | None, str | None]:
    """One rewrite through the reader seam; (reply, failure), the reply normalised."""
    result, failure = complete(prompt, SYSTEM, None, MAX_OUTPUT_TOKENS, sample=sample)
    if failure is not None:
        return None, failure
    return normalise(str(result)), None


def run_listing(
    complete: Any, entry: dict[str, Any], *, allow_prose: bool
) -> tuple[dict[str, Any], list[tuple[float, float]]]:
    """Round 1 (K draws per sentence) and KF round 2 (draw 1 fed back into its own context).

    Returns the listing report and the per-sentence (round1_mean, round2) pairs. Round 2 is
    scored against the same original sentence by the same scorer.
    """
    body = entry["body"]
    bodies = sentences(body)
    replies_by_sentence: list[list[str | None]] = []
    for k, sent in enumerate(bodies, start=1):
        replies: list[str | None] = []
        for draw in range(K_DRAWS):
            # The draw index rides to the transport: K byte-identical asks are K draws of a
            # distribution, and a replay cache must never collapse them into one answer.
            reply, _error = _ask_once(
                complete, render_ask(entry["title"], body, k, sent), sample=draw
            )
            replies.append(reply)  # None on failure: excluded from scoring, counted instead
        replies_by_sentence.append(replies)
    report = listing_report(
        entry["name"],
        entry["title"],
        body,
        replies_by_sentence,
        source_kind=entry["kind"],
        followers=entry.get("followers"),
        allow_prose=allow_prose,
    )

    kf_pairs: list[tuple[float, float]] = []
    for k, _sent in enumerate(bodies, start=1):
        answered = [reply for reply in replies_by_sentence[k - 1] if reply]
        if not answered:
            continue
        # The fixed point being tested is the REWRITE's: draw 1's rewrite goes back through
        # the same ask, as sentence k of its own updated listing, and round 2 is scored
        # against that rewrite. Scoring against the original cannot fall even when the
        # instrument works (the registration's amended KF records the first draft doing so).
        updated = bodies.copy()
        updated[k - 1] = answered[0]
        reply2, _error = _ask_once(
            complete, render_ask(entry["title"], " ".join(updated), k, answered[0])
        )
        round2 = span_diff(answered[0], reply2)[0] if reply2 else float("nan")
        kf_pairs.append((report["sentences"][k - 1]["mean_change_rate"], round2))
    return report, kf_pairs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument(
        "--pool",
        nargs=2,
        metavar=("HIGH_POOL", "LOW_POOL"),
        default=None,
        help="derived/ pools, read as blurb_gradient reads them (HIGH then LOW)",
    )
    parser.add_argument("--texts", nargs="*", default=[], help="our listings, as load_texts reads")
    parser.add_argument("--pairs", type=int, default=8)
    parser.add_argument("--out", type=Path, default=RESULTS / "blurb-rewrite.json")
    parser.add_argument(
        "--reader",
        default="registry",
        help="'registry' (default) or 'ollama:<model>' for a cross-family reader; its run "
        "writes its own suffixed results file, labelled and never pooled with another "
        "reader's numbers",
    )
    parser.add_argument("--yes", action="store_true")
    # Undocumented on purpose: the parent session runs the gated run. An operator typing this
    # flag by accident is not the failure mode being guarded; unattended quota spend is.
    parser.add_argument("--i-am-the-gated-run", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()

    try:
        reader_spec = reader_transport.parse_reader_spec(args.reader)
    except ValueError as error:
        parser.error(str(error))
        raise
    # A cross-family run never lands on the default file: one file per reader is why two
    # readers' numbers cannot be pooled by accident. The derived/-side text dump follows the
    # same suffixed stem, so it stays beside its own results file.
    args.out = reader_transport.out_with_reader(args.out, reader_spec)

    high: list[dict[str, Any]] = []
    low: list[dict[str, Any]] = []
    if args.pool:
        high = json.loads(Path(args.pool[0]).read_text(encoding="utf-8"))
        low = json.loads(Path(args.pool[1]).read_text(encoding="utf-8"))
    entries, pairs = _pool_entries(high, low, args.pairs)
    entries += _text_entries(listing_arena.load_texts(args.texts))
    if not entries:
        parser.error("give --pool and/or --texts; there is nothing to measure")

    plan = call_plan(entries)
    print(
        f"{len(entries)} listing(s): round 1 {plan['round1_calls']} + fixed point "
        f"{plan['fixed_point_calls']} = {plan['total']} call(s) over "
        f"{plan['sentences']} sentence(s)"
    )
    for listing in plan["listings"]:
        print(
            f"  {listing['kind']:4} {listing['name'][:44]:<44} {listing['sentences']} sentence(s)"
        )
    if args.dry_run:
        print("dry run: no registry constructed, nothing spent", file=sys.stderr)
        return 0
    if not args.run:
        parser.error("pass one of --selftest, --dry-run, --run")
    if plan["total"] > CALL_GUARD and not args.yes:
        print(f"{plan['total']} calls exceeds the {CALL_GUARD} guard; pass --yes", file=sys.stderr)
        return 1
    if not args.yes:
        print("pass --yes to spend, or --dry-run to see the plan", file=sys.stderr)
        return 1
    if not args.i_am_the_gated_run:
        print(
            "The first paid run is the operator's gate: even with --yes this exits unless the "
            "session that owns the decision passes its gating flag.",
            file=sys.stderr,
        )
        return 1

    complete = reader_transport.completer(
        reader_spec,
        build_request=build_request,
        registry=build_default_registry() if reader_spec.transport == "registry" else None,
        cache_path=(
            args.out.with_name(f"{args.out.stem}.raw.jsonl")
            if reader_spec.transport == "ollama"
            else None
        ),
    )
    pool_reports: list[dict[str, Any]] = []
    text_reports: list[dict[str, Any]] = []
    kf: list[tuple[float, float]] = []
    kf_failures = 0
    kl_rates: list[float] = []
    kl_lengths: list[int] = []

    for entry in entries:
        allow_prose = entry["kind"] == "ours"  # pool rows carry offsets and counts only
        report, kf_pairs = run_listing(complete, entry, allow_prose=allow_prose)
        for first, second in kf_pairs:
            if second == second:
                kf.append((first, second))
            else:
                kf_failures += 1
        for row in report["sentences"]:
            kl_rates.append(row["mean_change_rate"])
            kl_lengths.append(row["tokens"])
        (text_reports if allow_prose else pool_reports).append(report)
        print(
            f"  {entry['kind']:4} {entry['name'][:36]:<36} mean change_rate "
            f"{report['mean_change_rate']:.3f}"
        )

    # KG, on the same length-matched pairing blurb_gradient validated the readership with.
    means = {report["name"]: report["mean_change_rate"] for report in pool_reports}
    kg_pairs = [
        (means[str(bottom["source"])], means[str(top["source"])])
        for top, bottom in pairs
        if str(bottom["source"]) in means and str(top["source"]) in means
    ]
    kg = gradient_stat(kg_pairs)

    # KP: within-sentence across-draw agreement against the between-sentence contrast.
    within = [
        agreement
        for report in (*pool_reports, *text_reports)
        for row in report["sentences"]
        if (agreement := draw_agreement(row["changed_spans"])) is not None
    ]
    per_sentence_sets = [
        _changed_token_set(list(chain.from_iterable(row["changed_spans"])))
        for report in (*pool_reports, *text_reports)
        for row in report["sentences"]
    ]
    between = [_jaccard(a, b) for a, b in combinations(per_sentence_sets, 2)]
    controls = {
        "kf": fixed_point_summary([first for first, _ in kf], [second for _, second in kf]),
        "kg": kg,
        "kl": {"r": length_correlation(kl_rates, kl_lengths), "sentences": len(kl_rates)},
        "kp": draw_reliability(within, between),
    }

    failed_draws = sum(
        row["failed_draws"]
        for report in (*pool_reports, *text_reports)
        for row in report["sentences"]
    )
    result = {
        "study": BLURB_REWRITE_VERSION,
        "registration": "plan/blurb-rewrite-validity.md",
        # Written once, at the top: every number under it belongs to this reader, and a run
        # writes one file — the labelling that makes pooling two readers impossible by
        # construction rather than by care.
        "reader": reader_transport.reader_block(reader_spec),
        "registration_digest": registration_digest(),
        # Read before any verdict, the standing rule: a failed draw was excluded from every
        # rate, and a run with many of them is a fact about the day rather than the text.
        "transport_failures": {"draws": failed_draws, "fixed_point": kf_failures},
        "pool": pool_reports,   # digests, offsets, counts; no third-party prose, enforced
        "texts": text_reports,  # our own listings; prose permitted here and only here
        "controls": controls,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    # Pool rows with text live under derived/, which .gitignore covers for exactly that.
    DERIVED.mkdir(parents=True, exist_ok=True)
    (DERIVED / f"{args.out.stem}-text.json").write_text(
        json.dumps({"pool": pool_reports}, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    kf_summary = controls["kf"]
    if isinstance(kf_summary.get("pairs"), int) and kf_summary["pairs"]:
        print(
            f"\nKF fixed point: round1 {kf_summary['round1_mean']:.3f} -> round2 "
            f"{kf_summary['round2_mean']:.3f}; round2 below in "
            f"{kf_summary['share_round2_below']:.0%} of {kf_summary['pairs']} sentence(s)"
        )
    print(
        f"KG gradient: LOW above HIGH in {kg.get('wins', 0)}/{kg.get('pairs', 0)} pair(s), "
        f"share {kg.get('share')} interval {kg.get('bootstrap_interval')}"
    )
    print(f"KL length: r={controls['kl']['r']} over {controls['kl']['sentences']} sentence(s)")
    print(
        f"KP draws: within {controls['kp']['within_mean']} against between "
        f"{controls['kp']['between_mean']}"
    )
    print(
        f"transport failures: {failed_draws} draw(s), {kf_failures} fixed-point call(s) — "
        "read before any verdict"
    )
    if reader_spec.transport != "registry":
        print(f"reader {reader_transport.describe(reader_spec)}")
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())