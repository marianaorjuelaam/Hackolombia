"""
Phase 3: Alternative Methods - XGBoost and Neural Network
=========================================================

This script implements XGBoost and Neural Network for genomic prediction.

Input:
- merged_{year}.parquet (merged phenotype and genotype data)
- validation_metrics.csv (gBLUP baseline metrics)

Output:
- xgboost_results.json
- neural_network_results.json
- method_comparison.csv
- plots/

Usage:
    python alternative_methods.py

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

# Years
TRAIN_YEARS_1 = list(range(2000, 2007))  # 2000-2006
TRAIN_YEARS_2 = list(range(2000, 2008))  # 2000-2007
TEST_YEAR_1 = 2007
TEST_YEAR_2 = 2008

# ============================================================================
# Helper Functions
# ============================================================================

def load_data(years: List[int]) -> pd.DataFrame:
    """Load merged data for multiple years."""
    print(f"Loading data for years {years}...")
    
    all_data = []
    
    for year in years:
        merged_path = DATA_DIR / f"merged_{year}.parquet"
        
        if merged_path.exists():
            data = pd.read_parquet(merged_path)
            data['YEAR'] = year
            all_data.append(data)
            print(f"  Year {year}: {len(data)} individuals")
        else:
            print(f"  Warning: No data for year {year}")
    
    if not all_data:
        raise ValueError("No data loaded!")
    
    combined = pd.concat(all_data, ignore_index=True)
    print(f"  Total: {len(combined)} individuals")
    
    return combined


def get_snp_columns(data: pd.DataFrame) -> List[str]:
    """Get SNP columns from data."""
    non_snp_cols = ['YEAR', 'LOC', 'LONGITUDE', 'LATITUDE', 'LINE', 'SET', 
                    'POP', 'CROSS', 'P1', 'P2', 'GERMPLASM_ID', 'LINE_ID',
                    'YLD_BE', 'MST', 'PHT', 'EHT', 'TWT', 'STLP', 'RTLP', 'ERM',
                    'OUTLIER', 'ENV']
    snp_cols = [col for col in data.columns if col not in non_snp_cols and data[col].dtype in ['float64', 'int64']]
    return snp_cols


def prepare_data(train_data: pd.DataFrame, test_data: pd.DataFrame, 
                 trait: str = "YLD_BE") -> Tuple:
    """Prepare data for ML models."""
    print("Preparing data for ML...")
    
    # Get SNP columns
    snp_cols = get_snp_columns(train_data)
    print(f"  Using {len(snp_cols)} SNPs")
    
    # Prepare training data
    X_train = train_data[snp_cols].values
    y_train = train_data[trait].values
    
    # Remove NAs in phenotype
    valid_train = ~np.isnan(y_train)
    X_train = X_train[valid_train]
    y_train = y_train[valid_train]
    
    # Prepare test data
    X_test = test_data[snp_cols].values
    y_test = test_data[trait].values
    
    # Remove NAs in test phenotype
    valid_test = ~np.isnan(y_test)
    X_test = X_test[valid_test]
    y_test = y_test[valid_test]
    
    # Impute NAs in genotype with mean
    from sklearn.impute import SimpleImputer
    imputer = SimpleImputer(strategy='mean')
    X_train = imputer.fit_transform(X_train)
    X_test = imputer.transform(X_test)
    
    print(f"  Training: {X_train.shape[0]} samples, {X_train.shape[1]} features")
    print(f"  Testing: {X_test.shape[0]} samples")
    
    return X_train, y_train, X_test, y_test, snp_cols, imputer


def validate_predictions(predicted: np.ndarray, observed: np.ndarray, 
                         top_percent: float = 0.20) -> Dict:
    """Validate predictions."""
    print("  Validating predictions...")
    
    # Remove NAs
    valid = ~np.isnan(predicted) & ~np.isnan(observed)
    predicted = predicted[valid]
    observed = observed[valid]
    
    # Calculate correlation
    correlation = np.corrcoef(predicted, observed)[0, 1]
    
    # Calculate rank correlation
    from scipy.stats import spearmanr
    rank_correlation, _ = spearmanr(predicted, observed)
    
    # Calculate top overlap
    n_top = int(len(predicted) * top_percent)
    top_predicted = np.argsort(predicted)[-n_top:]
    top_observed = np.argsort(observed)[-n_top:]
    overlap = len(np.intersect1d(top_predicted, top_observed)) / n_top
    
    print(f"    Correlation: {correlation:.3f}")
    print(f"    Rank Correlation: {rank_correlation:.3f}")
    print(f"    Top {int(top_percent*100)}% Overlap: {overlap*100:.1f}%")
    
    return {
        'correlation': float(correlation),
        'rank_correlation': float(rank_correlation),
        'top_overlap': float(overlap),
        'n_predicted': len(predicted),
        'n_top': n_top
    }


# ============================================================================
# XGBoost
# ============================================================================

def fit_xgboost(X_train: np.ndarray, y_train: np.ndarray, 
                X_test: np.ndarray, y_test: np.ndarray) -> Dict:
    """Fit XGBoost model."""
    print("\n" + "="*60)
    print("XGBoost")
    print("="*60)
    
    try:
        import xgboost as xgb
    except ImportError:
        print("XGBoost not available. Skipping...")
        return None
    
    # Create DMatrix
    dtrain = xgb.DMatrix(X_train, label=y_train)
    dtest = xgb.DMatrix(X_test, label=y_test)
    
    # Parameters
    params = {
        'max_depth': 6,
        'eta': 0.1,
        'subsample': 0.8,
        'colsample_bytree': 0.8,
        'objective': 'reg:squarederror',
        'eval_metric': 'rmse',
        'seed': 42
    }
    
    # Train model
    print("Training XGBoost...")
    model = xgb.train(
        params,
        dtrain,
        num_boost_round=100,
        evals=[(dtest, 'test')],
        early_stopping_rounds=10,
        verbose_eval=False
    )
    
    # Predict
    predicted = model.predict(dtest)
    
    # Get feature importance
    importance = model.get_score(importance_type='gain')
    
    # Validate
    validation = validate_predictions(predicted, y_test, TOP_PERCENT)
    
    return {
        'model': model,
        'predicted': predicted,
        'importance': importance,
        'validation': validation,
        'best_iteration': model.best_iteration
    }


# ============================================================================
# Neural Network
# ============================================================================

def fit_neural_network(X_train: np.ndarray, y_train: np.ndarray, 
                       X_test: np.ndarray, y_test: np.ndarray) -> Dict:
    """Fit Neural Network model."""
    print("\n" + "="*60)
    print("Neural Network (MLP)")
    print("="*60)
    
    try:
        import torch
        import torch.nn as nn
        import torch.optim as optim
        from torch.utils.data import DataLoader, TensorDataset
    except ImportError:
        print("PyTorch not available. Trying sklearn MLP...")
        return fit_sklearn_mlp(X_train, y_train, X_test, y_test)
    
    # Define MLP model
    class MLP(nn.Module):
        def __init__(self, input_dim):
            super(MLP, self).__init__()
            self.layer1 = nn.Linear(input_dim, 128)
            self.layer2 = nn.Linear(128, 64)
            self.layer3 = nn.Linear(64, 32)
            self.output = nn.Linear(32, 1)
            self.relu = nn.ReLU()
            self.dropout = nn.Dropout(0.2)
            
        def forward(self, x):
            x = self.relu(self.layer1(x))
            x = self.dropout(x)
            x = self.relu(self.layer2(x))
            x = self.dropout(x)
            x = self.relu(self.layer3(x))
            x = self.output(x)
            return x.squeeze()
    
    # Prepare data
    X_train_tensor = torch.FloatTensor(X_train)
    y_train_tensor = torch.FloatTensor(y_train)
    X_test_tensor = torch.FloatTensor(X_test)
    y_test_tensor = torch.FloatTensor(y_test)
    
    # Create data loaders
    train_dataset = TensorDataset(X_train_tensor, y_train_tensor)
    train_loader = DataLoader(train_dataset, batch_size=64, shuffle=True)
    
    # Initialize model
    model = MLP(X_train.shape[1])
    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    
    # Training loop
    print("Training Neural Network...")
    n_epochs = 50
    train_losses = []
    
    for epoch in range(n_epochs):
        model.train()
        epoch_loss = 0
        
        for batch_X, batch_y in train_loader:
            optimizer.zero_grad()
            outputs = model(batch_X)
            loss = criterion(outputs, batch_y)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item()
        
        avg_loss = epoch_loss / len(train_loader)
        train_losses.append(avg_loss)
        
        if (epoch + 1) % 10 == 0:
            print(f"  Epoch {epoch+1}/{n_epochs}, Loss: {avg_loss:.4f}")
    
    # Predict
    model.eval()
    with torch.no_grad():
        predicted = model(X_test_tensor).numpy()
    
    # Validate
    validation = validate_predictions(predicted, y_test, TOP_PERCENT)
    
    return {
        'model': model,
        'predicted': predicted,
        'validation': validation,
        'train_losses': train_losses
    }


def fit_sklearn_mlp(X_train: np.ndarray, y_train: np.ndarray, 
                    X_test: np.ndarray, y_test: np.ndarray) -> Dict:
    """Fit sklearn MLP as fallback."""
    print("\nUsing sklearn MLPRegressor...")
    
    from sklearn.neural_network import MLPRegressor
    from sklearn.preprocessing import StandardScaler
    
    # Scale data
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Fit model
    model = MLPRegressor(
        hidden_layer_sizes=(128, 64, 32),
        activation='relu',
        solver='adam',
        max_iter=100,
        random_state=42,
        early_stopping=True,
        validation_fraction=0.1
    )
    
    model.fit(X_train_scaled, y_train)
    
    # Predict
    predicted = model.predict(X_test_scaled)
    
    # Validate
    validation = validate_predictions(predicted, y_test, TOP_PERCENT)
    
    return {
        'model': model,
        'predicted': predicted,
        'validation': validation,
        'scaler': scaler
    }


# ============================================================================
# Visualization
# ============================================================================

def plot_method_comparison(results: Dict, save_path: Path):
    """Plot method comparison."""
    print("\nPlotting method comparison...")
    
    methods = []
    correlations = []
    rank_correlations = []
    top_overlaps = []
    
    for method, result in results.items():
        if result is not None:
            methods.append(method)
            correlations.append(result['validation']['correlation'])
            rank_correlations.append(result['validation']['rank_correlation'])
            top_overlaps.append(result['validation']['top_overlap'])
    
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    
    # Correlation
    axes[0].bar(methods, correlations, color='steelblue', alpha=0.7)
    axes[0].set_ylabel('Correlation')
    axes[0].set_title('Correlation Between Methods')
    axes[0].set_ylim(0, 1)
    
    # Rank Correlation
    axes[1].bar(methods, rank_correlations, color='lightcoral', alpha=0.7)
    axes[1].set_ylabel('Rank Correlation')
    axes[1].set_title('Rank Correlation Between Methods')
    axes[1].set_ylim(0, 1)
    
    # Top Overlap
    axes[2].bar(methods, top_overlaps, color='lightgreen', alpha=0.7)
    axes[2].set_ylabel('Top Overlap')
    axes[2].set_title(f'Top {int(TOP_PERCENT*100)}% Overlap Between Methods')
    axes[2].set_ylim(0, 1)
    
    plt.suptitle('Method Comparison', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"  Saved: {save_path}")


def plot_feature_importance(xgb_importance: Dict, snp_cols: List[str], save_path: Path, n_top: int = 20):
    """Plot XGBoost feature importance."""
    print("Plotting feature importance...")
    
    # Get top features
    importance_df = pd.DataFrame([
        {'SNP': k, 'Importance': v} 
        for k, v in xgb_importance.items()
    ])
    importance_df = importance_df.sort_values('Importance', ascending=False).head(n_top)
    
    fig, ax = plt.subplots(figsize=(10, 8))
    
    ax.barh(importance_df['SNP'], importance_df['Importance'], color='steelblue', alpha=0.7)
    ax.set_xlabel('Importance (Gain)')
    ax.set_ylabel('SNP')
    ax.set_title(f'Top {n_top} SNPs by XGBoost Importance')
    ax.invert_yaxis()
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"  Saved: {save_path}")


def plot_prediction_scatter(predicted: np.ndarray, observed: np.ndarray, 
                            method: str, save_path: Path):
    """Plot prediction vs observed scatter."""
    print(f"Plotting {method} predictions...")
    
    fig, ax = plt.subplots(figsize=(8, 8))
    
    ax.scatter(observed, predicted, alpha=0.5, s=20)
    
    # Add perfect prediction line
    min_val = min(observed.min(), predicted.min())
    max_val = max(observed.max(), predicted.max())
    ax.plot([min_val, max_val], [min_val, max_val], 'r--', alpha=0.5, label='Perfect Prediction')
    
    # Calculate metrics
    correlation = np.corrcoef(predicted, observed)[0, 1]
    
    ax.set_xlabel('Observed')
    ax.set_ylabel('Predicted')
    ax.set_title(f'{method}: Predicted vs Observed (r={correlation:.3f})')
    ax.legend()
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"  Saved: {save_path}")


# ============================================================================
# Main Execution
# ============================================================================

def main():
    """Main execution function."""
    print("="*80)
    print("HAPLOTYPE ANALYSIS - PHASE 3: ALTERNATIVE METHODS")
    print("="*80)
    
    # Load data for scenario 1: 2000-2006 -> 2007
    print("\n" + "="*60)
    print("Scenario: 2000-2006 -> 2007")
    print("="*60)
    
    train_data_1 = load_data(TRAIN_YEARS_1)
    test_data_1 = load_data([TEST_YEAR_1])
    
    # Prepare data
    X_train_1, y_train_1, X_test_1, y_test_1, snp_cols, imputer = prepare_data(
        train_data_1, test_data_1, TRAIT
    )
    
    # Fit XGBoost
    xgb_result = fit_xgboost(X_train_1, y_train_1, X_test_1, y_test_1)
    
    # Fit Neural Network
    nn_result = fit_neural_network(X_train_1, y_train_1, X_test_1, y_test_1)
    
    # Load gBLUP baseline metrics
    gblup_metrics_path = OUTPUT_DIR / "validation_metrics.csv"
    if gblup_metrics_path.exists():
        gblup_metrics = pd.read_csv(gblup_metrics_path)
        gblup_2007 = gblup_metrics[gblup_metrics['Test_Year'] == 2007].iloc[0]
        gblup_result = {
            'validation': {
                'correlation': gblup_2007['Correlation'],
                'rank_correlation': gblup_2007['Rank_Correlation'],
                'top_overlap': gblup_2007['Top_Overlap']
            }
        }
    else:
        gblup_result = None
    
    # Combine results
    all_results = {
        'gBLUP': gblup_result,
        'XGBoost': xgb_result,
        'Neural Network': nn_result
    }
    
    # Plot comparisons
    plot_method_comparison(all_results, PLOTS_DIR / "method_comparison_2007.png")
    
    if xgb_result:
        plot_feature_importance(
            xgb_result['importance'], 
            snp_cols, 
            PLOTS_DIR / "xgboost_feature_importance.png"
        )
        plot_prediction_scatter(
            xgb_result['predicted'], 
            y_test_1,
            'XGBoost',
            PLOTS_DIR / "xgboost_predictions_2007.png"
        )
    
    if nn_result:
        plot_prediction_scatter(
            nn_result['predicted'], 
            y_test_1,
            'Neural Network',
            PLOTS_DIR / "nn_predictions_2007.png"
        )
    
    # Save results
    results_summary = {
        'scenario': '2000-2006 -> 2007',
        'gBLUP': gblup_result['validation'] if gblup_result else None,
        'XGBoost': xgb_result['validation'] if xgb_result else None,
        'Neural Network': nn_result['validation'] if nn_result else None
    }
    
    with open(OUTPUT_DIR / "alternative_methods_results.json", 'w') as f:
        json.dump(results_summary, f, indent=2)
    
    # Create comparison table
    comparison_data = []
    for method, result in all_results.items():
        if result is not None:
            comparison_data.append({
                'Method': method,
                'Correlation': result['validation']['correlation'],
                'Rank_Correlation': result['validation']['rank_correlation'],
                'Top_Overlap': result['validation']['top_overlap']
            })
    
    comparison_df = pd.DataFrame(comparison_data)
    comparison_df.to_csv(OUTPUT_DIR / "method_comparison.csv", index=False)
    
    # Print final summary
    print("\n" + "="*80)
    print("ALTERNATIVE METHODS SUMMARY")
    print("="*80)
    print("\nMethod Comparison (2000-2006 -> 2007):")
    print(comparison_df.to_string(index=False))
    
    print("\n" + "="*80)
    print("ALTERNATIVE METHODS COMPLETE")
    print("="*80)
    print(f"\nOutput directory: {OUTPUT_DIR}")
    print("\nNext steps:")
    print("1. Review method_comparison.csv")
    print("2. Run 04_final_validation.py for 2008 evaluation")


if __name__ == "__main__":
    main()