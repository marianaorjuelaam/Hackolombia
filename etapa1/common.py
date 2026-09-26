"""Configuración y utilidades compartidas del pipeline (Etapa 1)."""
from __future__ import annotations

import argparse
import json
import logging
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd

# ----------------------------------------------------------------------------
# Parámetros
# ----------------------------------------------------------------------------
CLUSTERS = ["C1", "C2"]
TRAITS = ["YLD_BE", "MST", "TWT", "STLP", "RTLP", "PHT", "EHT", "ERM"]
PRIMARY_TRAIT = "YLD_BE"

# Rangos plausibles (filas fuera de rango -> NaN para ese rasgo)
TRAIT_BOUNDS = {
    "YLD_BE": (20, 400),   # bu/ac
    "MST": (5, 45),        # % humedad
    "TWT": (35, 70),       # lb/bu
    "STLP": (0, 100),
    "RTLP": (0, 100),
    "PHT": (30, 150),      # pulgadas
    "EHT": (5, 90),
    "ERM": (70, 140),
}

OUTLIER_Z = 4.0            # |residuo estandarizado| para descartar parcelas
ENV_MIN_LINES_QC = 30      # mínimo de líneas para juzgar la calidad de un ambiente
ENV_MIN_R = 0.05           # se excluye un ambiente si el límite superior 90 % de su r LOO < 0.05
FIRST_YEAR, TARGET_YEAR = 2000, 2008

GENO_SCALE = 100           # genotipos guardados como int8 = round(g * 100), g en [-1, 1]
ORIGIN_SCALE = 200         # dosis de origen P1 guardada como uint8 = round(d * 200), d en [0, 1]


def get_paths(data_dir: str | Path, out_dir: str | Path) -> dict:
    data_dir, out_dir = Path(data_dir), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    return {
        "data": data_dir,
        "out": out_dir,
        "pheno_csv": {c: data_dir / f"{c}_Phenotype_Data_V2.csv" for c in CLUSTERS},
        "unimputed_zip": {c: data_dir / f"Unimputed_{c}_Genome_Data.zip" for c in CLUSTERS},
        "imputed_c1_zip": data_dir / "ImputedC1Populations.zip",
        "env_csv": data_dir / "environmental_features.csv",
    }


def base_argparser(desc: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=desc)
    p.add_argument("--data-dir", required=True, help="Carpeta 'Simplified Hackathon Dataset V3'")
    p.add_argument("--out-dir", default="artifacts", help="Carpeta de salida")
    return p


def get_logger(name: str) -> logging.Logger:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(name)s | %(message)s", datefmt="%H:%M:%S")
    return logging.getLogger(name)


# ----------------------------------------------------------------------------
# Identificadores
# ----------------------------------------------------------------------------
_num_hash = re.compile(r"^0*(\d+)(#\d+)?$")


def norm_line_key(raw) -> str | None:
    """Normaliza el identificador de línea dentro de su población.

    '00000000012' -> '12' ; '000000325#1' -> '325#1' ; 12.0 -> '12'.
    Resuelve el sufijo '.0' de C2 (LINE guardado como float) y los ceros a la izquierda
    de los archivos genómicos, que rompen el join sugerido en la guía oficial.
    """
    if raw is None or (isinstance(raw, float) and np.isnan(raw)):
        return None
    s = str(raw).strip()
    if s.endswith(".0"):
        s = s[:-2]
    m = _num_hash.match(s)
    if not m:
        return s
    return str(int(m.group(1))) + (m.group(2) or "")


def line_uid(pop: str, line_key: str) -> str:
    return f"{pop}.{line_key}"


def env_id(year, loc) -> str:
    return f"{int(year)}_{loc}"


# ----------------------------------------------------------------------------
# Varios
# ----------------------------------------------------------------------------
def save_json(obj, path: Path):
    path.write_text(json.dumps(obj, indent=2, default=lambda o: o.item() if hasattr(o, "item") else str(o)))


class Timer:
    def __init__(self, log, label):
        self.log, self.label = log, label

    def __enter__(self):
        self.t = time.time()
        self.log.info(f"▶ {self.label}")
        return self

    def __exit__(self, *a):
        self.log.info(f"✔ {self.label} ({time.time() - self.t:.1f}s)")


def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * np.arcsin(np.sqrt(a))
