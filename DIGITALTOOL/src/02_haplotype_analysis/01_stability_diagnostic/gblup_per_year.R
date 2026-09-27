#' Phase 1: Stability Diagnostic - gBLUP per Year
#' ================================================
#'
#' This script fits gBLUP separately for each year and extracts SNP effects.
#'
#' Input:
#' - pooled_genotype_{year}.parquet (pooled genotype matrix per year)
#' - pooled_phenotype_{year}.parquet (pooled phenotype per year)
#'
#' Output:
#' - gblup_results_{year}.rds (gBLUP model results per year)
#' - snp_effects_{year}.csv (SNP effects per year)
#' - blup_values_{year}.csv (BLUP values for individuals per year)
#'
#' Usage:
#'     Rscript gblup_per_year.R
#'
#' Requirements:
#'     - R packages: arrow, sommer, data.table, jsonlite

# ============================================================================
# Configuration
# ============================================================================

# Load libraries
library(arrow)
library(data.table)
library(jsonlite)

# Try to load sommer, if not available, use alternative
if (requireNamespace("sommer", quietly = TRUE)) {
    library(sommer)
    use_sommer <- TRUE
} else {
    cat("Warning: sommer not available. Using rrBLUP instead.\n")
    if (requireNamespace("rrBLUP", quietly = TRUE)) {
        library(rrBLUP)
        use_sommer <- FALSE
    } else {
        stop("Neither sommer nor rrBLUP is available. Please install one of them.")
    }
}

# Paths
# Detect script location. A fixed number of "../.." hops is fragile: it
# silently resolves to the wrong directory (e.g. a Windows drive root) when
# the script is sourced interactively (RStudio "Source" does not chdir, so
# getwd() is the R session's working directory, not the script's folder).
# Instead, find the actual script path when possible, then walk UP the tree
# looking for the repo root (identified by containing a "DIGITALTOOL" folder)
# rather than assuming a fixed depth.
args <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args, value = TRUE)
if (length(file_arg) > 0) {
    # Launched via `Rscript gblup_per_year.R`
    SCRIPT_DIR <- normalizePath(dirname(sub("^--file=", "", file_arg)))
} else if (requireNamespace("rstudioapi", quietly = TRUE) &&
           tryCatch(rstudioapi::isAvailable(), error = function(e) FALSE)) {
    # Run interactively from RStudio (e.g. "Source" button)
    SCRIPT_DIR <- normalizePath(dirname(rstudioapi::getSourceEditorContext()$path))
} else {
    SCRIPT_DIR <- normalizePath(getwd())
}

find_base_dir <- function(start_dir) {
    dir <- start_dir
    for (i in 1:10) {
        if (dir.exists(file.path(dir, "DIGITALTOOL"))) {
            return(dir)
        }
        parent <- dirname(dir)
        if (parent == dir) return(NULL)  # reached filesystem root
        dir <- parent
    }
    return(NULL)
}

BASE_DIR <- find_base_dir(SCRIPT_DIR)
if (is.null(BASE_DIR)) {
    stop(sprintf(
        "Could not locate the repo root (a folder containing 'DIGITALTOOL') above '%s'. Run this script with `Rscript gblup_per_year.R` from its own folder, or setwd() into the repo first.",
        SCRIPT_DIR
    ))
}
DATA_DIR <- file.path(BASE_DIR, "DIGITALTOOL", "data", "processed", "haplotype_analysis")
OUTPUT_DIR <- file.path(BASE_DIR, "DIGITALTOOL", "data", "processed", "haplotype_analysis")

# Create output directory if it doesn't exist
dir.create(OUTPUT_DIR, showWarnings = FALSE, recursive = TRUE)

# Parameters
TRAIT <- "YLD_BE"  # Primary trait for analysis

# Years to process
YEARS <- 2000:2007  # Exclude 2008 (test set)

# ============================================================================
# Helper Functions
# ============================================================================

#' Load preprocessed data for a given year
load_year_data <- function(year) {
    cat(sprintf("\nLoading data for year %d...\n", year))
    
    # Load genotype matrix
    geno_path <- file.path(DATA_DIR, sprintf("pooled_genotype_%d.parquet", year))
    if (!file.exists(geno_path)) {
        cat(sprintf("  Warning: Genotype file not found: %s\n", geno_path))
        return(NULL)
    }
    geno <- as.data.frame(read_parquet(geno_path))
    
    # Load phenotype data
    pheno_path <- file.path(DATA_DIR, sprintf("pooled_phenotype_%d.parquet", year))
    if (!file.exists(pheno_path)) {
        cat(sprintf("  Warning: Phenotype file not found: %s\n", pheno_path))
        return(NULL)
    }
    pheno <- as.data.frame(read_parquet(pheno_path))
    
    # Load merged data (has both genotype and phenotype)
    merged_path <- file.path(DATA_DIR, sprintf("merged_%d.parquet", year))
    if (!file.exists(merged_path)) {
        cat(sprintf("  Warning: Merged file not found: %s\n", merged_path))
        return(NULL)
    }
    merged <- as.data.frame(read_parquet(merged_path))
    
    cat(sprintf("  Loaded %d individuals with %d SNPs\n", nrow(geno), ncol(geno) - 1))
    
    return(list(
        geno = geno,
        pheno = pheno,
        merged = merged,
        year = year
    ))
}


#' Fit gBLUP model using sommer
fit_gblup_sommer <- function(geno_data, merged_data, trait = "YLD_BE") {
    cat("  Fitting gBLUP with sommer...\n")

    # Prepare data
    data <- merged_data

    # Build the genomic relationship matrix from the unique-individual
    # genotype matrix (one row per LINE_ID). `merged_data` repeats each
    # individual once per environment/replicate, so building G directly
    # from it would blow G up to n_merged x n_merged (with duplicate
    # row/col names) instead of n_individuals x n_individuals - much
    # bigger than necessary and O(n^3) in the mixed model fit.
    geno_snp_cols <- setdiff(names(geno_data), "LINE_ID")
    geno_snp_cols <- geno_snp_cols[sapply(geno_data[geno_snp_cols], is.numeric)]

    cat(sprintf("    Using %d SNPs for gBLUP\n", length(geno_snp_cols)))

    # Extract genotype matrix
    Z <- as.matrix(geno_data[geno_snp_cols])

    # Center genotype matrix
    Z_centered <- scale(Z, center = TRUE, scale = FALSE)

    # Calculate genomic relationship matrix
    G <- tcrossprod(Z_centered) / ncol(Z_centered)

    # Add individual IDs (one per unique genotyped individual)
    rownames(G) <- geno_data$LINE_ID
    colnames(G) <- geno_data$LINE_ID

    # Prepare phenotype
    y <- data[[trait]]
    
    # Fit model
    # Simple gBLUP: y = mu + Zu + e
    # Where u ~ N(0, G*sigma2_u), e ~ N(0, I*sigma2_e)
    
    tryCatch({
        # Use sommer for mixed model
        data$LINE_ID <- as.factor(data$LINE_ID)
        
        # Fit model
        fit <- mmer(YLD_BE ~ 1,
                    random = ~ vsr(LINE_ID, Gu = G),
                    data = data,
                    verbose = FALSE)
        
        # Extract BLUPs
        blups <- as.numeric(fit$U$`u:LINE_ID`$YLD_BE)
        names(blups) <- levels(data$LINE_ID)
        
        # Extract variance components
        sigma2_u <- fit$sigma$`u:LINE_ID`
        sigma2_e <- fit$sigma$units
        
        # Calculate heritability
        h2 <- sigma2_u / (sigma2_u + sigma2_e)
        
        cat(sprintf("    Heritability: %.3f\n", h2))
        
        return(list(
            model = fit,
            blups = blups,
            sigma2_u = sigma2_u,
            sigma2_e = sigma2_e,
            h2 = h2,
            method = "sommer"
        ))
        
    }, error = function(e) {
        cat(sprintf("    Error with sommer: %s\n", e$message))
        cat("    Falling back to rrBLUP...\n")
        return(NULL)
    })
}


#' Fit gBLUP model using rrBLUP
fit_gblup_rrblup <- function(merged_data, trait = "YLD_BE") {
    cat("  Fitting gBLUP with rrBLUP...\n")
    
    # Prepare data
    data <- merged_data
    
    # Get SNP columns
    non_snp_cols <- c("YEAR", "LOC", "LONGITUDE", "LATITUDE", "LINE", "SET", 
                      "POP", "CROSS", "P1", "P2", "GERMPLASM_ID", "LINE_ID",
                      "YLD_BE", "MST", "PHT", "EHT", "TWT", "STLP", "RTLP", "ERM",
                      "OUTLIER", "ENV")
    snp_cols <- setdiff(names(data), non_snp_cols)
    snp_cols <- snp_cols[sapply(data[snp_cols], is.numeric)]
    
    cat(sprintf("    Using %d SNPs for gBLUP\n", length(snp_cols)))
    
    # Extract genotype matrix
    Z <- as.matrix(data[snp_cols])
    
    # Center and scale
    Z_scaled <- scale(Z, center = TRUE, scale = TRUE)
    
    # Prepare phenotype
    y <- data[[trait]]
    
    # Remove NAs
    valid_idx <- !is.na(y)
    y <- y[valid_idx]
    Z_scaled <- Z_scaled[valid_idx, ]
    
    tryCatch({
        # Fit mixed model with rrBLUP
        fit <- mixed.solve(y = y, Z = Z_scaled, K = NULL, SE = FALSE, return.Hinv = FALSE)
        
        # Extract SNP effects
        snp_effects <- as.numeric(fit$u)
        names(snp_effects) <- snp_cols
        
        # Calculate BLUPs (predicted genetic values)
        blups <- as.numeric(Z_scaled %*% snp_effects)
        names(blups) <- data$LINE_ID[valid_idx]
        
        # Extract variance components
        sigma2_u <- fit$Vu
        sigma2_e <- fit$Ve
        
        # Calculate heritability
        h2 <- sigma2_u / (sigma2_u + sigma2_e)
        
        cat(sprintf("    Heritability: %.3f\n", h2))
        
        return(list(
            model = fit,
            blups = blups,
            snp_effects = snp_effects,
            sigma2_u = sigma2_u,
            sigma2_e = sigma2_e,
            h2 = h2,
            method = "rrBLUP"
        ))
        
    }, error = function(e) {
        cat(sprintf("    Error with rrBLUP: %s\n", e$message))
        return(NULL)
    })
}


#' Extract SNP effects from gBLUP model
extract_snp_effects <- function(gblup_result, snp_names) {
    if (is.null(gblup_result)) {
        return(rep(NA, length(snp_names)))
    }
    
    if (gblup_result$method == "rrBLUP") {
        return(gblup_result$snp_effects)
    } else {
        # For sommer, we need to calculate SNP effects differently
        # This is a simplified version - in practice, you'd use the model's coefficient table
        return(rep(NA, length(snp_names)))
    }
}


# ============================================================================
# Main Processing
# ============================================================================

main <- function() {
    cat(paste(rep("=", 80), collapse = ""), "\n")
    cat("HAPLOTYPE ANALYSIS - PHASE 1: STABILITY DIAGNOSTIC\n")
    cat(paste(rep("=", 80), collapse = ""), "\n")
    
    # Storage for results
    all_results <- list()
    snp_effects_by_year <- list()
    blups_by_year <- list()
    
    # Process each year
    for (year in YEARS) {
        cat(sprintf("\n%s\n", paste(rep("=", 60), collapse = "")))
        cat(sprintf("Processing Year %d\n", year))
        cat(sprintf("%s\n", paste(rep("=", 60), collapse = "")))
        
        # Load data
        year_data <- load_year_data(year)
        
        if (is.null(year_data)) {
            cat(sprintf("  Skipping year %d (no data)\n", year))
            next
        }
        
        # Fit gBLUP
        if (use_sommer) {
            gblup_result <- tryCatch({
                fit_gblup_sommer(year_data$geno, year_data$merged, trait = TRAIT)
            }, error = function(e) {
                cat(sprintf("  sommer failed: %s\n", e$message))
                NULL
            })
            
            # If sommer fails, try rrBLUP
            if (is.null(gblup_result)) {
                gblup_result <- fit_gblup_rrblup(year_data$merged, trait = TRAIT)
            }
        } else {
            gblup_result <- fit_gblup_rrblup(year_data$merged, trait = TRAIT)
        }
        
        if (!is.null(gblup_result)) {
            # Get SNP names
            non_snp_cols <- c("YEAR", "LOC", "LONGITUDE", "LATITUDE", "LINE", "SET", 
                              "POP", "CROSS", "P1", "P2", "GERMPLASM_ID", "LINE_ID",
                              "YLD_BE", "MST", "PHT", "EHT", "TWT", "STLP", "RTLP", "ERM",
                              "OUTLIER", "ENV")
            snp_names <- setdiff(names(year_data$merged), non_snp_cols)
            snp_names <- snp_names[sapply(year_data$merged[snp_names], is.numeric)]
            
            # Extract SNP effects
            snp_effects <- extract_snp_effects(gblup_result, snp_names)
            names(snp_effects) <- snp_names
            snp_effects_by_year[[as.character(year)]] <- snp_effects
            
            # Save BLUPs
            blups_df <- data.frame(
                LINE_ID = names(gblup_result$blups),
                BLUP = as.numeric(gblup_result$blups),
                year = year
            )
            blups_by_year[[as.character(year)]] <- blups_df
            
            # Save results
            all_results[[as.character(year)]] <- list(
                year = year,
                h2 = gblup_result$h2,
                sigma2_u = gblup_result$sigma2_u,
                sigma2_e = gblup_result$sigma2_e,
                n_individuals = length(gblup_result$blups),
                n_snps = length(snp_effects),
                method = gblup_result$method
            )
            
            # Save BLUPs to file
            blup_path <- file.path(OUTPUT_DIR, sprintf("blup_values_%d.csv", year))
            fwrite(blups_df, blup_path)
            cat(sprintf("  Saved BLUPs: %s\n", blup_path))
            
            # Save SNP effects to file
            effects_df <- data.frame(
                SNP = names(snp_effects),
                Effect = as.numeric(snp_effects)
            )
            effects_path <- file.path(OUTPUT_DIR, sprintf("snp_effects_%d.csv", year))
            fwrite(effects_df, effects_path)
            cat(sprintf("  Saved SNP effects: %s\n", effects_path))
        }
    }
    
    # Create SNP effects matrix
    cat("\n\nCreating SNP effects matrix...\n")
    
    if (length(snp_effects_by_year) > 0) {
        # Get all SNP names
        all_snps <- unique(unlist(lapply(snp_effects_by_year, names)))
        
        # Create matrix
        effects_matrix <- matrix(NA, nrow = length(all_snps), ncol = length(snp_effects_by_year))
        rownames(effects_matrix) <- all_snps
        colnames(effects_matrix) <- names(snp_effects_by_year)
        
        # Fill matrix
        for (year_name in names(snp_effects_by_year)) {
            year_effects <- snp_effects_by_year[[year_name]]
            effects_matrix[names(year_effects), year_name] <- year_effects
        }
        
        # Save effects matrix
        effects_matrix_path <- file.path(OUTPUT_DIR, "snp_effects_matrix.csv")
        fwrite(as.data.frame(effects_matrix), effects_matrix_path, row.names = TRUE)
        cat(sprintf("  Saved SNP effects matrix: %s\n", effects_matrix_path))
        
        # Calculate correlation matrix
        cat("\nCalculating correlation matrix...\n")
        
        # Remove SNPs with all NAs
        valid_snps <- rowSums(!is.na(effects_matrix)) >= 2
        effects_matrix_valid <- effects_matrix[valid_snps, ]
        
        # Calculate correlation
        cor_matrix <- cor(effects_matrix_valid, use = "pairwise.complete.obs")
        
        # Save correlation matrix
        cor_matrix_path <- file.path(OUTPUT_DIR, "snp_effects_correlation_matrix.csv")
        fwrite(as.data.frame(cor_matrix), cor_matrix_path, row.names = TRUE)
        cat(sprintf("  Saved correlation matrix: %s\n", cor_matrix_path))
        
        # Print summary
        cat("\n\nCorrelation Summary:\n")
        cat("Average correlation between years:", mean(cor_matrix[upper.tri(cor_matrix)]), "\n")
        cat("Min correlation:", min(cor_matrix[upper.tri(cor_matrix)]), "\n")
        cat("Max correlation:", max(cor_matrix[upper.tri(cor_matrix)]), "\n")
    }
    
    # Save summary
    summary <- list(
        parameters = list(
            trait = TRAIT,
            years_processed = YEARS
        ),
        results = all_results
    )
    
    summary_path <- file.path(OUTPUT_DIR, "stability_diagnostic_summary.json")
    write_json(summary, summary_path, pretty = TRUE, auto_unbox = TRUE)
    cat(sprintf("\nSaved summary: %s\n", summary_path))
    
    # Print final summary
    cat("\n\n", paste(rep("=", 80), collapse = ""), "\n")
    cat("STABILITY DIAGNOSTIC SUMMARY\n")
    cat(paste(rep("=", 80), collapse = ""), "\n")
    
    cat("\nResults by Year:\n")
    for (year_name in names(all_results)) {
        res <- all_results[[year_name]]
        cat(sprintf("  %s: h2=%.3f, n=%d, method=%s\n", 
                    year_name, res$h2, res$n_individuals, res$method))
    }
    
    cat("\n", paste(rep("=", 80), collapse = ""), "\n")
    cat("STABILITY DIAGNOSTIC COMPLETE\n")
    cat(paste(rep("=", 80), collapse = ""), "\n")
    cat("\nOutput directory:", OUTPUT_DIR, "\n")
    cat("\nNext steps:\n")
    cat("1. Run 02_temporal_validation.py for gBLUP analysis\n")
    cat("2. Check snp_effects_correlation_matrix.csv for stability\n")
}

# Run main function
main()