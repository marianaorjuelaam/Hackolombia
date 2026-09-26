# Etapa 2: Genomic prediction and the 2008 line ranking

Stage 2 turns Stage 1's line values into predictions for brand-new lines and a ranked 2008 advancement list with uncertainty. The notebook `Line_Selection_Model.ipynb` explains every step in plain language with charts.

## How to run

```bash
bash ../etapa1/run_stage1.sh "/path/Simplified Hackathon Dataset V3" artifacts   # ~5-8 min
bash run_stage2.sh "/path/Simplified Hackathon Dataset V3" artifacts             # ~5 min
```

`run_stage2.sh` first reruns `s05_cv_baselines.py --trait MST` (moisture baselines) into `artifacts_mst`, then runs `s06_stage2.py`. Results go to `resultados/`. The notebook only reads `resultados/`, so it opens in seconds.

## Model

A line's value is split in two, as in Stage 1:

**line value (BLUE) = family value (POP_BLUE) + within-family deviation (DEV)**

| Part | Model | Notes |
|---|---|---|
| Family | Stage 1 baselines: B3 (C1) and the average of B1 and B3 (C2) | Chosen per cluster by r between families over 2004-2007 |
| Within family | W1: ridge regression (rrBLUP) on genotypes centred within each family, trained on DEV weighted by 1/PEV | New. Ranks siblings; family-only models can't |
| | W2: parent-segment model (effect per parent x 10 cM segment) | Weight 0.25 in C2, 0 in C1 (chosen on validation) |
| Uncertainty | Empirical error SD by cluster and number of parents with history, calibrated to 90% coverage on 2004-2007 | Gives `YLD_PRED_SD` and `P_TOP10` |
| Moisture | Same pipeline on MST | `MST_PRED` |

**Validation:** forward in time (train on years < Y, predict the new families of Y, Y = 2004 to 2007). All choices were made on 2004 to 2007. 2008 was scored once, at the end.

**Note on parent origin:** `origin_uint8` is the fraction from `PA` in `geno/{C}_lines.parquet`. `PA` matches `P1` from `populations.parquet` only about 45% of the time, so always use `PA`/`PB` with the origin matrix.

## Results (yield)

| | C1 validation | C1 2008 | C2 validation | C2 2008 |
|---|---|---|---|---|
| r overall, B1 parent history | 0.231 | 0.321 | 0.295 | 0.279 |
| r overall, B3 genomic family | 0.371 | 0.331 | 0.401 | 0.646 |
| **r overall, Stage 2 total** | **0.393** | **0.344** | **0.426** | **0.636** |
| rho within families, Stage 2 | 0.238 | 0.175 | 0.234 | 0.187 |

Advancing 10% of lines, % of the maximum possible gain:

| Strategy | C1 validation | C1 2008 | C2 validation | C2 2008 |
|---|---|---|---|---|
| Random | 0 | 2 | 0 | 0 |
| Family prediction only | 23 | 25 | 30 | 59 |
| Total prediction, one list | 29 | 16 | 30 | 57 |
| **Two-step: top 30% families, best siblings** | **36** | **27** | **31** | **51** |

The recommended strategy is the two-step selection: it's the most consistent, and it keeps more families in the program.

## Output files (`resultados/`)

| File | Contents |
|---|---|
| `ranking_2008_lines.csv` | **The decision file** (no 2008 observations). One row per 2008 line: `YLD_PRED` (family and within parts), `YLD_PRED_SD`, `P_TOP10`, `MST_PRED`, ranks, `ADVANCE_5PCT` / `ADVANCE_10PCT` / `ADVANCE_20PCT` |
| `ranking_2008_families.csv` | One row per 2008 family: parents, tester, predicted value, SD, lines advanced |
| `ranking_2008_with_answer_key.csv` | Same ranking with the observed 2008 values, for scoring only |
| `predictions_all_years.parquet` | Predictions for every test year 2004 to 2008 (for charts and the notebook) |
| `stage2_scores.csv` | All metrics by cluster, year, model and trait |
| `selection_strategies.csv` | Realized gain for each selection strategy |
| `stage2_choices.json` | Chosen models, penalties and uncertainty SDs |

Yield predictions are relative to the year's average line (0 = average), in bu/ac.

## Limitations

- Observed line values are only about 45% signal within families, so every score understates true accuracy.
- Family values are tangled with site effects (most sites test one family).
- Progeny were genotyped at 49 to 123 markers; the rest is imputed.
- The 2008 intervals covered about 84% instead of 90%; the highest `P_TOP10` group (over 40%) was over-optimistic because siblings share family-level errors.
