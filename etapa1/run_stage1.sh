#!/usr/bin/env bash
# Uso: bash run_stage1.sh "/ruta/Simplified Hackathon Dataset V3" [carpeta_salida]
set -euo pipefail
DATA="$1"; OUT="${2:-artifacts}"
cd "$(dirname "$0")"
python3 s01_clean_phenotypes.py --data-dir "$DATA" --out-dir "$OUT"
python3 s02_build_genotypes.py  --data-dir "$DATA" --out-dir "$OUT"
python3 s03_environment.py      --data-dir "$DATA" --out-dir "$OUT"
python3 s04_line_values.py      --data-dir "$DATA" --out-dir "$OUT"
python3 s05_cv_baselines.py     --data-dir "$DATA" --out-dir "$OUT"
echo "Etapa 1 completa → $OUT"
