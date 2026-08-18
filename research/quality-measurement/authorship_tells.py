"""Can a classifier tell our prose from human LitRPG, and if so, on which features?

**The reframe this module rests on.** All 21 refuted proxies were trying to answer *is this text
good?*, and every label available for that question is contaminated: engagement tracks cover art
and launch timing, comment counts track archive capture date, declared-AI tracks the year
(§2 Pass 2's `tricolon_rate` row, where 0.629 against pre-LLM prose collapsed the moment the
undeclared-2025 control read 0.606 beside it). This module asks a different question — *is this
text ours?* — and that question has the one uncontaminated label this project will ever own. We
know with certainty which scenes our pipeline wrote. Pass 2 failed because it tried to detect
*other people's* AI text through an unreliable declaration; nothing here depends on anyone
declaring anything.

**Answering it is useful in both directions, which is why it is worth running before anything
expensive.** A separation at chance says there are no surface tells and the human read that
prompted this was about something a bag of counts cannot reach. A clean separation hands back a
*ranked list* of the features carrying it, which converts one reader's impression into an
enumerated target — and a target a deterministic repair can be verified against, which is the
only repair shape §2 Pass 4 leaves standing.

**n=10 is the binding constraint and it decides the whole design.** Ten drafted scenes cannot
train anything, so this does not report a bare AUC and call it a finding. It fits the
discriminator on our scenes against the human pool, scores it leave-one-out, and then runs *the
identical procedure* with ten randomly drawn human chapters standing in for ours, many times, to
get the distribution of AUC this method produces at this n when there is nothing to find. The
headline is our AUC's position in that null, never the AUC itself. §2's first method rule, which
is the one every dead proxy broke.

**The pre-LLM cohort is the reference, and that is measured rather than assumed.** Em dashes per
1k words in human LitRPG: median 0.00 with p90 1.91 in the 2021-22 shard, median 1.11 with p90
11.86 in the 2025 shard. The 2025 corpus has moved toward the machine, which is either LLM
contamination of RoyalRoad or a genuine style shift, and either way it is not a clean negative
class for tell work. Both are computed here so the comparison is visible rather than asserted.

**Two cheats are controlled in the same pass because both would produce a perfect score for
nothing.** Our scenes carry `[STATUS]` lines and bolded system-voice headers, so a classifier
could learn our *formatting*; `--strip-system` removes them from both sides and the run reports
AUC with and without. And our scenes are ~1,000 words while human chapters range widely, so
length enters as an explicit feature whose weight is reported rather than as an invisible
confound — if `words` is doing the work, the tells are a length artifact.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import statistics
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

#: Everything is a rate per 1k words or a dimensionless ratio, so a 900-word scene and a
#: 4,000-word chapter are comparable without normalising afterwards and forgetting to.
_EM = "—"
_INTERIOR = re.compile(
    r"\b(?:thought|realised|realized|wondered|remembered|felt|knew|hoped|feared|wanted|"
    r"decided|understood|noticed|hated|loved|regretted|believed|suspected|expected)\b", re.I)
_BODY = re.compile(
    r"\b(?:shoulders?|jaws?|hands?|eyes?|face|mouth|throat|fingers?|breath|chest|"
    r"spines?|knees?|neck|wrists?|teeth|tongue|palms?)\b", re.I)
_HEDGE = re.compile(r"\b(?:seemed|somehow|almost|slightly|perhaps|maybe|something like)\b", re.I)
_FIRST = re.compile(r"\b(?:I|me|my|mine|myself)\b")
_THIRD = re.compile(r"\b(?:he|him|his|she|her|hers|they|them|their)\b", re.I)
_LY = re.compile(r"\b\w+ly\b", re.I)
_PARTICIPLE_OPEN = re.compile(r"(?:^|\. )\w+ing\b", re.M)
_SENT = re.compile(r"(?<=[.!?])[\"'”\u2019]*\s+")
#: The system voice: bolded headers and any line carrying a bracketed tag.
_SYSTEM = re.compile(r"\*\*[^*\n]*\*\*|^.*\[[A-Z][A-Z ]+\].*$", re.MULTILINE)


def strip_system(text: str) -> str:
    return _SYSTEM.sub(" ", text)


def features(text: str) -> dict[str, float]:
    """Surface counts only. No model, no corpus statistics, nothing to leak across the split."""
    words = text.split()
    n = max(len(words), 1)
    sentences = [s for s in _SENT.split(text) if s.strip()]
    lengths = [len(s.split()) for s in sentences] or [0]
    quoted = sum(len(m) for m in re.findall(r"[\"“][^\"”]{1,400}[\"”]", text))
    blocks = [b for b in text.split("\n\n") if b.strip()]
    inner = len(_INTERIOR.findall(text))
    unique = len({w.lower().strip(".,;:!?\"'—") for w in words})
    return {
        "em_per_1k": 1000.0 * text.count(_EM) / n,
        "comma_per_1k": 1000.0 * text.count(",") / n,
        "semicolon_per_1k": 1000.0 * text.count(";") / n,
        "colon_per_1k": 1000.0 * text.count(":") / n,
        "question_per_1k": 1000.0 * text.count("?") / n,
        "exclaim_per_1k": 1000.0 * text.count("!") / n,
        "interior_per_1k": 1000.0 * inner / n,
        "body_per_1k": 1000.0 * len(_BODY.findall(text)) / n,
        "body_to_interior": len(_BODY.findall(text)) / max(inner, 1),
        "hedge_per_1k": 1000.0 * len(_HEDGE.findall(text)) / n,
        "first_person_per_1k": 1000.0 * len(_FIRST.findall(text)) / n,
        "third_person_per_1k": 1000.0 * len(_THIRD.findall(text)) / n,
        "adverb_ly_per_1k": 1000.0 * len(_LY.findall(text)) / n,
        "participle_open_per_1k": 1000.0 * len(_PARTICIPLE_OPEN.findall(text)) / n,
        "and_opener_per_1k": 1000.0 * len(re.findall(r"(?:^|\. )And ", text)) / n,
        "but_opener_per_1k": 1000.0 * len(re.findall(r"(?:^|\. )But ", text)) / n,
        "triple_per_1k": 1000.0 * len(re.findall(r"\b\w+, \w+,? and \w+\b", text)) / n,
        "dialogue_ratio": quoted / max(len(text), 1),
        "sentence_len_mean": statistics.fmean(lengths),
        "sentence_len_cv": (
            statistics.pstdev(lengths) / statistics.fmean(lengths)
            if len(lengths) > 1 and statistics.fmean(lengths) else 0.0
        ),
        "paragraph_len_mean": statistics.fmean([len(b.split()) for b in blocks] or [0.0]),
        "type_token": unique / n,
        "word_len_mean": statistics.fmean([len(w) for w in words] or [0.0]),
        # Length is a feature rather than a hidden confound. If this carries the separation,
        # the tells are an artifact of our scenes being uniformly ~1,000 words.
        "words": float(n),
    }


FEATURE_NAMES = tuple(features("a word. two words here.").keys())


#: Mutable so a run can exclude features and re-measure. `words` is the one that matters:
#: it carries real weight in the first run, so a separation reported with it in the set is
#: partly a statement that our scenes are ~1,000 words and human chapters are longer.
ACTIVE: list[str] = list(FEATURE_NAMES)


def _matrix(rows: list[dict[str, float]]) -> Any:
    import numpy as np

    return np.array([[row[name] for name in ACTIVE] for row in rows], dtype=float)


def loo_auc(ours: list[dict[str, float]], theirs: list[dict[str, float]], seed: int) -> float:
    """Leave-one-out AUC for the positive class, refitting without the held-out positive.

    Held out on the positive side only: with 10 positives and thousands of negatives, holding
    out a negative changes nothing, and refitting per positive is what keeps a 10-sample class
    from being scored by a model that memorised it.
    """
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    negative = _matrix(theirs)
    scores: list[float] = []
    for index in range(len(ours)):
        train_pos = _matrix([row for i, row in enumerate(ours) if i != index])
        held = _matrix([ours[index]])
        features_all = np.vstack([train_pos, negative])
        labels = np.concatenate([np.ones(len(train_pos)), np.zeros(len(negative))])
        scaler = StandardScaler().fit(features_all)
        model = LogisticRegression(
            max_iter=2000, class_weight="balanced", random_state=seed
        ).fit(scaler.transform(features_all), labels)
        scores.append(float(model.decision_function(scaler.transform(held))[0]))
    negative_scores = _score_all(ours, theirs, seed)
    # AUC = P(a held-out positive outranks a random negative), computed directly.
    wins = 0.0
    for pos in scores:
        wins += sum(1 for neg in negative_scores if pos > neg)
        wins += 0.5 * sum(1 for neg in negative_scores if pos == neg)
    return wins / (len(scores) * len(negative_scores))


def _score_all(
    ours: list[dict[str, float]], theirs: list[dict[str, float]], seed: int
) -> list[float]:
    """Negative-class scores under a model fitted on all positives. Negatives are never held out."""
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    features_all = np.vstack([_matrix(ours), _matrix(theirs)])
    labels = np.concatenate([np.ones(len(ours)), np.zeros(len(theirs))])
    scaler = StandardScaler().fit(features_all)
    model = LogisticRegression(
        max_iter=2000, class_weight="balanced", random_state=seed
    ).fit(scaler.transform(features_all), labels)
    return list(model.decision_function(scaler.transform(_matrix(theirs))))


def coefficients(
    ours: list[dict[str, float]], theirs: list[dict[str, float]], seed: int
) -> list[tuple[str, float]]:
    """Standardised weights, largest magnitude first — the ranked tell list, if there is one."""
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    features_all = np.vstack([_matrix(ours), _matrix(theirs)])
    labels = np.concatenate([np.ones(len(ours)), np.zeros(len(theirs))])
    scaler = StandardScaler().fit(features_all)
    model = LogisticRegression(
        max_iter=2000, class_weight="balanced", random_state=seed
    ).fit(scaler.transform(features_all), labels)
    pairs = list(zip(ACTIVE, model.coef_[0], strict=True))
    return sorted(pairs, key=lambda pair: -abs(pair[1]))


def null_distribution(
    theirs: list[dict[str, float]], size: int, replicates: int, seed: int
) -> list[float]:
    """AUC when `size` human chapters stand in for ours. What this method reports on nothing.

    The whole point of the module. An AUC of 0.99 means nothing until this says what 0.99 is
    worth at n=10 against thousands of negatives, and the honest expectation is that it is worth
    quite a lot — a tiny positive class is easy to separate by accident.
    """
    rng = random.Random(seed)
    aucs: list[float] = []
    for replicate in range(replicates):
        picked = rng.sample(range(len(theirs)), size)
        stand_in = [theirs[i] for i in picked]
        rest = [row for i, row in enumerate(theirs) if i not in set(picked)]
        aucs.append(loo_auc(stand_in, rest, seed + replicate))
    return sorted(aucs)


def dump_ours(book_db: str, min_words: int, destination: str) -> int:
    """Write the positive class to JSON so an interpreter without the package can read it."""
    from corpus_io import generated_scenes

    units = generated_scenes(book_db, min_words=min_words)
    Path(destination).parent.mkdir(parents=True, exist_ok=True)
    Path(destination).write_text(
        json.dumps(
            {"source": book_db, "min_words": min_words,
             "scenes": [{"unit_id": u.unit_id, "text": u.text} for u in units]},
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"wrote {len(units)} scenes to {destination}")
    return len(units)


def run(args: argparse.Namespace) -> dict[str, Any]:
    from corpus_io import royalroad_chapters

    if not args.ours_json:
        from corpus_io import generated_scenes

    prepare = strip_system if args.strip_system else (lambda text: text)
    if args.ours_json:
        # Two interpreters, no overlap: `generated_scenes` needs the package installed and
        # `royalroad_chapters` needs pyarrow, and nothing on this machine has both. Dumping our
        # side to JSON from the package-having interpreter is the bridge, and it also means the
        # positive class survives without a live book database. `--dump-ours` writes it.
        payload = json.loads(Path(args.ours_json).read_text(encoding="utf-8"))
        ours = [features(prepare(entry["text"])) for entry in payload["scenes"]]
    else:
        ours = [
            features(prepare(unit.text))
            for unit in generated_scenes(args.book_db, min_words=args.min_words)
        ]
    report: dict[str, Any] = {
        "ours_n": len(ours),
        "active_features": list(ACTIVE),
        "human_word_band": [args.min_words, args.max_words],
        "strip_system": args.strip_system,
        "features": list(FEATURE_NAMES),
        "protocol": "plan/stage-0-decisions.md §75",
        "cohorts": {},
    }
    for shard, label in ((30, "pre_llm_2021_22"), (3, "post_llm_2025")):
        theirs = [
            features(prepare(unit.text))
            for unit in royalroad_chapters(
                shards=(shard,), min_words=args.min_words, limit=args.limit
            )
            if args.max_words <= 0 or len(unit.text.split()) <= args.max_words
        ]
        if len(theirs) < 100:
            report["cohorts"][label] = {"error": f"only {len(theirs)} chapters"}
            continue
        auc = loo_auc(ours, theirs, args.seed)
        null = null_distribution(theirs, len(ours), args.replicates, args.seed)
        above = sum(1 for value in null if value >= auc) / len(null)
        report["cohorts"][label] = {
            "human_n": len(theirs),
            "auc": round(auc, 4),
            "null_median": round(statistics.median(null), 4),
            "null_p95": round(null[min(int(0.95 * len(null)), len(null) - 1)], 4),
            "null_max": round(null[-1], 4),
            "null_replicates": len(null),
            "p_value": round(above, 4),
            "separates": bool(above < 0.05),
            "top_features": [
                {"feature": name, "weight": round(weight, 4)}
                for name, weight in coefficients(ours, theirs, args.seed)[:10]
            ],
        }
        print(f"  {label}: auc {auc:.4f} vs null median "
              f"{statistics.median(null):.4f}, p={above:.4f}", file=sys.stderr, flush=True)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--book-db", default=str(HERE / "corpora" / "toll.db"))
    parser.add_argument("--min-words", type=int, default=500)
    parser.add_argument("--limit", type=int, default=1500, help="human chapters per cohort")
    parser.add_argument("--replicates", type=int, default=60, help="null draws per cohort")
    parser.add_argument("--strip-system", action="store_true",
                        help="remove system-voice lines from both sides; run it both ways")
    parser.add_argument("--max-words", type=int, default=0,
                        help="length-match the human side; 0 disables")
    parser.add_argument("--drop", default="", help="comma-separated features to exclude")
    parser.add_argument("--ours-json", help="positive class as JSON; see --dump-ours")
    parser.add_argument("--dump-ours", help="write the positive class to this path and exit")
    parser.add_argument("--seed", type=int, default=20260818)
    parser.add_argument("--out", default=str(HERE / "results" / "authorship-tells.json"))
    args = parser.parse_args(argv)

    if args.drop:
        dropped = {name.strip() for name in args.drop.split(",") if name.strip()}
        ACTIVE[:] = [name for name in FEATURE_NAMES if name not in dropped]

    if args.dump_ours:
        dump_ours(args.book_db, args.min_words, args.dump_ours)
        return 0

    report = run(args)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    for label, cohort in report["cohorts"].items():
        print(f"\n=== {label} ===")
        print(json.dumps({k: v for k, v in cohort.items() if k != "top_features"}, indent=2))
        for entry in cohort.get("top_features", []):
            print(f"    {entry['weight']:+8.4f}  {entry['feature']}")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
