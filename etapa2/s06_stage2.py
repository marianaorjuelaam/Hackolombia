"""Stage 2: genomic prediction of every line's value, with uncertainty, and the 2008 ranking.

A line's total value (what we select on) is split in two, exactly like Stage 1 (s04):

    line value  =  FAMILY value            +  WITHIN-FAMILY deviation
    (BLUE)         (POP_BLUE)                  (DEV)

  * FAMILY part: predicted by the Stage 1 baselines B1 (parent history), B2 (+ tester) and
    B3 (ridge on the parents' expected genotype + tester). We test simple ensembles of them.
  * WITHIN part: new here. Siblings share parents, so what makes one sibling better than another
    is WHICH parent it inherited each chromosome segment from. Two genomic models:
      W1  ridge regression (rrBLUP) on genotypes centred within each family
      W2  parent-segment model: an effect for each parent's 10 cM chromosome segment
    Both are trained on the DEV values (weighted by 1/PEV) of earlier years.

Validation: forward in time, exactly as Stage 1 (train on years < Y, predict the new families of
Y, Y = 2004..2007). Hyper-parameters and model choices are made on 2004-2007 only.
2008 is scored at the end as the untouched holdout.

Uncertainty: an empirical prediction-error SD per line, built from the validation years:
  family error (depends on how many of the parents have history: 0, 1 or 2) plus
  within-family error. From it we compute the probability that a line truly lands in the top 10 %.

Run:  bash run_stage2.sh "/path/Simplified Hackathon Dataset V3" artifacts
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.sparse.linalg import lsqr
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "etapa1"))
from metrics import evaluate  # noqa: E402  (Stage 1 metrics, so numbers are comparable)

CLUSTERS = ["C1", "C2"]
VAL_YEARS = [2004, 2005, 2006, 2007]
HOLDOUT = 2008
TEST_YEARS = VAL_YEARS + [HOLDOUT]
W1_LAMBDAS = [1000, 3000, 10000]
W2_LAMBDAS = [100, 300, 1000]
SEG_CM = 10.0
TOP = 0.10
CACHE_DIR = None  # set in main()


def log(msg):
    print(time.strftime("%H:%M:%S"), "|", msg, flush=True)


# ---------------------------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------------------------
def load_cluster(art: Path, C: str, trait: str):
    lv = pd.read_parquet(art / "line_values.parquet")
    L = pd.read_parquet(art / "geno" / f"{C}_lines.parquet")[["LINE_ID", "ROW", "PA", "PB"]]
    d = lv[(lv.CLUSTER == C)][["LINE_ID", "POP", "YEAR", f"BLUE_{trait}", f"DEV_{trait}", f"PEV_{trait}",
                               f"POP_BLUE_{trait}", f"POP_PEV_{trait}", "P1", "P2", "TESTER", "GEN"]]
    d = d.rename(columns={f"BLUE_{trait}": "y", f"DEV_{trait}": "dev", f"PEV_{trait}": "pev",
                          f"POP_BLUE_{trait}": "pop_blue", f"POP_PEV_{trait}": "pop_pev"})
    d = d.merge(L, on="LINE_ID", how="inner").sort_values(["YEAR", "POP"]).reset_index(drop=True)
    return d


def center_within_family(X: np.ndarray, pops: pd.Series) -> np.ndarray:
    codes = pd.factorize(pops)[0]
    sums = np.zeros((codes.max() + 1, X.shape[1]))
    np.add.at(sums, codes, X)
    return X - (sums / np.bincount(codes)[:, None])[codes].astype(X.dtype)


def segment_design(art: Path, C: str, d: pd.DataFrame):
    """Sparse design for W2: +centred origin on (PA, segment), -centred origin on (PB, segment)."""
    mk = pd.read_parquet(art / "geno" / "markers.parquet")
    mk["seg"] = pd.factorize(mk.CHR.astype(str) + "_" + (mk.CM // SEG_CM).astype(int).astype(str))[0]
    nb = mk.seg.max() + 1
    O = np.load(art / "geno" / f"{C}_origin_uint8.npy")[d.ROW.to_numpy()].astype(np.float32) / 200
    Ob = np.stack([O[:, (mk.seg == b).to_numpy()].mean(1) for b in range(nb)], 1)
    Ob = center_within_family(Ob, d.POP)
    par = pd.Index(sorted(set(d.PA.astype(str)) | set(d.PB.astype(str))))
    pa, pb = par.get_indexer(d.PA.astype(str)), par.get_indexer(d.PB.astype(str))
    n = len(d)
    cols = np.concatenate([pa[:, None] * nb + np.arange(nb), pb[:, None] * nb + np.arange(nb)], 1).ravel()
    vals = np.concatenate([Ob, -Ob], 1).ravel()
    return sparse.csr_matrix((vals, (np.repeat(np.arange(n), 2 * nb), cols)), shape=(n, len(par) * nb))


# ---------------------------------------------------------------------------------------------
# Within-family models
# ---------------------------------------------------------------------------------------------
def within_models(art: Path, C: str, d: pd.DataFrame):
    """Return a DataFrame with W1 and W2 predictions for every test-year line, per lambda."""
    G = np.load(art / "geno" / f"{C}_geno_int8.npy")
    X = center_within_family(G[d.ROW.to_numpy()].astype(np.float32) / 100, d.POP)
    has = d.dev.notna().to_numpy()
    y = d.dev.fillna(0).to_numpy()
    w = np.where(has, 1 / d.pev.to_numpy(), 0.0)
    w = w / w[has].mean()
    years = sorted(d.YEAR.unique())
    # W1: sufficient statistics per year, summed for each training window
    XtWX, XtWy = {}, {}
    for yr in years:
        m = (d.YEAR == yr).to_numpy()
        Xm = X[m].astype(np.float64)
        XtWX[yr] = (Xm * w[m, None]).T @ Xm
        XtWy[yr] = (Xm * w[m, None]).T @ y[m]
    Xs = segment_design(art, C, d)
    sw = np.sqrt(w)
    out = []
    for Y in TEST_YEARS:
        S = sum(XtWX[yr] for yr in years if yr < Y)
        b = sum(XtWy[yr] for yr in years if yr < Y)
        te = (d.YEAR == Y).to_numpy()
        tr = (d.YEAR < Y).to_numpy() & has
        frame = d.loc[te, ["LINE_ID"]].copy()
        for lam in W1_LAMBDAS:
            beta = np.linalg.solve(S + lam * np.eye(S.shape[0]), b)
            frame[f"W1_{lam}"] = X[te] @ beta
        Xtr = sparse.diags(sw[tr]) @ Xs[tr]
        for lam in W2_LAMBDAS:
            beta = lsqr(Xtr, y[tr] * sw[tr], damp=np.sqrt(lam), atol=1e-6, btol=1e-6, iter_lim=400)[0]
            frame[f"W2_{lam}"] = Xs[te] @ beta
        out.append(frame)
        log(f"  {C} within-family models for {Y} done")
    return pd.concat(out)


# ---------------------------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------------------------
def zs(s):
    return (s - s.mean()) / s.std() if s.std() > 0 else s * 0


def run_trait(art: Path, art_base: Path, trait: str):
    # family predictions are family-level: attach them by POP so lines without an observed BLUE get one too
    base = pd.read_parquet(art_base / "baseline_predictions.parquet").groupby("POP")[["B1", "B2", "B3"]].mean().reset_index()
    pops = pd.read_parquet(art / "populations.parquet")
    frames = []
    for C in CLUSTERS:
        d = load_cluster(art, C, trait)
        cache = CACHE_DIR / f"within_{trait}_{C}.parquet" if CACHE_DIR else None
        if cache is not None and cache.exists():
            wm = pd.read_parquet(cache)
        else:
            wm = within_models(art, C, d)
            if cache is not None:
                wm.to_parquet(cache, index=False)
        t = d[d.YEAR.isin(TEST_YEARS)].merge(wm, on="LINE_ID").merge(base, on="POP", how="left")
        t["CLUSTER"] = C
        # how many parents of the family have history (drives family-level uncertainty)
        seen = []
        for Y in TEST_YEARS:
            prev = pops[(pops.CLUSTER == C) & (pops.YEAR < Y)]
            known = set(prev.P1) | set(prev.P2)
            cur = t[t.YEAR == Y]
            seen.append(pd.Series(cur.P1.isin(known).astype(int) + cur.P2.isin(known).astype(int), index=cur.index))
        t["N_PARENTS_KNOWN"] = pd.concat(seen)
        frames.append(t)
    T = pd.concat(frames, ignore_index=True)
    return T


def pick_and_score(T: pd.DataFrame, trait: str):
    """Choose family model, within model and lambdas on 2004-2007; score everything."""
    val = T[T.YEAR.isin(VAL_YEARS)]
    choices = {}
    rows = []
    for C in CLUSTERS:
        v = val[val.CLUSTER == C]
        # within: best lambda for each model, then test W1 alone vs W1 + a*W2
        def rho(df, col, target="dev"):
            return np.nanmean([evaluate(g.rename(columns={target: "yy"}), "yy", col)["rho_within_pops"]
                               for _, g in df.groupby("YEAR")])
        w1 = max(W1_LAMBDAS, key=lambda l: rho(v, f"W1_{l}"))
        w2 = max(W2_LAMBDAS, key=lambda l: rho(v, f"W2_{l}"))
        best_mix, best_r = 0.0, rho(v, f"W1_{w1}")
        for a in [0.25, 0.5, 0.75, 1.0]:
            vv = v.assign(mix=v[f"W1_{w1}"] + a * v[f"W2_{w2}"])
            r = rho(vv, "mix")
            if r > best_r + 0.002:
                best_mix, best_r = a, r
        # family: B1, B2, B3 or averages (on the bu scale, averaging keeps units)
        fam_opts = {"B1": ["B1"], "B2": ["B2"], "B3": ["B3"], "B1+B3": ["B1", "B3"], "B2+B3": ["B2", "B3"]}
        # chosen by family-level accuracy (r between families), which is stable across years;
        # the top-10 % gain metric swings too much between years to choose with.
        def rpop(df, cols):
            df = df.assign(f=df[cols].mean(axis=1))
            return np.nanmean([evaluate(g, "y", "f")["r_between_pops"] for _, g in df.groupby("YEAR")])
        fam = max(fam_opts, key=lambda k: rpop(v, fam_opts[k]))
        choices[C] = dict(W1_lambda=w1, W2_lambda=w2, W2_weight=best_mix, family_model=fam,
                          family_cols=fam_opts[fam])
    # build final predictions
    parts = []
    for C in CLUSTERS:
        c = choices[C]
        t = T[T.CLUSTER == C].copy()
        t["PRED_FAMILY"] = t[c["family_cols"]].mean(axis=1)
        t["PRED_WITHIN"] = t[f"W1_{c['W1_lambda']}"] + c["W2_weight"] * t[f"W2_{c['W2_lambda']}"]
        t["PRED_TOTAL"] = t.PRED_FAMILY + t.PRED_WITHIN
        parts.append(t)
    T = pd.concat(parts, ignore_index=True)
    # ---- scores for every model, every year ----
    models = {"B1 parent history (family only)": "B1", "B2 parent history + tester (family only)": "B2",
              "B3 genomic family model (family only)": "B3",
              "Stage 2 family part only": "PRED_FAMILY", "Stage 2 total (family + within)": "PRED_TOTAL"}
    for C in CLUSTERS:
        for Y in TEST_YEARS:
            g = T[(T.CLUSTER == C) & (T.YEAR == Y)]
            for name, col in models.items():
                s = evaluate(g, "y", col, top=TOP)
                s.update(cluster=C, year=Y, model=name, holdout=Y == HOLDOUT, trait=trait)
                rows.append(s)
            s = evaluate(g.rename(columns={"dev": "yy"}), "yy", "PRED_WITHIN", top=TOP)
            rows.append(dict(cluster=C, year=Y, model="Within-family model on DEV", holdout=Y == HOLDOUT,
                             trait=trait, rho_within_pops=s["rho_within_pops"]))
    return T, pd.DataFrame(rows), choices


def add_uncertainty(T: pd.DataFrame):
    """Empirical error SD from validation years, by cluster and number of known parents."""
    val = T[T.YEAR.isin(VAL_YEARS)]
    T = T.copy()
    fam_sd, within_sd = {}, {}
    for C in CLUSTERS:
        v = val[val.CLUSTER == C]
        pv = v.drop_duplicates("POP")
        # family error: squared error vs POP_BLUE minus the noise already in POP_BLUE
        for k in (0, 1, 2):
            pk = pv[pv.N_PARENTS_KNOWN == k]
            if len(pk) < 5:
                pk = pv
            e2 = np.nanmean((pk.pop_blue - pk.PRED_FAMILY) ** 2) - np.nanmean(pk.pop_pev)
            fam_sd[(C, k)] = float(np.sqrt(max(e2, 1.0)))
        e2w = np.nanmean((v.dev - v.PRED_WITHIN) ** 2) - np.nanmean(v.pev)
        within_sd[C] = float(np.sqrt(max(e2w, 1.0)))
    T["SD_FAMILY"] = [fam_sd[(c, k)] for c, k in zip(T.CLUSTER, T.N_PARENTS_KNOWN)]
    T["SD_WITHIN"] = T.CLUSTER.map(within_sd)
    T["PRED_SD"] = np.sqrt(T.SD_FAMILY ** 2 + T.SD_WITHIN ** 2)
    # calibrate: scale SDs so a 90 % interval covers 90 % of observed BLUEs in 2004-2007 (not 2008)
    v = T[T.YEAR.isin(VAL_YEARS) & T.y.notna()]
    def cover(k):
        return np.mean(np.abs(v.y - v.PRED_TOTAL) < 1.645 * np.sqrt((k * v.PRED_SD) ** 2 + v.pev))
    ks = np.arange(1.0, 2.01, 0.02)
    k = float(ks[np.argmin([abs(cover(x) - 0.90) for x in ks])])
    T["PRED_SD"] = k * T.PRED_SD
    fam_sd = {key: val * k for key, val in fam_sd.items()}
    within_sd = {key: val * k for key, val in within_sd.items()}
    within_sd["calibration_factor"] = k
    # probability of truly being in the top 10 % of the year's lines (normal approximation)
    out = []
    for (C, Y), g in T.groupby(["CLUSTER", "YEAR"]):
        g = g.copy()
        true_sd = np.sqrt(g.PRED_TOTAL.var() + g.PRED_SD.pow(2).mean())
        cut = g.PRED_TOTAL.mean() + norm.ppf(1 - TOP) * true_sd
        g["P_TOP10"] = 1 - norm.cdf((cut - g.PRED_TOTAL) / g.PRED_SD)
        out.append(g)
    return pd.concat(out), fam_sd, within_sd


FAMILY_SHARE = 0.30   # two-step selection: best 30 % of families, then the best siblings inside them


def select_two_step(g: pd.DataFrame, share: float, family_share: float = FAMILY_SHARE) -> pd.Index:
    k = max(1, int(round(share * len(g))))
    fams = g.drop_duplicates("POP").nlargest(max(1, int(round(family_share * g.POP.nunique()))), "YLD_PRED_FAMILY").POP
    cand = g[g.POP.isin(fams)]
    if len(cand) <= k:
        return cand.index
    per = k / len(cand)
    sel = cand.groupby("POP", group_keys=False).apply(
        lambda x: x.nlargest(max(1, int(round(per * len(x)))), "YLD_PRED_WITHIN"), include_groups=False).index
    return sel


def realized_gain(g, sel):
    k = len(sel); mu = g.YLD_OBS_BLUE.mean()
    best = g.nlargest(k, "YLD_OBS_BLUE").YLD_OBS_BLUE.mean() - mu
    got = g.loc[sel, "YLD_OBS_BLUE"].mean() - mu
    return got, 100 * got / best


def strategy_table(P: pd.DataFrame) -> pd.DataFrame:
    rows = []
    rng = np.random.default_rng(0)
    for (C, Y), g in P.dropna(subset=["YLD_OBS_BLUE"]).groupby(["CLUSTER", "YEAR"]):
        k = int(round(0.10 * len(g)))
        strat = {
            "Random": g.sample(k, random_state=int(Y)).index,
            "Family prediction only": g.assign(r=rng.random(len(g))).sort_values(["YLD_PRED_FAMILY", "r"], ascending=False).index[:k],
            "Total prediction, one list": g.nlargest(k, "YLD_PRED").index,
            "Two-step: top 30% families, best siblings": select_two_step(g, 0.10),
        }
        for name, sel in strat.items():
            got, pct = realized_gain(g, sel)
            rows.append(dict(cluster=C, year=Y, strategy=name, gain_bu=got, gain_pct_of_max=pct,
                             n_families=g.loc[sel, "POP"].nunique()))
    return pd.DataFrame(rows)


def ranking_2008(P: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    R = P[P.YEAR == HOLDOUT].copy()
    parts = []
    for C, g in R.groupby("CLUSTER"):
        g = g.copy()
        g["RANK_IN_CLUSTER"] = g.YLD_PRED.rank(ascending=False, method="first").astype(int)
        g["RANK_IN_FAMILY"] = g.groupby("POP").YLD_PRED_WITHIN.rank(ascending=False, method="first").astype(int)
        g["MST_VS_CLUSTER"] = g.MST_PRED - g.MST_PRED.mean()
        for share in (0.05, 0.10, 0.20):
            g[f"ADVANCE_{int(share*100)}PCT"] = g.index.isin(select_two_step(g, share))
        parts.append(g)
    R = pd.concat(parts).sort_values(["CLUSTER", "RANK_IN_CLUSTER"])
    fam = R.groupby(["CLUSTER", "POP"]).agg(P1=("P1", "first"), P2=("P2", "first"), TESTER=("TESTER", "first"),
                                              GEN=("GEN", "first"), N_LINES=("LINE_ID", "size"),
                                              N_PARENTS_KNOWN=("N_PARENTS_KNOWN", "first"),
                                              FAMILY_PRED=("YLD_PRED_FAMILY", "first"),
                                              FAMILY_SD=("YLD_PRED_SD", "mean"),
                                              BEST_LINE_PRED=("YLD_PRED", "max"),
                                              N_ADVANCE_10PCT=("ADVANCE_10PCT", "sum"),
                                              OBS_FAMILY_BLUE=("YLD_OBS_FAMILY", "first")).reset_index()
    fam["FAMILY_RANK"] = fam.groupby("CLUSTER").FAMILY_PRED.rank(ascending=False, method="first").astype(int)
    return R, fam.sort_values(["CLUSTER", "FAMILY_RANK"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--art", default="artifacts", help="Stage 1 output folder")
    ap.add_argument("--art-mst", default="artifacts_mst", help="s05 baselines run with --trait MST")
    ap.add_argument("--out", default="resultados")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    global CACHE_DIR
    CACHE_DIR = out / "_cache"; CACHE_DIR.mkdir(exist_ok=True)
    art = Path(a.art)

    log("Yield: fitting models")
    T, scores, choices = pick_and_score(run_trait(art, art, "YLD_BE"), "YLD_BE")
    T, fam_sd, within_sd = add_uncertainty(T)
    log("Moisture: fitting models")
    M, scores_m, choices_m = pick_and_score(run_trait(art, Path(a.art_mst), "MST"), "MST")

    keep = ["LINE_ID", "POP", "CLUSTER", "YEAR", "GEN", "P1", "P2", "TESTER", "N_PARENTS_KNOWN",
            "PRED_FAMILY", "PRED_WITHIN", "PRED_TOTAL", "PRED_SD", "P_TOP10", "y", "dev", "pop_blue"]
    P = T[keep].rename(columns={"PRED_FAMILY": "YLD_PRED_FAMILY", "PRED_WITHIN": "YLD_PRED_WITHIN",
                                "PRED_TOTAL": "YLD_PRED", "PRED_SD": "YLD_PRED_SD", "y": "YLD_OBS_BLUE",
                                "dev": "YLD_OBS_DEV", "pop_blue": "YLD_OBS_FAMILY"})
    P = P.merge(M[["LINE_ID", "PRED_TOTAL", "y"]].rename(columns={"PRED_TOTAL": "MST_PRED", "y": "MST_OBS_BLUE"}),
                on="LINE_ID", how="left")
    P.to_parquet(out / "predictions_all_years.parquet", index=False)
    ST = strategy_table(P)
    ST.to_csv(out / "selection_strategies.csv", index=False)
    R, fam = ranking_2008(P)
    obs_cols = ["YLD_OBS_BLUE", "YLD_OBS_DEV", "YLD_OBS_FAMILY", "MST_OBS_BLUE"]
    # decision file: what a breeder gets in January 2008 (no observed 2008 columns)
    R.drop(columns=obs_cols).to_csv(out / "ranking_2008_lines.csv", index=False)
    fam.drop(columns=["OBS_FAMILY_BLUE"]).to_csv(out / "ranking_2008_families.csv", index=False)
    # scoring file: same ranking with the 2008 answer key attached (used only for evaluation)
    R.to_csv(out / "ranking_2008_with_answer_key.csv", index=False)
    log("\nSelection strategies, % of max gain (validation mean | 2008):\n" +
        ST.assign(split=np.where(ST.year == HOLDOUT, "2008", "val")).pivot_table(
            index=["cluster", "strategy"], columns="split", values="gain_pct_of_max").round(1).to_string())
    pd.concat([scores, scores_m]).to_csv(out / "stage2_scores.csv", index=False)
    json.dump({"yield": choices, "moisture": choices_m,
               "uncertainty": {"family_sd": {f"{c}_{k}": v for (c, k), v in fam_sd.items()}, "within_sd": within_sd}},
              open(out / "stage2_choices.json", "w"), indent=2, default=str)
    cols = ["r_overall", "r_between_pops", "rho_within_pops", "top10_precision", "gain_captured_pct"]
    S = scores[scores.model != "Within-family model on DEV"]
    log("Choices: " + json.dumps(choices, default=str))
    log("\nValidation 2004-2007 (mean):\n" + S[~S.holdout].groupby(["cluster", "model"])[cols].mean().round(3).to_string())
    log("\nHoldout 2008:\n" + S[S.holdout].set_index(["cluster", "model"])[cols].round(3).to_string())
    W = scores[scores.model == "Within-family model on DEV"].pivot_table(index="cluster", columns="year", values="rho_within_pops")
    log("\nWithin-family rank correlation on DEV by year:\n" + W.round(3).to_string())


if __name__ == "__main__":
    main()
