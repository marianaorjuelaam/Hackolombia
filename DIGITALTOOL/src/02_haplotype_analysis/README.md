# Haplotype Analysis Pipeline

## Overview

This pipeline implements a haplotype-based genomic prediction approach for a corn breeding program. The goal is to identify favorable haplotypes (SNP alleles associated with high performance) and validate if they persist across years.

## Key Insight

The goal is NOT to track individuals across years (impossible since each cross appears in only one year). Instead, we identify **favorable haplotypes** and verify if they **persist** in the next year's population.

**Central question**: "If SNP10 = -1 consistently gives high yield in years 2000-2007, is SNP10 = -1 present in the top performers of 2008?"

## Pipeline Structure

```
02_haplotype_analysis/
├── 00_preprocessing/
│   └── preprocess_data.py          # Pool individuals by year, filter SNPs
├── 01_stability_diagnostic/
│   ├── gblup_per_year.R           # Fit gBLUP per year (R)
│   └── stability_diagnostic.py    # Analyze SNP effect stability
├── 02_temporal_validation/
│   └── temporal_validation.R      # Cumulative gBLUP training
├── 03_alternative_methods/
│   └── alternative_methods.py     # XGBoost and Neural Network
├── 04_final_validation/
│   └── final_validation.py        # 2008 evaluation
└── README.md                      # This file
```

## Execution Order

### Phase 0: Preprocessing
```bash
cd DIGITALTOOL/src/02_haplotype_analysis/00_preprocessing
python preprocess_data.py
```

**What it does:**
- Loads phenotype and genomic data
- Pools all individuals by year (regardless of family)
- Filters SNPs by MAF (>0.05) and NA (<20%)
- Imputes missing values with mean
- Saves pooled data per year

**Output:**
- `pooled_genotype_{year}.parquet`
- `pooled_phenotype_{year}.parquet`
- `merged_{year}.parquet`
- `preprocessing_summary.json`

### Phase 1: Stability Diagnostic

**Step 1: Fit gBLUP per year (R)**
```bash
cd DIGITALTOOL/src/02_haplotype_analysis/01_stability_diagnostic
Rscript gblup_per_year.R
```

**Step 2: Analyze stability (Python)**
```bash
python stability_diagnostic.py
```

**What it does:**
- Fits gBLUP separately for each year (2000-2007)
- Extracts SNP effects from each model
- Correlates SNP effects across years
- Determines stability category (HIGH/MEDIUM/LOW)

**Output:**
- `snp_effects_matrix.csv`
- `snp_effects_correlation_matrix.csv`
- `stability_metrics.json`
- `stability_report.html`
- `plots/` (correlation heatmap, consecutive correlations, etc.)

### Phase 2: Temporal Validation

```bash
cd DIGITALTOOL/src/02_haplotype_analysis/02_temporal_validation
Rscript temporal_validation.R
```

**What it does:**
- Trains gBLUP on cumulative years (2000-2006, 2000-2007)
- Predicts on next year (2007, 2008)
- Identifies favorable haplotypes
- Validates predictions

**Output:**
- `predicted_blups_{year}.csv`
- `haplotype_favorable.csv`
- `validation_metrics.csv`
- `temporal_validation_summary.json`

### Phase 3: Alternative Methods

```bash
cd DIGITALTOOL/src/02_haplotype_analysis/03_alternative_methods
python alternative_methods.py
```

**What it does:**
- Fits XGBoost model
- Fits Neural Network (MLP)
- Compares with gBLUP baseline
- Generates feature importance plots

**Output:**
- `method_comparison.csv`
- `alternative_methods_results.json`
- `plots/` (method comparison, feature importance, predictions)

### Phase 4: Final Validation

```bash
cd DIGITALTOOL/src/02_haplotype_analysis/04_final_validation
python final_validation.py
```

**What it does:**
- Validates favorable haplotypes on 2008 data
- Calculates enrichment in top performers
- Generates final report

**Output:**
- `haplotype_validation_2008.csv`
- `final_validation_metrics.json`
- `final_validation_report.html`
- `plots/` (enrichment, top haplotypes comparison)

## Requirements

### Python Requirements
```
pandas>=1.5.0
numpy>=1.23.0
pyarrow>=10.0.0
matplotlib>=3.6.0
seaborn>=0.12.0
scikit-learn>=1.1.0
xgboost>=1.7.0
torch>=1.13.0 (optional, for neural network)
scipy>=1.9.0
```

### R Requirements
```r
install.packages(c("arrow", "data.table", "jsonlite", "here"))
install.packages("rrBLUP")  # or "sommer" for more advanced models
```

## Key Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| MAF_THRESHOLD | 0.05 | Minimum minor allele frequency |
| NA_THRESHOLD | 0.20 | Maximum proportion of NA per SNP |
| IMPUTATION_METHOD | "mean" | Method for imputing missing values |
| TRAIT | "YLD_BE" | Primary trait for analysis |
| TOP_PERCENT | 0.20 | Top percentage for haplotype analysis |

## Interpretation

### Stability Categories

- **HIGH (correlation > 0.5)**: SNP effects are consistent across years. Cumulative pooling is recommended.
- **MEDIUM (0.3 < correlation < 0.5)**: SNP effects show moderate consistency. Weighted pooling may be appropriate.
- **LOW (correlation < 0.3)**: SNP effects vary significantly. Rolling window is recommended.

### Validation Metrics

- **Correlation**: Pearson correlation between predicted and observed values
- **Rank Correlation**: Spearman correlation (robust to outliers)
- **Top Overlap**: Proportion of predicted top individuals that are also in observed top

### Haplotype Enrichment

- **Enrichment > 1**: Favorable haplotype is more frequent in top performers than in general population
- **Enrichment = 1**: No difference between top and general population
- **Enrichment < 1**: Favorable haplotype is less frequent in top performers

## Troubleshooting

### Memory Issues

For years with >80k individuals (2003, 2004, 2005):
- Subsample individuals (modify preprocess_data.py)
- Use rrBLUP instead of sommer (more memory efficient)
- Process in chunks

### Package Not Found

If R packages are not available:
```r
install.packages("arrow")
install.packages("data.table")
install.packages("jsonlite")
install.packages("here")
install.packages("rrBLUP")
```

If Python packages are not available:
```bash
pip install pandas numpy pyarrow matplotlib seaborn scikit-learn xgboost scipy
```

## References

- Henderson, C. R. (1984). Applications of Linear Models in Animal Breeding. University of Guelph.
- Crossa, J., et al. (2017). Genomic selection in plant breeding: methods, models, and perspectives. Trends in Plant Science, 22(11), 961-975.

## Para Ejecutar

```bash
cd /mnt/DOC/Hackolombia/DIGITALTOOL/src/02_haplotype_analysis

# Fase 0: Preprocesamiento
python 00_preprocessing/preprocess_data.py

# Fase 1: Diagnóstico de estabilidad
Rscript 01_stability_diagnostic/gblup_per_year.R
python 01_stability_diagnostic/stability_diagnostic.py

# Fase 2: Validación temporal
Rscript 02_temporal_validation/temporal_validation.R

# Fase 3: Métodos alternativos
python 03_alternative_methods/alternative_methods.py

# Fase 4: Validación final
python 04_final_validation/final_validation.py
```

## Contact

For questions or issues, please refer to the AGENTS.md file in the .opencode directory.