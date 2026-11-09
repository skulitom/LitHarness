"""Paired reconstruction, arm E: the chat model rewrites its drafts against a classifier's reasons.

  python steer.py [--limit N] [--agent claude]
Three sweeps. In each, a classifier learns the background titles' real openings against every draft so far of
the *other* titles, and each title's latest draft is rewritten against what that classifier holds against it.
The target's opening is never read here. Resumable by sweep; traces are kept outside the tree.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run  # noqa: E402
import score  # noqa: E402
from diagnose import NAMES  # noqa: E402
from litharness import files, serial, transport  # noqa: E402

SWEEPS, FOLDS, GAPS, WORDS = 3, 5, 8, 12
KEEP = [i for i, n in enumerate(NAMES) if n not in {"I_me_my", "was_were_had"}]  # the outline fixes person and tense
SHARES = {"sent_le4_share", "para_le10_share", "para_ge60_share", "spoken_share", "para_starts_quote", "type_token",
          "start_pronoun", "start_conj", "start_article"}
PER = " per 1,000 words"
SAY = dict(zip(NAMES, [
    "Mean sentence length, in words", "Median sentence length, in words",
    "Length of the longest tenth of sentences, in words", "Spread of sentence lengths (standard deviation, in words)",
    "Share of sentences of four words or fewer", "Mean paragraph length, in words",
    "Median paragraph length, in words", "Length of the longest tenth of paragraphs, in words",
    "Share of paragraphs of ten words or fewer", "Share of paragraphs of sixty words or more",
    "Share of the text inside quotation marks", "Share of paragraphs that open with a quotation mark",
    "Exclamation marks" + PER, "Question marks" + PER, "Commas" + PER, "Semicolons" + PER, "Colons" + PER,
    "Dashes" + PER, "Ellipses" + PER, "Parentheses" + PER, "Square brackets" + PER, 'The word "said"' + PER,
    "Words ending in -ly" + PER, "Contractions" + PER, "", "", "Similes (like, as if, as though)" + PER,
    "Words in capitals" + PER, "Filler words (just, really, actually, pretty, kind of, well, okay)" + PER,
    "Share of distinct words in the first 1,000", "Mean word length, in letters",
    "Share of sentences that start with a pronoun", "Share of sentences that start with and, but, so or or",
    "Share of sentences that start with the, a or an"]))
PROMPT = """Below are an outline, a draft written from it, and measurements that set the draft apart from published LitRPG web serial openings. Rewrite the draft so that every measurement listed moves into the published range, while it still covers the outline's lines in order. Change how it is written, not what happens. About {words} words. Output only the chapter text.

=== MEASUREMENTS ===
{measurements}

=== OUTLINE ===
{outline}

=== DRAFT ===
{draft}"""


def features(texts: list[str], vocab: list[str]) -> dict[str, np.ndarray]:
    views = score.blocks([score.norm(t) for t in texts], vocab)
    return {"style": views["style"][:, KEEP], "words": views["words"]}


def fit(real: np.ndarray, fake: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The same ridge as the scorer, kept as per-feature weights so a draft's score can be explained."""
    train, y = np.vstack([real, fake]), np.array([0.0] * len(real) + [1.0] * len(fake))
    mean, deviation = train.mean(0), train.std(0) + 1e-9
    a = (train - mean) / deviation
    alpha = np.linalg.solve(a @ a.T / a.shape[1] + score.LAMBDA * np.eye(len(a)), y - y.mean())
    return mean, deviation, a.T @ alpha / a.shape[1]


def blame(x: np.ndarray, model: tuple) -> np.ndarray:
    """Each feature's push toward 'rewritten'; the sum is the draft's score."""
    return (x - model[0]) / model[1] * model[2]


def show(name: str, value: float) -> str:
    return f"{100 * value:.0f}%" if name in SHARES else f"{value:.1f}"


def measurements(x: dict, models: dict, ref: dict) -> str:
    push, low, high = blame(x["style"], models["style"]), *ref["range"]
    order = [i for i in np.argsort(-push) if push[i] > 0 and not low[i] <= x["style"][i] <= high[i]][:GAPS]
    lines = [f"- {SAY[NAMES[KEEP[i]]]}: yours {show(NAMES[KEEP[i]], x['style'][i])}; published openings usually "
             f"{show(NAMES[KEEP[i]], low[i])} to {show(NAMES[KEEP[i]], high[i])}." for i in order]
    push, z = blame(x["words"], models["words"]), (x["words"] - ref["words"][0]) / ref["words"][1]
    ranked = [i for i in np.argsort(-push) if push[i] > 0]
    over, under = [ref["vocab"][i] for i in ranked if z[i] > 0.5][:WORDS], [ref["vocab"][i] for i in ranked
                                                                             if z[i] < -0.5][:WORDS]
    if over:
        lines.append("- Common words you use far more than published openings do: " + ", ".join(over) + ".")
    if under:
        lines.append("- Common words you use far less than published openings do: " + ", ".join(under) + ".")
    return "\n".join(lines)


def path(title: str, sweep: int) -> Path:
    return run.DATA / "arms" / ("A" if sweep == 0 else f"E-sweeps/r{sweep}") / f"{title}.txt"


def crossfit(titles: list[str], upto: int, ref: dict):
    """For each fold of titles: models trained on background real against the other folds' drafts 0..upto."""
    drafts = {t: features([files.read(path(t, s)) for s in range(upto + 1)], ref["vocab"]) for t in titles}
    order = list(np.random.default_rng(run.SEED).permutation(sorted(titles)))
    for fold in range(FOLDS):
        held = order[fold::FOLDS]
        models = {view: fit(ref["real"][view], np.vstack([drafts[t][view] for t in titles if t not in held]))
                  for view in ("style", "words")}
        for title in held:
            yield title, drafts[title], models


def steer(agent: str, limit: int | None) -> str:
    plan = run.plan()
    vocab = score.vocabulary(plan["background"])
    real = features([score.real(t) for t in plan["background"]], vocab)
    ref = {"vocab": vocab, "real": real, "range": np.percentile(real["style"], [25, 75], axis=0),
           "words": (real["words"].mean(0), real["words"].std(0) + 1e-9)}
    titles = [t for t in plan["targets"][:limit] if path(t, 0).is_file()]
    failed: set[str] = set()
    for sweep in range(1, SWEEPS + 1):
        titles = [t for t in titles if t not in failed]
        jobs = [(t, PROMPT.format(words=run.words(t), outline=run.outline(t), draft=files.read(path(t, sweep - 1)).strip(),
                                  measurements=measurements({v: x[v][-1] for v in x}, models, ref)))
                for t, x, models in crossfit(titles, sweep - 1, ref) if not path(t, sweep).is_file()]

        def one(job: tuple[str, str]) -> str | None:
            try:
                files.write(path(job[0], sweep), run.chat(f"E{sweep}", job[0], job[1], agent) + "\n")
            except (ValueError, OSError) as error:
                print(f"E sweep {sweep} {job[0]}: FAILED {error}", file=sys.stderr, flush=True)
                return job[0]
            return None

        with ThreadPoolExecutor(run.WORKERS) as pool:
            failed |= {t for t in pool.map(one, jobs) if t}
        print(f"E sweep {sweep}: {len(jobs)} to write, {len(failed)} titles failed so far", flush=True)
    titles = [t for t in titles if t not in failed]
    for title, x, models in crossfit(titles, SWEEPS, ref):  # keep each title's least 'rewritten' draft
        marks = sum(blame(x[view], models[view]).sum(1) for view in ("style", "words"))
        kept = int(np.argmin(marks))
        files.write(run.DATA / "arms" / "E" / f"{title}.txt", files.read(path(title, kept)))
        files.save(run.DATA / "steer" / f"{title}.json", {"score_by_sweep": [round(float(m), 3) for m in marks],
                                                          "kept": kept})
    return f"E: {len(titles)} kept, {len(failed)} failed"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--agent")
    args = parser.parse_args()
    agent = ":".join(transport.resolve(args.agent or serial.writer()))
    box = files.box_lock()
    files.lock(box, "paired-reconstruction E")
    try:
        transport.preflight(transport.resolve(agent)[0])
        serial.pinned(agent)
        print(steer(agent, args.limit))
    finally:
        files.unlock(box)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
