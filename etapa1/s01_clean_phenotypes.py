"""Etapa 1.1 — Limpieza de fenotipos.

Salidas (en --out-dir):
  pheno_clean.parquet   una fila por parcela, columnas normalizadas, ambos clusters
  populations.parquet   una fila por población (padres, tester, generación, año, sitios)
  qc_phenotypes.json    reporte de control de calidad
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from common import (CLUSTERS, TRAIT_BOUNDS, TRAITS, Timer, base_argparser, env_id, get_logger,
                    get_paths, line_uid, norm_line_key, save_json)

log = get_logger("s01")

KEEP = ["YEAR_x", "LOC", "LONGITUDE", "LATITUDE", "LINE", "SET", "CLUSTER", "shorthand_x",
        "GERMPLASM_ID", "GENERATION_NAME", "CROSS", "GERMPLASM_ID_TESTER", "ProjectID"] + TRAITS
RENAME = {"YEAR_x": "YEAR", "shorthand_x": "POP", "GERMPLASM_ID_TESTER": "TESTER",
          "GENERATION_NAME": "GEN", "ProjectID": "PROJECT_ID"}


def clean_cluster(path, cluster: str, qc: dict) -> pd.DataFrame:
    raw = pd.read_csv(path, low_memory=False, dtype={"LINE": str, "SET": str, "CROSS": str})
    q = qc.setdefault(cluster, {})
    q["rows_raw"] = len(raw)

    # Columnas duplicadas del merge original: se verifica que sean idénticas antes de descartarlas
    q["dup_cols_identical"] = {
        "YEAR_x==YEAR_y": bool((raw.YEAR_x == raw.YEAR_y).all()),
        "shorthand_x==shorthand_y": bool((raw.shorthand_x == raw.shorthand_y).all()),
        "ProjectID==MAB_PROJECT_ID": bool((raw.ProjectID == raw.MAB_PROJECT_ID).all()),
    }
    df = raw[KEEP].rename(columns=RENAME).copy()
    del raw

    # Identificadores normalizados
    df["LINE_KEY"] = df["LINE"].map(norm_line_key)
    df["LINE_ID"] = [line_uid(p, k) for p, k in zip(df.POP, df.LINE_KEY)]
    df["CLUSTER"] = cluster
    df["ENV"] = [env_id(y, l) for y, l in zip(df.YEAR, df.LOC)]
    # CROSS 'A*2/B' = retrocruza con A como padre recurrente: A aporta 1 − (1/2)^n = 3/4 del genoma
    parents = df["CROSS"].str.split("/", expand=True)
    for k, col in ((0, "P1"), (1, "P2")):
        raw_p = parents[k].str.strip()
        df[col] = raw_p.str.replace(r"\*\d+$", "", regex=True)
        df[f"{col}_DOSE"] = raw_p.str.extract(r"\*(\d+)$")[0].astype(float).fillna(1)
    # Padre recurrente con '*n' aporta 1 − ½ⁿ y el donante ½ⁿ (A*2/B → 0.75 / 0.25). Cruza simple: 0.5 / 0.5.
    n_rec = np.maximum(df.P1_DOSE, df.P2_DOSE)
    rec_share = 1 - 0.5 ** n_rec
    df["P1_W"] = np.where(df.P1_DOSE > df.P2_DOSE, rec_share, np.where(df.P2_DOSE > df.P1_DOSE, 1 - rec_share, 0.5))
    df["P2_W"] = 1 - df.P1_W
    df = df.drop(columns=["P1_DOSE", "P2_DOSE"])
    df["TESTER"] = df["TESTER"].map(lambda x: "T_UNK" if pd.isna(x) else f"T{int(x)}")
    q["rows_missing_tester"] = int((df.TESTER == "T_UNK").sum())

    # Algunas poblaciones registran la misma línea como '12' y como '00000000012'
    # (mismos ambientes, parcelas distintas; r≈0.2 entre ambos registros): se unifican.
    fmts = df.groupby("LINE_ID").LINE.nunique()
    q["line_ids_unified_from_2_formats"] = int((fmts > 1).sum())

    # Duplicados exactos de parcela
    dup = df.duplicated(["LINE_ID", "ENV", "SET"] + TRAITS)
    q["exact_duplicate_rows_dropped"] = int(dup.sum())
    df = df[~dup]

    # Rangos plausibles
    q["values_out_of_bounds"] = {}
    for t, (lo, hi) in TRAIT_BOUNDS.items():
        bad = df[t].notna() & ~df[t].between(lo, hi)
        q["values_out_of_bounds"][t] = int(bad.sum())
        df.loc[bad, t] = np.nan

    # Filas sin ningún rasgo
    no_trait = df[TRAITS].isna().all(axis=1)
    q["rows_without_traits_dropped"] = int(no_trait.sum())
    df = df[~no_trait]

    # Coordenadas: una sola por localidad (mediana) para evitar inconsistencias
    coords = df.groupby("LOC")[["LATITUDE", "LONGITUDE"]].median()
    q["locs_with_inconsistent_coords"] = int((df.groupby("LOC")[["LATITUDE", "LONGITUDE"]].nunique() > 1).any(axis=1).sum())
    df = df.drop(columns=["LATITUDE", "LONGITUDE"]).join(coords, on="LOC")

    q["rows_clean"] = len(df)
    q["missing_rate"] = df[TRAITS].isna().mean().round(3).to_dict()
    q["n_lines"] = int(df.LINE_ID.nunique())
    q["n_pops"] = int(df.POP.nunique())
    q["n_envs"] = int(df.ENV.nunique())
    q["years"] = df.groupby("YEAR").LINE_ID.nunique().to_dict()
    q["line_ids_with_hash_suffix"] = int(df.LINE_KEY.str.contains("#").sum())
    q["pops_in_multiple_years"] = int((df.groupby("POP").YEAR.nunique() > 1).sum())
    q["pops_with_multiple_testers"] = int((df.groupby("POP").TESTER.nunique() > 1).sum())
    q["pops_backcross_weighted_parents"] = int(df[df.P1_W != 0.5].POP.nunique())
    return df


def population_table(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("POP")
    pops = g.agg(CLUSTER=("CLUSTER", "first"), YEAR=("YEAR", "first"), CROSS=("CROSS", "first"),
                 P1=("P1", "first"), P2=("P2", "first"), P1_W=("P1_W", "first"), P2_W=("P2_W", "first"), TESTER=("TESTER", lambda s: s.mode().iat[0]),
                 GEN=("GEN", lambda s: s.mode().iat[0]), N_LINES=("LINE_ID", "nunique"),
                 N_ENVS=("ENV", "nunique"), N_PLOTS=("LINE_ID", "size"),
                 LOCS=("LOC", lambda s: ",".join(sorted(s.unique())))).reset_index()
    return pops


def main():
    args = base_argparser(__doc__).parse_args()
    P = get_paths(args.data_dir, args.out_dir)
    qc = {}
    parts = []
    for c in CLUSTERS:
        with Timer(log, f"limpiando {c}"):
            parts.append(clean_cluster(P["pheno_csv"][c], c, qc))
    df = pd.concat(parts, ignore_index=True)
    for col in ["POP", "LOC", "ENV", "TESTER", "GEN", "CLUSTER", "P1", "P2", "SET"]:
        df[col] = df[col].astype("category")
    df.to_parquet(P["out"] / "pheno_clean.parquet", index=False)

    pops = population_table(df)
    pops.to_parquet(P["out"] / "populations.parquet", index=False)

    # Resumen de cuánto "conocemos" a los padres de cada año objetivo (sin mirar el futuro)
    known = {}
    for c in CLUSTERS:
        pc = pops[pops.CLUSTER == c]
        for y in sorted(pc.YEAR.unique()):
            past = pc[pc.YEAR < y]
            seen = set(past.P1) | set(past.P2)
            cur = pc[pc.YEAR == y]
            n_known = cur.P1.isin(seen).astype(int) + cur.P2.isin(seen).astype(int)
            known[f"{c}_{y}"] = {"pops": len(cur), "ge1_parent_seen": int((n_known >= 1).sum()),
                                 "both_seen": int((n_known == 2).sum())}
    qc["parents_seen_before_by_year"] = known
    save_json(qc, P["out"] / "qc_phenotypes.json")
    log.info(f"pheno_clean: {len(df):,} parcelas | {df.LINE_ID.nunique():,} líneas | {len(pops)} poblaciones")


if __name__ == "__main__":
    main()
