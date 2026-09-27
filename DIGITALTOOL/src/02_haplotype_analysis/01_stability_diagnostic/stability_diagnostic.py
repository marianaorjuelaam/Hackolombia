"""
Phase 1: Stability Diagnostic - Correlation Analysis
=====================================================

This script analyzes the correlation of SNP effects across years
to determine the stability of genetic effects.

Input:
- snp_effects_matrix.csv (SNP effects per year)
- snp_effects_correlation_matrix.csv (correlation matrix)

Output:
- stability_report.html (visual report)
- stability_metrics.json (quantitative metrics)
- plots/ (individual plots)

Usage:
    python stability_diagnostic.py

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
OUTPUT_DIR = BASE_DIR / "DIGITALTOOL" / "data" / "processed" / "haplotype_analysis" / "plots"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Parameters
YEARS = list(range(2000, 2008))  # 2000-2007

# ============================================================================
# Helper Functions
# ============================================================================

def load_snp_effects() -> pd.DataFrame:
    """Load SNP effects matrix."""
    print("Loading SNP effects matrix...")
    
    effects_path = DATA_DIR / "snp_effects_matrix.csv"
    if not effects_path.exists():
        raise FileNotFoundError(f"SNP effects file not found: {effects_path}")
    
    effects = pd.read_csv(effects_path, index_col=0)
    print(f"  Loaded {effects.shape[0]} SNPs x {effects.shape[1]} years")
    
    return effects


def load_correlation_matrix() -> pd.DataFrame:
    """Load correlation matrix."""
    print("Loading correlation matrix...")
    
    cor_path = DATA_DIR / "snp_effects_correlation_matrix.csv"
    if not cor_path.exists():
        raise FileNotFoundError(f"Correlation matrix not found: {cor_path}")
    
    cor_matrix = pd.read_csv(cor_path, index_col=0)
    print(f"  Loaded {cor_matrix.shape[0]}x{cor_matrix.shape[1]} correlation matrix")
    
    return cor_matrix


def calculate_stability_metrics(cor_matrix: pd.DataFrame) -> Dict:
    """Calculate stability metrics from correlation matrix."""
    print("\nCalculating stability metrics...")
    
    # Get upper triangle (excluding diagonal)
    upper_tri = cor_matrix.values[np.triu_indices_from(cor_matrix.values, k=1)]
    
    # Calculate metrics
    metrics = {
        'mean_correlation': float(np.nanmean(upper_tri)),
        'median_correlation': float(np.nanmedian(upper_tri)),
        'std_correlation': float(np.nanstd(upper_tri)),
        'min_correlation': float(np.nanmin(upper_tri)),
        'max_correlation': float(np.nanmax(upper_tri)),
        'prop_positive': float(np.nanmean(upper_tri > 0)),
        'prop_above_0.3': float(np.nanmean(upper_tri > 0.3)),
        'prop_above_0.5': float(np.nanmean(upper_tri > 0.5)),
    }
    
    # Calculate consecutive year correlations
    consecutive_corrs = []
    for i in range(len(cor_matrix.columns) - 1):
        year1 = cor_matrix.columns[i]
        year2 = cor_matrix.columns[i + 1]
        corr = cor_matrix.loc[year1, year2]
        consecutive_corrs.append({
            'year1': int(year1),
            'year2': int(year2),
            'correlation': float(corr)
        })
    
    metrics['consecutive_correlations'] = consecutive_corrs
    
    # Determine stability category
    mean_corr = metrics['mean_correlation']
    if mean_corr > 0.5:
        stability_category = "HIGH"
        recommendation = "Use cumulative pooling (all years)"
    elif mean_corr > 0.3:
        stability_category = "MEDIUM"
        recommendation = "Use weighted pooling (more weight to recent years)"
    else:
        stability_category = "LOW"
        recommendation = "Use rolling window (last 3-4 years)"
    
    metrics['stability_category'] = stability_category
    metrics['recommendation'] = recommendation
    
    return metrics


def plot_correlation_heatmap(cor_matrix: pd.DataFrame, save_path: Path):
    """Plot correlation heatmap."""
    print("Plotting correlation heatmap...")
    
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # Create heatmap
    sns.heatmap(
        cor_matrix,
        annot=True,
        fmt='.3f',
        cmap='RdYlBu_r',
        center=0,
        vmin=-1,
        vmax=1,
        square=True,
        ax=ax
    )
    
    ax.set_title('SNP Effect Correlation Between Years', fontsize=14, fontweight='bold')
    ax.set_xlabel('Year', fontsize=12)
    ax.set_ylabel('Year', fontsize=12)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"  Saved: {save_path}")


def plot_consecutive_correlations(metrics: Dict, save_path: Path):
    """Plot consecutive year correlations."""
    print("Plotting consecutive year correlations...")
    
    consecutive = metrics['consecutive_correlations']
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    years = [f"{c['year1']}-{c['year2']}" for c in consecutive]
    corrs = [c['correlation'] for c in consecutive]
    
    bars = ax.bar(years, corrs, color='steelblue', alpha=0.7)
    
    # Add value labels
    for bar, corr in zip(bars, corrs):
        ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.01,
                f'{corr:.3f}', ha='center', va='bottom', fontsize=10)
    
    ax.axhline(y=0.5, color='green', linestyle='--', alpha=0.5, label='High stability (0.5)')
    ax.axhline(y=0.3, color='orange', linestyle='--', alpha=0.5, label='Medium stability (0.3)')
    
    ax.set_xlabel('Year Pair', fontsize=12)
    ax.set_ylabel('Correlation', fontsize=12)
    ax.set_title('SNP Effect Correlation Between Consecutive Years', fontsize=14, fontweight='bold')
    ax.legend()
    ax.set_ylim(0, 1)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"  Saved: {save_path}")


def plot_snp_effects_distribution(effects: pd.DataFrame, save_path: Path):
    """Plot distribution of SNP effects across years."""
    print("Plotting SNP effects distribution...")
    
    fig, axes = plt.subplots(2, 4, figsize=(16, 8))
    axes = axes.flatten()
    
    for idx, year in enumerate(effects.columns):
        ax = axes[idx]
        year_effects = effects[year].dropna()
        
        ax.hist(year_effects, bins=50, color='steelblue', alpha=0.7, edgecolor='black')
        ax.axvline(x=0, color='red', linestyle='--', alpha=0.5)
        ax.set_title(f'Year {year}', fontsize=12)
        ax.set_xlabel('SNP Effect', fontsize=10)
        ax.set_ylabel('Frequency', fontsize=10)
    
    plt.suptitle('Distribution of SNP Effects by Year', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"  Saved: {save_path}")


def plot_top_snps_stability(effects: pd.DataFrame, save_path: Path, n_top: int = 20):
    """Plot stability of top SNPs across years."""
    print(f"Plotting top {n_top} SNPs stability...")
    
    # Calculate mean absolute effect for each SNP
    mean_abs_effects = effects.abs().mean(axis=1)
    top_snps = mean_abs_effects.nlargest(n_top).index
    
    # Get effects for top SNPs
    top_effects = effects.loc[top_snps]
    
    fig, ax = plt.subplots(figsize=(14, 8))
    
    for snp in top_snps:
        snp_effects = top_effects.loc[snp].values
        ax.plot(effects.columns, snp_effects, marker='o', label=snp, alpha=0.7)
    
    ax.axhline(y=0, color='black', linestyle='-', alpha=0.3)
    ax.set_xlabel('Year', fontsize=12)
    ax.set_ylabel('SNP Effect', fontsize=12)
    ax.set_title(f'Top {n_top} SNPs: Effect Stability Across Years', fontsize=14, fontweight='bold')
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=8)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"  Saved: {save_path}")


def generate_stability_report(metrics: Dict, save_path: Path):
    """Generate HTML stability report."""
    print("Generating stability report...")
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>SNP Effect Stability Diagnostic</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            h1 {{ color: #2c3e50; }}
            h2 {{ color: #34495e; }}
            .metric {{ background-color: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 5px; }}
            .metric-value {{ font-size: 24px; font-weight: bold; color: #2c3e50; }}
            .metric-label {{ font-size: 14px; color: #7f8c8d; }}
            .stability-high {{ color: #27ae60; }}
            .stability-medium {{ color: #f39c12; }}
            .stability-low {{ color: #e74c3c; }}
            .recommendation {{ background-color: #e8f5e9; padding: 20px; margin: 20px 0; border-radius: 5px; border-left: 5px solid #27ae60; }}
            table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #34495e; color: white; }}
            tr:nth-child(even) {{ background-color: #f2f2f2; }}
            .plot {{ text-align: center; margin: 20px 0; }}
            .plot img {{ max-width: 100%; height: auto; }}
        </style>
    </head>
    <body>
        <h1>SNP Effect Stability Diagnostic Report</h1>
        
        <h2>Summary</h2>
        <div class="metric">
            <div class="metric-label">Stability Category</div>
            <div class="metric-value stability-{metrics['stability_category'].lower()}">{metrics['stability_category']}</div>
        </div>
        
        <div class="metric">
            <div class="metric-label">Mean Correlation Between Years</div>
            <div class="metric-value">{metrics['mean_correlation']:.3f}</div>
        </div>
        
        <div class="metric">
            <div class="metric-label">Median Correlation Between Years</div>
            <div class="metric-value">{metrics['median_correlation']:.3f}</div>
        </div>
        
        <h2>Recommendation</h2>
        <div class="recommendation">
            <p><strong>{metrics['recommendation']}</strong></p>
            <p>Based on the analysis of SNP effect correlations across years.</p>
        </div>
        
        <h2>Detailed Metrics</h2>
        <table>
            <tr>
                <th>Metric</th>
                <th>Value</th>
            </tr>
            <tr>
                <td>Mean Correlation</td>
                <td>{metrics['mean_correlation']:.3f}</td>
            </tr>
            <tr>
                <td>Median Correlation</td>
                <td>{metrics['median_correlation']:.3f}</td>
            </tr>
            <tr>
                <td>Std Correlation</td>
                <td>{metrics['std_correlation']:.3f}</td>
            </tr>
            <tr>
                <td>Min Correlation</td>
                <td>{metrics['min_correlation']:.3f}</td>
            </tr>
            <tr>
                <td>Max Correlation</td>
                <td>{metrics['max_correlation']:.3f}</td>
            </tr>
            <tr>
                <td>Proportion Positive</td>
                <td>{metrics['prop_positive']:.1%}</td>
            </tr>
            <tr>
                <td>Proportion > 0.3</td>
                <td>{metrics['prop_above_0.3']:.1%}</td>
            </tr>
            <tr>
                <td>Proportion > 0.5</td>
                <td>{metrics['prop_above_0.5']:.1%}</td>
            </tr>
        </table>
        
        <h2>Consecutive Year Correlations</h2>
        <table>
            <tr>
                <th>Year Pair</th>
                <th>Correlation</th>
            </tr>
    """
    
    for corr in metrics['consecutive_correlations']:
        html_content += f"""
            <tr>
                <td>{corr['year1']}-{corr['year2']}</td>
                <td>{corr['correlation']:.3f}</td>
            </tr>
        """
    
    html_content += """
        </table>
        
        <h2>Plots</h2>
        <div class="plot">
            <h3>Correlation Heatmap</h3>
            <img src="plots/correlation_heatmap.png" alt="Correlation Heatmap">
        </div>
        
        <div class="plot">
            <h3>Consecutive Year Correlations</h3>
            <img src="plots/consecutive_correlations.png" alt="Consecutive Year Correlations">
        </div>
        
        <div class="plot">
            <h3>SNP Effects Distribution</h3>
            <img src="plots/snp_effects_distribution.png" alt="SNP Effects Distribution">
        </div>
        
        <div class="plot">
            <h3>Top SNPs Stability</h3>
            <img src="plots/top_snps_stability.png" alt="Top SNPs Stability">
        </div>
        
        <h2>Interpretation</h2>
        <p>
            <strong>High stability (correlation > 0.5):</strong> SNP effects are consistent across years. 
            Cumulative pooling (using all years) is recommended to maximize statistical power.
        </p>
        <p>
            <strong>Medium stability (0.3 < correlation < 0.5):</strong> SNP effects show moderate consistency. 
            Weighted pooling (more weight to recent years) may be appropriate.
        </p>
        <p>
            <strong>Low stability (correlation < 0.3):</strong> SNP effects vary significantly across years. 
            Rolling window (using only recent years) is recommended.
        </p>
        
        <h2>Next Steps</h2>
        <ol>
            <li>If stability is HIGH: Run <code>02_temporal_validation.py</code> with cumulative pooling</li>
            <li>If stability is MEDIUM: Run <code>02_temporal_validation.py</code> with weighted pooling</li>
            <li>If stability is LOW: Run <code>02_temporal_validation.py</code> with rolling window</li>
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
    print("HAPLOTYPE ANALYSIS - PHASE 1: STABILITY DIAGNOSTIC")
    print("="*80)
    
    # Load data
    effects = load_snp_effects()
    cor_matrix = load_correlation_matrix()
    
    # Calculate metrics
    metrics = calculate_stability_metrics(cor_matrix)
    
    # Save metrics
    metrics_path = DATA_DIR / "stability_metrics.json"
    with open(metrics_path, 'w') as f:
        json.dump(metrics, f, indent=2)
    print(f"\nSaved metrics: {metrics_path}")
    
    # Generate plots
    plot_correlation_heatmap(cor_matrix, OUTPUT_DIR / "correlation_heatmap.png")
    plot_consecutive_correlations(metrics, OUTPUT_DIR / "consecutive_correlations.png")
    plot_snp_effects_distribution(effects, OUTPUT_DIR / "snp_effects_distribution.png")
    plot_top_snps_stability(effects, OUTPUT_DIR / "top_snps_stability.png")
    
    # Generate report
    report_path = DATA_DIR / "stability_report.html"
    generate_stability_report(metrics, report_path)
    
    # Print summary
    print("\n" + "="*80)
    print("STABILITY DIAGNOSTIC SUMMARY")
    print("="*80)
    print(f"\nStability Category: {metrics['stability_category']}")
    print(f"Mean Correlation: {metrics['mean_correlation']:.3f}")
    print(f"Recommendation: {metrics['recommendation']}")
    
    print("\n" + "="*80)
    print("STABILITY DIAGNOSTIC COMPLETE")
    print("="*80)
    print(f"\nOutput directory: {OUTPUT_DIR}")
    print(f"Report: {report_path}")
    print("\nNext steps:")
    print("1. Review stability_report.html")
    print("2. Run 02_temporal_validation.py based on stability category")


if __name__ == "__main__":
    main()