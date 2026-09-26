"""Etapa 1.3 — Ambiente: limpieza, unidades, relleno de huecos y normales sin fuga de información.

Puntos clave
  * El archivo cubre ~100 % de los ambientes de C1 pero ~80 % de los de C2 → se rellenan los
    faltantes: suelo desde la misma localidad en otro año (el suelo no cambia) o la localidad
    más cercana; clima desde el ambiente más cercano del MISMO año.
  * El clima de abril–octubre de 2008 NO se conoce en enero de 2008. Para predecir el año Y solo
    se deben usar 'normales': promedio del clima de la localidad en años < Y (o de las localidades
    vecinas si la localidad es nueva). env_normals.parquet ya viene construido así.
  * DP01/DP10 son conteos de días con precipitación (≥0,01 y ≥0,1 pulgadas, convención NOAA
    GHCN), no punto de rocío como dice el diccionario.

Salidas: env_actual.parquet, env_normals.parquet, qc_environment.json
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from common import Timer, base_argparser, env_id, get_logger, get_paths, haversine_km, save_json

log = get_logger("s03")
warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)
MONTHS = ["04", "05", "06", "07", "08", "09", "10"]
DEPTHS = ["0_5cm", "5_15cm", "15_30cm", "30_60cm", "60_100cm", "100_200cm"]
DEPTH_CM = np.array([5, 10, 15, 30, 40, 100])
SOIL_VARS = {"cfvo": 0.1, "clay": 0.1, "silt": 0.1, "sand": 0.1, "nitrogen": 0.01, "phh2o": 0.1, "soc": 0.1}
# factores: vol‰→%, ‰→%, cg/kg→g/kg, pH×10→pH, dg/kg→g/kg


def add_derived(e: pd.DataFrame) -> pd.DataFrame:
    e = e.copy()
    col = lambda v, ms: [f"X{m}_{v}" for m in ms]
    e["PRCP_season"] = e[col("PRCP", MONTHS[1:6])].sum(1)          # may–sep
    e["PRCP_JulAug"] = e[col("PRCP", ["07", "08"])].sum(1)        # floración y llenado
    e["PRCP_AprMay"] = e[col("PRCP", ["04", "05"])].sum(1)        # siembra
    e["TAVG_JunAug"] = e[col("TAVG", ["06", "07", "08"])].mean(1)
    e["CLDD_season"] = e[col("CLDD", MONTHS[1:6])].sum(1)          # calor acumulado (≈ GDD)
    e["CLDD_JulAug"] = e[col("CLDD", ["07", "08"])].sum(1)        # estrés térmico en floración
    e["RAINDAYS_season"] = e[col("DP10", MONTHS[1:6])].sum(1)
    e["HTDD_AprMay"] = e[col("HTDD", ["04", "05"])].sum(1)        # primavera fría
    e["DRY_JulAug"] = e["PRCP_JulAug"] / (1 + e["CLDD_JulAug"])   # índice simple de balance hídrico
    return e


def soil_summary(e: pd.DataFrame) -> pd.DataFrame:
    out = {}
    for v, f in SOIL_VARS.items():
        M = e[[f"{v}_{d}" for d in DEPTHS]].to_numpy(float) * f
        e[[f"{v}_{d}" for d in DEPTHS]] = M
        out[f"{v}_0_30"] = (M[:, :3] * DEPTH_CM[:3]).sum(1) / DEPTH_CM[:3].sum()
        out[f"{v}_0_100"] = (M[:, :5] * DEPTH_CM[:5]).sum(1) / DEPTH_CM[:5].sum()
    return pd.concat([e, pd.DataFrame(out, index=e.index)], axis=1)


def main():
    args = base_argparser(__doc__).parse_args()
    P = get_paths(args.data_dir, args.out_dir)
    qc = {}
    with Timer(log, "ambiente"):
        raw = pd.read_csv(P["env_csv"])
        pheno = pd.read_parquet(P["out"] / "pheno_clean.parquet",
                                columns=["YEAR", "LOC", "ENV", "LATITUDE", "LONGITUDE", "CLUSTER"])
        envs = pheno.groupby("ENV", observed=True).agg(YEAR=("YEAR", "first"), LOC=("LOC", "first"),
                                                        LAT=("LATITUDE", "first"), LON=("LONGITUDE", "first"),
                                                        CLUSTERS=("CLUSTER", lambda s: ",".join(sorted(s.astype(str).unique())))).reset_index()
        envs["LOC"] = envs["LOC"].astype(str)

        # Algunas localidades no traen coordenadas: se usa el centroide de las localidades del mismo
        # estado (los dos primeros caracteres del código, p. ej. IA, IL, NE) y se marca la fuente.
        envs["STATE"] = envs.LOC.str[:2]
        envs["COORD_SOURCE"] = np.where(envs.LAT.notna(), "observed", "state_centroid")
        st = envs.dropna(subset=["LAT"]).drop_duplicates("LOC").groupby("STATE")[["LAT", "LON"]].mean()
        for c in ["LAT", "LON"]:
            envs[c] = envs[c].fillna(envs.STATE.map(st[c]))
        still = envs.LAT.isna()
        envs.loc[still, "COORD_SOURCE"] = "global_centroid"
        envs.loc[still, ["LAT", "LON"]] = envs.dropna(subset=["LAT"])[["LAT", "LON"]].mean().to_numpy()
        qc["locs_without_coords"] = sorted(envs[envs.COORD_SOURCE != "observed"].LOC.unique().tolist())

        raw["ENV"] = [env_id(y, l) for y, l in zip(raw.YEAR, raw.LOC)]
        soil_cols = [f"{v}_{d}" for v in SOIL_VARS for d in DEPTHS]
        weather_cols = [c for c in raw.columns if c.startswith("X")]
        qc["soil_varies_within_loc"] = int((raw.groupby("LOC")[soil_cols].nunique() > 1).any(axis=1).sum())

        # Suelo estático por localidad
        soil_loc = raw.groupby("LOC")[soil_cols].median()
        loc_xy = envs.groupby("LOC")[["LAT", "LON"]].first()
        e = envs.merge(raw[["ENV"] + weather_cols], on="ENV", how="left")
        e["WEATHER_SOURCE"] = np.where(e[weather_cols[0]].notna(), "observed", None)

        # Clima faltante: ambiente más cercano del mismo año
        have = e[e.WEATHER_SOURCE == "observed"]
        miss_idx = e.index[e.WEATHER_SOURCE.isna()]
        dists = []
        for i in miss_idx:
            cand = have[have.YEAR == e.at[i, "YEAR"]]
            d = haversine_km(e.at[i, "LAT"], e.at[i, "LON"], cand.LAT.to_numpy(), cand.LON.to_numpy())
            j = int(np.argmin(d))
            e.loc[i, weather_cols] = cand.iloc[j][weather_cols].to_numpy()
            e.at[i, "WEATHER_SOURCE"] = f"nearest_same_year:{cand.iloc[j].LOC}"
            dists.append(float(d[j]))
        e["WEATHER_FILL_KM"] = 0.0
        e.loc[miss_idx, "WEATHER_FILL_KM"] = dists

        # Suelo: misma localidad si existe, si no la más cercana
        soil = []
        src = []
        for loc, lat, lon in zip(e.LOC, e.LAT, e.LON):
            if loc in soil_loc.index:
                soil.append(soil_loc.loc[loc].to_numpy()); src.append("same_loc")
            else:
                d = haversine_km(lat, lon, loc_xy.loc[soil_loc.index, "LAT"].to_numpy(), loc_xy.loc[soil_loc.index, "LON"].to_numpy())
                d = np.where(np.isnan(d), np.inf, d)
                j = int(np.argmin(d)); soil.append(soil_loc.iloc[j].to_numpy()); src.append(f"nearest:{soil_loc.index[j]}")
        e[soil_cols] = np.vstack(soil)
        e["SOIL_SOURCE"] = src

        e = soil_summary(add_derived(e)).copy()
        qc["envs_total"] = len(e)
        qc["envs_weather_filled"] = int(len(miss_idx))
        qc["weather_fill_km_median"] = float(np.median(dists)) if dists else 0.0
        qc["weather_fill_km_p90"] = float(np.percentile(dists, 90)) if dists else 0.0
        qc["envs_soil_from_other_loc"] = int((e.SOIL_SOURCE != "same_loc").sum())
        qc["filled_by_cluster"] = e[e.WEATHER_SOURCE != "observed"].CLUSTERS.value_counts().to_dict()
        e.to_parquet(P["out"] / "env_actual.parquet", index=False)

        # ---------------- Normales sin fuga: para el año Y solo se usan años < Y ----------------
        wfeat = weather_cols + ["PRCP_season", "PRCP_JulAug", "PRCP_AprMay", "TAVG_JunAug", "CLDD_season",
                                "CLDD_JulAug", "RAINDAYS_season", "HTDD_AprMay", "DRY_JulAug"]
        loc_year = e.groupby(["LOC", "YEAR"])[wfeat].mean()
        rows = []
        n_new = {}
        for _, r in e.iterrows():
            Y = r.YEAR
            past = loc_year[loc_year.index.get_level_values("YEAR") < Y]
            if len(past) == 0:  # primer año: no hay historia
                vals, how, nyrs = r[wfeat].to_numpy(float) * np.nan, "no_history", 0
            elif r.LOC in past.index.get_level_values("LOC"):
                sub = past.loc[r.LOC]
                vals, how, nyrs = sub.mean().to_numpy(), "loc_history", len(sub)
            else:
                pl = past.groupby(level="LOC").mean()
                d = haversine_km(r.LAT, r.LON, loc_xy.loc[pl.index, "LAT"].to_numpy(), loc_xy.loc[pl.index, "LON"].to_numpy())
                k = np.argsort(d)[:3]
                w = 1 / np.maximum(d[k], 10.0)
                vals, how, nyrs = (pl.iloc[k].to_numpy() * w[:, None]).sum(0) / w.sum(), "idw_3_neighbors", 0
                n_new[Y] = n_new.get(Y, 0) + 1
            rows.append([r.ENV, how, nyrs] + list(vals))
        nm = pd.DataFrame(rows, columns=["ENV", "NORMAL_SOURCE", "NORMAL_YEARS"] + [f"N_{c}" for c in wfeat])
        static = e[["ENV", "YEAR", "LOC", "STATE", "LAT", "LON", "COORD_SOURCE", "CLUSTERS"] + [c for c in e.columns if c.endswith(("_0_30", "_0_100"))] + soil_cols]
        normals = static.merge(nm, on="ENV")
        normals.to_parquet(P["out"] / "env_normals.parquet", index=False)
        qc["new_locs_by_year_using_neighbors"] = {int(k): v for k, v in sorted(n_new.items())}
        qc["normal_source_counts_2008"] = normals[normals.YEAR == 2008].NORMAL_SOURCE.value_counts().to_dict()
        save_json(qc, P["out"] / "qc_environment.json")
        log.info(qc)


if __name__ == "__main__":
    main()
