"""Etapa 1.4 — Valores fenotípicos por línea (primera etapa del modelo en dos etapas).

Modelo por cluster y rasgo:   y_r = E_ambiente(r) + L_línea(r) + e_r ,  Var(e_r) = σ²_ambiente(r)

  * E y L fijos, resueltos exactamente absorbiendo las líneas (sistema reducido del tamaño del
    número de ambientes) — correcto aunque cada población esté en un subconjunto distinto de sitios.
  * Varianza residual heterogénea por ambiente (ponderación 1/σ²_j, 3 iteraciones): los ensayos
    ruidosos pesan menos.
  * Parcelas atípicas: residuo estandarizado |z| > 4 (con corrección por leverage) se descarta.
  * Calidad de ambiente: r entre el valor de las líneas en ese ambiente y su media en los demás
    (leave-one-environment-out). Ambientes con r < 0 y ≥ 30 líneas se excluyen.
  * Identificabilidad: ningún genotipo se repite entre años (no hay testigos comunes), así que los
    BLUE se centran dentro de cada componente conectado (≈ año). Son comparables dentro del año,
    NO entre años; la tendencia genética entre años no es estimable con estos datos.

Salidas
  line_values.parquet       una fila por línea: BLUE, PEV, REL, BLUP intra-familia por rasgo
  pop_values.parquet        media por población y rasgo
  env_quality.parquet       efecto de ensayo, σ² residual, r LOO y exclusión por ambiente y rasgo
  varcomp.parquet           componentes de varianza y heredabilidades por cluster, rasgo y año
  qc_line_values.json
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.sparse.csgraph import connected_components

from common import (CLUSTERS, ENV_MIN_LINES_QC, ENV_MIN_R, OUTLIER_Z, PRIMARY_TRAIT, TRAITS, Timer,
                    base_argparser, get_logger, get_paths, save_json)

log = get_logger("s04")


def solve_two_way(y, li, ej, w, nL, nE):
    """Solución exacta de mínimos cuadrados ponderados para y = E_j + L_i (w = peso por fila)."""
    A = sparse.csr_matrix((w, (li, ej)), shape=(nL, nE))                 # a_i[j] = Σ w
    W_line = np.asarray(A.sum(1)).ravel()
    S_line = np.bincount(li, weights=w * y, minlength=nL)
    W_env = np.bincount(ej, weights=w, minlength=nE)
    S_env = np.bincount(ej, weights=w * y, minlength=nE)
    Dinv = sparse.diags(1.0 / W_line)
    C = (sparse.diags(W_env) - A.T @ Dinv @ A).toarray()
    b = S_env - A.T @ (S_line / W_line)
    E = np.linalg.lstsq(C, b, rcond=None)[0]
    L = (S_line - A @ E) / W_line
    return E, L, W_line, A, C


def components(li, ej, nL, nE):
    """Componente conectado de cada ambiente (grafo bipartito línea–ambiente)."""
    B = sparse.csr_matrix((np.ones(len(li)), (li, ej)), shape=(nL, nE))
    n, lab = connected_components((B.T @ B) > 0, directed=False)
    return n, lab


def fit_trait(df: pd.DataFrame, trait: str, qc: dict):
    d = df[["LINE_ID", "ENV", "POP", "YEAR", trait]].dropna(subset=[trait]).copy()
    d["LINE_ID"] = d["LINE_ID"].astype(str)
    d["ENV"] = d["ENV"].astype(str)
    q = {"plots_in": len(d)}
    excluded_envs: set[str] = set()
    removed_outliers = 0

    for outer in range(3):  # (1) ajuste → (2) sin atípicos → (3) sin ambientes malos
        d = d[~d.ENV.isin(excluded_envs)]
        lcode, lines = pd.factorize(d.LINE_ID)
        ecode, envs = pd.factorize(d.ENV)
        y = d[trait].to_numpy(float)
        nL, nE, N = len(lines), len(envs), len(d)
        ncomp, comp_env = components(lcode, ecode, nL, nE)

        w_env = np.ones(nE)
        for _ in range(3):  # varianzas heterogéneas por ambiente
            E, L, W_line, A, C = solve_two_way(y, lcode, ecode, w_env[ecode], nL, nE)
            r = y - E[ecode] - L[lcode]
            df_corr = N / max(N - nL - nE, 1)
            s2 = np.bincount(ecode, weights=r ** 2, minlength=nE) / np.bincount(ecode, minlength=nE) * df_corr
            s2 = np.clip(s2, np.nanmedian(s2) * 0.1, None)  # evita pesos infinitos en ensayos diminutos
            w_env = 1.0 / s2
        # Residuo estandarizado con leverage de la línea
        h = w_env[ecode] / W_line[lcode]
        with np.errstate(divide="ignore", invalid="ignore"):
            z = np.where(h < 0.999, r / np.sqrt(s2[ecode] * (1 - h)), 0.0)

        if outer == 0:
            out = np.abs(z) > OUTLIER_Z
            removed_outliers = int(out.sum())
            d = d[~out]
            continue

        # Calidad de ambiente (leave-one-environment-out), solo en la pasada 2
        x = y - E[ecode]
        tmp = pd.DataFrame({"l": lcode, "e": ecode, "x": x, "w": w_env[ecode]})
        le = tmp.groupby(["l", "e"]).agg(x=("x", "mean"), w=("w", "sum")).reset_index()
        S = L * W_line
        le["loo"] = (S[le.l] - le.w * le.x) / (W_line[le.l] - le.w)
        le = le[np.isfinite(le.loo) & ((W_line[le.l] - le.w) > 1e-12)]
        r_env = le.groupby("e").apply(lambda g: g.x.corr(g.loo) if len(g) >= 5 else np.nan, include_groups=False)
        n_lines_env = le.groupby("e").size()
        env_tab = pd.DataFrame({
            "ENV": envs, "TRIAL_EFFECT": E, "SIGMA2": s2,
            "N_PLOTS": np.bincount(ecode, minlength=nE),
            "R_LOO": r_env.reindex(range(nE)).to_numpy(),
            "N_LINES_LOO": n_lines_env.reindex(range(nE)).fillna(0).astype(int).to_numpy(),
            "COMPONENT": comp_env})
        # Se excluye solo si el ambiente es CLARAMENTE poco informativo: límite superior (90 %) de r < umbral
        n_eff = np.maximum(env_tab.N_LINES_LOO - 3, 1)
        r_upper = np.tanh(np.arctanh(env_tab.R_LOO.clip(-0.999, 0.999)) + 1.645 / np.sqrt(n_eff))
        env_tab["R_LOO_UPPER90"] = r_upper
        bad = (r_upper < ENV_MIN_R) & (env_tab.N_LINES_LOO >= ENV_MIN_LINES_QC)
        if outer == 1 and bad.any():
            excluded_envs |= set(env_tab.ENV[bad])
            continue
        break

    env_tab["EXCLUDED"] = False
    if excluded_envs:
        env_tab = pd.concat([env_tab, pd.DataFrame({"ENV": sorted(excluded_envs), "EXCLUDED": True})], ignore_index=True)

    # Centrado dentro de componente conectado (≈ año)
    comp_line = pd.Series(comp_env[ecode]).groupby(lcode).first().reindex(range(nL)).to_numpy()
    Lc = L - pd.Series(L).groupby(comp_line).transform("mean").to_numpy()

    meta = d.drop_duplicates("LINE_ID").set_index("LINE_ID").loc[lines, ["POP", "YEAR"]]
    n_env = pd.Series(ecode).groupby(lcode).nunique().reindex(range(nL)).to_numpy()
    lv = pd.DataFrame({"LINE_ID": lines, "POP": meta.POP.astype(str).to_numpy(), "YEAR": meta.YEAR.to_numpy(),
                       "BLUE": Lc, "PEV": 1.0 / W_line,
                       "N_PLOTS": np.bincount(lcode, minlength=nL), "N_ENV": n_env})

    # ------------------------------------------------------------------------------------------
    # Separación intra / entre familias.
    # ~90 % de las combinaciones ambiente×SET alojan UNA sola población: cada familia es su propio
    # ensayo, así que la media familiar está confundida con el efecto de ensayo (familia×ambiente).
    #   * Intra-familia: desviación de la línea respecto a su familia → limpia (errores de ambiente
    #     se cancelan entre hermanos que comparten los mismos ensayos).
    #   * Entre familias: modelo sobre medias de ensayo T_pj = E_j + POP_p + ε_pj con
    #     Var(ε) = σ²_pe + σ²_e/n_pj; σ²_pe (familia×ambiente) se estima de los residuos.
    # ------------------------------------------------------------------------------------------
    lv["POP_MEAN"] = lv.groupby("POP").BLUE.transform("mean")
    lv["DEV"] = lv.BLUE - lv.POP_MEAN
    dev_map = pd.Series(lv.DEV.to_numpy(), index=lv.LINE_ID)
    tr = pd.DataFrame({"POP": d.POP.astype(str).to_numpy(), "ENV": d.ENV.to_numpy(),
                       "t": y - dev_map.reindex(d.LINE_ID).to_numpy(), "s2": s2[ecode]})
    T = tr.groupby(["POP", "ENV"]).agg(t=("t", "mean"), n=("t", "size"), s2=("s2", "mean")).reset_index()
    pc, pops_u = pd.factorize(T.POP)
    ec2, envs2 = pd.factorize(T.ENV)
    s2_pe = float(np.median(s2)) / 4
    for _ in range(4):
        w_t = 1.0 / (s2_pe + T.s2.to_numpy() / T.n.to_numpy())
        Ep, Pp, Wp, Ap, Cp = solve_two_way(T.t.to_numpy(), pc, ec2, w_t, len(pops_u), len(envs2))
        res = T.t.to_numpy() - Ep[ec2] - Pp[pc]
        dfc = len(T) / max(len(T) - len(pops_u) - len(envs2), 1)
        s2_pe = max(np.mean(res ** 2) * dfc - np.mean(T.s2 / T.n), 1.0)
    Cinv = np.linalg.pinv(Cp, hermitian=True)
    Mp = sparse.diags(1.0 / Wp) @ Ap
    pop_pev = 1.0 / Wp + np.asarray(Mp.multiply(Mp @ Cinv).sum(1)).ravel()
    _, comp_p = components(pc, ec2, len(pops_u), len(envs2))
    comp_pop = pd.Series(comp_p[ec2]).groupby(pc).first().reindex(range(len(pops_u))).to_numpy()
    Pc = Pp - pd.Series(Pp).groupby(comp_pop).transform("mean").to_numpy()
    popdf = pd.DataFrame({"POP": pops_u, "POP_BLUE": Pc, "POP_PEV": pop_pev, "POP_N_TRIALS": np.bincount(pc)})

    # Chequeo empírico: reproducibilidad de medias familiares partiendo los ambientes al azar
    rng = np.random.default_rng(7)
    half = pd.Series(rng.integers(0, 2, len(envs2)), index=envs2)
    halves = []
    for hv in (0, 1):
        m = T.ENV.map(half).to_numpy() == hv
        a, b = pd.factorize(T.POP[m]); e_, _ = pd.factorize(T.ENV[m])
        _, Ph, _, _, _ = solve_two_way(T.t.to_numpy()[m], a, e_, np.ones(m.sum()), len(b), e_.max() + 1)
        _, lab = components(a, e_, len(b), e_.max() + 1)
        cp = pd.Series(lab[e_]).groupby(a).first().reindex(range(len(b))).to_numpy()
        halves.append(pd.Series(Ph - pd.Series(Ph).groupby(cp).transform("mean").to_numpy(), index=b))
    j = halves[0].index.intersection(halves[1].index)
    r_half = float(halves[0][j].corr(halves[1][j]))
    q["pop_means_split_env_r"] = r_half
    q["pop_means_reliability_empirical"] = 2 * r_half / (1 + r_half) if r_half > -1 else np.nan
    q["sigma2_pop_x_env"] = s2_pe

    lv = lv.drop(columns=["POP_MEAN"]).merge(popdf, on="POP", how="left")

    # Componentes de varianza por año (momentos corregidos por PEV)
    vc_rows = []
    for yr, g in lv.groupby("YEAR"):
        pev = g.PEV.mean()
        nbar = g.groupby("POP").size().mean()
        s2_within = max(g.DEV.var() - pev * (1 - 1 / nbar), 0.0)
        pg = g.drop_duplicates("POP")
        s2_between = max(pg.POP_BLUE.var() - pg.POP_PEV.mean(), 0.0)
        vc_rows.append({"YEAR": yr, "N_LINES": len(g), "N_POPS": len(pg), "PEV_MEAN": pev,
                        "S2_G_WITHIN": s2_within, "S2_G_BETWEEN": s2_between,
                        "H2_LINE_WITHIN": s2_within / (s2_within + pev) if s2_within + pev > 0 else np.nan,
                        "POP_PEV_MEAN": pg.POP_PEV.mean(),
                        "POP_MEAN_REL": s2_between / (s2_between + pg.POP_PEV.mean()) if s2_between > 0 else 0.0,
                        "SIGMA2_E_MEDIAN": float(np.median(s2)), "SIGMA2_POPxENV": s2_pe})
    vc = pd.DataFrame(vc_rows)
    by_year = vc.set_index("YEAR")
    s2w = lv.YEAR.map(by_year.S2_G_WITHIN)
    s2b = lv.YEAR.map(by_year.S2_G_BETWEEN)
    lv["REL_WITHIN"] = s2w / (s2w + lv.PEV)
    lv["REL_POP"] = s2b / (s2b + lv.POP_PEV)
    lv["BLUP_POP"] = lv.REL_POP * lv.POP_BLUE
    # Valor contraído para ranking amplio: familia contraída + desviación intra-familia contraída
    lv["BLUP"] = lv.BLUP_POP + lv.REL_WITHIN * lv.DEV
    lv["BLUE"] = lv.POP_BLUE + lv.DEV   # BLUE coherente con el modelo de dos niveles

    q.update({"plots_used": len(d), "outliers_removed": removed_outliers,
              "envs_excluded": len(excluded_envs), "envs_used": int(nE), "lines": int(nL),
              "connected_components": int(ncomp),
              "h2_line_within_median": float(vc.H2_LINE_WITHIN.median()),
              "pop_mean_reliability_median": float(vc.POP_MEAN_REL.median()),
              "pops_per_env_median": float(d.groupby("ENV").POP.nunique().median())})
    qc[trait] = q
    return lv, env_tab, vc


def split_half_check(df, trait="YLD_BE"):
    """Chequeo independiente: correlación entre medias de línea con ambientes partidos al azar."""
    d = df[["LINE_ID", "ENV", "POP", trait]].dropna().copy()
    # quitar media de población×ambiente deja solo la señal intra-familia
    d["x"] = d[trait] - d.groupby(["POP", "ENV"], observed=True)[trait].transform("mean")
    rng = np.random.default_rng(1)
    envs = d.ENV.unique()
    half = dict(zip(envs, rng.integers(0, 2, len(envs))))
    d["h"] = d.ENV.map(half).astype(int)
    w = d.pivot_table(index="LINE_ID", columns="h", values="x", aggfunc="mean", observed=True).dropna()
    r = w[0].corr(w[1])
    return float(r), float(2 * r / (1 + r))  # Spearman–Brown → repetibilidad de la media completa


def main():
    ap = base_argparser(__doc__)
    ap.add_argument("--traits", nargs="+", default=TRAITS)
    args = ap.parse_args()
    P = get_paths(args.data_dir, args.out_dir)
    pheno = pd.read_parquet(P["out"] / "pheno_clean.parquet")
    qc, lines_all, envs_all, vcs_all = {}, [], [], []
    for C in CLUSTERS:
        dC = pheno[pheno.CLUSTER == C]
        qc[C] = {}
        for t in args.traits:
            with Timer(log, f"{C} {t}"):
                lv, et, vc = fit_trait(dC, t, qc[C])
            lv["CLUSTER"], lv["TRAIT"] = C, t
            et["CLUSTER"], et["TRAIT"] = C, t
            vc["CLUSTER"], vc["TRAIT"] = C, t
            lines_all.append(lv); envs_all.append(et); vcs_all.append(vc)
        r, rel = split_half_check(dC)
        qc[C]["split_half_within_pop_YLD"] = {"r_half": r, "spearman_brown_full": rel}

    lines_long = pd.concat(lines_all, ignore_index=True)
    # Formato ancho: una fila por línea
    wide = lines_long.pivot_table(index=["LINE_ID", "POP", "CLUSTER", "YEAR"], columns="TRAIT",
                                  values=["BLUE", "DEV", "PEV", "REL_WITHIN", "POP_BLUE", "POP_PEV", "REL_POP", "BLUP", "N_ENV"], observed=True)
    wide.columns = [f"{a}_{b}" for a, b in wide.columns]
    wide = wide.reset_index()
    pops = pd.read_parquet(P["out"] / "populations.parquet")
    wide = wide.merge(pops[["POP", "P1", "P2", "P1_W", "P2_W", "TESTER", "GEN"]], on="POP", how="left")
    wide.to_parquet(P["out"] / "line_values.parquet", index=False)

    popv = (lines_long
            .groupby(["CLUSTER", "POP", "YEAR", "TRAIT"])
            .apply(lambda g: pd.Series({"POP_BLUE": g.POP_BLUE.iat[0], "POP_PEV": g.POP_PEV.iat[0],
                                        "REL_POP": g.REL_POP.iat[0], "POP_N_TRIALS": g.POP_N_TRIALS.iat[0],
                                        "N_LINES": len(g), "SD_DEV": g.DEV.std()}), include_groups=False)
            .reset_index().merge(pops[["POP", "P1", "P2", "P1_W", "P2_W", "TESTER", "GEN"]], on="POP", how="left"))
    popv.to_parquet(P["out"] / "pop_values.parquet", index=False)
    pd.concat(envs_all, ignore_index=True).to_parquet(P["out"] / "env_quality.parquet", index=False)
    vcs = pd.concat(vcs_all, ignore_index=True)
    vcs.to_parquet(P["out"] / "varcomp.parquet", index=False)
    save_json(qc, P["out"] / "qc_line_values.json")
    log.info("\n" + vcs[vcs.TRAIT == PRIMARY_TRAIT].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
