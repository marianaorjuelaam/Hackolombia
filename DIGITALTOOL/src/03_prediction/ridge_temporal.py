"""
Prediction Phase 1: Temporal ridge baseline (SNP-BLUP in primal form)
======================================================================

Expanding-window validation: for each test year t, train on every line from
years < t and predict the environment-adjusted yield (BLUE) of year-t lines.

Ridge on markers is equivalent to gBLUP but only needs a p x p system
(p = number of SNPs), so it never builds the n x n relationship matrix.
The penalty is chosen on year t-1 (trained on years < t-1), never on year t.

Metrics per test year:
- r_all:      Pearson r between predicted and observed BLUE (all lines)
- r_within:   mean Pearson r inside each population (pops with >= MIN_POP_SIZE lines)
- gain_all:   mean BLUE of the predicted top 20% minus year mean (oracle = true top 20%)
- gain_within: same, selecting the top 20% inside each population

Input:  data/processed/prediction/{X.npy, lines.parquet}  (from build_dataset.py)
Output: data/processed/prediction/ridge_temporal_results.csv

Usage:
    python ridge_temporal.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).parent.parent.parent.parent
DATA_DIR = BASE_DIR / "DIGITALTOOL" / "data" / "processed" / "prediction"

MAX_SNP_NA = 0.20
MIN_POP_SIZE = 20
TOP_FRACTION = 0.20
LAMBDAS = np.logspace(1, 6, 26)
TEST_YEARS = list(range(2002, 2009))
FIRST_YEAR = 2000


def load_data():
    X = np.load(DATA_DIR / "X.npy", mmap_mode="r")
    lines = pd.read_parquet(DATA_DIR / "lines.parquet")
    keep_snps = np.where(np.isnan(X).mean(axis=0) < MAX_SNP_NA)[0]
    print(f"  {X.shape[0]} lines, {len(keep_snps)}/{X.shape[1]} SNPs with NA < {MAX_SNP_NA:.0%}")
    # Mean imputation with the mean of pre-2008 lines: 2008 is never used for fitting anything.
    pre = (lines["YEAR"] < 2008).to_numpy()
    mu = np.nanmean(np.asarray(X[pre][:, keep_snps]), axis=0)
    return X, lines, keep_snps, mu


def year_block(X, lines, keep_snps, mu, year):
    idx = np.where(lines["YEAR"].to_numpy() == year)[0]
    Xy = np.asarray(X[idx][:, keep_snps], dtype=np.float64)
    nan = np.isnan(Xy)
    Xy[nan] = np.broadcast_to(mu, Xy.shape)[nan]
    return idx, Xy


def sufficient_stats(Xy, y):
    return {"n": len(y), "s": Xy.sum(axis=0), "A": Xy.T @ Xy, "b": Xy.T @ y, "ys": y.sum()}


def combine(stats_list):
    return {k: sum(s[k] for s in stats_list) for k in ("n", "s", "A", "b", "ys")}


def solve_path(st, lambdas):
    """Return (x_mean, y_mean, betas[len(lambdas), p]) for centered ridge."""
    n = st["n"]
    xm, ym = st["s"] / n, st["ys"] / n
    Ac = st["A"] - n * np.outer(xm, xm)
    bc = st["b"] - n * xm * ym
    w, V = np.linalg.eigh(Ac)
    w = np.clip(w, 0, None)
    Vb = V.T @ bc
    betas = np.stack([V @ (Vb / (w + lam)) for lam in lambdas])
    return xm, ym, betas


def predict(Xy, xm, ym, beta):
    return ym + (Xy - xm) @ beta.T if beta.ndim == 2 else ym + (Xy - xm) @ beta


def pearson(a, b):
    if len(a) < 3 or a.std() == 0 or b.std() == 0:
        return np.nan
    return float(np.corrcoef(a, b)[0, 1])


def top_gain(pred, y, frac=TOP_FRACTION):
    k = max(1, int(round(len(y) * frac)))
    return float(y[np.argsort(-pred)[:k]].mean() - y.mean())


def metrics(pred, y, pops):
    out = {"r_all": pearson(pred, y), "gain_all": top_gain(pred, y),
           "oracle_gain_all": top_gain(y, y)}
    rs, gs, os_, ws = [], [], [], []
    for pop in np.unique(pops):
        m = pops == pop
        if m.sum() < MIN_POP_SIZE:
            continue
        rs.append(pearson(pred[m], y[m]))
        gs.append(top_gain(pred[m], y[m]))
        os_.append(top_gain(y[m], y[m]))
        ws.append(m.sum())
    ws = np.array(ws, dtype=float)
    out["r_within"] = float(np.nansum(np.array(rs) * ws) / ws[~np.isnan(rs)].sum())
    out["gain_within"] = float(np.average(gs, weights=ws))
    out["oracle_gain_within"] = float(np.average(os_, weights=ws))
    out["n_pops"] = len(ws)
    return out


def main():
    print("Loading data...")
    X, lines, keep_snps, mu = load_data()
    y_all = lines["BLUE"].to_numpy(dtype=np.float64)
    years = sorted(lines["YEAR"].unique())

    print("Computing per-year sufficient statistics...")
    blocks, stats = {}, {}
    for yr in years:
        idx, Xy = year_block(X, lines, keep_snps, mu, yr)
        blocks[yr] = (idx, Xy)
        stats[yr] = sufficient_stats(Xy, y_all[idx])
        print(f"  {yr}: {len(idx)} lines")

    rows = []
    for t in TEST_YEARS:
        # 1) choose lambda on year t-1 using years < t-1
        train_prev = [y for y in years if FIRST_YEAR <= y < t - 1]
        if train_prev:
            xm, ym, betas = solve_path(combine([stats[y] for y in train_prev]), LAMBDAS)
            idx_v, Xv = blocks[t - 1]
            yv = y_all[idx_v]
            scores = [pearson(predict(Xv, xm, ym, b), yv) for b in betas]
            lam = LAMBDAS[int(np.nanargmax(scores))]
        else:
            lam = LAMBDAS[len(LAMBDAS) // 2]

        # 2) refit on all years < t with that lambda, predict year t
        train = [y for y in years if y < t]
        xm, ym, betas = solve_path(combine([stats[y] for y in train]), [lam])
        idx_t, Xt = blocks[t]
        pred = predict(Xt, xm, ym, betas[0])
        res = metrics(pred, y_all[idx_t], lines["POP"].to_numpy()[idx_t])
        res.update({"test_year": t, "lambda": lam, "n_train": sum(stats[y]["n"] for y in train),
                    "n_test": len(idx_t)})
        rows.append(res)
        print(f"  test {t}: train n={res['n_train']}, lambda={lam:.0f} | "
              f"r_all={res['r_all']:.3f}  r_within={res['r_within']:.3f}  "
              f"gain_all={res['gain_all']:.2f}/{res['oracle_gain_all']:.2f}  "
              f"gain_within={res['gain_within']:.2f}/{res['oracle_gain_within']:.2f}")

    out = pd.DataFrame(rows)[["test_year", "n_train", "n_test", "n_pops", "lambda", "r_all", "r_within",
                              "gain_all", "oracle_gain_all", "gain_within", "oracle_gain_within"]]
    out.to_csv(DATA_DIR / "ridge_temporal_results.csv", index=False)
    print(out.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
