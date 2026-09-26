#!/usr/bin/env bash
# Usage: bash run_stage2.sh "/path/Simplified Hackathon Dataset V3" [stage1_artifacts_folder]
# Needs Stage 1 first:  bash ../etapa1/run_stage1.sh "<data>" artifacts
set -euo pipefail
DATA="$1"; ART="$(realpath "${2:-artifacts}")"
cd "$(dirname "$0")"
# moisture baselines (same s05 script, trait MST) into their own folder
MST="${ART}_mst"; mkdir -p "$MST/geno"
cp "$ART/line_values.parquet" "$ART/pop_values.parquet" "$MST/"
cp "$ART"/geno/*_parents.parquet "$MST/geno/"
(cd ../etapa1 && python3 s05_cv_baselines.py --data-dir "$DATA" --out-dir "$MST" --trait MST)
python3 s06_stage2.py --art "$ART" --art-mst "$MST" --out resultados
echo "Stage 2 done -> etapa2/resultados"
