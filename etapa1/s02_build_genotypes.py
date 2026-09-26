"""Etapa 1.2 — Reconstrucción e imputación de genotipos (ambos clusters, mismo método).

Por qué: ImputedC2Populations.zip está corrupto y los archivos imputados de C1 dejan ~48 %
de NA justo en los marcadores polimórficos entre padres (los únicos informativos dentro de
familia). Se re-imputa todo desde los archivos sin imputar con un método transparente.

Método (poblaciones biparentales): la progenie se genotipó con 49–123 SNPs y los padres con
2.911. En cada marcador polimórfico observado se calcula la dosis de origen del padre A
d ∈ {0, 0.5, 1}; entre marcadores observados d se interpola linealmente en cM dentro del
cromosoma (esperanza aproximada bajo recombinación) y el genotipo se reconstruye como
g = P_B + d·(P_A − P_B). Las llamadas observadas nunca se sobrescriben.

Salidas (en --out-dir/geno):
  {C}_geno_int8.npy     genotipos g·100 (int8, líneas × marcadores), sin faltantes
  {C}_origin_uint8.npy  dosis de origen del padre A d·200 (uint8) — base para modelos de haplotipo
  {C}_lines.parquet     índice de filas (POP, LINE_KEY, LINE_ID, PA, PB, calidad)
  {C}_parents.parquet   genotipo completo de cada padre (float32, NaN = faltante)
  markers.parquet       mapa (cromosoma, cM) en el orden de las columnas
  qc_genotypes.json     validación: precisión con enmascaramiento y comparación con el imputado oficial
"""
from __future__ import annotations

import io
import warnings
import zipfile

import numpy as np
import pandas as pd

from common import (CLUSTERS, GENO_SCALE, ORIGIN_SCALE, Timer, base_argparser, get_logger, get_paths,
                    line_uid, norm_line_key, save_json)

log = get_logger("s02")
warnings.filterwarnings("ignore", category=RuntimeWarning)
RNG = np.random.default_rng(2008)


# ----------------------------------------------------------------------------
# Lectura en streaming, población por población
# ----------------------------------------------------------------------------
def iter_populations(zip_path, chunksize=3000):
    zf = zipfile.ZipFile(zip_path)
    member = [n for n in zf.namelist() if n.endswith(".csv") and not n.startswith("__MACOSX")][0]
    with zf.open(member) as fh:
        reader = pd.read_csv(io.TextIOWrapper(fh), chunksize=chunksize, na_values=["NA"],
                             skipinitialspace=True, low_memory=False,
                             dtype={"projects": str, "projectID": str, "shorthand": str, "LINE": str})
        buf = None
        for chunk in reader:
            buf = chunk if buf is None else pd.concat([buf, chunk], ignore_index=True)
            pops = buf["shorthand"].to_numpy()
            last = pops[-1]
            done = buf[pops != last]
            for pop, block in done.groupby("shorthand", sort=False):
                yield pop, block
            buf = buf[pops == last].reset_index(drop=True)
        if buf is not None and len(buf):
            yield buf["shorthand"].iat[0], buf


# ----------------------------------------------------------------------------
# Imputación de una población
# ----------------------------------------------------------------------------
def impute_population(block: pd.DataFrame, markers: list[str], order: np.ndarray,
                      chrom: np.ndarray, cm: np.ndarray, mask_frac: float = 0.0):
    """Devuelve dict con g (n×m, float32), d (n×m), ids y métricas opcionales de enmascaramiento."""
    line = block["LINE"]
    is_map = line.isna().to_numpy()
    is_par = line.fillna("").str.startswith("PID").to_numpy()
    X = block[markers].to_numpy(np.float32)[:, order]

    # Mapa propio de la población (se verifica contra el global)
    map_rows = X[is_map]
    map_ok = map_rows.shape[0] == 2 and np.allclose(map_rows[0], chrom) and np.allclose(map_rows[1], cm, atol=1e-3)

    par_ids = line[is_par].tolist()
    if len(par_ids) != 2:
        return {"error": f"{len(par_ids)} padres"}
    PA, PB = X[is_par]
    G = X[~is_map & ~is_par].copy()
    prog_keys = [norm_line_key(v) for v in line[~is_map & ~is_par]]
    n, m = G.shape

    informative = (~np.isnan(PA)) & (~np.isnan(PB)) & (np.abs(PA) == 1) & (np.abs(PB) == 1) & (PA != PB)

    truth = None
    if mask_frac > 0:  # enmascarar llamadas observadas informativas para validar
        obs_inf = (~np.isnan(G)) & informative[None, :]
        cand = np.argwhere(obs_inf)
        pick = cand[RNG.random(len(cand)) < mask_frac]
        truth = (pick, G[pick[:, 0], pick[:, 1]].copy())
        G[pick[:, 0], pick[:, 1]] = np.nan

    observed = ~np.isnan(G)
    with np.errstate(invalid="ignore", divide="ignore"):
        D_obs = np.where(informative[None, :] & observed, (G - PB[None, :]) / (PA - PB)[None, :], np.nan)

    D = np.full((n, m), np.nan, dtype=np.float32)
    no_obs_chrom = np.zeros(n, dtype=np.int16)
    for c in np.unique(chrom):
        idx = np.where(chrom == c)[0]
        pos = cm[idx]
        for i in range(n):
            di = D_obs[i, idx]
            ok = ~np.isnan(di)
            if not ok.any():
                no_obs_chrom[i] += 1
                continue
            xp, inv = np.unique(pos[ok], return_inverse=True)
            fp = np.bincount(inv, weights=di[ok]) / np.bincount(inv)
            D[i, idx] = np.interp(pos, xp, fp)
    # Cromosomas sin observaciones: esperanza poblacional en ese marcador (≈0.5 en F2, sesgada en BC)
    col_mean = np.nanmean(np.where(np.isnan(D), np.nan, D), axis=0) if np.isfinite(D).any() else np.full(m, 0.5)
    col_mean = np.where(np.isnan(col_mean), 0.5, col_mean)
    D = np.where(np.isnan(D), col_mean[None, :], D)

    both_par = ~np.isnan(PA) & ~np.isnan(PB)
    Gimp = np.where(both_par[None, :], PB[None, :] + D * (PA - PB)[None, :], np.nan).astype(np.float32)
    Gimp = np.where(observed, G, Gimp)  # nunca sobrescribir llamadas reales
    # Marcadores con padre faltante y sin llamada: media de la población en ese marcador
    pm = np.nanmean(np.where(np.isnan(Gimp), np.nan, Gimp), axis=0) if n else np.array([])
    fill = np.isnan(Gimp) & ~np.isnan(pm)[None, :]
    Gimp[fill] = np.broadcast_to(pm, Gimp.shape)[fill]

    out = {"pop_parents": par_ids, "PA": PA, "PB": PB, "G": Gimp, "D": D.astype(np.float32),
           "keys": prog_keys, "n_obs": observed.sum(1), "no_obs_chrom": no_obs_chrom,
           "n_informative": int(informative.sum()), "map_ok": bool(map_ok)}
    if truth is not None:
        (rc, true_vals) = truth
        pred = Gimp[rc[:, 0], rc[:, 1]]
        pred_disc = np.clip(np.round(pred), -1, 1)
        d_at = D[rc[:, 0], rc[:, 1]]
        conf = np.isclose(d_at * 2, np.round(d_at * 2), atol=1e-4)  # marcadores flanqueantes coinciden
        out["mask"] = {"n": len(true_vals), "concord": float(np.mean(pred_disc == true_vals)),
                       "abs_err": float(np.mean(np.abs(pred - true_vals))),
                       "n_conf": int(conf.sum()),
                       "concord_conf": float(np.mean(pred_disc[conf] == true_vals[conf])) if conf.any() else np.nan,
                       "concord_unconf": float(np.mean(pred_disc[~conf] == true_vals[~conf])) if (~conf).any() else np.nan}
    return out


# ----------------------------------------------------------------------------
# Comparación con los archivos imputados oficiales (solo C1, C2 viene corrupto)
# ----------------------------------------------------------------------------
def compare_official(zf: zipfile.ZipFile, pop: str, keys, G, markers_sorted):
    name = f"ImputedPopulationsC1/{pop}_Imputed.csv"
    if name not in zf.namelist():
        return None
    off = pd.read_csv(zf.open(name), index_col=0)
    off.index = [norm_line_key(i) for i in off.index.astype(str)]
    off = off[[k for k in off.columns]]
    common = [k for k in keys if k in off.index]
    if not common:
        return None
    pos = {k: i for i, k in enumerate(keys)}
    ours = G[[pos[k] for k in common]]
    theirs = off.loc[common, markers_sorted].to_numpy(np.float32)
    ok = ~np.isnan(theirs)
    return {"official_na_frac": float(1 - ok.mean()),
            "agree_where_official_called": float(np.mean(np.clip(np.round(ours[ok]), -1, 1) == theirs[ok]))}


def main():
    ap = base_argparser(__doc__)
    ap.add_argument("--mask-pops", type=int, default=60, help="poblaciones por cluster para validar con enmascaramiento")
    ap.add_argument("--compare-pops", type=int, default=80, help="poblaciones C1 a comparar con el imputado oficial")
    args = ap.parse_args()
    P = get_paths(args.data_dir, args.out_dir)
    gdir = P["out"] / "geno"
    gdir.mkdir(exist_ok=True)
    qc = {}
    marker_table = None

    for C in CLUSTERS:
        with Timer(log, f"genotipos {C}"):
            zpath = P["unimputed_zip"][C]
            header = pd.read_csv(zipfile.ZipFile(zpath).open(
                [n for n in zipfile.ZipFile(zpath).namelist() if n.endswith(".csv") and "MACOSX" not in n][0]), nrows=2,
                na_values=["NA"], skipinitialspace=True)
            markers = list(header.columns[4:])
            chrom_raw = header.iloc[0, 4:].astype(float).to_numpy()
            cm_raw = header.iloc[1, 4:].astype(float).to_numpy()
            order = np.lexsort((cm_raw, chrom_raw))
            chrom, cm = chrom_raw[order], cm_raw[order]
            msorted = [markers[i] for i in order]
            if marker_table is None:
                marker_table = pd.DataFrame({"MARKER": msorted, "CHR": chrom.astype(int), "CM": cm})

            off_zip = zipfile.ZipFile(P["imputed_c1_zip"]) if C == "C1" and zipfile.is_zipfile(P["imputed_c1_zip"]) else None
            geno_blocks, orig_blocks, idx_rows, parents = [], [], [], {}
            mask_stats, cmp_stats, q = [], [], {"pops": 0, "pops_skipped": [], "map_mismatch_pops": 0}
            for k, (pop, block) in enumerate(iter_populations(zpath)):
                do_mask = k % max(1, 500 // args.mask_pops) == 0
                if do_mask:  # corrida separada con enmascaramiento, solo para medir
                    r = impute_population(block, markers, order, chrom, cm, mask_frac=0.15)
                    if "mask" in r:
                        mask_stats.append(r["mask"])
                res = impute_population(block, markers, order, chrom, cm)
                if "error" in res:
                    q["pops_skipped"].append((pop, res["error"]))
                    continue
                q["pops"] += 1
                q["map_mismatch_pops"] += int(not res["map_ok"])
                geno_blocks.append(np.clip(np.round(res["G"] * GENO_SCALE), -127, 127).astype(np.int8)
                                   if not np.isnan(res["G"]).any() else res["G"])
                orig_blocks.append(np.round(res["D"] * ORIGIN_SCALE).astype(np.uint8))
                pa, pb = [p.replace("PID", "") for p in res["pop_parents"]]
                for key, nobs, noc in zip(res["keys"], res["n_obs"], res["no_obs_chrom"]):
                    idx_rows.append((pop, key, line_uid(pop, key), pa, pb, int(nobs), int(noc), res["n_informative"]))
                for pid, vec in zip((pa, pb), (res["PA"], res["PB"])):
                    parents.setdefault(pid, []).append(vec)
                if off_zip is not None and len(cmp_stats) < args.compare_pops:
                    c = compare_official(off_zip, pop, res["keys"], res["G"], msorted)
                    if c:
                        cmp_stats.append(c)
                if q["pops"] % 100 == 0:
                    log.info(f"  {C}: {q['pops']} poblaciones")

            # Relleno final de faltantes residuales (padre sin dato y sin llamadas) con la media del cluster
            float_blocks = [b for b in geno_blocks if b.dtype != np.int8]
            if float_blocks:
                colsum = np.zeros(len(msorted)); colcnt = np.zeros(len(msorted))
                for b in geno_blocks:
                    bf = b.astype(np.float32) / GENO_SCALE if b.dtype == np.int8 else b
                    colsum += np.nansum(bf, 0); colcnt += (~np.isnan(bf)).sum(0)
                cmean = colsum / np.maximum(colcnt, 1)
                n_resid = 0
                for i, b in enumerate(geno_blocks):
                    if b.dtype != np.int8:
                        nan = np.isnan(b); n_resid += int(nan.sum())
                        b = np.where(nan, cmean[None, :], b)
                        geno_blocks[i] = np.clip(np.round(b * GENO_SCALE), -127, 127).astype(np.int8)
                q["residual_cells_filled_with_cluster_mean"] = n_resid

            D = np.vstack(orig_blocks); del orig_blocks
            np.save(gdir / f"{C}_origin_uint8.npy", D); del D
            G = np.vstack(geno_blocks); del geno_blocks
            np.save(gdir / f"{C}_geno_int8.npy", G)
            lines = pd.DataFrame(idx_rows, columns=["POP", "LINE_KEY", "LINE_ID", "PA", "PB", "N_OBS_SNPS",
                                                    "CHR_WITHOUT_OBS", "POP_INFORMATIVE_SNPS"])
            lines["ROW"] = np.arange(len(lines))
            dup = lines.LINE_ID.duplicated(keep="first")
            q["duplicate_line_ids_in_genotypes"] = int(dup.sum())
            lines["DUPLICATE"] = dup
            lines.to_parquet(gdir / f"{C}_lines.parquet", index=False)

            # Padres: consenso entre poblaciones (si difieren, NaN en ese marcador)
            par_ids, par_mat, inconsist = [], [], 0
            for pid, vecs in parents.items():
                V = np.vstack(vecs)
                cons = np.nanmedian(V, 0) if len(vecs) > 1 else V[0]
                if len(vecs) > 1:
                    disagree = (np.nanmax(V, 0) != np.nanmin(V, 0))
                    inconsist += int(disagree.sum())
                    cons = np.where(disagree, np.nan, cons)
                par_ids.append(pid); par_mat.append(cons)
            pdf = pd.DataFrame(np.vstack(par_mat).astype(np.float32), columns=msorted)
            pdf.insert(0, "PARENT", par_ids)
            pdf.to_parquet(gdir / f"{C}_parents.parquet", index=False)

            colmean = np.zeros(G.shape[1])
            for s0 in range(0, G.shape[0], 10000):  # por bloques para no duplicar la matriz en memoria
                colmean += G[s0:s0 + 10000].sum(0, dtype=np.int64)
            colmean /= G.shape[0] * GENO_SCALE
            p_allele = (colmean + 1) / 2
            maf = np.minimum(p_allele, 1 - p_allele)
            marker_table[f"MAF_{C}"] = maf
            q.update({
                "n_lines": int(len(lines)), "n_parents": len(par_ids),
                "parent_marker_inconsistencies": inconsist,
                "markers_maf_lt_0.01": int((maf < 0.01).sum()),
                "median_obs_snps_per_line": float(lines.N_OBS_SNPS.median()),
                "median_informative_snps_per_pop": float(lines.drop_duplicates("POP").POP_INFORMATIVE_SNPS.median()),
                "lines_with_chr_without_obs_pct": float((lines.CHR_WITHOUT_OBS > 0).mean() * 100),
                "mask_validation": {
                    "pops": len(mask_stats),
                    "cells": int(sum(s["n"] for s in mask_stats)),
                    "concordance": float(np.average([s["concord"] for s in mask_stats], weights=[s["n"] for s in mask_stats])) if mask_stats else None,
                    "mean_abs_error": float(np.average([s["abs_err"] for s in mask_stats], weights=[s["n"] for s in mask_stats])) if mask_stats else None,
                    "share_confident_cells": float(sum(s["n_conf"] for s in mask_stats) / max(1, sum(s["n"] for s in mask_stats))),
                    "concordance_confident": float(np.nanmean([s["concord_conf"] for s in mask_stats])) if mask_stats else None,
                    "concordance_uncertain": float(np.nanmean([s["concord_unconf"] for s in mask_stats])) if mask_stats else None,
                    "baseline_always_het_or_major": "≈0.50 en F2",
                },
            })
            if cmp_stats:
                q["vs_official_imputed_C1"] = {
                    "pops": len(cmp_stats),
                    "official_na_frac": float(np.mean([s["official_na_frac"] for s in cmp_stats])),
                    "agreement_where_official_called": float(np.mean([s["agree_where_official_called"] for s in cmp_stats])),
                }
            qc[C] = q
            del G

    marker_table.to_parquet(gdir / "markers.parquet", index=False)
    qc["C2_official_zip_is_valid"] = zipfile.is_zipfile(P["data"] / "ImputedC2Populations.zip")
    save_json(qc, P["out"] / "qc_genotypes.json")


if __name__ == "__main__":
    main()
