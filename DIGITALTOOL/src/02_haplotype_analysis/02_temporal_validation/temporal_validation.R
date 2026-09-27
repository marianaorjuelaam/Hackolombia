#' Phase 2: Temporal Validation - Cumulative gBLUP
#' ================================================
#'
#' This script performs temporal validation using cumulative training.
#'
#' Strategy:
#' - Train on years 2000-2006, predict 2007
#' - Train on years 2000-2007, predict 2008
#'
#' Input:
#' - merged_{year}.parquet (merged phenotype and genotype data)
#' - stability_metrics.json (stability category)
#'
#' Output:
#' - temporal_validation_results.json
#' - predicted_blups_{year}.csv
#' - haplotype_favorable.csv
#' - validation_metrics.csv
#'
#' Usage:
#'     Rscript temporal_validation.R
#'
#' Requirements:
#'     - R packages: arrow, data.table, jsonlite, rrBLUP

# ============================================================================
# Configuration
# ============================================================================

# Load libraries
library(arrow)
library(data.table)
library(jsonlite)

# Try to load rrBLUP
if (requireNamespace("rrBLUP", quietly = TRUE)) {
    library(rrBLUP)
} else {
    stop("rrBLUP package not available. Please install it.")
}

# Paths
# Detect script location
args <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args, value = TRUE)
if (length(file_arg) > 0) {
    SCRIPT_DIR <- normalizePath(dirname(sub("^--file=", "", file_arg)))
} else {
    SCRIPT_DIR <- getwd()
}
BASE_DIR <- normalizePath(file.path(SCRIPT_DIR, "../../../../.."))
DATA_DIR <- file.path(BASE_DIR, "DIGITALTOOL", "data", "processed", "haplotype_analysis")
OUTPUT_DIR <- file.path(BASE_DIR, "DIGITALTOOL", "data", "processed", "haplotype_analysis")

# Create output directory if it doesn't exist
dir.create(OUTPUT_DIR, showWarnings = FALSE, recursive = TRUE)

# Parameters
TRAIT <- "YLD_BE"
TOP_PERCENT <- 0.20  # Top 20% for haplotype analysis

# ============================================================================
# Helper Functions
# ============================================================================

#' Load merged data for multiple years
load_merged_data <- function(years) {
    cat(sprintf("Loading data for years %s...\n", paste(years, collapse = ", ")))
    
    all_data <- list()
    
    for (year in years) {
        merged_path <- file.path(DATA_DIR, sprintf("merged_%d.parquet", year))
        
        if (file.exists(merged_path)) {
            data <- as.data.frame(read_parquet(merged_path))
            data$YEAR <- year
            all_data[[as.character(year)]] <- data
            cat(sprintf("  Year %d: %d individuals\n", year, nrow(data)))
        } else {
            cat(sprintf("  Warning: No data for year %d\n", year))
        }
    }
    
    if (length(all_data) == 0) {
        stop("No data loaded!")
    }
    
    # Combine all data
    combined <- rbindlist(all_data, fill = TRUE)
    cat(sprintf("  Total: %d individuals\n", nrow(combined)))
    
    return(combined)
}


#' Get SNP columns from data
get_snp_columns <- function(data) {
    non_snp_cols <- c("YEAR", "LOC", "LONGITUDE", "LATITUDE", "LINE", "SET", 
                      "POP", "CROSS", "P1", "P2", "GERMPLASM_ID", "LINE_ID",
                      "YLD_BE", "MST", "PHT", "EHT", "TWT", "STLP", "RTLP", "ERM",
                      "OUTLIER", "ENV")
    snp_cols <- setdiff(names(data), non_snp_cols)
    snp_cols <- snp_cols[sapply(data[snp_cols], is.numeric)]
    return(snp_cols)
}


#' Fit gBLUP and predict
fit_gblup_predict <- function(train_data, test_data, trait = "YLD_BE") {
    cat("  Fitting gBLUP...\n")
    
    # Get SNP columns
    snp_cols <- get_snp_columns(train_data)
    cat(sprintf("    Using %d SNPs\n", length(snp_cols)))
    
    # Prepare training data
    Z_train <- as.matrix(train_data[snp_cols])
    y_train <- train_data[[trait]]
    
    # Remove NAs in phenotype
    valid_train <- !is.na(y_train)
    Z_train <- Z_train[valid_train, ]
    y_train <- y_train[valid_train]
    
    # Center and scale
    Z_train_scaled <- scale(Z_train, center = TRUE, scale = TRUE)
    
    # Fit model
    fit <- mixed.solve(y = y_train, Z = Z_train_scaled, K = NULL, SE = FALSE, return.Hinv = FALSE)
    
    # Extract SNP effects
    snp_effects <- as.numeric(fit$u)
    names(snp_effects) <- snp_cols
    
    # Predict for test data
    Z_test <- as.matrix(test_data[snp_cols])
    Z_test_scaled <- scale(Z_test, center = attr(Z_train_scaled, "scaled:center"), 
                           scale = attr(Z_train_scaled, "scaled:scale"))
    
    # Calculate predicted genetic values
    predicted <- as.numeric(Z_test_scaled %*% snp_effects)
    
    # Calculate variance components
    sigma2_u <- fit$Vu
    sigma2_e <- fit$Ve
    h2 <- sigma2_u / (sigma2_u + sigma2_e)
    
    cat(sprintf("    Heritability: %.3f\n", h2))
    
    return(list(
        snp_effects = snp_effects,
        predicted = predicted,
        sigma2_u = sigma2_u,
        sigma2_e = sigma2_e,
        h2 = h2,
        test_ids = test_data$LINE_ID
    ))
}


#' Identify favorable haplotypes
identify_favorable_haplotypes <- function(snp_effects, data, trait = "YLD_BE", 
                                          top_percent = 0.20) {
    cat("  Identifying favorable haplotypes...\n")
    
    # Get SNP columns
    snp_cols <- get_snp_columns(data)
    
    # Calculate predicted values
    Z <- as.matrix(data[snp_cols])
    predicted <- as.numeric(Z %*% snp_effects[names(snp_cols)])
    
    # Identify top individuals
    n_top <- ceiling(nrow(data) * top_percent)
    top_idx <- order(predicted, decreasing = TRUE)[1:n_top]
    bottom_idx <- order(predicted, decreasing = FALSE)[1:n_top]
    
    # Calculate allele frequencies in top vs bottom
    favorable <- list()
    
    for (snp in snp_cols) {
        # Get genotype values
        snp_data <- data[[snp]]
        
        # Calculate frequencies in top and bottom
        top_freq <- mean(snp_data[top_idx], na.rm = TRUE)
        bottom_freq <- mean(snp_data[bottom_idx], na.rm = TRUE)
        
        # Determine favorable allele
        # If top has higher frequency of 1, then 1 is favorable
        # If top has higher frequency of -1, then -1 is favorable
        if (top_freq > bottom_freq) {
            favorable_allele <- 1
            effect_size <- top_freq - bottom_freq
        } else if (top_freq < bottom_freq) {
            favorable_allele <- -1
            effect_size <- bottom_freq - top_freq
        } else {
            favorable_allele <- 0
            effect_size <- 0
        }
        
        favorable[[snp]] <- data.frame(
            SNP = snp,
            Favorable_Allele = favorable_allele,
            Effect_Size = effect_size,
            Top_Freq = top_freq,
            Bottom_Freq = bottom_freq,
            SNP_Effect = snp_effects[snp]
        )
    }
    
    favorable_df <- rbindlist(favorable)
    favorable_df <- favorable_df[order(-abs(favorable_df$Effect_Size)), ]
    
    return(favorable_df)
}


#' Validate predictions
validate_predictions <- function(predicted, observed, line_ids) {
    cat("  Validating predictions...\n")
    
    # Remove NAs
    valid <- !is.na(predicted) & !is.na(observed)
    predicted <- predicted[valid]
    observed <- observed[valid]
    line_ids <- line_ids[valid]
    
    # Calculate correlation
    correlation <- cor(predicted, observed)
    
    # Calculate rank correlation
    rank_correlation <- cor(predicted, observed, method = "spearman")
    
    # Calculate top overlap
    n_top <- ceiling(length(predicted) * TOP_PERCENT)
    top_predicted <- order(predicted, decreasing = TRUE)[1:n_top]
    top_observed <- order(observed, decreasing = TRUE)[1:n_top]
    overlap <- length(intersect(top_predicted, top_observed)) / n_top
    
    cat(sprintf("    Correlation: %.3f\n", correlation))
    cat(sprintf("    Rank Correlation: %.3f\n", rank_correlation))
    cat(sprintf("    Top %d%% Overlap: %.1f%%\n", TOP_PERCENT * 100, overlap * 100))
    
    return(list(
        correlation = correlation,
        rank_correlation = rank_correlation,
        top_overlap = overlap,
        n_predicted = length(predicted),
        n_top = n_top
    ))
}


# ============================================================================
# Main Processing
# ============================================================================

main <- function() {
    cat("="*80, "\n")
    cat("HAPLOTYPE ANALYSIS - PHASE 2: TEMPORAL VALIDATION\n")
    cat("="*80, "\n")
    
    # Load stability metrics to determine strategy
    metrics_path <- file.path(DATA_DIR, "stability_metrics.json")
    if (file.exists(metrics_path)) {
        metrics <- fromJSON(metrics_path)
        cat(sprintf("\nStability category: %s\n", metrics$stability_category))
        cat(sprintf("Recommendation: %s\n", metrics$recommendation))
    } else {
        cat("\nWarning: Stability metrics not found. Using cumulative pooling.\n")
    }
    
    # Define validation scenarios
    scenarios <- list(
        list(
            name = "2000-2006 -> 2007",
            train_years = 2000:2006,
            test_year = 2007
        ),
        list(
            name = "2000-2007 -> 2008",
            train_years = 2000:2007,
            test_year = 2008
        )
    )
    
    all_results <- list()
    all_favorable <- list()
    
    for (scenario in scenarios) {
        cat(sprintf("\n%s\n", paste(rep("=", 60), collapse = "")))
        cat(sprintf("Scenario: %s\n", scenario$name))
        cat(sprintf("%s\n", paste(rep("=", 60), collapse = "")))
        
        # Load training data
        train_data <- load_merged_data(scenario$train_years)
        
        # Load test data
        test_data <- load_merged_data(scenario$test_year)
        
        # Fit gBLUP and predict
        result <- fit_gblup_predict(train_data, test_data, trait = TRAIT)
        
        # Validate predictions
        validation <- validate_predictions(
            predicted = result$predicted,
            observed = test_data[[TRAIT]],
            line_ids = test_data$LINE_ID
        )
        
        # Identify favorable haplotypes
        favorable <- identify_favorable_haplotypes(
            snp_effects = result$snp_effects,
            data = train_data,
            trait = TRAIT,
            top_percent = TOP_PERCENT
        )
        
        # Save results
        all_results[[scenario$name]] <- list(
            scenario = scenario$name,
            train_years = scenario$train_years,
            test_year = scenario$test_year,
            h2 = result$h2,
            sigma2_u = result$sigma2_u,
            sigma2_e = result$sigma2_e,
            validation = validation,
            n_train = nrow(train_data),
            n_test = nrow(test_data)
        )
        
        # Save predicted BLUPs
        pred_df <- data.frame(
            LINE_ID = result$test_ids,
            Predicted = result$predicted,
            Observed = test_data[[TRAIT]],
            Year = scenario$test_year
        )
        pred_path <- file.path(OUTPUT_DIR, sprintf("predicted_blups_%d.csv", scenario$test_year))
        fwrite(pred_df, pred_path)
        cat(sprintf("\n  Saved predictions: %s\n", pred_path))
        
        # Save favorable haplotypes
        favorable$Scenario <- scenario$name
        all_favorable[[scenario$name]] <- favorable
        
        # Save SNP effects
        effects_df <- data.frame(
            SNP = names(result$snp_effects),
            Effect = as.numeric(result$snp_effects)
        )
        effects_path <- file.path(OUTPUT_DIR, sprintf("snp_effects_%s.csv", 
                                                        gsub("->", "to", scenario$name)))
        fwrite(effects_df, effects_path)
    }
    
    # Combine favorable haplotypes
    favorable_combined <- rbindlist(all_favorable)
    favorable_path <- file.path(OUTPUT_DIR, "haplotype_favorable.csv")
    fwrite(favorable_combined, favorable_path)
    cat(sprintf("\nSaved favorable haplotypes: %s\n", favorable_path))
    
    # Save validation metrics
    validation_metrics <- rbindlist(lapply(all_results, function(x) {
        data.frame(
            Scenario = x$scenario,
            Train_Years = paste(x$train_years, collapse = ","),
            Test_Year = x$test_year,
            N_Train = x$n_train,
            N_Test = x$n_test,
            Heritability = x$h2,
            Correlation = x$validation$correlation,
            Rank_Correlation = x$validation$rank_correlation,
            Top_Overlap = x$validation$top_overlap
        )
    }))
    metrics_path <- file.path(OUTPUT_DIR, "validation_metrics.csv")
    fwrite(validation_metrics, metrics_path)
    cat(sprintf("Saved validation metrics: %s\n", metrics_path))
    
    # Save summary
    summary <- list(
        parameters = list(
            trait = TRAIT,
            top_percent = TOP_PERCENT
        ),
        results = all_results
    )
    summary_path <- file.path(OUTPUT_DIR, "temporal_validation_summary.json")
    write_json(summary, summary_path, pretty = TRUE, auto_unbox = TRUE)
    
    # Print final summary
    cat("\n\n", paste(rep("=", 80), collapse = ""), "\n")
    cat("TEMPORAL VALIDATION SUMMARY\n")
    cat(paste(rep("=", 80), collapse = ""), "\n")
    
    cat("\nValidation Metrics:\n")
    print(validation_metrics)
    
    cat("\n\nTop 10 Favorable Haplotypes (from last scenario):\n")
    print(head(favorable_combined[order(-abs(favorable_combined$Effect_Size)), ], 10))
    
    cat("\n", paste(rep("=", 80), collapse = ""), "\n")
    cat("TEMPORAL VALIDATION COMPLETE\n")
    cat(paste(rep("=", 80), collapse = ""), "\n")
    cat("\nOutput directory:", OUTPUT_DIR, "\n")
    cat("\nNext steps:\n")
    cat("1. Review validation_metrics.csv\n")
    cat("2. Review haplotype_favorable.csv\n")
    cat("3. Run 03_alternative_methods.py for XGBoost and Neural Network\n")
    cat("4. Run 04_final_validation.py for 2008 evaluation\n")
}

# Run main function
main()