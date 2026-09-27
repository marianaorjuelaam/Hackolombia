"""
Prediction Phase 0: Build line-level dataset
=============================================

Builds one row per genotyped line with an environment-adjusted yield (BLUE)
and a float32 genotype matrix covering ALL populations (no per-year SNP
filtering, no population cap), so every year shares the same 2911 SNPs.

Model per year (each population/line is planted in exactly one year):
    YLD_BE = mu + env(YEAR x LOC) + tester + line + error
fitted by backfitting; the line effect + mu is the line's adjusted yield.

Input:
- Simplified Hackathon Dataset V3/C1_Phenotype_Data_V2.csv
- Simplified Hackathon Dataset V3/ImputedPopulationsC1/C1.*_Imputed.csv

Output (data/processed/prediction/):
- X.npy          float32 genotype matrix (n_lines x n_snps)
- lines.parquet  LINE_ID, POP, YEAR, BLUE, N_OBS (row-aligned with X.npy)
- snps.txt       SNP names (column order of X.npy)
- parents.csv    POP, PARENT1, PARENT2

Usage:
    python build_dataset.py
"""

import re
import glob
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).parent.parent.parent.parent  # Hackolombia
DATA_DIR = BASE_DIR / "Simplified Hackathon Dataset V3"
OUTPUT_DIR = BASE_DIR / "DIGITALTOOL" / "data" / "processed" / "prediction"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TRAIT = "YLD_BE"
N_BACKFIT_ITER = 20


def load_phenotype() -> pd.DataFrame:
    cols = ["YEAR_x", "shorthand_x", "LOC", "LINE_UNIQUE_ID", "GERMPLASM_ID_TESTER", TRAIT]
    pheno = pd.read_csv(DATA_DIR / "C1_Phenotype_Data_V2.csv", usecols=cols, low_memory=False)
    pheno = pheno.rename(columns={"YEAR_x": "YEAR", "shorthand_x": "POP",
                                  "LINE_UNIQUE_ID": "LINE_ID", "GERMPLASM_ID_TESTER": "TESTER"})
    pheno = pheno[pheno[TRAIT].notna()].copy()
    pheno["TESTER"] = pheno["TESTER"].fillna(-1).astype(int).astype(str)
    pheno["ENV"] = pheno["YEAR"].astype(int).astype(str) + "_" + pheno["LOC"].astype(str)
    print(f"  {len(pheno)} yield observations, {pheno['LINE_ID'].nunique()} lines")
    return pheno


def group_means(codes: np.ndarray, values: np.ndarray, n_groups: int) -> np.ndarray:
    sums = np.bincount(codes, weights=values, minlength=n_groups)
    counts = np.bincount(codes, minlength=n_groups)
    return sums / np.maximum(counts, 1)


def fit_additive_model(df: pd.DataFrame) -> pd.DataFrame:
    """Backfit YLD = mu + env + tester + line for one year; return per-line BLUE."""
    y = df[TRAIT].to_numpy(dtype=float)
    env, env_u = pd.factorize(df["ENV"])
    tester, tester_u = pd.factorize(df["TESTER"])
    line, line_u = pd.factorize(df["LINE_ID"])

    mu = y.mean()
    env_eff = np.zeros(len(env_u))
    tester_eff = np.zeros(len(tester_u))
    line_eff = np.zeros(len(line_u))

    for _ in range(N_BACKFIT_ITER):
        env_eff = group_means(env, y - mu - tester_eff[tester] - line_eff[line], len(env_u))
        tester_eff = group_means(tester, y - mu - env_eff[env] - line_eff[line], len(tester_u))
        line_eff = group_means(line, y - mu - env_eff[env] - tester_eff[tester], len(line_u))

    n_obs = np.bincount(line, minlength=len(line_u))
    return pd.DataFrame({"LINE_ID": line_u, "BLUE": mu + line_eff, "N_OBS": n_obs})


def build_blues(pheno: pd.DataFrame) -> pd.DataFrame:
    blues = []
    for year, df in pheno.groupby("YEAR"):
        res = fit_additive_model(df)
        res["YEAR"] = int(year)
        res["POP"] = res["LINE_ID"].str.extract(r"^(C\d+\.\d+)\.")[0]
        blues.append(res)
        print(f"  {int(year)}: {len(res)} lines, {df['ENV'].nunique()} envs, "
              f"{df['TESTER'].nunique()} testers, BLUE sd={res['BLUE'].std():.1f}")
    return pd.concat(blues, ignore_index=True)


def clean_id(idx: str) -> str:
    try:
        return str(int(idx))
    except (ValueError, TypeError):
        return str(idx)


def load_genotypes(needed_ids: set):
    """Stack all population files into a float32 matrix, keeping only lines with a BLUE."""
    files = sorted(glob.glob(str(DATA_DIR / "ImputedPopulationsC1" / "C1.*_Imputed.csv")))
    snps = None
    blocks, ids, parents = [], [], []
    for i, f in enumerate(files):
        pop = "C1." + re.search(r"C1\.(\d+)_", f).group(1)
        df = pd.read_csv(f, index_col=0, dtype={0: str})
        if snps is None:
            snps = list(df.columns)
        elif list(df.columns) != snps:
            raise ValueError(f"SNP columns differ in {f}")
        parents.append((pop, df.index[0], df.index[1]))
        prog = df.iloc[2:].copy()
        # Genotype files index progeny by zero-padded number ("00000000082");
        # phenotype LINE_ID is population-qualified ("C1.100.82"). Non-numeric
        # suffixes are kept verbatim, as in the phenotype file.
        prog.index = [f"{pop}.{clean_id(i)}" for i in prog.index]
        keep = prog.index.isin(needed_ids)
        blocks.append(prog.loc[keep].to_numpy(dtype=np.float32))
        ids.extend(prog.index[keep])
        if (i + 1) % 100 == 0:
            print(f"  read {i + 1}/{len(files)} populations")
    X = np.vstack(blocks)
    return X, ids, snps, pd.DataFrame(parents, columns=["POP", "PARENT1", "PARENT2"])


def main():
    print("Loading phenotype...")
    pheno = load_phenotype()
    print("Fitting environment-adjusted yield per year...")
    blues = build_blues(pheno)

    print("Loading genotypes...")
    X, ids, snps, parents = load_genotypes(set(blues["LINE_ID"]))
    print(f"  genotype matrix: {X.shape}, NaN count: {int(np.isnan(X).sum())}")

    lines = pd.DataFrame({"LINE_ID": ids}).merge(blues, on="LINE_ID", how="left")
    assert lines["BLUE"].notna().all()
    print(f"  lines with genotype and phenotype: {len(lines)} of {len(blues)} phenotyped")

    np.save(OUTPUT_DIR / "X.npy", X)
    lines.to_parquet(OUTPUT_DIR / "lines.parquet", index=False)
    (OUTPUT_DIR / "snps.txt").write_text("\n".join(snps))
    parents.to_csv(OUTPUT_DIR / "parents.csv", index=False)
    print(f"Saved to {OUTPUT_DIR}")
    print(lines.groupby("YEAR").agg(n_lines=("LINE_ID", "size"), n_pops=("POP", "nunique")).T.to_string())


if __name__ == "__main__":
    main()
