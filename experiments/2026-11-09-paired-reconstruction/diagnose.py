"""Paired reconstruction, after the fact: length-matched rescoring and the style counts that differ most.

Not part of the declared protocol. No model calls; prints numbers only.
"""
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import score  # noqa: E402

NAMES = ["sent_mean", "sent_median", "sent_p90", "sent_sd", "sent_le4_share", "para_mean", "para_median", "para_p90",
         "para_le10_share", "para_ge60_share", "spoken_share", "para_starts_quote", "exclaim", "question", "comma",
         "semicolon", "colon", "dash", "ellipsis", "paren", "bracket", "said", "ly_words", "contractions", "I_me_my",
         "was_were_had", "simile", "ALLCAPS", "filler_words", "type_token", "word_len", "start_pronoun", "start_conj",
         "start_article"]


def main() -> dict:
    plan = json.loads((score.DATA / "pairs.json").read_text(encoding="utf-8"))
    vocab, out = score.vocabulary(plan["background"]), {}
    for arm in "ABCDE":
        done =[t for t in plan["targets"] if (score.DATA / "arms" / arm / f"{t}.txt").is_file()]
        written = [score.norm((score.DATA / "arms" / arm / f"{t}.txt").read_text(encoding="utf-8")) for t in done]
        # length-matched: the real opening is cut to its rewrite's word count, then the rewrite to the real's
        originals = [score.opening((score.CORPUS / t / "ch01.txt").read_text(encoding="utf-8", errors="replace"),
                                   min(len(w.split()), score.CUT)) for t, w in zip(done, written)]
        written = [score.opening(w, len(o.split())) for w, o in zip(written, originals)]
        y, groups = np.array([0] * len(done) + [1] * len(done)), np.array(done + done)
        found = score.separate(score.blocks(originals + written, vocab), y, groups)
        found.pop("oof")
        r, w = np.array([score.style(o) for o in originals]), np.array([score.style(x) for x in written])
        gap = (w.mean(0) - r.mean(0)) / (np.sqrt((w.var(0) + r.var(0)) / 2) + 1e-9)
        top = sorted(zip(NAMES, gap, r.mean(0), w.mean(0)), key=lambda row: -abs(row[1]))[:10]
        out[arm] = {"length_matched": found,
                    "largest_gaps": [{"count": n, "gap_sd": round(float(g), 2), "real": round(float(a), 3),
                                      "rewritten": round(float(b), 3)} for n, g, a, b in top]}
    return out


if __name__ == "__main__":
    print(json.dumps(main(), indent=1))
