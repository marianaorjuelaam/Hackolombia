"""
Stage 4 Phase 0: multi-trait line-level dataset + real/imputed SNP mask
=========================================================================

Extends `03_prediction/build_dataset.py` in two ways:

1. Predicts the full phenotype vector (8 traits), not just YLD_BE. Each trait
   gets its own per-year environment-adjusted BLUE, same backfitting model as
   stage 03 (`trait = mu + env(YEAR x LOC) + tester + line`). Traits vary a
   lot in coverage (MST/YLD_BE ~96-97% of rows, PHT/EHT only ~22-29%), so the
   output table is wide with NaNs where a trait wasn't measured for a line.
2. Builds a real/imputed marker mask alongside the genotype matrix. The
   `ImputedPopulationsC1` files used for X are already fully imputed; the
   *unimputed* source (`Unimputed_C1_Genome_Data.zip`) still has the raw
   missingness. Checked directly: progeny lines have ~97-98% NA there (only
   ~50-90 of 2911 SNPs actually observed per line), vs <1.5% NA for the two
   parents. The mask lets a model tell real calls from reconstructed ones.

Input:
- Simplified Hackathon Dataset V3/C1_Phenotype_Data_V2.csv
- Simplified Hackathon Dataset V3/ImputedPopulationsC1/C1.*_Imputed.csv
- Simplified Hackathon Dataset V3/Unimputed_C1_Genome_Data.zip

Output (data/processed/multi_trait_prediction/):
- X.npy          float32 genotype matrix (n_lines x n_snps), imputed
- real_mask.npy  uint8 mask (n_lines x n_snps), 1 = directly observed, 0 = imputed
- lines.parquet  LINE_ID, POP, YEAR, BLUE_<trait>/N_OBS_<trait> per trait
- snps.txt       SNP names (column order shared by X.npy and real_mask.npy)
- parents.csv    POP, PARENT1, PARENT2

Usage:
    python build_dataset.py
"""

import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).parent.parent.parent.parent  # Hackolombia
DATA_DIR = BASE_DIR / "Simplified Hackathon Dataset V3"
OUTPUT_DIR = BASE_DIR / "DIGITALTOOL" / "data" / "processed" / "multi_trait_prediction"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(BASE_DIR / "DIGITALTOOL" / "src" / "03_prediction"))
from build_dataset import load_genotypes, clean_id  # noqa: E402  (reused, not reimplemented)

TRAITS = ["ERM", "MST", "PHT", "RTLP", "STLP", "TWT", "YLD_BE", "EHT"]
N_BACKFIT_ITER = 20
MASK_CHUNKSIZE = 5000


def load_phenotype() -> pd.DataFrame:
    cols = ["YEAR_x", "shorthand_x", "LOC", "LINE_UNIQUE_ID", "GERMPLASM_ID_TESTER", *TRAITS]
    pheno = pd.read_csv(DATA_DIR / "C1_Phenotype_Data_V2.csv", usecols=cols, low_memory=False)
    pheno = pheno.rename(columns={"YEAR_x": "YEAR", "shorthand_x": "POP",
                                  "LINE_UNIQUE_ID": "LINE_ID", "GERMPLASM_ID_TESTER": "TESTER"})
    pheno["TESTER"] = pheno["TESTER"].fillna(-1).astype(int).astype(str)
    pheno["ENV"] = pheno["YEAR"].astype(int).astype(str) + "_" + pheno["LOC"].astype(str)
    print(f"  {len(pheno)} rows, {pheno['LINE_ID'].nunique()} lines")
    return pheno


def group_means(codes: np.ndarray, values: np.ndarray, n_groups: int) -> np.ndarray:
    sums = np.bincount(codes, weights=values, minlength=n_groups)
    counts = np.bincount(codes, minlength=n_groups)
    return sums / np.maximum(counts, 1)


def fit_additive_model(df: pd.DataFrame, trait: str) -> pd.DataFrame:
    """Backfit trait = mu + env + tester + line for one year; return per-line BLUE."""
    y = df[trait].to_numpy(dtype=float)
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
    return pd.DataFrame({"LINE_ID": line_u, f"BLUE_{trait}": mu + line_eff, f"N_OBS_{trait}": n_obs})


def build_all_blues(pheno: pd.DataFrame) -> pd.DataFrame:
    """One BLUE/N_OBS column pair per trait, outer-joined on LINE_ID (NaN where not measured)."""
    n_all = pheno["LINE_ID"].nunique()
    tables = []
    for trait in TRAITS:
        sub = pheno[pheno[trait].notna()]
        rows = [fit_additive_model(df, trait) for _, df in sub.groupby("YEAR")]
        t = pd.concat(rows, ignore_index=True).set_index("LINE_ID")
        print(f"  {trait}: {len(t)} lines ({len(t) / n_all:.1%} of all phenotyped lines)")
        tables.append(t)

    wide = pd.concat(tables, axis=1, join="outer")
    year_by_line = pheno.drop_duplicates("LINE_ID").set_index("LINE_ID")["YEAR"]
    wide["YEAR"] = year_by_line.reindex(wide.index)
    wide["POP"] = wide.index.str.extract(r"^(C\d+\.\d+)\.")[0].to_numpy()
    wide = wide.reset_index().rename(columns={"index": "LINE_ID"})
    return wide


def build_real_mask(ids: list, snps: list) -> np.ndarray:
    """Real (1) vs imputed (0) marker mask, aligned to `ids` x `snps`, from the
    unimputed source file. Only progeny rows (zero-padded numeric LINE id)
    count; the two parent rows and two per-population metadata rows are
    skipped, mirroring `load_genotypes`'s `prog = df.iloc[2:]` split."""
    pos = {lid: i for i, lid in enumerate(ids)}
    mask = np.zeros((len(ids), len(snps)), dtype=np.uint8)
    found = np.zeros(len(ids), dtype=bool)

    dtype_map = {"shorthand": str, "LINE": str, **{s: "float32" for s in snps}}
    usecols = ["shorthand", "LINE", *snps]

    n_seen, n_chunks = 0, 0
    with zipfile.ZipFile(DATA_DIR / "Unimputed_C1_Genome_Data.zip") as zf, \
            zf.open("C1_Genome_Data.csv") as f:
        reader = pd.read_csv(f, usecols=usecols, dtype=dtype_map, chunksize=MASK_CHUNKSIZE, low_memory=False)
        for chunk in reader:
            n_seen += len(chunk)
            n_chunks += 1
            is_progeny = chunk["LINE"].notna() & chunk["LINE"].str.match(r"^\d+$")
            prog = chunk[is_progeny]
            if prog.empty:
                continue
            lids = prog["shorthand"] + "." + prog["LINE"].map(clean_id)
            row_pos = lids.map(pos)
            hit = row_pos.notna()
            if not hit.any():
                continue
            row_idx = row_pos[hit].to_numpy(dtype=int)
            observed = prog.loc[hit, snps].notna().to_numpy()
            mask[row_idx] = observed.astype(np.uint8)
            found[row_idx] = True
            if n_chunks % 10 == 0:
                print(f"  scanned {n_seen} raw genotype rows, matched {int(found.sum())}/{len(ids)} lines so far")

    print(f"  scanned {n_seen} raw genotype rows total")
    missing = int((~found).sum())
    if missing:
        print(f"  WARNING: {missing} lines not found in the unimputed file (left as fully imputed)")
    else:
        print("  every line matched to the unimputed file")
    print(f"  overall real-marker fraction: {mask.mean():.4f}")
    return mask


def main():
    print("Loading phenotype (8 traits)...")
    pheno = load_phenotype()

    print("Fitting environment-adjusted BLUEs per trait...")
    wide = build_all_blues(pheno)

    print("Loading genotypes (union of lines phenotyped for >=1 trait)...")
    X, ids, snps, parents = load_genotypes(set(wide["LINE_ID"]))
    print(f"  genotype matrix: {X.shape}, NaN count: {int(np.isnan(X).sum())}")

    lines = pd.DataFrame({"LINE_ID": ids}).merge(wide, on="LINE_ID", how="left")
    assert lines["YEAR"].notna().all()
    blue_cols = [f"BLUE_{t}" for t in TRAITS]
    assert lines[blue_cols].notna().any(axis=1).all()
    print(f"  lines with genotype and >=1 trait: {len(lines)} of {len(wide)} phenotyped")
    for t in TRAITS:
        cov = lines[f"BLUE_{t}"].notna().mean()
        print(f"    {t}: {int(lines[f'BLUE_{t}'].notna().sum())} lines ({cov:.1%})")

    print("Building real/imputed SNP mask from Unimputed_C1_Genome_Data.zip...")
    mask = build_real_mask(ids, snps)

    ordered_cols = ["LINE_ID", "POP", "YEAR"] + [c for t in TRAITS for c in (f"BLUE_{t}", f"N_OBS_{t}")]
    lines = lines[ordered_cols]

    np.save(OUTPUT_DIR / "X.npy", X)
    np.save(OUTPUT_DIR / "real_mask.npy", mask)
    lines.to_parquet(OUTPUT_DIR / "lines.parquet", index=False)
    (OUTPUT_DIR / "snps.txt").write_text("\n".join(snps))
    parents.to_csv(OUTPUT_DIR / "parents.csv", index=False)
    print(f"Saved to {OUTPUT_DIR}")
    print(lines.groupby("YEAR").agg(n_lines=("LINE_ID", "size"), n_pops=("POP", "nunique")).T.to_string())


if __name__ == "__main__":
    main()
