"""
Site and plot-budget analysis (run separately for C1 and C2)
============================================================

Questions answered with the raw yield data of each cluster, using only within-family
information (site effects are confounded with family effects because ~90% of sites test a
single family, so site-level yield averages are NOT used):

1. Informativeness of a site-year: within-family correlation between the line values measured
   there and the same lines' mean at the other sites of that year.
2. Persistence: does the informativeness of a site repeat the next year?
3. Backtest: keeping half of the sites planted in year t, chosen with information from years
   < t, does it preserve the ranking of lines better than a random half?
4. Retention: which characteristics separate the sites that breeders kept from one year to
   the next (size of the trial, informativeness)?
5. Reliability of a line mean as a function of the number of observations averaged.

Output (data/processed/prediction/final_analysis/):
    site_informativeness.csv, site_persistence.csv, site_backtest.csv,
    site_retention.csv, reliability_by_obs.csv

Usage:
    python site_analysis.py
"""

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

BASE_DIR = Path(__file__).parent.parent.parent.parent
DATA = BASE_DIR / "Simplified Hackathon Dataset V3"
OUT = BASE_DIR / "DIGITALTOOL" / "data" / "processed" / "prediction" / "final_analysis"
OUT.mkdir(parents=True, exist_ok=True)

MIN_LINES = 30
N_RANDOM = 100
N_ITER = 20


def group_means(codes, values, n_groups):
    return np.bincount(codes, weights=values, minlength=n_groups) / np.maximum(np.bincount(codes, minlength=n_groups), 1)


def load(cluster):
    cols = ["YEAR_x", "shorthand_x", "LOC", "LINE_UNIQUE_ID", "GERMPLASM_ID_TESTER", "YLD_BE"]
    d = pd.read_csv(DATA / f"{cluster}_Phenotype_Data_V2.csv", usecols=cols, low_memory=False)
    d = d.rename(columns={"YEAR_x": "YEAR", "shorthand_x": "POP", "LINE_UNIQUE_ID": "LINE_ID", "GERMPLASM_ID_TESTER": "TESTER"})
    d = d[d["YLD_BE"].notna()].copy()
    d["TESTER"] = d["TESTER"].fillna(-1).astype(int).astype(str)
    d["ENV"] = d["YEAR"].astype(int).astype(str) + "_" + d["LOC"].astype(str)
    return d


def adjust_year(df):
    """Yield minus environment and tester effects (backfitting); line and family effects remain."""
    y = df["YLD_BE"].to_numpy(float)
    env, eu = pd.factorize(df["ENV"])
    te, tu = pd.factorize(df["TESTER"])
    li, lu = pd.factorize(df["LINE_ID"])
    mu = y.mean()
    e, t, l = np.zeros(len(eu)), np.zeros(len(tu)), np.zeros(len(lu))
    for _ in range(N_ITER):
        e = group_means(env, y - mu - t[te] - l[li], len(eu))
        t = group_means(te, y - mu - e[env] - l[li], len(tu))
        l = group_means(li, y - mu - e[env] - t[te], len(lu))
    out = df[["POP", "LOC", "LINE_ID"]].copy()
    out["li"], out["ei"], out["yadj"] = li, env, y - e[env] - t[te]
    return out


def informativeness(obs):
    g = obs.groupby(["li", "ei"]).agg(a=("yadj", "mean"), c=("yadj", "size"), pop=("POP", "first"), loc=("LOC", "first")).reset_index()
    s = obs.groupby("li")["yadj"].agg(["sum", "size"])
    g = g.join(s, on="li")
    g["b"] = (g["sum"] - g["a"] * g["c"]) / (g["size"] - g["c"]).replace(0, np.nan)
    g = g.dropna(subset=["b"])
    rows = []
    for ei, d in g.groupby("ei"):
        if len(d) < MIN_LINES:
            continue
        a = d["a"] - d.groupby("pop")["a"].transform("mean")
        b = d["b"] - d.groupby("pop")["b"].transform("mean")
        if a.std() > 0 and b.std() > 0:
            rows.append(dict(LOC=d["loc"].iloc[0], n_lines=len(d), r_within=float(np.corrcoef(a, b)[0, 1])))
    return pd.DataFrame(rows)


def retained_accuracy(obs, keep_locs):
    """Within-family r between line means over kept sites and over the remaining sites."""
    d = obs.assign(keep=obs["LOC"].isin(keep_locs))
    g = d.groupby(["li", "keep"])["yadj"].mean().unstack().dropna()
    if len(g) < 100 or True not in g.columns or False not in g.columns:
        return np.nan
    pop = d.groupby("li")["POP"].first().reindex(g.index)
    a = g[True] - g[True].groupby(pop).transform("mean")
    b = g[False] - g[False].groupby(pop).transform("mean")
    return float(np.corrcoef(a, b)[0, 1])


def reliability_by_obs(obs, rng, max_m=6):
    # line codes (li) restart in every year, so group by the global line id
    grp = obs.groupby("LINE_ID")["yadj"].apply(np.asarray)
    pop = obs.groupby("LINE_ID")["POP"].first()
    rows = []
    for m in range(1, max_m + 1):
        ids = np.array([i for i, v in grp.items() if len(v) >= 2 * m])
        if len(ids) < 500:
            break
        ids = rng.choice(ids, size=min(len(ids), 15000), replace=False)
        a, b = [], []
        for i in ids:
            v = rng.permutation(grp[i])
            a.append(v[:m].mean())
            b.append(v[m:2 * m].mean())
        df = pd.DataFrame({"a": a, "b": b, "pop": pop.reindex(ids).to_numpy()})
        for c in ("a", "b"):
            df[c] = df[c] - df.groupby("pop")[c].transform("mean")
        rows.append(dict(m=m, reliability=float(df["a"].corr(df["b"])), n_lines=len(ids)))
    return pd.DataFrame(rows)


def run_cluster(cluster):
    rng = np.random.default_rng(0)
    d = load(cluster)
    obs_by_year = {int(y): adjust_year(df) for y, df in d.groupby("YEAR")}
    info = []
    for y, obs in obs_by_year.items():
        r = informativeness(obs)
        info.append(r.assign(year=y))
    info = pd.concat(info, ignore_index=True)
    info["cluster"] = cluster

    # persistence of site informativeness between consecutive years
    piv = info.pivot_table(index="LOC", columns="year", values="r_within")
    pers = []
    for y in sorted(piv.columns):
        if y - 1 in piv.columns:
            c = piv[[y - 1, y]].dropna()
            if len(c) > 8:
                pers.append(dict(cluster=cluster, year=y, n_sites=len(c), corr=float(np.corrcoef(c[y - 1], c[y])[0, 1])))

    # backtest: keep half of the planted sites
    bt = []
    for t in sorted(obs_by_year):
        if t < 2003:
            continue
        obs = obs_by_year[t]
        locs = sorted(obs["LOC"].unique())
        past = info[info.year < t].groupby("LOC")["r_within"].mean()
        known = [l for l in locs if l in past.index]
        if len(known) < 10:
            continue
        k = len(known) // 2
        unknown = set(locs) - set(known)
        top = set(past.loc[known].sort_values(ascending=False).index[:k])
        rand = [retained_accuracy(obs, set(rng.choice(known, k, replace=False)) | unknown) for _ in range(N_RANDOM)]
        bt.append(dict(cluster=cluster, year=t, n_known=len(known), n_sites=len(locs),
                       r_informative=retained_accuracy(obs, top | unknown), r_random_mean=np.nanmean(rand),
                       r_random_p05=np.nanpercentile(rand, 5), r_random_p95=np.nanpercentile(rand, 95)))

    # retention: sites kept from year t-1 to t
    ret = []
    for t in sorted(obs_by_year):
        if t - 1 not in obs_by_year:
            continue
        prev, cur = obs_by_year[t - 1], set(obs_by_year[t]["LOC"])
        n_obs = prev.groupby("LOC").size()
        inf = info[info.year == t - 1].set_index("LOC")["r_within"]
        tab = pd.DataFrame({"kept": [l in cur for l in n_obs.index], "n_obs": n_obs.to_numpy(), "inf": inf.reindex(n_obs.index).to_numpy()}, index=n_obs.index)
        row = dict(cluster=cluster, year=t, n_prev=len(tab), kept=int(tab["kept"].sum()))
        for c in ("n_obs", "inf"):
            x = tab.dropna(subset=[c])
            if x["kept"].nunique() == 2:
                row[f"{c}_kept"], row[f"{c}_dropped"] = x[x.kept][c].mean(), x[~x.kept][c].mean()
                row[f"p_{c}"] = stats.mannwhitneyu(x[x.kept][c], x[~x.kept][c]).pvalue
        ret.append(row)

    rel = reliability_by_obs(pd.concat(obs_by_year.values()), rng)
    rel["cluster"] = cluster
    return info, pd.DataFrame(pers), pd.DataFrame(bt), pd.DataFrame(ret), rel


def main():
    parts = [run_cluster(c) for c in ("C1", "C2")]
    names = ["site_informativeness", "site_persistence", "site_backtest", "site_retention", "reliability_by_obs"]
    for i, n in enumerate(names):
        pd.concat([p[i] for p in parts], ignore_index=True).to_csv(OUT / f"{n}.csv", index=False)
        print(f"saved {n}.csv")


if __name__ == "__main__":
    main()
