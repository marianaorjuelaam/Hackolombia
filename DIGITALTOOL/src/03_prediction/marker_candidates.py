"""
Prediction Phase 2: Candidate marker regions with replicated effects
=====================================================================

For each trait, estimates the effect of every SNP INSIDE each family (genotype and
phenotype centered within family, so population structure does not create effects),
using years < 2008 as discovery and 2008 as independent replication.

A SNP is a candidate when |t| > T_DISCOVERY in discovery, the sign agrees in 2008
and |t| > T_REPLICATION there. Candidates are grouped into LD regions (average-linkage
clustering of within-family SNP correlations) so a region is reported once, by its
lead SNP. Effects are marginal (one SNP at a time) and SNPs are markers, not causal variants.

Input:  data/processed/prediction/{X.npy, lines.parquet, snps.txt}
        Simplified Hackathon Dataset V3/C1_Phenotype_Data_V2.csv
Output: data/processed/prediction/snp_effects_all_traits.csv   (one row per SNP)
        data/processed/prediction/marker_regions_{trait}.csv   (one row per LD region)

Usage:
    python marker_candidates.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform

sys.path.insert(0, str(Path(__file__).parent))
import build_dataset as bd
import ridge_temporal as rt

BASE_DIR = Path(__file__).parent.parent.parent.parent
DATA_DIR = BASE_DIR / "DIGITALTOOL" / "data" / "processed" / "prediction"
PHENO_CSV = BASE_DIR / "Simplified Hackathon Dataset V3" / "C1_Phenotype_Data_V2.csv"

TRAITS = ["YLD_BE", "MST", "ERM", "TWT"]
T_DISCOVERY = 5.0
T_REPLICATION = 2.5
LD_DISTANCE = 0.5       # cut of 1 - |r| in average linkage (mean |r| >= 0.5 inside a region)
LD_SAMPLE = 20000


def load_traits() -> pd.DataFrame:
    cols = ["YEAR_x", "LOC", "LINE_UNIQUE_ID", "GERMPLASM_ID_TESTER"] + TRAITS
    ph = pd.read_csv(PHENO_CSV, usecols=cols, low_memory=False)
    ph = ph.rename(columns={"YEAR_x": "YEAR", "LINE_UNIQUE_ID": "LINE_ID", "GERMPLASM_ID_TESTER": "TESTER"})
    ph["TESTER"] = ph["TESTER"].fillna(-1).astype(int).astype(str)
    ph["ENV"] = ph["YEAR"].astype(int).astype(str) + "_" + ph["LOC"].astype(str)
    return ph


def line_blues(ph: pd.DataFrame, trait: str) -> pd.DataFrame:
    """Environment- and tester-adjusted mean per line (same backfitting as build_dataset.py)."""
    d = ph[ph[trait].notna()].copy()
    d[bd.TRAIT] = d[trait]
    out = []
    for _, df in d.groupby("YEAR"):
        out.append(bd.fit_additive_model(df)[["LINE_ID", "BLUE"]])
    return pd.concat(out, ignore_index=True)


def load_genotypes():
    X = np.load(DATA_DIR / "X.npy", mmap_mode="r")
    lines = pd.read_parquet(DATA_DIR / "lines.parquet")
    snps = np.array((DATA_DIR / "snps.txt").read_text().split("\n"))
    keep = np.where(np.isnan(X).mean(axis=0) < rt.MAX_SNP_NA)[0]
    X = np.asarray(X[:, keep], dtype=np.float32)
    pre = (lines["YEAR"] < 2008).to_numpy()
    mu = np.nanmean(X[pre], axis=0)
    for j in range(X.shape[1]):
        col = X[:, j]
        col[np.isnan(col)] = mu[j]
    X -= mu
    sd = X[pre].std(axis=0)
    sd[sd < 1e-6] = 1.0
    X /= sd
    return X, lines, snps[keep]


def center_within(A: np.ndarray, codes: np.ndarray, rows: np.ndarray) -> None:
    """In place: subtract the family mean over `rows` from those rows."""
    for c in np.unique(codes[rows]):
        ii = rows[codes[rows] == c]
        A[ii] -= A[ii].mean(axis=0)


def within_effects(Xw, yw, rows, codes):
    """Within-family correlation of every SNP with the trait, and its t statistic."""
    xs, ys = Xw[rows], yw[rows]
    r = (xs.T @ ys) / np.sqrt((xs ** 2).sum(axis=0) * (ys ** 2).sum() + 1e-12)
    n_eff = len(rows) - len(np.unique(codes[rows]))
    return r, r * np.sqrt(n_eff), float(ys.std())


def main():
    print("Loading genotypes...")
    X, lines, snp_names = load_genotypes()
    years = lines["YEAR"].to_numpy()
    codes, _ = pd.factorize(lines["POP"].to_numpy())
    Xw = X.copy()
    center_within(Xw, codes, np.arange(len(X)))

    print("Clustering SNPs into LD regions (within-family correlations)...")
    rng = np.random.default_rng(0)
    sub = rng.choice(len(Xw), size=min(LD_SAMPLE, len(Xw)), replace=False)
    Xs = Xw[sub] / (Xw[sub].std(axis=0) + 1e-9)
    corr = np.clip((Xs.T @ Xs) / len(Xs), -1, 1)
    dist = 1 - np.abs(corr)
    np.fill_diagonal(dist, 0)
    region = fcluster(linkage(squareform(dist, checks=False), "average"), t=LD_DISTANCE, criterion="distance")
    print(f"  {len(snp_names)} SNPs -> {region.max()} LD regions")

    ph = load_traits()
    table = pd.DataFrame({"SNP": snp_names, "LD_REGION": region})
    for trait in TRAITS:
        blue = lines[["LINE_ID"]].merge(line_blues(ph, trait), on="LINE_ID", how="left")["BLUE"].to_numpy(float)
        ok = ~np.isnan(blue)
        yc = blue - pd.Series(blue).groupby(years).transform("mean").to_numpy()
        yw = yc.copy()
        yw[~ok] = 0.0
        center_within(yw[:, None], codes, np.where(ok)[0])
        disc, rep = np.where(ok & (years < 2008))[0], np.where(ok & (years == 2008))[0]
        r_d, t_d, sd_y = within_effects(Xw, yw, disc, codes)
        r_r, t_r, _ = within_effects(Xw, yw, rep, codes)
        table[f"{trait}_r"], table[f"{trait}_t"] = r_d, t_d
        table[f"{trait}_r2008"], table[f"{trait}_t2008"] = r_r, t_r
        table[f"{trait}_effect"] = r_d * sd_y   # change in trait (own units) per 1 sd of the SNP, within family
        cand = (np.abs(t_d) > T_DISCOVERY) & (np.sign(r_d) == np.sign(r_r)) & (np.abs(t_r) > T_REPLICATION)
        table[f"{trait}_candidate"] = cand
        print(f"{trait}: |t|>{T_DISCOVERY:g} in discovery: {(np.abs(t_d) > T_DISCOVERY).sum()} SNPs | "
              f"replicated in 2008: {cand.sum()} SNPs in {table.loc[cand, 'LD_REGION'].nunique()} LD regions")

    table.to_csv(DATA_DIR / "snp_effects_all_traits.csv", index=False)

    print("\nCorrelation between SNP effect vectors of different traits (within-family, discovery):")
    print(table[[f"{t}_r" for t in TRAITS]].corr().round(2).to_string())

    for trait in TRAITS:
        c = table[table[f"{trait}_candidate"]]
        if c.empty:
            continue
        regions = (c.assign(abs_t=c[f"{trait}_t"].abs()).sort_values("abs_t", ascending=False)
                   .groupby("LD_REGION").agg(lead_SNP=("SNP", "first"), n_candidate_snps=("SNP", "size"),
                                            effect=(f"{trait}_effect", "first"), t_discovery=(f"{trait}_t", "first"),
                                            t_2008=(f"{trait}_t2008", "first"),
                                            **{f"r_{o}": (f"{o}_r", "first") for o in TRAITS if o != trait})
                   .sort_values("t_discovery", key=np.abs, ascending=False))
        regions.to_csv(DATA_DIR / f"marker_regions_{trait}.csv")
        print(f"\n{trait}: top regions (effect = change in {trait} per 1 sd of the SNP, within family)")
        print(regions.head(12).round(3).to_string())


if __name__ == "__main__":
    main()
