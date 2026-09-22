"""Cross-arm vs within-cell noise check for the fcr.v0 v2/v3 arms (read-only)."""
import json, statistics, sys
from pathlib import Path
import numpy as np
sys.dont_write_bytecode = True
ARM = Path(r"C:\DEV\LitHarness\research\quality-measurement\cost-that-bites")

def share(actions):
    reads = [w for a, w in actions if a == "read"]
    return 0.25 if not reads else sum(w == "A" for w in reads) / len(reads)

cells = {}
for tag in ("v2", "v3"):
    d = json.loads((ARM / f"results-arm-{tag}.json").read_text(encoding="utf-8"))
    for row in d["rows"]:
        s = row["session"]
        cells.setdefault((tag, row["target_name"][-2:], row["version"]), []).append((s["replicate"], share(s["actions"])))
books = sorted({b for _, b, _ in cells})
out = {}
for v in ("intact", "shuffled", "sham"):
    m2 = np.array([np.mean([x for _, x in cells[("v2", b, v)]]) for b in books])
    m3 = np.array([np.mean([x for _, x in cells[("v3", b, v)]]) for b in books])
    w = {t: np.mean([np.var([x for _, x in cells[(t, b, v)]], ddof=1) for b in books]) for t in ("v2", "v3")}
    out[v] = {"within_cell_noise_of_mean(w/3)": float(np.mean(list(w.values())) / 3),
              "cross_arm_noise_of_mean(var(m2-m3)/2)": float(np.var(m2 - m3, ddof=1) / 2),
              "cross_arm_cov(true between-book var)": float(np.cov(m2, m3)[0, 1]),
              "within_arm_between_book_var_minus_noise": float(np.mean([np.var(m2, ddof=1), np.var(m3, ddof=1)]) - np.mean(list(w.values())) / 3)}
    # replicate-matched vs mismatched session correlation across arms
    s2 = np.array([[x for _, x in sorted(cells[("v2", b, v)])] for b in books])
    s3 = np.array([[x for _, x in sorted(cells[("v3", b, v)])] for b in books])
    matched = np.mean([np.corrcoef(s2[:, r], s3[:, r])[0, 1] for r in range(3)])
    mism = np.mean([np.corrcoef(s2[:, r], s3[:, q])[0, 1] for r in range(3) for q in range(3) if r != q])
    within = np.mean([np.corrcoef(s2[:, r], s2[:, q])[0, 1] for r in range(3) for q in range(3) if r < q] +
                     [np.corrcoef(s3[:, r], s3[:, q])[0, 1] for r in range(3) for q in range(3) if r < q])
    out[v]["session_corr_cross_arm_same_replicate"] = float(matched)
    out[v]["session_corr_cross_arm_other_replicate"] = float(mism)
    out[v]["session_corr_within_arm_between_replicates"] = float(within)
I2 = np.array([np.mean([x for _, x in cells[("v2", b, "intact")]]) for b in books]); S2 = np.array([np.mean([x for _, x in cells[("v2", b, "shuffled")]]) for b in books])
I3 = np.array([np.mean([x for _, x in cells[("v3", b, "intact")]]) for b in books]); S3 = np.array([np.mean([x for _, x in cells[("v3", b, "shuffled")]]) for b in books])
d2, d3 = I2 - S2, I3 - S3
out["paired_d"] = {"var_d_v2": float(np.var(d2, ddof=1)), "var_d_v3": float(np.var(d3, ddof=1)),
                   "cross_arm_noise_var_d(var(d2-d3)/2)": float(np.var(d2 - d3, ddof=1) / 2),
                   "cross_arm_cov_d(tau2)": float(np.cov(d2, d3)[0, 1]),
                   "within_cell_noise_var_d": float(out["intact"]["within_cell_noise_of_mean(w/3)"] + out["shuffled"]["within_cell_noise_of_mean(w/3)"])}
# session share distribution
allI = [x for (t, b, v), xs in cells.items() if v == "intact" for _, x in xs]
vals, counts = np.unique(np.round(allI, 3), return_counts=True)
out["intact_share_distribution"] = {str(k): int(c) for k, c in zip(vals, counts)}
print(json.dumps(out, indent=1))
(Path(__file__).parent / "noise_check.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
