"""Métricas de evaluación pensadas para la decisión de selección (no solo correlación global).

Todas comparan predicciones contra BLUEs observados (con ruido), así que son una cota inferior
de la precisión real; dividir por √h² da una estimación de la precisión frente al valor genético.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import warnings

from scipy.stats import ConstantInputWarning, pearsonr, spearmanr

warnings.filterwarnings("ignore", category=ConstantInputWarning)


def _safe_r(a, b, f=pearsonr):
    a, b = np.asarray(a, float), np.asarray(b, float)
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 3 or np.std(a[ok]) == 0 or np.std(b[ok]) == 0:
        return np.nan
    return float(f(a[ok], b[ok])[0])


def evaluate(df: pd.DataFrame, true: str = "y", pred: str = "yhat", group: str = "POP",
             top: float = 0.10, min_pop: int = 10) -> dict:
    d = df[[group, true, pred]].dropna(subset=[true]).copy()
    out = {"n_lines": len(d), "n_pops": d[group].nunique()}
    have_pred = d[pred].notna()
    out["coverage"] = float(have_pred.mean())
    d = d[have_pred]

    out["r_overall"] = _safe_r(d[true], d[pred])
    out["rho_overall"] = _safe_r(d[true], d[pred], spearmanr)

    pm = d.groupby(group)[[true, pred]].mean()
    out["r_between_pops"] = _safe_r(pm[true], pm[pred])

    rows = []
    for _, g in d.groupby(group):
        if len(g) >= min_pop and g[pred].std() > 0:
            rows.append((len(g), _safe_r(g[true], g[pred], spearmanr)))
    if rows:
        n, r = np.array(rows).T
        ok = np.isfinite(r)
        out["rho_within_pops"] = float(np.average(r[ok], weights=n[ok])) if ok.any() else np.nan
    else:
        out["rho_within_pops"] = np.nan

    # Decisión: seleccionar el top X % predicho
    k = max(1, int(round(top * len(d))))
    sel = d.nlargest(k, pred)
    best = d.nlargest(k, true)
    mu = d[true].mean()
    out[f"top{int(top*100)}_precision"] = float(len(set(sel.index) & set(best.index)) / k)
    out["gain_selected_bu"] = float(sel[true].mean() - mu)          # diferencial de selección realizado
    out["gain_max_bu"] = float(best[true].mean() - mu)              # si supiéramos el BLUE real
    out["gain_captured_pct"] = float(100 * out["gain_selected_bu"] / out["gain_max_bu"]) if out["gain_max_bu"] else np.nan
    return out
