"""Call-free power analysis for a milder paragraph-shuffle arm on the fcr.v0 costed reader.

Inputs (read-only): research/quality-measurement/cost-that-bites/results-arm-v2.json and
results-arm-v3.json (per-session action records), and texts.json written by export_texts.py
from scratchpad COPIES of the fitness stores plus the candidate current-pipeline books.

Outputs: results.json beside this script. Nothing in the repository is written; bytecode is off.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import statistics
import sys
from pathlib import Path

import numpy as np

sys.dont_write_bytecode = True
REPO = Path(r"C:\DEV\LitHarness")
QM = REPO / "research" / "quality-measurement"
ARM = QM / "cost-that-bites"
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(QM))

import ablate  # noqa: E402  stdlib-only module; paragraphs(), _rng(), paragraph_shuffle()

# ------------------------------------------------------------------ frozen constants (verified)
CHUNK_WORDS = 300          # bcr.py:80
MIDSTREAM_CHUNK = 3        # feed_core.py:118
BUDGET_UNITS, READ_COST = 24, 3   # feed_core.py:104, :89
MIN_CHUNKS_FEED = MIDSTREAM_CHUNK + BUDGET_UNITS // READ_COST   # feed_core.py:123 -> 11
SHUFFLE_SALT = "cost-that-bites/shuffle"   # cost_that_bites.py
ALPHA = 0.10               # feed_core.CONTROL_ALPHA; 90% interval, two one-sided 5% tests
RESAMPLES = 2000           # bcr._resamples()
K = 3                      # replicates per version per book (v2 design)
assert MIN_CHUNKS_FEED == 11


def chunks(text: str, words: int = CHUNK_WORDS) -> list[str]:
    """Exact copy of bcr.chunks (bcr.py:282)."""
    out, current, size = [], [], 0
    for block in ablate.paragraphs(text):
        current.append(block)
        size += len(block.split())
        if size >= words:
            out.append("\n\n".join(current))
            current, size = [], 0
    if current:
        tail = "\n\n".join(current)
        if out:
            out[-1] = out[-1] + "\n\n" + tail
        else:
            out.append(tail)
    return out


def chunk_count_blocks(blocks: list[str], order: list[int]) -> int:
    """len(chunks(...)) computed on a paragraph order without re-joining text."""
    n, size = 0, 0
    pending = False
    for i in order:
        size += len(blocks[i].split())
        pending = True
        if size >= CHUNK_WORDS:
            n += 1
            size, pending = 0, False
    if pending and n == 0:
        n = 1
    return n


# ------------------------------------------------------------------ permutations of each family
def perm_book_shuffle(text: str, index: int) -> list[int]:
    """cost_that_bites.book_shuffle's order, exactly (index 0 = bare salt)."""
    blocks = ablate.paragraphs(text)
    order = list(range(len(blocks)))
    salt = SHUFFLE_SALT if index == 0 else f"{SHUFFLE_SALT}/{index}"
    ablate._rng(text, salt).shuffle(order)
    if order == list(range(len(blocks))):
        order = order[1:] + order[:1]
    return order


def perm_ablate(text: str, strength: float) -> list[int]:
    """ablate.paragraph_shuffle's order (bcr D1 family), exactly: pick round(s*N) positions,
    rotate their contents by one random non-zero offset. Deterministic per text: ONE variant."""
    blocks = ablate.paragraphs(text)
    n = len(blocks)
    rng = ablate._rng(text, "para")
    count = max(2, round(strength * n))
    picked = sorted(rng.sample(range(n), min(count, n)))
    offset = rng.randrange(1, len(picked))
    shuffled = picked[offset:] + picked[:offset]
    out = list(range(n))
    for target, source in zip(picked, shuffled):
        out[target] = source
    return out


def perm_partial(text: str, strength: float, index: int) -> list[int]:
    """Hypothetical milder book_shuffle: pick round(s*N) positions (seeded like book_shuffle, with
    a dose-tagged salt) and give their contents a uniformly random non-identity permutation."""
    blocks = ablate.paragraphs(text)
    n = len(blocks)
    rng = ablate._rng(text, f"{SHUFFLE_SALT}/partial/{strength}/{index}")
    count = max(2, round(strength * n))
    picked = sorted(rng.sample(range(n), count))
    src = picked[:]
    while src == picked:
        rng.shuffle(src)
    out = list(range(n))
    for target, source in zip(picked, src):
        out[target] = source
    return out


def metrics(order: list[int], blocks: list[str]) -> dict[str, float]:
    n = len(order)
    arr = np.asarray(order)
    displaced = float(np.mean(arr != np.arange(n)))
    broken = float(np.mean(arr[1:] != arr[:-1] + 1))
    # normalized Kendall distance (fraction of discordant pairs)
    inv = 0
    a = arr
    for i in range(n - 1):
        inv += int(np.sum(a[i + 1:] < a[i]))
    kendall = inv / (n * (n - 1) / 2)
    # window the reader sees: output positions inside chunks 1..MIN_CHUNKS_FEED of the dosed copy
    size, c, win_end = 0, 0, n
    for pos, i in enumerate(order):
        size += len(blocks[i].split())
        if size >= CHUNK_WORDS:
            c += 1
            size = 0
            if c == MIN_CHUNKS_FEED:
                win_end = pos + 1
                break
    w = arr[:win_end]
    broken_window = float(np.mean(w[1:] != w[:-1] + 1)) if len(w) > 1 else 0.0
    # share of the window's paragraphs that come from outside the window's original span
    foreign = float(np.mean(w >= win_end))
    return {"displaced": displaced, "broken_adjacency": broken, "kendall": kendall,
            "broken_adjacency_window": broken_window, "foreign_in_window": foreign}


# ------------------------------------------------------------------ 1. the sessions
def session_share(actions) -> float:
    reads = [w for a, w in actions if a == "read"]
    if not reads:
        return 0.25
    return sum(1 for w in reads if w == "A") / len(reads)


def load_arm(path: Path):
    d = json.loads(path.read_text(encoding="utf-8"))
    cells: dict[str, dict[str, list]] = {}
    for row in d["rows"]:
        s = row["session"]
        assert row["rotation"] == 0 and s["unanswered"] == 0
        book = row["target_name"][-2:]
        cells.setdefault(book, {}).setdefault(row["version"], []).append(
            (s["replicate"], session_share(s["actions"]), tuple(map(tuple, s["actions"]))))
    for book in cells:
        for v in cells[book]:
            cells[book][v].sort()
    # verify against the committed book means
    for book, vs in d["reading"]["book_means"].items():
        for v, m in vs.items():
            mine = statistics.fmean(x[1] for x in cells[book][v])
            assert abs(mine - m) < 1e-9, (path.name, book, v, mine, m)
    return d, cells


def cluster_interval(values: np.ndarray, rng: np.random.Generator, alpha=ALPHA, B=RESAMPLES):
    """bcr.cluster_interval's percentile rule (one value per cluster), numpy RNG."""
    n = len(values)
    idx = rng.integers(0, n, size=(B, n))
    means = np.sort(values[idx].mean(axis=1))
    tail = max(1, math.ceil(alpha / 2 * B))
    return float(values.mean()), float(means[tail - 1]), float(means[B - tail])


def main() -> None:
    results: dict = {"inputs": {}, "notes": []}
    arms = {}
    for tag in ("v2", "v3"):
        d, cells = load_arm(ARM / f"results-arm-{tag}.json")
        arms[tag] = cells
        results["inputs"][tag] = {
            "file": f"research/quality-measurement/cost-that-bites/results-arm-{tag}.json",
            "registered_intact_minus_shuffled": d["reading"]["target_read_share"]["intact_minus_shuffled"],
            "registered_sham_minus_shuffled": d["reading"]["target_read_share"]["sham_minus_shuffled"],
        }
    books = sorted(arms["v2"])

    # Are v3's intact/sham sessions fresh draws or cache replays of v2?
    same_actions = {v: sum(arms["v2"][b][v][r][2] == arms["v3"][b][v][r][2]
                           for b in books for r in range(K)) for v in ("intact", "sham", "shuffled")}
    results["v3_sessions_identical_to_v2"] = {v: f"{c} of {len(books) * K}" for v, c in same_actions.items()}

    # ---- 2. variance decomposition per arm
    var = {}
    per_book = {}
    for tag, cells in arms.items():
        I = np.array([statistics.fmean(x[1] for x in cells[b]["intact"]) for b in books])
        S = np.array([statistics.fmean(x[1] for x in cells[b]["shuffled"]) for b in books])
        H = np.array([statistics.fmean(x[1] for x in cells[b]["sham"]) for b in books])
        wv = {v: float(np.mean([np.var([x[1] for x in cells[b][v]], ddof=1) for b in books]))
              for v in ("intact", "shuffled", "sham")}
        d_is, d_ih, d_hs = I - S, I - H, H - S
        noise_is = (wv["intact"] + wv["shuffled"]) / K
        noise_ih = (wv["intact"] + wv["sham"]) / K
        var[tag] = {
            "mean_intact_minus_shuffled": float(d_is.mean()),
            "paired_sd_intact_minus_shuffled": float(d_is.std(ddof=1)),
            "se_intact_minus_shuffled": float(d_is.std(ddof=1) / math.sqrt(len(books))),
            "books_positive": int(np.sum(d_is > 0)), "books_negative": int(np.sum(d_is < 0)),
            "paired_sd_intact_minus_sham": float(d_ih.std(ddof=1)),
            "paired_sd_sham_minus_shuffled": float(d_hs.std(ddof=1)),
            "within_cell_session_sd": {v: math.sqrt(x) for v, x in wv.items()},
            "noise_part_of_paired_var_is": noise_is,
            "tau2_effect_heterogeneity_is": float(d_is.var(ddof=1) - noise_is),
            "tau2_null_contrast_ih": float(d_ih.var(ddof=1) - noise_ih),
            "between_book_sd_intact_mean": float(I.std(ddof=1)),
            "between_book_sd_intact_true": math.sqrt(max(0.0, I.var(ddof=1) - wv["intact"] / K)),
            "between_book_sd_shuffled_mean": float(S.std(ddof=1)),
            "between_book_sd_shuffled_true": math.sqrt(max(0.0, S.var(ddof=1) - wv["shuffled"] / K)),
            "corr_intact_shuffled_book_means": float(np.corrcoef(I, S)[0, 1]),
            "session_sd_all_intact": float(np.std([x[1] for b in books for x in cells[b]["intact"]], ddof=1)),
        }
        per_book[tag] = {"I": I, "S": S, "H": H, "d": d_is}
    d2, d3 = per_book["v2"]["d"], per_book["v3"]["d"]
    rank = lambda x: np.argsort(np.argsort(x))
    cross = {
        "pearson_d_v2_v3": float(np.corrcoef(d2, d3)[0, 1]),
        "spearman_d_v2_v3": float(np.corrcoef(rank(d2), rank(d3))[0, 1]),
        "cov_d_v2_v3_as_tau2_estimate": float(np.cov(d2, d3)[0, 1]),
        "pearson_intact_v2_v3": float(np.corrcoef(per_book["v2"]["I"], per_book["v3"]["I"])[0, 1]),
        "pearson_shuffled_v2_v3": float(np.corrcoef(per_book["v2"]["S"], per_book["v3"]["S"])[0, 1]),
        "per_book_d": {b: [round(float(x), 4), round(float(y), 4)] for b, x, y in zip(books, d2, d3)},
    }
    var["cross_arm"] = cross
    results["variance"] = var

    # design-input summaries (pooled across arms for SIZING only, as v2 sized from v1)
    delta_full = float((d2.mean() + d3.mean()) / 2)
    sd_paired_full = float(math.sqrt((d2.var(ddof=1) + d3.var(ddof=1)) / 2))
    w_I = statistics.fmean([var[t]["within_cell_session_sd"]["intact"] ** 2 for t in arms])
    w_S = statistics.fmean([var[t]["within_cell_session_sd"]["shuffled"] ** 2 for t in arms])
    w_H = statistics.fmean([var[t]["within_cell_session_sd"]["sham"] ** 2 for t in arms])
    tau2_eff = max(0.0, statistics.fmean([var[t]["tau2_effect_heterogeneity_is"] for t in arms]))
    tau2_null = max(0.0, statistics.fmean([var[t]["tau2_null_contrast_ih"] for t in arms]))
    results["design_inputs"] = {
        "delta_full_mean_of_arms": delta_full, "delta_full_low_arm": float(min(d2.mean(), d3.mean())),
        "paired_sd_full_rms_of_arms": sd_paired_full,
        "within_cell_var": {"intact": w_I, "shuffled": w_S, "sham": w_H},
        "tau2_effect_heterogeneity": tau2_eff, "tau2_null_contrast": tau2_null,
    }

    # ---- 3. dose metrics and chunk floor on the fitness shelf
    texts = json.loads((OUT / "texts.json").read_text(encoding="utf-8"))
    fitness = texts["fitness"]
    doses = (0.15, 0.35, 0.65, 1.0)
    seeds = range(10)
    fam_metrics = {"book_shuffle_full": [], **{f"partial_{s}": [] for s in doses},
                   **{f"ablate_{s}": [] for s in doses}}
    floor = {k: {"min": 99, "fail": []} for k in fam_metrics}
    intact_chunks = {}
    for name, text in fitness:
        blocks = ablate.paragraphs(text)
        intact_chunks[name] = len(chunks(text))
        assert chunk_count_blocks(blocks, list(range(len(blocks)))) == intact_chunks[name]
        for idx in seeds:
            o = perm_book_shuffle(text, idx)
            fam_metrics["book_shuffle_full"].append(metrics(o, blocks))
            c = chunk_count_blocks(blocks, o)
            floor["book_shuffle_full"]["min"] = min(floor["book_shuffle_full"]["min"], c)
            if c < MIN_CHUNKS_FEED:
                floor["book_shuffle_full"]["fail"].append(f"{name}@seed{idx}:{c}")
            for s in doses:
                o = perm_partial(text, s, idx)
                fam_metrics[f"partial_{s}"].append(metrics(o, blocks))
                c = chunk_count_blocks(blocks, o)
                key = f"partial_{s}"
                floor[key]["min"] = min(floor[key]["min"], c)
                if c < MIN_CHUNKS_FEED:
                    floor[key]["fail"].append(f"{name}@seed{idx}:{c}")
        for s in doses:  # ablate family: one deterministic variant per text
            o = perm_ablate(text, s)
            # verify our reconstruction against the real function (joined with "\n")
            assert ablate.paragraph_shuffle(text, s) == "\n".join(blocks[i] for i in o)
            real = len(chunks(ablate.paragraph_shuffle(text, s)))
            assert real == chunk_count_blocks(blocks, o)
            fam_metrics[f"ablate_{s}"].append(metrics(o, blocks))
            key = f"ablate_{s}"
            floor[key]["min"] = min(floor[key]["min"], real)
            if real < MIN_CHUNKS_FEED:
                floor[key]["fail"].append(f"{name}:{real}")
    # known fact check: fitness-08 seed 4 chunks to 10 (PREREG-v3 amendment a)
    f08 = dict(fitness)["fitness-08"]
    assert chunk_count_blocks(ablate.paragraphs(f08), perm_book_shuffle(f08, 4)) == 10
    summary = {}
    for k, rows in fam_metrics.items():
        summary[k] = {m: float(np.mean([r[m] for r in rows])) for m in rows[0]}
        summary[k]["n_variants"] = len(rows)
        summary[k]["chunk_min"] = floor[k]["min"]
        summary[k]["below_floor"] = floor[k]["fail"]
    paras = [len(ablate.paragraphs(t)) for _, t in fitness]
    results["shelf"] = {
        "intact_chunks": intact_chunks, "paragraphs_per_book": [min(paras), statistics.fmean(paras), max(paras)],
        "words_per_book": [min(len(t.split()) for _, t in fitness), max(len(t.split()) for _, t in fitness)],
        "families": summary,
        "note": "partial_s seeds 0-9 are a hypothetical seeded partial book_shuffle; ablate_s is the "
                "bcr D1 paragraph_shuffle, deterministic per text (one variant, no seed index).",
    }

    # ---- attenuation assumptions: f(s) = effect(s) / effect(full book_shuffle)
    full = summary["book_shuffle_full"]
    attenuation = {}
    for fam in ("partial", "ablate"):
        for s in (0.35, 0.65):
            m = summary[f"{fam}_{s}"]
            a = {
                "A1_linear_in_strength": s,
                "A2_broken_adjacency_ratio": m["broken_adjacency"] / full["broken_adjacency"],
                "A3_kendall_ratio": m["kendall"] / full["kendall"],
                "A4_convex_s_squared": s * s,
            }
            a["bracket"] = [min(a.values()), max(a.values())]
            attenuation[f"{fam}_{s}"] = a
    results["attenuation"] = attenuation

    # ---- 4. power
    rng = np.random.default_rng(20260922)
    pooled = {b: {v: np.array([x[1] for t in arms for x in arms[t][b][v]]) for v in ("intact", "shuffled", "sham")}
              for b in books}

    P = np.stack([np.stack([pooled[b][v] for v in ("intact", "shuffled", "sham")]) for b in books])  # (20,3,6)
    assert P.shape == (len(books), 3, 2 * K)

    def lower_bounds(D: np.ndarray, batch: int = 25) -> np.ndarray:
        """bcr.cluster_interval's lower percentile bound, per row of D (trials x books)."""
        T, n = D.shape
        tail = max(1, math.ceil(ALPHA / 2 * RESAMPLES))
        out = np.empty(T)
        for a in range(0, T, batch):
            blk = D[a:a + batch]
            idx = rng.integers(0, n, size=(blk.shape[0], RESAMPLES, n))
            means = np.take_along_axis(blk[:, None, :].repeat(RESAMPLES, 1), idx, axis=2).mean(axis=2)
            means.sort(axis=1)
            out[a:a + batch] = means[:, tail - 1]
        return out

    def sim_parametric(f: float, n: int, trials: int, hetero: str, k: int = K) -> dict[str, float]:
        """Book-level normal model: book effect ~ N(f*delta, tau_null2 + tau_eff2*(f^2 or 1)),
        cell means carry session noise/K; the dosed cell's noise is shared by both contrasts."""
        w_D = w_I + f * (w_S - w_I)
        t_eff = tau2_eff * (f * f if hetero == "proportional" else 1.0)
        book_eff = rng.normal(f * delta_full, math.sqrt(tau2_null + t_eff), (trials, n))
        eI = rng.normal(0, math.sqrt(w_I / k), (trials, n))
        eD = rng.normal(0, math.sqrt(w_D / k), (trials, n))
        eH = rng.normal(0, math.sqrt(w_H / k), (trials, n))
        d = book_eff + eI - eD
        hs = book_eff + eH - eD
        lo, lo2 = lower_bounds(d), lower_bounds(hs)
        return {"primary": float(np.mean(lo > 0)), "joint": float(np.mean((lo > 0) & (lo2 > 0))),
                "sd_d": float(d.std(axis=1, ddof=1).mean())}

    def sim_empirical(f: float, n: int, trials: int) -> dict[str, float]:
        """Resample books from the 20 and sessions from each book's pooled v2+v3 cells (6 per
        version); a dosed session is a shuffled session with probability f, else an intact one."""
        bs = rng.integers(0, len(books), (trials, n))[..., None]
        draw = lambda v: P[bs, v, rng.integers(0, 2 * K, (trials, n, K))]
        I, H = draw(0), draw(2)
        D = np.where(rng.random((trials, n, K)) < f, draw(1), draw(0))
        d = I.mean(axis=2) - D.mean(axis=2)
        hs = H.mean(axis=2) - D.mean(axis=2)
        lo, lo2 = lower_bounds(d), lower_bounds(hs)
        return {"primary": float(np.mean(lo > 0)), "joint": float(np.mean((lo > 0) & (lo2 > 0))),
                "sd_d": float(d.std(axis=1, ddof=1).mean())}

    # analytic n for 0.8 power on the primary (one-sided 5% z, percentile-bootstrap-like)
    z = 1.6449 + 0.8416

    def n_for_08(f: float, hetero: str) -> float:
        w_D = w_I + f * (w_S - w_I)
        t_eff = tau2_eff * (f * f if hetero == "proportional" else 1.0)
        sd_d = math.sqrt(tau2_null + t_eff + (w_I + w_D) / K)
        return (z * sd_d / (f * delta_full)) ** 2 if f > 0 else float("inf")

    trials = 1000
    grid = {}
    f_values = sorted({0.0, 1.0} | {round(a[k], 4) for a in attenuation.values()
                                    for k in a if k != "bracket"})
    for f in f_values:
        row = {"parametric_proportional_n20": sim_parametric(f, 20, trials, "proportional"),
               "parametric_constant_n20": sim_parametric(f, 20, trials, "constant"),
               "empirical_mixture_n20": sim_empirical(f, 20, trials),
               "n_for_0.8_analytic_proportional": n_for_08(f, "proportional"),
               "n_for_0.8_analytic_constant": n_for_08(f, "constant")}
        grid[str(f)] = row
        print(f"f={f:.4f}", {k: (v if not isinstance(v, dict) else {kk: round(vv, 3) for kk, vv in v.items()})
                             for k, v in row.items()})
    results["power_grid_by_attenuation"] = grid

    # ---- 4b. sensitivity: variance split, replicates, a smaller full effect, a 6-book held-out set
    phi = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))
    cross_tau2 = float(np.cov(d2, d3)[0, 1])            # between-book effect variance, cross-arm
    cross_noise = float(np.var(d2 - d3, ddof=1) / 2)    # noise variance of a book's d at k=3

    def var_d(f: float, split: str, k: int = K) -> float:
        if split == "within_arm":   # noise from replicate spread inside cells, tau2 scales f^2
            w_D = w_I + f * (w_S - w_I)
            return tau2_null + tau2_eff * f * f + (w_I + w_D) / k
        if split == "cross_arm":    # tau2 from Cov(d_v2, d_v3), noise from Var(d_v2 - d_v3)/2
            return cross_tau2 * f * f + cross_noise * K / k
        raise ValueError(split)

    def analytic(f: float, n: int, split: str, k: int = K, delta: float = delta_full) -> float:
        sd = math.sqrt(var_d(f, split, k))
        return phi(f * delta / (sd / math.sqrt(n)) - 1.6449)

    def n08(f: float, split: str, k: int = K, delta: float = delta_full) -> float:
        return (z * math.sqrt(var_d(f, split, k)) / (f * delta)) ** 2

    table = {}
    for key, a in attenuation.items():
        for aname, f in a.items():
            if aname == "bracket":
                continue
            g = grid[str(round(f, 4))]
            table[f"{key}|{aname}"] = {
                "f": f, "expected_shift": f * delta_full,
                "power_n20_primary": {"parametric_within_arm_proportional": g["parametric_proportional_n20"]["primary"],
                                      "parametric_within_arm_constant_hetero": g["parametric_constant_n20"]["primary"],
                                      "empirical_mixture": g["empirical_mixture_n20"]["primary"],
                                      "analytic_cross_arm_split": analytic(f, 20, "cross_arm")},
                "power_n20_joint_moves_with_order": {"parametric_within_arm_proportional": g["parametric_proportional_n20"]["joint"],
                                                     "empirical_mixture": g["empirical_mixture_n20"]["joint"]},
                "books_for_0.8_primary_k3": {"analytic_within_arm": n08(f, "within_arm"),
                                             "analytic_cross_arm": n08(f, "cross_arm")},
                "power_n20_k6_analytic": {"within_arm": analytic(f, 20, "within_arm", 6), "cross_arm": analytic(f, 20, "cross_arm", 6)},
                "books_for_0.8_k6_analytic": {"within_arm": n08(f, "within_arm", 6), "cross_arm": n08(f, "cross_arm", 6)},
                "power_n20_if_full_effect_is_v2s_0.164": {"within_arm": analytic(f, 20, "within_arm", delta=float(d2.mean())),
                                                          "cross_arm": analytic(f, 20, "cross_arm", delta=float(d2.mean()))},
            }
    table["full_shuffle_reference|f=1"] = {"f": 1.0, "expected_shift": delta_full,
        "power_n20_primary": {"parametric_within_arm_proportional": grid["1.0"]["parametric_proportional_n20"]["primary"],
                              "empirical_mixture": grid["1.0"]["empirical_mixture_n20"]["primary"],
                              "analytic_cross_arm_split": analytic(1.0, 20, "cross_arm")}}
    results["power_table"] = table
    results["k6_n20_parametric_within_arm_sim"] = {
        str(round(f, 4)): sim_parametric(f, 20, 1000, "proportional", k=6)
        for f in (0.1225, 0.35, 0.4225, 0.5295, 0.5734, 0.617, 0.65, 0.7233, 0.8788, 1.0)}
    results["variance_splits"] = {"within_arm": {"tau2": tau2_eff, "noise_var_d_k3": var_d(1.0, "within_arm") - tau2_eff},
                                  "cross_arm": {"tau2": cross_tau2, "noise_var_d_k3": cross_noise},
                                  "total_var_d_observed_rms": sd_paired_full ** 2}
    results["held_out_6_books"] = {
        f"f={f}": {"power_within_arm": analytic(f, 6, "within_arm"), "power_cross_arm": analytic(f, 6, "cross_arm"),
                   "simulated_empirical_n6": sim_empirical(f, 6, 1000)["primary"]}
        for f in (1.0, 0.65, 0.35)}

    # empirical n for 0.8: search n (books) with the mixture model, for the key f values
    def n_search(f: float) -> dict:
        out = {}
        for n in (20, 30, 40, 50, 60, 80, 100, 120, 160):
            p = sim_empirical(f, n, 400)["primary"]
            out[n] = p
            if p >= 0.8:
                break
        return out

    results["empirical_n_search"] = {}
    for key, a in attenuation.items():
        for aname in ("A1_linear_in_strength", "A2_broken_adjacency_ratio", "A4_convex_s_squared"):
            f = round(a[aname], 4)
            tag = f"{key}:{aname}:{f}"
            if f >= 0.3:
                results["empirical_n_search"][tag] = n_search(f)
                print(tag, results["empirical_n_search"][tag])

    # ---- 5. current-pipeline books against the floor
    cand = {}
    for name, entry in texts["candidates"].items():
        text = entry["text"]
        blocks = ablate.paragraphs(text)
        c_intact = len(chunks(text))
        # window-matched copy: first 13 chunks' worth (the fitness shelf's 11-13 chunk length)
        cand[name] = {"chapters": entry["chapters"], "words": len(text.split()),
                      "paragraphs": len(blocks), "chunks_intact": c_intact,
                      "meets_floor_intact": c_intact >= MIN_CHUNKS_FEED,
                      "lexical_chapter_sort_breaks_order": entry.get("lexical_order_differs"),
                      "full_shuffle_chunk_min_seeds0_9": min(chunk_count_blocks(blocks, perm_book_shuffle(text, i)) for i in range(10)),
                      "partial_0.65_chunk_min_seeds0_9": min(chunk_count_blocks(blocks, perm_partial(text, 0.65, i)) for i in range(10)),
                      "partial_0.35_chunk_min_seeds0_9": min(chunk_count_blocks(blocks, perm_partial(text, 0.35, i)) for i in range(10)),
                      "ablate_0.65_chunks": chunk_count_blocks(blocks, perm_ablate(text, 0.65)),
                      "ablate_0.35_chunks": chunk_count_blocks(blocks, perm_ablate(text, 0.35)),
                      "foreign_in_window_full_shuffle": float(np.mean([metrics(perm_book_shuffle(text, i), blocks)["foreign_in_window"] for i in range(3)])),
                      "foreign_in_window_partial_0.65": float(np.mean([metrics(perm_partial(text, 0.65, i), blocks)["foreign_in_window"] for i in range(3)])),
                      "reader_window_words": sum(len(c.split()) for c in chunks(text)[:MIN_CHUNKS_FEED])}
    results["current_pipeline_books"] = cand

    (OUT / "results.json").write_text(json.dumps(results, indent=2, default=float), encoding="utf-8")
    print(json.dumps({k: results[k] for k in ("variance", "design_inputs", "attenuation")}, indent=1, default=float))
    print(json.dumps(results["shelf"]["families"], indent=1))
    print(json.dumps(cand, indent=1))


if __name__ == "__main__":
    main()
