"""
Phase 4: Final Validation - 2008 Evaluation
============================================

This script performs the final validation using 2008 data as the test set.

Input:
- merged_{year}.parquet (merged phenotype and genotype data)
- haplotype_favorable.csv (favorable haplotypes from Phase 2)
- snp_effects_2000-2007 to 2008.csv (SNP effects from Phase 2)

Output:
- final_validation_report.html
- final_validation_metrics.json
- haplotype_validation_2008.csv
- plots/

Usage:
    python final_validation.py

Author: Haplotype Analysis Pipeline
Date: 2024
"""

import os
import sys
import json
import numpy as np
import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
# Configuration
# ============================================================================

# Paths
BASE_DIR = Path(__file__).parent.parent.parent.parent.parent  # Go up to Hackolombia
DATA_DIR = BASE_DIR / "DIGITALTOOL" / "data" / "processed" / "haplotype_analysis"
OUTPUT_DIR = BASE_DIR / "DIGITALTOOL" / "data" / "processed" / "haplotype_analysis"
PLOTS_DIR = OUTPUT_DIR / "plots"
PLOTS_DIR.mkdir(parents=True, exist_ok=True)

# Parameters
TRAIT = "YLD_BE"
TOP_PERCENT = 0.20  # Top 20% for haplotype analysis
N_TOP_HAPLOTYPES = 50  # Number of top haplotypes to validate

# ============================================================================
# Helper Functions
# ============================================================================

def load_data(year: int) -> pd.DataFrame:
    """Load merged data for a given year."""
    print(f"Loading data for year {year}...")
    
    merged_path = DATA_DIR / f"merged_{year}.parquet"
    
    if not merged_path.exists():
        raise FileNotFoundError(f"Data file not found: {merged_path}")
    
    data = pd.read_parquet(merged_path)
    print(f"  Loaded {len(data)} individuals")
    
    return data


def get_snp_columns(data: pd.DataFrame) -> List[str]:
    """Get SNP columns from data."""
    non_snp_cols = ['YEAR', 'LOC', 'LONGITUDE', 'LATITUDE', 'LINE', 'SET', 
                    'POP', 'CROSS', 'P1', 'P2', 'GERMPLASM_ID', 'LINE_ID',
                    'YLD_BE', 'MST', 'PHT', 'EHT', 'TWT', 'STLP', 'RTLP', 'ERM',
                    'OUTLIER', 'ENV']
    snp_cols = [col for col in data.columns if col not in non_snp_cols and data[col].dtype in ['float64', 'int64']]
    return snp_cols


def validate_haplotype_persistence(favorable_haplotypes: pd.DataFrame, 
                                   data_2008: pd.DataFrame,
                                   top_percent: float = 0.20) -> Dict:
    """
    Validate if favorable haplotypes from 2000-2007 are present in 2008 top performers.
    """
    print("\nValidating haplotype persistence...")
    
    # Get SNP columns
    snp_cols = get_snp_columns(data_2008)
    
    # Get top performers in 2008
    n_top = int(len(data_2008) * top_percent)
    top_2008_idx = data_2008[TRAIT].nlargest(n_top).index
    
    # Get favorable haplotypes (sorted by effect size)
    top_haplotypes = favorable_haplotypes.nlargest(N_TOP_HAPLOTYPES, 'Effect_Size')
    
    results = []
    
    for _, row in top_haplotypes.iterrows():
        snp = row['SNP']
        favorable_allele = row['Favorable_Allele']
        
        if snp not in snp_cols:
            continue
        
        # Get genotype values for top 2008 performers
        top_2008_genotypes = data_2008.loc[top_2008_idx, snp]
        
        # Calculate frequency of favorable allele in top 2008
        if favorable_allele == 1:
            freq_in_top = (top_2008_genotypes == 1).mean()
        elif favorable_allele == -1:
            freq_in_top = (top_2008_genotypes == -1).mean()
        else:
            freq_in_top = (top_2008_genotypes == 0).mean()
        
        # Calculate frequency in all 2008
        all_2008_genotypes = data_2008[snp]
        if favorable_allele == 1:
            freq_in_all = (all_2008_genotypes == 1).mean()
        elif favorable_allele == -1:
            freq_in_all = (all_2008_genotypes == -1).mean()
        else:
            freq_in_all = (all_2008_genotypes == 0).mean()
        
        # Enrichment: ratio of frequency in top vs all
        enrichment = freq_in_top / freq_in_all if freq_in_all > 0 else 0
        
        results.append({
            'SNP': snp,
            'Favorable_Allele': favorable_allele,
            'Effect_Size_2007': row['Effect_Size'],
            'Freq_In_Top_2008': freq_in_top,
            'Freq_In_All_2008': freq_in_all,
            'Enrichment': enrichment
        })
    
    results_df = pd.DataFrame(results)
    
    # Calculate summary statistics
    mean_enrichment = results_df['Enrichment'].mean()
    prop_enriched = (results_df['Enrichment'] > 1).mean()
    
    print(f"  Mean enrichment in top 2008: {mean_enrichment:.3f}")
    print(f"  Proportion with enrichment > 1: {prop_enriched:.1%}")
    
    return {
        'results': results_df,
        'mean_enrichment': mean_enrichment,
        'prop_enriched': prop_enriched
    }


def validate_predictions_2008(predicted_path: Path, data_2008: pd.DataFrame) -> Dict:
    """Validate predictions for 2008."""
    print("\nValidating 2008 predictions...")
    
    if not predicted_path.exists():
        print(f"  Warning: Predictions file not found: {predicted_path}")
        return None
    
    # Load predictions
    predictions = pd.read_csv(predicted_path)
    
    # Merge with observed data
    merged = pd.merge(
        predictions,
        data_2008[['LINE_ID', TRAIT]],
        on='LINE_ID',
        how='inner',
        suffixes=('_pred', '_obs')
    )
    
    if len(merged) == 0:
        print("  Warning: No matching individuals found")
        return None
    
    # Calculate metrics
    predicted = merged['Predicted'].values
    observed = merged[f'{TRAIT}_obs'].values
    
    # Remove NAs
    valid = ~np.isnan(predicted) & ~np.isnan(observed)
    predicted = predicted[valid]
    observed = observed[valid]
    
    # Correlation
    correlation = np.corrcoef(predicted, observed)[0, 1]
    
    # Rank correlation
    from scipy.stats import spearmanr
    rank_correlation, _ = spearmanr(predicted, observed)
    
    # Top overlap
    n_top = int(len(predicted) * TOP_PERCENT)
    top_predicted = np.argsort(predicted)[-n_top:]
    top_observed = np.argsort(observed)[-n_top:]
    overlap = len(np.intersect1d(top_predicted, top_observed)) / n_top
    
    print(f"  Correlation: {correlation:.3f}")
    print(f"  Rank Correlation: {rank_correlation:.3f}")
    print(f"  Top {int(TOP_PERCENT*100)}% Overlap: {overlap*100:.1f}%")
    
    return {
        'correlation': float(correlation),
        'rank_correlation': float(rank_correlation),
        'top_overlap': float(overlap),
        'n_predicted': len(predicted),
        'n_top': n_top
    }


# ============================================================================
# Visualization
# ============================================================================

def plot_enrichment(results_df: pd.DataFrame, save_path: Path):
    """Plot enrichment of favorable haplotypes in 2008."""
    print("Plotting enrichment...")
    
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    # Distribution of enrichment
    axes[0].hist(results_df['Enrichment'], bins=30, color='steelblue', alpha=0.7, edgecolor='black')
    axes[0].axvline(x=1, color='red', linestyle='--', alpha=0.5, label='No enrichment')
    axes[0].set_xlabel('Enrichment')
    axes[0].set_ylabel('Frequency')
    axes[0].set_title('Distribution of Haplotype Enrichment in 2008 Top')
    axes[0].legend()
    
    # Enrichment vs effect size
    axes[1].scatter(results_df['Effect_Size_2007'], results_df['Enrichment'], 
                    alpha=0.5, color='steelblue')
    axes[1].axhline(y=1, color='red', linestyle='--', alpha=0.5)
    axes[1].set_xlabel('Effect Size (2007)')
    axes[1].set_ylabel('Enrichment in 2008 Top')
    axes[1].set_title('Enrichment vs Effect Size')
    
    plt.suptitle('Haplotype Persistence: 2007 -> 2008', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"  Saved: {save_path}")


def plot_top_haplotypes_comparison(results_df: pd.DataFrame, save_path: Path, n_top: int = 20):
    """Plot comparison of top haplotypes."""
    print("Plotting top haplotypes comparison...")
    
    # Get top haplotypes by enrichment
    top_haplotypes = results_df.nlargest(n_top, 'Enrichment')
    
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Create bar plot
    x = np.arange(len(top_haplotypes))
    width = 0.35
    
    ax.bar(x - width/2, top_haplotypes['Freq_In_Top_2008'], width, 
           label='Freq in Top 2008', color='steelblue', alpha=0.7)
    ax.bar(x + width/2, top_haplotypes['Freq_In_All_2008'], width,
           label='Freq in All 2008', color='lightcoral', alpha=0.7)
    
    ax.set_xlabel('SNP')
    ax.set_ylabel('Frequency')
    ax.set_title(f'Top {n_top} Haplotypes: Frequency in Top vs All 2008')
    ax.set_xticks(x)
    ax.set_xticklabels(top_haplotypes['SNP'], rotation=45, ha='right')
    ax.legend()
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"  Saved: {save_path}")


def generate_final_report(haplotype_validation: Dict, 
                          prediction_validation: Dict,
                          save_path: Path):
    """Generate final HTML report."""
    print("Generating final report...")
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Final Validation Report - 2008</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            h1 {{ color: #2c3e50; }}
            h2 {{ color: #34495e; }}
            .metric {{ background-color: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 5px; }}
            .metric-value {{ font-size: 24px; font-weight: bold; color: #2c3e50; }}
            .metric-label {{ font-size: 14px; color: #7f8c8d; }}
            .success {{ color: #27ae60; }}
            .warning {{ color: #f39c12; }}
            .failure {{ color: #e74c3c; }}
            table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #34495e; color: white; }}
            tr:nth-child(even) {{ background-color: #f2f2f2; }}
            .plot {{ text-align: center; margin: 20px 0; }}
            .plot img {{ max-width: 100%; height: auto; }}
            .conclusion {{ background-color: #e8f5e9; padding: 20px; margin: 20px 0; border-radius: 5px; border-left: 5px solid #27ae60; }}
        </style>
    </head>
    <body>
        <h1>Final Validation Report - 2008</h1>
        
        <h2>Executive Summary</h2>
        <p>
            This report presents the final validation of the haplotype-based genomic prediction approach.
            The model was trained on years 2000-2007 and evaluated on 2008 data.
        </p>
        
        <h2>Haplotype Persistence Validation</h2>
        <div class="metric">
            <div class="metric-label">Mean Enrichment in 2008 Top Performers</div>
            <div class="metric-value {'success' if haplotype_validation['mean_enrichment'] > 1.1 else 'warning' if haplotype_validation['mean_enrichment'] > 1 else 'failure'}">
                {haplotype_validation['mean_enrichment']:.3f}
            </div>
            <p>Values > 1 indicate favorable haplotypes are enriched in top performers</p>
        </div>
        
        <div class="metric">
            <div class="metric-label">Proportion of Haplotypes with Enrichment > 1</div>
            <div class="metric-value {'success' if haplotype_validation['prop_enriched'] > 0.6 else 'warning' if haplotype_validation['prop_enriched'] > 0.5 else 'failure'}">
                {haplotype_validation['prop_enriched']:.1%}
            </div>
            <p>Proportion of favorable haplotypes that are more frequent in top performers</p>
        </div>
    """
    
    if prediction_validation:
        html_content += f"""
        <h2>Prediction Validation</h2>
        <div class="metric">
            <div class="metric-label">Correlation (Predicted vs Observed)</div>
            <div class="metric-value {'success' if prediction_validation['correlation'] > 0.5 else 'warning' if prediction_validation['correlation'] > 0.3 else 'failure'}">
                {prediction_validation['correlation']:.3f}
            </div>
        </div>
        
        <div class="metric">
            <div class="metric-label">Rank Correlation</div>
            <div class="metric-value {'success' if prediction_validation['rank_correlation'] > 0.5 else 'warning' if prediction_validation['rank_correlation'] > 0.3 else 'failure'}">
                {prediction_validation['rank_correlation']:.3f}
            </div>
        </div>
        
        <div class="metric">
            <div class="metric-label">Top {int(TOP_PERCENT*100)}% Overlap</div>
            <div class="metric-value {'success' if prediction_validation['top_overlap'] > 0.3 else 'warning' if prediction_validation['top_overlap'] > 0.2 else 'failure'}">
                {prediction_validation['top_overlap']:.1%}
            </div>
            <p>Proportion of predicted top individuals that are also in observed top</p>
        </div>
        """
    
    html_content += f"""
        <h2>Top Haplotypes</h2>
        <p>The following table shows the top haplotypes with highest enrichment in 2008:</p>
        <table>
            <tr>
                <th>SNP</th>
                <th>Favorable Allele</th>
                <th>Effect Size (2007)</th>
                <th>Freq in Top 2008</th>
                <th>Freq in All 2008</th>
                <th>Enrichment</th>
            </tr>
    """
    
    top_haplotypes = haplotype_validation['results'].nlargest(10, 'Enrichment')
    for _, row in top_haplotypes.iterrows():
        html_content += f"""
            <tr>
                <td>{row['SNP']}</td>
                <td>{row['Favorable_Allele']}</td>
                <td>{row['Effect_Size_2007']:.3f}</td>
                <td>{row['Freq_In_Top_2008']:.3f}</td>
                <td>{row['Freq_In_All_2008']:.3f}</td>
                <td>{row['Enrichment']:.3f}</td>
            </tr>
        """
    
    html_content += """
        </table>
        
        <h2>Plots</h2>
        <div class="plot">
            <h3>Haplotype Enrichment</h3>
            <img src="plots/haplotype_enrichment_2008.png" alt="Haplotype Enrichment">
        </div>
        
        <div class="plot">
            <h3>Top Haplotypes Comparison</h3>
            <img src="plots/top_haplotypes_2008.png" alt="Top Haplotypes Comparison">
        </div>
        
        <h2>Conclusions</h2>
        <div class="conclusion">
    """
    
    if haplotype_validation['mean_enrichment'] > 1.1 and haplotype_validation['prop_enriched'] > 0.6:
        html_content += """
            <p><strong>Strong Support:</strong> The favorable haplotypes identified in 2000-2007 
            are significantly enriched in 2008 top performers. This validates the haplotype-based 
            approach for genomic prediction.</p>
        """
    elif haplotype_validation['mean_enrichment'] > 1 and haplotype_validation['prop_enriched'] > 0.5:
        html_content += """
            <p><strong>Moderate Support:</strong> There is moderate evidence that favorable haplotypes 
            persist across years. The approach shows promise but may need refinement.</p>
        """
    else:
        html_content += """
            <p><strong>Limited Support:</strong> The favorable haplotypes from 2000-2007 
            do not strongly persist in 2008. This may be due to environmental differences, 
            G×E interactions, or other factors.</p>
        """
    
    html_content += """
        </div>
        
        <h2>Recommendations</h2>
        <ol>
            <li>Use the identified favorable haplotypes as a guide for selection decisions</li>
            <li>Consider environmental factors when interpreting results</li>
            <li>Validate with additional years if available</li>
            <li>Integrate with other selection criteria (GCA, SCA, etc.)</li>
        </ol>
    </body>
    </html>
    """
    
    with open(save_path, 'w') as f:
        f.write(html_content)
    
    print(f"  Saved: {save_path}")


# ============================================================================
# Main Execution
# ============================================================================

def main():
    """Main execution function."""
    print("="*80)
    print("HAPLOTYPE ANALYSIS - PHASE 4: FINAL VALIDATION (2008)")
    print("="*80)
    
    # Load 2008 data
    data_2008 = load_data(2008)
    
    # Load favorable haplotypes
    favorable_path = OUTPUT_DIR / "haplotype_favorable.csv"
    if not favorable_path.exists():
        print(f"Error: Favorable haplotypes file not found: {favorable_path}")
        print("Please run 02_temporal_validation.R first.")
        return
    
    favorable_haplotypes = pd.read_csv(favorable_path)
    print(f"\nLoaded {len(favorable_haplotypes)} favorable haplotypes")
    
    # Validate haplotype persistence
    haplotype_validation = validate_haplotype_persistence(
        favorable_haplotypes, 
        data_2008, 
        TOP_PERCENT
    )
    
    # Save haplotype validation results
    haplotype_validation['results'].to_csv(
        OUTPUT_DIR / "haplotype_validation_2008.csv", 
        index=False
    )
    
    # Validate predictions
    predicted_path = OUTPUT_DIR / "predicted_blups_2008.csv"
    prediction_validation = validate_predictions_2008(predicted_path, data_2008)
    
    # Generate plots
    plot_enrichment(
        haplotype_validation['results'], 
        PLOTS_DIR / "haplotype_enrichment_2008.png"
    )
    plot_top_haplotypes_comparison(
        haplotype_validation['results'], 
        PLOTS_DIR / "top_haplotypes_2008.png"
    )
    
    # Generate final report
    generate_final_report(
        haplotype_validation, 
        prediction_validation, 
        OUTPUT_DIR / "final_validation_report.html"
    )
    
    # Save summary
    summary = {
        'parameters': {
            'trait': TRAIT,
            'top_percent': TOP_PERCENT,
            'n_top_haplotypes': N_TOP_HAPLOTYPES
        },
        'haplotype_validation': {
            'mean_enrichment': haplotype_validation['mean_enrichment'],
            'prop_enriched': haplotype_validation['prop_enriched']
        },
        'prediction_validation': prediction_validation
    }
    
    with open(OUTPUT_DIR / "final_validation_metrics.json", 'w') as f:
        json.dump(summary, f, indent=2)
    
    # Print final summary
    print("\n" + "="*80)
    print("FINAL VALIDATION SUMMARY")
    print("="*80)
    
    print(f"\nHaplotype Persistence:")
    print(f"  Mean Enrichment: {haplotype_validation['mean_enrichment']:.3f}")
    print(f"  Proportion Enriched: {haplotype_validation['prop_enriched']:.1%}")
    
    if prediction_validation:
        print(f"\nPrediction Validation:")
        print(f"  Correlation: {prediction_validation['correlation']:.3f}")
        print(f"  Rank Correlation: {prediction_validation['rank_correlation']:.3f}")
        print(f"  Top {int(TOP_PERCENT*100)}% Overlap: {prediction_validation['top_overlap']:.1%}")
    
    print("\n" + "="*80)
    print("FINAL VALIDATION COMPLETE")
    print("="*80)
    print(f"\nOutput directory: {OUTPUT_DIR}")
    print(f"Report: {OUTPUT_DIR / 'final_validation_report.html'}")
    print("\nKey files:")
    print("  - haplotype_validation_2008.csv")
    print("  - final_validation_metrics.json")
    print("  - final_validation_report.html")


if __name__ == "__main__":
    main()