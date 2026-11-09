"""Paired reconstruction, scoring half: can a classifier tell rewritten openings from the real ones?

No model calls. Reads the genre corpus and the arms' outputs from $LITHARNESS_HOME, never from the tree.
  python score.py baseline          real-vs-real null band and the era split (the bars)
  python score.py arms [A B C D]    each arm against its real twins, with guards
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys
import unicodedata
import zlib

import numpy as np

HOME = Path(os.environ.get("LITHARNESS_HOME") or Path.home() / "LitHarness-data")
CORPUS, DATA = HOME / "corpora" / "genre", HOME / "evals" / "paired-reconstruction"
CUT, LAMBDA, FOLDS, REPEATS, HASH = 1200, 0.1, 5, 5, 4096
WORD = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")
SWAP = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "—": "--", "–": "-",
                      "…": "...", " ": " "})


def norm(text: str) -> str:
    """Typography a reader cannot see is removed from both sides: quote and dash shapes, markdown, headings."""
    text = unicodedata.normalize("NFKC", text.replace("\r\n", "\n")).translate(SWAP)
    kept = []
    for block in re.split(r"\n\s*\n", text):
        block = " ".join(block.split())
        block = re.sub(r"^#+\s*|\*\*|__|(?<!\w)[*_](?=\w)|(?<=\w)[*_](?!\w)", "", block)
        if block and not re.fullmatch(r"(chapter|prologue)\b.{0,60}|[-*=~_ ]{3,}", block, re.I):
            kept.append(block)
    return "\n\n".join(kept)


def opening(text: str, words: int = CUT) -> str:
    """Whole paragraphs from the top until the count is reached."""
    out, count = [], 0
    for block in norm(text).split("\n\n"):
        out.append(block)
        count += len(block.split())
        if count >= words:
            break
    return "\n\n".join(out)


def real(title: str) -> str:
    return opening((CORPUS / title / "ch01.txt").read_text(encoding="utf-8", errors="replace"))


def rate(pattern: str, text: str, per: int) -> float:
    return 1000 * len(re.findall(pattern, text)) / max(per, 1)


def style(text: str) -> list[float]:
    """Counts a reader would feel: sentence and paragraph shape, dialogue, punctuation, voice."""
    words, paragraphs = WORD.findall(text.lower()), text.split("\n\n")
    n = len(words)
    sentences = [len(s.split()) for s in re.split(r"(?<=[.!?\"])\s+", text) if s.split()]
    plen = [len(p.split()) for p in paragraphs]
    q = lambda xs, p: float(np.percentile(xs, p)) if xs else 0.0
    spoken = sum(len(m) for m in re.findall(r'"[^"]{1,600}"', text))
    starts = [s.split()[0].lower().strip('"') for s in re.split(r"(?<=[.!?])\s+", text) if s.split()]
    share = lambda group: sum(w in group for w in starts) / max(len(starts), 1)
    return [float(np.mean(sentences)), q(sentences, 50), q(sentences, 90), float(np.std(sentences)),
            sum(s <= 4 for s in sentences) / max(len(sentences), 1), float(np.mean(plen)), q(plen, 50), q(plen, 90),
            sum(p <= 10 for p in plen) / len(plen), sum(p >= 60 for p in plen) / len(plen),
            spoken / max(len(text), 1), sum(p.startswith('"') for p in paragraphs) / len(paragraphs),
            *(rate(p, text, n) for p in (r"!", r"\?", r",", r";", r":", r"--", r"\.\.\.", r"\(", r"\[", r"\bsaid\b",
                                         r"\b\w+ly\b", r"\b\w+'(?:t|s|d|ll|re|ve|m)\b", r"\b(?:I|me|my)\b",
                                         r"\b(?:was|were|had)\b", r"\b(?:like|as if|as though)\b", r"\b[A-Z]{3,}\b",
                                         r"\b(?:just|really|actually|basically|pretty|kind of|sort of|well|okay)\b")),
            len(set(words[:1000])) / max(min(n, 1000), 1), float(np.mean([len(w) for w in words] or [0])),
            share({"he", "she", "i", "they", "it", "we"}), share({"and", "but", "so", "or"}),
            share({"the", "a", "an"})]


def vocabulary(titles: list[str], size: int = 400) -> list[str]:
    counts: dict[str, int] = {}
    for title in titles:
        for word in set(WORD.findall(real(title).lower())):
            counts[word] = counts.get(word, 0) + 1
    return sorted(counts, key=lambda w: (-counts[w], w))[:size]


def blocks(texts: list[str], vocab: list[str]) -> dict[str, np.ndarray]:
    """Three views of each text: style counts, common-word rates, hashed character 3- and 4-grams."""
    index, frequency, grams = {w: i for i, w in enumerate(vocab)}, np.zeros((len(texts), len(vocab))), np.zeros(
        (len(texts), HASH))
    for row, text in enumerate(texts):
        words = WORD.findall(text.lower())
        for word in words:
            if word in index:
                frequency[row, index[word]] += 1 / len(words)
        flat = re.sub(r"\s+", " ", text.lower())
        for size in (3, 4):
            for i in range(len(flat) - size + 1):
                grams[row, zlib.crc32(flat[i:i + size].encode()) % HASH] += 1
        grams[row] = np.log1p(grams[row] * 5000 / max(len(flat), 1))
    return {"style": np.array([style(t) for t in texts]), "words": frequency, "chars": grams}


def scores(train: np.ndarray, y: np.ndarray, test: np.ndarray) -> np.ndarray:
    """Ridge classifier in sample space on features standardised by the training rows."""
    mean, deviation = train.mean(0), train.std(0) + 1e-9
    a, b = (train - mean) / deviation, (test - mean) / deviation
    kernel = a @ a.T / a.shape[1]
    return (b @ a.T / a.shape[1]) @ np.linalg.solve(kernel + LAMBDA * np.eye(len(a)), y - y.mean())


def auc(positive: np.ndarray, negative: np.ndarray) -> float:
    wins = (positive[:, None] > negative[None, :]).sum() + 0.5 * (positive[:, None] == negative[None, :]).sum()
    return float(wins / (len(positive) * len(negative)))


def separate(views: dict[str, np.ndarray], y: np.ndarray, groups: np.ndarray, seed: int = 0) -> dict:
    """Out-of-fold scores with whole titles held out; class 1 is 'rewritten'. Reports each view and all three
    side by side; the headline is the best of them, and the null is computed the same way."""
    views = views | {"all": np.hstack([(v - v.mean(0)) / (v.std(0) + 1e-9) / np.sqrt(v.shape[1])
                                       for v in views.values()])}
    out, random = {name: np.zeros(len(y)) for name in views}, np.random.default_rng(seed)
    names = np.unique(groups)
    for _ in range(REPEATS):
        order = random.permutation(names)
        for fold in range(FOLDS):
            held = np.isin(groups, order[fold::FOLDS])
            for name, x in views.items():
                out[name][held] += scores(x[~held], y[~held].astype(float), x[held]) / REPEATS
    result = {name: round(auc(s[y == 1], s[y == 0]), 3) for name, s in out.items()}
    best = max(result, key=result.get)
    s = out[best]
    spread = np.sqrt((s[y == 1].var() + s[y == 0].var()) / 2) + 1e-9
    return result | {"best": best, "auc": result[best], "dprime": round(float((s[y == 1].mean() - s[y == 0].mean())
                                                                             / spread), 2), "oof": s}


def interval(s: np.ndarray, y: np.ndarray, groups: np.ndarray, draws: int = 1000) -> list[float]:
    """Bootstrap over titles of the pooled out-of-fold AUC."""
    random, names, found = np.random.default_rng(1), np.unique(groups), []
    rows = {g: np.flatnonzero(groups == g) for g in names}
    for _ in range(draws):
        take = np.concatenate([rows[g] for g in random.choice(names, len(names))])
        if 0 < y[take].sum() < len(take):
            found.append(auc(s[take][y[take] == 1], s[take][y[take] == 0]))
    return [round(float(np.percentile(found, p)), 3) for p in (2.5, 97.5)]


def shared(a: str, b: str, n: int) -> float:
    """Share of a's word n-grams that also occur in b."""
    grams = lambda t: {tuple(w[i:i + n]) for w in [WORD.findall(t.lower())] for i in range(len(w) - n + 1)}
    mine = grams(a)
    return len(mine & grams(b)) / max(len(mine), 1)


def baseline() -> dict:
    plan = json.loads((DATA / "pairs.json").read_text(encoding="utf-8"))
    pool, vocab = plan["background"], vocabulary(plan["background"])
    views = blocks([real(t) for t in pool], vocab)
    groups, random, null = np.arange(len(pool)), np.random.default_rng(7), []
    for _ in range(40):
        y = np.zeros(len(pool), int)
        y[random.permutation(len(pool))[:len(pool) // 2]] = 1
        null.append(separate(views, y, groups)["auc"])
    era = np.array([plan["era"][t] == "2024-25" for t in pool], int)
    split = separate(views, era, groups)
    found = {"titles": len(pool), "null_median": round(float(np.median(null)), 3),
             "null_p95": round(float(np.percentile(null, 95)), 3), "null_max": max(null),
             "era": {k: v for k, v in split.items() if k != "oof"}, "era_interval": interval(split["oof"], era, groups)}
    (DATA / "baseline.json").write_text(json.dumps(found, indent=2), encoding="utf-8")
    return found


def arms(names: list[str]) -> dict:
    plan = json.loads((DATA / "pairs.json").read_text(encoding="utf-8"))
    vocab, report = vocabulary(plan["background"]), {}
    for arm in names:
        done = [t for t in plan["targets"] if (DATA / "arms" / arm / f"{t}.txt").is_file()]
        if len(done) < 10:
            report[arm] = {"n": len(done), "note": "too few rewrites to score"}
            continue
        originals = [real(t) for t in done]
        written = [norm((DATA / "arms" / arm / f"{t}.txt").read_text(encoding="utf-8")) for t in done]
        y, groups = np.array([0] * len(done) + [1] * len(done)), np.array(done + done)
        found = separate(blocks(originals + written, vocab), y, groups)
        s = found.pop("oof")
        gap = s[len(done):] - s[:len(done)]  # each rewrite against its own real twin
        examples = {t: "\n\n".join(real(e) for e in plan["exemplars_for"][t]) for t in done}
        outline = {t: (DATA / "skeleton" / f"{t}.txt").read_text(encoding="utf-8") for t in done}
        names_in = lambda t: set(re.findall(r"\b[A-Z][a-z]{2,}\b", " ".join(outline[t].splitlines()[2:])))
        covered = [np.mean([n in w for n in names_in(t)] or [1.0]) for t, w in zip(done, written)]
        report[arm] = found | {
            "n": len(done), "interval": interval(s, y, groups), "pair_wins": round(float(np.mean(gap > 0)), 3),
            "length_ratio": round(float(np.median([len(w.split()) / len(o.split())
                                                   for w, o in zip(written, originals)])), 2),
            "copied_from_examples_8gram_max": round(max(shared(w, examples[t], 8) for t, w in zip(done, written)), 4),
            "copied_from_twin_8gram_max": round(max(shared(w, o, 8) for w, o in zip(written, originals)), 4),
            "outline_names_covered": round(float(np.mean(covered)), 3)}
    (DATA / "scores.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    verb = sys.argv[1] if len(sys.argv) > 1 else ""
    found = baseline() if verb == "baseline" else arms(sys.argv[2:] or list("ABCD")) if verb == "arms" else __doc__
    print(found if isinstance(found, str) else json.dumps(found, indent=2))
