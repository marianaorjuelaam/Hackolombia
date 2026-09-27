"""
Phase 0: Preprocessing for Haplotype Analysis
==============================================

This script pools all individuals by year, filters SNPs by MAF and NA,
and prepares the data for genomic prediction.

Input:
- C1_Phenotype_Data_V2.csv (phenotype data)
- ImputedPopulationsC1/*.csv (genomic data for each family)

Output:
- pooled_genotype_{year}.parquet (pooled genotype matrix per year)
- pooled_phenotype_{year}.parquet (pooled phenotype per year)
- snp_filter_report.csv (SNP filtering summary)
- preprocessing_summary.json (summary statistics)

Usage:
    python preprocess_data.py

Author: Haplotype Analysis Pipeline
Date: 2024
"""

import os
import sys
import json
import glob
import re
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
# Configuration
# ============================================================================

# Paths
BASE_DIR = Path(__file__).parent.parent.parent.parent.parent  # Go up to Hackolombia
DATA_DIR = BASE_DIR / "Simplified Hackathon Dataset V3"
OUTPUT_DIR = BASE_DIR / "DIGITALTOOL" / "data" / "processed" / "haplotype_analysis"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Parameters
MAF_THRESHOLD = 0.05  # Minimum minor allele frequency
NA_THRESHOLD = 0.20   # Maximum proportion of NA per SNP
IMPUTATION_METHOD = "mean"  # "mean" or "median"

# Years to process
YEARS = list(range(2000, 2009))  # 2000-2008

# Smoke-test switch: cap how many populations (crosses) get pooled per year,
# so the whole pipeline (this script -> gblup_per_year.R -> stability
# diagnostic) can be run end-to-end on a tiny slice of data.
# Set to None for the full production run over every population.
MAX_POPULATIONS_PER_YEAR = 5

# ============================================================================
# Helper Functions
# ============================================================================

def load_phenotype_data() -> pd.DataFrame:
    """Load and clean phenotype data."""
    print("Loading phenotype data...")
    pheno_path = DATA_DIR / "C1_Phenotype_Data_V2.csv"
    pheno = pd.read_csv(pheno_path, low_memory=False)
    
    # Keep only _x columns (remove _y duplicates)
    cols_x = [c for c in pheno.columns if '_y' not in c and c != 'Unnamed: 0']
    pheno = pheno[cols_x]
    
    # Rename _x columns to clean names
    rename_map = {
        'YEAR_x': 'YEAR',
        'shorthand_x': 'POP',
        'projects_x': 'projects',
        'LINE_UNIQUE_ID': 'LINE_ID',
        'Unnamed: 0_x': 'row_id',
    }
    pheno = pheno.rename(columns=rename_map)
    
    # Extract population number from POP (e.g., "C1.1" -> "1")
    pheno['POP_NUM'] = pheno['POP'].str.extract(r'C\d+\.(\d+)').astype(str)
    
    print(f"  Loaded {len(pheno)} records with {len(pheno.columns)} columns")
    return pheno


def get_genomic_files() -> Dict[str, Path]:
    """Get all genomic files and create mapping."""
    print("Scanning genomic files...")
    genomic_dir = DATA_DIR / "ImputedPopulationsC1"
    genomic_files = {}
    
    for f in genomic_dir.glob("C1.*_Imputed.csv"):
        # Extract population number from filename (e.g., "C1.100_Imputed.csv" -> "100")
        pop_num = f.stem.split('.')[1].replace('_Imputed', '')
        genomic_files[pop_num] = f
    
    print(f"  Found {len(genomic_files)} genomic files")
    return genomic_files


def load_genomic_file(filepath: Path) -> Tuple[pd.DataFrame, List[str]]:
    """
    Load a single genomic file.
    
    Returns:
        genotype_matrix: DataFrame with individuals as rows, SNPs as columns
        parent_ids: List of parent IDs (first two rows)
    """
    df = pd.read_csv(filepath, index_col=0)
    
    # First two rows are parents
    parent_ids = list(df.index[:2])
    
    # Remove parent rows for now (we'll use them later for parent analysis)
    df_progeny = df.iloc[2:]
    
    return df_progeny, parent_ids


def calculate_maf(genotypes: pd.Series) -> float:
    """Calculate minor allele frequency for a SNP."""
    # Remove NAs
    genotypes = genotypes.dropna()
    
    if len(genotypes) == 0:
        return 0.0
    
    # Count alleles: -1, 0, 1
    counts = genotypes.value_counts()
    
    # Calculate allele frequencies
    # For -1, 0, 1 coding:
    # -1 = homozygous reference (p)
    # 0 = heterozygous (2pq)
    # 1 = homozygous alternate (q)
    
    n = len(genotypes)
    if n == 0:
        return 0.0
    
    # Calculate frequency of alternate allele (1)
    alt_freq = (counts.get(1, 0) + 0.5 * counts.get(0, 0)) / n
    
    # MAF is the minimum of alt_freq and 1-alt_freq
    maf = min(alt_freq, 1 - alt_freq)
    
    return maf


def filter_snps(genotype_matrix: pd.DataFrame, 
                maf_threshold: float = 0.05,
                na_threshold: float = 0.20) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Filter SNPs based on MAF and NA proportion.
    
    Returns:
        filtered_matrix: Genotype matrix after filtering
        filter_report: DataFrame with filtering statistics
    """
    print(f"  Filtering SNPs (MAF > {maf_threshold}, NA < {na_threshold})...")
    
    n_snps_original = genotype_matrix.shape[1]
    filter_stats = []
    
    snps_to_keep = []
    
    for snp in genotype_matrix.columns:
        snp_data = genotype_matrix[snp]
        
        # Calculate NA proportion
        na_prop = snp_data.isna().mean()
        
        # Calculate MAF (only on non-NA values)
        maf = calculate_maf(snp_data)
        
        # Check if SNP passes filters
        passes_maf = maf >= maf_threshold
        passes_na = na_prop <= na_threshold
        is_polymorphic = snp_data.nunique() > 1
        
        if passes_maf and passes_na and is_polymorphic:
            snps_to_keep.append(snp)
        
        filter_stats.append({
            'snp': snp,
            'maf': maf,
            'na_prop': na_prop,
            'n_unique': snp_data.nunique(),
            'passes_maf': passes_maf,
            'passes_na': passes_na,
            'is_polymorphic': is_polymorphic,
            'kept': passes_maf and passes_na and is_polymorphic
        })
    
    filter_report = pd.DataFrame(filter_stats)
    filtered_matrix = genotype_matrix[snps_to_keep]
    
    print(f"    Original: {n_snps_original} SNPs")
    print(f"    After MAF filter: {filter_report['passes_maf'].sum()} SNPs")
    print(f"    After NA filter: {filter_report['passes_na'].sum()} SNPs")
    print(f"    After polymorphic filter: {filter_report['is_polymorphic'].sum()} SNPs")
    print(f"    Final: {len(snps_to_keep)} SNPs")
    
    return filtered_matrix, filter_report


def impute_missing(genotype_matrix: pd.DataFrame, 
                   method: str = "mean") -> pd.DataFrame:
    """Impute missing values in genotype matrix."""
    print(f"  Imputing missing values ({method})...")
    
    na_before = genotype_matrix.isna().sum().sum()
    
    if method == "mean":
        # Impute with mean of each SNP
        imputed = genotype_matrix.fillna(genotype_matrix.mean())
    elif method == "median":
        # Impute with median of each SNP
        imputed = genotype_matrix.fillna(genotype_matrix.median())
    else:
        raise ValueError(f"Unknown imputation method: {method}")
    
    na_after = imputed.isna().sum().sum()
    print(f"    NA before: {na_before}")
    print(f"    NA after: {na_after}")
    
    return imputed


# ============================================================================
# Main Processing
# ============================================================================

def pool_individuals_by_year(pheno: pd.DataFrame, 
                             genomic_files: Dict[str, Path]) -> Dict[int, pd.DataFrame]:
    """
    Pool all individuals from a given year into a single genotype matrix.
    
    Returns:
        Dictionary mapping year -> pooled genotype matrix
    """
    print("\nPooling individuals by year...")
    
    pooled_by_year = {}
    
    for year in YEARS:
        print(f"\nProcessing year {year}...")
        
        # Get phenotype data for this year
        pheno_year = pheno[pheno['YEAR'] == year]
        print(f"  Found {len(pheno_year)} individuals in phenotype data")
        
        if len(pheno_year) == 0:
            continue
        
        # Get unique populations for this year
        populations = pheno_year['POP'].unique()
        if MAX_POPULATIONS_PER_YEAR is not None:
            populations = populations[:MAX_POPULATIONS_PER_YEAR]
            print(f"  Found {len(pheno_year['POP'].unique())} populations "
                  f"(smoke test: using first {len(populations)})")
        else:
            print(f"  Found {len(populations)} populations")

        # Load and pool genotype data
        genotype_matrices = []
        individuals_loaded = 0
        
        for pop in populations:
            pop_str = str(pop)
            
            # Extract population number from POP (e.g., "C1.1" -> "1")
            import re
            pop_num_match = re.search(r'C\d+\.(\d+)', pop_str)
            if pop_num_match:
                pop_num = pop_num_match.group(1)
            else:
                pop_num = pop_str
            
            # Find the genomic file for this population
            if pop_num in genomic_files:
                try:
                    geno, parents = load_genomic_file(genomic_files[pop_num])
                    # Genomic file rows are indexed by individual number only
                    # (e.g. "00000000082"), while phenotype LINE_ID is
                    # population-qualified (e.g. "C1.100.82"). Rebuild the
                    # index so it matches LINE_ID for the merge. Most rows are
                    # zero-padded integers and should drop the padding, but a
                    # few populations (e.g. C1.39, C1.126, C1.34) carry
                    # non-numeric suffixes (e.g. "000000029.1", "00000TF%405")
                    # that LINE_ID keeps verbatim, so fall back to the raw
                    # string for those instead of failing the whole file.
                    def _clean_id(idx):
                        try:
                            return str(int(idx))
                        except (ValueError, TypeError):
                            return str(idx)
                    geno.index = [f"{pop_str}.{_clean_id(idx)}" for idx in geno.index]
                    genotype_matrices.append(geno)
                    individuals_loaded += len(geno)
                except Exception as e:
                    print(f"    Warning: Could not load population {pop_str}: {e}")
        
        if genotype_matrices:
            # Concatenate all genotype matrices
            pooled_geno = pd.concat(genotype_matrices, axis=0)
            
            # Filter to only individuals that are in the phenotype data
            # (some individuals might be in genotype but not phenotype)
            pheno_ids = set(pheno_year['LINE_ID'].astype(str))
            geno_ids = set(pooled_geno.index.astype(str))
            common_ids = pheno_ids.intersection(geno_ids)
            
            if common_ids:
                pooled_geno = pooled_geno.loc[list(common_ids)]
                print(f"  Pooled {len(pooled_geno)} individuals with genotype data")
                pooled_by_year[year] = pooled_geno
            else:
                print(f"  Warning: No matching individuals found for year {year}")
        else:
            print(f"  Warning: No genotype data loaded for year {year}")
    
    return pooled_by_year


def process_year(year: int, 
                 genotype_matrix: pd.DataFrame,
                 pheno_year: pd.DataFrame,
                 output_dir: Path) -> Dict:
    """
    Process a single year: filter, impute, and save.
    
    Returns:
        Dictionary with processing statistics
    """
    print(f"\n{'='*60}")
    print(f"Processing Year {year}")
    print(f"{'='*60}")
    
    # Step 1: Filter SNPs
    filtered_geno, filter_report = filter_snps(
        genotype_matrix, 
        maf_threshold=MAF_THRESHOLD,
        na_threshold=NA_THRESHOLD
    )
    
    # Step 2: Impute missing values
    imputed_geno = impute_missing(filtered_geno, method=IMPUTATION_METHOD)
    
    # Step 3: Merge with phenotype data
    # Create a common ID for merging
    imputed_geno['LINE_ID'] = imputed_geno.index.astype(str)
    pheno_year = pheno_year.copy()
    pheno_year['LINE_ID'] = pheno_year['LINE_ID'].astype(str)
    
    # Merge
    merged = pd.merge(
        pheno_year,
        imputed_geno,
        on='LINE_ID',
        how='inner'
    )
    
    print(f"  Merged dataset: {len(merged)} individuals, {len(merged.columns)} columns")
    
    # Step 4: Save outputs
    # Save genotype matrix
    geno_output = output_dir / f"pooled_genotype_{year}.parquet"
    imputed_geno.to_parquet(geno_output)
    print(f"  Saved genotype matrix: {geno_output}")
    
    # Save phenotype data
    pheno_output = output_dir / f"pooled_phenotype_{year}.parquet"
    pheno_year.to_parquet(pheno_output)
    print(f"  Saved phenotype data: {pheno_output}")
    
    # Save merged data
    merged_output = output_dir / f"merged_{year}.parquet"
    merged.to_parquet(merged_output)
    print(f"  Saved merged data: {merged_output}")
    
    # Save filter report
    filter_output = output_dir / f"snp_filter_report_{year}.csv"
    filter_report.to_csv(filter_output, index=False)
    
    # Calculate statistics
    stats = {
        'year': year,
        'n_individuals_original': len(genotype_matrix),
        'n_individuals_filtered': len(imputed_geno),
        'n_snps_original': genotype_matrix.shape[1],
        'n_snps_filtered': filtered_geno.shape[1],
        'n_snps_kept': imputed_geno.shape[1] - 1,  # Subtract LINE_ID column
        'na_before_imputation': int(filtered_geno.isna().sum().sum()),
        'na_after_imputation': int(imputed_geno.isna().sum().sum()),
        'n_populations': len(pheno_year['POP'].unique()),
        'n_merged': len(merged)
    }
    
    return stats


# ============================================================================
# Main Execution
# ============================================================================

def main():
    """Main execution function."""
    print("="*80)
    print("HAPLOTYPE ANALYSIS - PHASE 0: PREPROCESSING")
    print("="*80)
    
    # Step 1: Load phenotype data
    pheno = load_phenotype_data()
    
    # Step 2: Get genomic files
    genomic_files = get_genomic_files()
    
    # Step 3: Pool individuals by year
    pooled_by_year = pool_individuals_by_year(pheno, genomic_files)
    
    # Step 4: Process each year
    all_stats = []
    
    for year, genotype_matrix in pooled_by_year.items():
        pheno_year = pheno[pheno['YEAR'] == year]
        
        stats = process_year(
            year=year,
            genotype_matrix=genotype_matrix,
            pheno_year=pheno_year,
            output_dir=OUTPUT_DIR
        )
        all_stats.append(stats)
    
    # Step 5: Save summary
    summary = {
        'parameters': {
            'maf_threshold': MAF_THRESHOLD,
            'na_threshold': NA_THRESHOLD,
            'imputation_method': IMPUTATION_METHOD,
            'years_processed': list(pooled_by_year.keys())
        },
        'statistics': all_stats
    }
    
    summary_path = OUTPUT_DIR / "preprocessing_summary.json"
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"\nSaved summary: {summary_path}")
    
    # Step 6: Create summary table
    stats_df = pd.DataFrame(all_stats)
    stats_path = OUTPUT_DIR / "preprocessing_statistics.csv"
    stats_df.to_csv(stats_path, index=False)
    print(f"Saved statistics: {stats_path}")
    
    # Print summary
    print("\n" + "="*80)
    print("PREPROCESSING SUMMARY")
    print("="*80)
    print("\nStatistics by Year:")
    print(stats_df.to_string(index=False))
    
    print("\n" + "="*80)
    print("PREPROCESSING COMPLETE")
    print("="*80)
    print(f"\nOutput directory: {OUTPUT_DIR}")
    print("\nNext steps:")
    print("1. Run 01_stability_diagnostic.py to assess SNP effect stability")
    print("2. Run 02_temporal_validation.py for gBLUP analysis")


if __name__ == "__main__":
    main()