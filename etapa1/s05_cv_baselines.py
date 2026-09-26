"""Etapa 1.5 — Esquema de validación y modelos base (el marcador que la Etapa 2 debe superar).

Validación hacia adelante en el tiempo (imita la decisión real de enero):
    entrenar con años < Y  →  predecir las poblaciones NUEVAS del año Y,  Y = 2004…2007
    FINAL: entrenar ≤ 2007 → 2008 (reservado; se reporta, no se usa para ajustar nada)
Además, cada población de entrenamiento recibe un pliegue interno (GroupKFold por población)
para ajustar hiperparámetros sin que la media familiar se filtre entre entrenamiento y prueba.

Modelos base
  B0  selección al azar (ganancia esperada = 0)
  B1  GCA histórico de los padres (media contraída de sus familias anteriores)
  B2  B1 + efecto histórico del tester
  B3  B2 + genotipo de los padres (ridge sobre el promedio de los padres) — primer uso de marcadores

Salidas: cv_folds.json, baseline_scores.csv, baseline_predictions.parquet
"""
from __future__ import annotations

import zlib

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

from common import CLUSTERS, PRIMARY_TRAIT, TARGET_YEAR, base_argparser, get_logger, get_paths, save_json
from metrics import evaluate

log = get_logger("s05")
TEST_YEARS = [2004, 2005, 2006, 2007, TARGET_YEAR]
N_INNER = 5
SHRINK_K = 1.0  # contracción de medias históricas hacia 0 (≈ n/(n+k))


def shrunk_mean(values: pd.Series, keys: pd.Series) -> pd.Series:
    g = values.groupby(keys)
    return g.sum() / (g.size() + SHRINK_K)


def parent_history(pops_tr: pd.DataFrame, value: str = "POP_BLUE") -> pd.Series:
    """GCA histórico de cada padre: media de sus familias ponderada por su aporte genético
    (0.75 si fue recurrente en retrocruza) y por la confiabilidad de la media familiar."""
    long = pd.concat([pops_tr[["P1", "P1_W", value, "REL_POP"]].rename(columns={"P1": "P", "P1_W": "W"}),
                      pops_tr[["P2", "P2_W", value, "REL_POP"]].rename(columns={"P2": "P", "P2_W": "W"})])
    w = 2 * long.W * long.REL_POP
    g = (long[value] * w).groupby(long.P)
    return g.sum() / (w.groupby(long.P).sum() + SHRINK_K)


def parent_geno_matrix(parents: pd.DataFrame, pids: list[str]) -> np.ndarray:
    M = parents.set_index("PARENT").reindex(pids)
    X = M.to_numpy(np.float32)
    col_mean = np.nanmean(parents.drop(columns="PARENT").to_numpy(np.float32), 0)
    return np.where(np.isnan(X), col_mean[None, :], X)


def main():
    ap = base_argparser(__doc__)
    ap.add_argument("--trait", default=PRIMARY_TRAIT)
    args = ap.parse_args()
    P = get_paths(args.data_dir, args.out_dir)
    lv = pd.read_parquet(P["out"] / "line_values.parquet")
    popv = pd.read_parquet(P["out"] / "pop_values.parquet")
    popv = popv[popv.TRAIT == args.trait].copy()
    popv["REL_POP"] = popv.REL_POP.fillna(0.0)
    t = args.trait

    # ---- Pliegues ----
    folds = []
    for C in CLUSTERS:
        pc = popv[popv.CLUSTER == C]
        for Y in TEST_YEARS:
            folds.append({"cluster": C, "name": f"{C}_test{Y}", "final": Y == TARGET_YEAR,
                          "train_years": sorted(int(y) for y in pc.YEAR.unique() if y < Y), "test_year": Y,
                          "n_train_pops": int((pc.YEAR < Y).sum()), "n_test_pops": int((pc.YEAR == Y).sum()),
                          "n_test_lines": int(((lv.CLUSTER == C) & (lv.YEAR == Y) & lv[f"BLUE_{t}"].notna()).sum())})
    inner = {p: int(zlib.crc32(p.encode()) % N_INNER) for p in popv.POP.unique()}  # estable entre sesiones
    save_json({"forward_folds": folds, "inner_group_fold_by_pop": inner}, P["out"] / "cv_folds.json")

    # ---- Modelos base ----
    scores, preds = [], []
    for C in CLUSTERS:
        parents = pd.read_parquet(P["out"] / "geno" / f"{C}_parents.parquet")
        pc = popv[popv.CLUSTER == C].copy()
        lc = lv[(lv.CLUSTER == C) & lv[f"BLUE_{t}"].notna()][["LINE_ID", "POP", "YEAR", f"BLUE_{t}"]].rename(columns={f"BLUE_{t}": "y"})
        for Y in TEST_YEARS:
            tr, te = pc[pc.YEAR < Y], pc[pc.YEAR == Y].copy()
            gca = parent_history(tr)
            tst = shrunk_mean(tr.POP_BLUE, tr.TESTER)
            te["B1"] = te.P1_W * te.P1.map(gca).fillna(0.0) + te.P2_W * te.P2.map(gca).fillna(0.0)
            te["B2"] = te.B1 + te.TESTER.map(tst).fillna(0.0)

            # B3: ridge sobre genotipo promedio de los padres (predice la media familiar esperada)
            def expected_geno(p):  # genotipo esperado de la familia = promedio ponderado de los padres
                return (p.P1_W.to_numpy()[:, None] * parent_geno_matrix(parents, p.P1.tolist())
                        + p.P2_W.to_numpy()[:, None] * parent_geno_matrix(parents, p.P2.tolist()))
            Xtr, Xte = expected_geno(tr), expected_geno(te)
            ytr = (tr.POP_BLUE - tr.TESTER.map(tst).fillna(0.0)).to_numpy()
            swt = tr.REL_POP.clip(0.05).to_numpy()   # familias mal conectadas pesan menos
            best_a, best_r = None, -np.inf
            for a in [10, 100, 1000, 10000]:   # ajuste interno por pliegues de población
                rs = []
                fk = tr.POP.map(inner).to_numpy()
                for k in range(N_INNER):
                    m = Ridge(alpha=a).fit(Xtr[fk != k], ytr[fk != k], sample_weight=swt[fk != k])
                    rs.append(np.corrcoef(m.predict(Xtr[fk == k]), ytr[fk == k])[0, 1])
                if np.nanmean(rs) > best_r:
                    best_a, best_r = a, np.nanmean(rs)
            te["B3"] = Ridge(alpha=best_a).fit(Xtr, ytr, sample_weight=swt).predict(Xte) + te.TESTER.map(tst).fillna(0.0)

            L = lc[lc.YEAR == Y].merge(te[["POP", "B1", "B2", "B3"]], on="POP", how="left")
            L["B0"] = np.random.default_rng(Y).normal(size=len(L))
            for b in ["B0", "B1", "B2", "B3"]:
                s = evaluate(L, "y", b)
                s.update({"cluster": C, "test_year": Y, "model": b, "final_holdout": Y == TARGET_YEAR,
                          "ridge_alpha": best_a if b == "B3" else None})
                scores.append(s)
            preds.append(L.assign(CLUSTER=C))
            log.info(f"{C} {Y}: B1 r_pop={scores[-3]['r_between_pops']:.3f}  B3 r_pop={scores[-1]['r_between_pops']:.3f}")

    sc = pd.DataFrame(scores)
    sc.to_csv(P["out"] / "baseline_scores.csv", index=False)
    pd.concat(preds).to_parquet(P["out"] / "baseline_predictions.parquet", index=False)
    cols = ["r_overall", "r_between_pops", "rho_within_pops", "top10_precision", "gain_selected_bu", "gain_captured_pct"]
    dev = sc[~sc.final_holdout].groupby(["cluster", "model"])[cols].mean().round(3)
    log.info("\nPromedio 2004–2007 (validación):\n" + dev.to_string())
    log.info("\nHoldout 2008:\n" + sc[sc.final_holdout].set_index(["cluster", "model"])[cols].round(3).to_string())


if __name__ == "__main__":
    main()
