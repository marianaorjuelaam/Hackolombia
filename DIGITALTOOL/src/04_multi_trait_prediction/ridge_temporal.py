"""
Stage 4 Phase 1: multi-trait expanding-window ridge baseline
==============================================================

Same scheme as `03_prediction/ridge_temporal.py` (SNP-BLUP in primal ridge
form, sufficient statistics per year, lambda tuned on year t-1, refit on
years < t, predict year t) — run once per trait, and with the real/imputed
SNP mask concatenated to the genotype as an extra 0/1 feature block, so the
model can weigh reconstructed calls differently from directly observed ones.

Traits vary a lot in coverage (see build_dataset.py), so each trait gets its
own row filter (lines where that trait's BLUE is non-null) and its own
per-year sufficient statistics — they can't share one precomputed block like
the single-trait version does.

Input:  data/processed/multi_trait_prediction/{X.npy, real_mask.npy, lines.parquet}
Output: data/processed/multi_trait_prediction/ridge_multitrait_results.csv

Usage:
    python ridge_temporal.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).parent.parent.parent.parent
DATA_DIR = BASE_DIR / "DIGITALTOOL" / "data" / "processed" / "multi_trait_prediction"

sys.path.insert(0, str(BASE_DIR / "DIGITALTOOL" / "src" / "03_prediction"))
from ridge_temporal import sufficient_stats, combine, solve_path, predict, metrics, pearson  # noqa: E402

MAX_SNP_NA = 0.20
LAMBDAS = np.logspace(1, 6, 26)
TEST_YEARS = [2006, 2007, 2008]
FIRST_YEAR = 2000
TRAITS = ["ERM", "MST", "PHT", "RTLP", "STLP", "TWT", "YLD_BE", "EHT"]


def load_data():
    X = np.load(DATA_DIR / "X.npy", mmap_mode="r")
    mask = np.load(DATA_DIR / "real_mask.npy", mmap_mode="r")
    lines = pd.read_parquet(DATA_DIR / "lines.parquet")
    keep_snps = np.where(np.isnan(X).mean(axis=0) < MAX_SNP_NA)[0]
    print(f"  {X.shape[0]} lines, {len(keep_snps)}/{X.shape[1]} SNPs with NA < {MAX_SNP_NA:.0%}")
    pre = (lines["YEAR"] < 2008).to_numpy()
    mu = np.nanmean(np.asarray(X[pre][:, keep_snps]), axis=0)
    return X, mask, lines, keep_snps, mu


def year_features(X, mask, keep_snps, mu, idx, use_mask):
    Xy = np.asarray(X[idx][:, keep_snps], dtype=np.float64)
    nan = np.isnan(Xy)
    Xy[nan] = np.broadcast_to(mu, Xy.shape)[nan]
    if not use_mask:
        return Xy
    My = np.asarray(mask[idx][:, keep_snps], dtype=np.float64)
    return np.concatenate([Xy, My], axis=1)


def run_ridge(trait, X, mask, lines, keep_snps, mu, use_mask=True):
    """Expanding-window ridge for one trait; returns one row per test year."""
    blue_col = f"BLUE_{trait}"
    obs = lines[blue_col].notna().to_numpy()
    y_all = lines[blue_col].to_numpy(dtype=np.float64)
    pops_all = lines["POP"].to_numpy()
    years_all = lines["YEAR"].to_numpy()

    years = sorted(lines.loc[obs, "YEAR"].unique())
    blocks, stats = {}, {}
    for yr in years:
        idx = np.where(obs & (years_all == yr))[0]
        if len(idx) == 0:
            continue
        Xy = year_features(X, mask, keep_snps, mu, idx, use_mask)
        blocks[yr] = (idx, Xy)
        stats[yr] = sufficient_stats(Xy, y_all[idx])

    rows = []
    for t in TEST_YEARS:
        if t not in blocks:
            continue
        train_prev = [y for y in years if FIRST_YEAR <= y < t - 1 and y in stats]
        if train_prev:
            xm, ym, betas = solve_path(combine([stats[y] for y in train_prev]), LAMBDAS)
            idx_v, Xv = blocks.get(t - 1, (None, None))
            if idx_v is not None:
                yv = y_all[idx_v]
                scores = [pearson(predict(Xv, xm, ym, b), yv) for b in betas]
                lam = LAMBDAS[int(np.nanargmax(scores))]
            else:
                lam = LAMBDAS[len(LAMBDAS) // 2]
        else:
            lam = LAMBDAS[len(LAMBDAS) // 2]

        train = [y for y in years if y < t and y in stats]
        if not train:
            continue
        xm, ym, betas = solve_path(combine([stats[y] for y in train]), [lam])
        idx_t, Xt = blocks[t]
        pred = predict(Xt, xm, ym, betas[0])
        res = metrics(pred, y_all[idx_t], pops_all[idx_t])
        res.update({"trait": trait, "use_mask": use_mask, "test_year": t, "lambda": lam,
                    "n_train": sum(stats[y]["n"] for y in train), "n_test": len(idx_t)})
        rows.append(res)
    return pd.DataFrame(rows)


def main():
    print("Loading data...")
    X, mask, lines, keep_snps, mu = load_data()

    show_cols = ["test_year", "n_train", "n_test", "r_all", "r_within", "gain_all", "gain_within"]
    all_rows = []
    for trait in TRAITS:
        print(f"\n=== {trait} (with mask) ===")
        r = run_ridge(trait, X, mask, lines, keep_snps, mu, use_mask=True)
        all_rows.append(r)
        if not r.empty:
            print(r[show_cols].round(3).to_string(index=False))

    # Isolate the mask's effect on YLD_BE (comparable to stage 03's single-trait ridge).
    print("\n=== YLD_BE (without mask, for comparison against stage 03) ===")
    r_nomask = run_ridge("YLD_BE", X, mask, lines, keep_snps, mu, use_mask=False)
    all_rows.append(r_nomask)
    if not r_nomask.empty:
        print(r_nomask[show_cols].round(3).to_string(index=False))

    out = pd.concat(all_rows, ignore_index=True)
    cols = ["trait", "use_mask", "test_year", "n_train", "n_test", "n_pops", "lambda",
            "r_all", "r_within", "gain_all", "oracle_gain_all", "gain_within", "oracle_gain_within"]
    out = out[cols]
    out.to_csv(DATA_DIR / "ridge_multitrait_results.csv", index=False)
    print(f"\nSaved {DATA_DIR / 'ridge_multitrait_results.csv'}")


if __name__ == "__main__":
    main()
