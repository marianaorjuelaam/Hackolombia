/**
 * Core TypeScript interfaces for CULTIVA.
 * These mirror the Python ML pipeline outputs so that mock data can be
 * replaced by real API responses without changing UI components.
 *
 * Source pipeline stages:
 *   s04_line_values.py         → LineValue / CandidateLine
 *   s07b3_genomic_ridge.py     → Prediction
 *   s08b_2008_blind_prediction.py → Prediction
 *   s08c_family_selection_score.py → FamilyScore
 *   s08d_budget_allocation.py  → CohortRecommendation
 *   s08f_cultiva_allocation_engine.py → CohortRecommendation
 */

// ─── Enums ────────────────────────────────────────────────────────────────────

export type Population = 'C1' | 'C2'
export type CandidateStatus = 'elite' | 'promising' | 'watch' | 'uncertain' | 'hidden_gem'
export type HumanDecision = 'advance' | 'watch' | 'drop' | 'pending'
export type AIRecommendation = 'advance' | 'watch' | 'drop'
export type SelectionStrategy = 'maximize_performance' | 'balanced' | 'prioritize_stability' | 'preserve_diversity'

// ─── Core data types ──────────────────────────────────────────────────────────

/** A single maize candidate line. Maps to s04 line_values + s08b predictions. */
export interface CandidateLine {
  id: string                          // e.g. "C2-1847"
  lineCode: string                    // Original line code from dataset
  population: Population
  family?: string                     // Breeding family
  year: number                        // Trial year

  // Genomic prediction output (s07b3 / s08b)
  prediction: Prediction

  // Phenotypic BLUE from s04_line_values.py
  observedBlue?: number               // Best Linear Unbiased Estimate
  observedPercentile?: number         // Percentile rank among population

  // Derived scores (s08c family_selection_score)
  scores: CandidateScores

  status: CandidateStatus
  aiRecommendation: AIRecommendation
  humanDecision: HumanDecision

  // Flags
  isHiddenGem: boolean
  hasDisagreement: boolean            // Human vs AI disagree

  // Optional extended data
  passport?: BreedingPassport

  // Data provenance
  _source: 'mock' | 'api'            // Track whether this came from mock or real data
}

/** Genomic prediction from Ridge regression model. Maps to s07b3 / s08b outputs. */
export interface Prediction {
  predictedValue: number              // Predicted grain yield (t/ha)
  confidence: number                  // Model confidence 0–1
  confidenceInterval: [number, number] // 95% CI
  genomicEBV?: number                 // Estimated Breeding Value
  reliability?: number                // REL from s04
  modelVersion: string
  _source: 'mock' | 'api'
}

/** Composite scores for ranking and display. Maps to s08c family_selection_score. */
export interface CandidateScores {
  yieldPotential: number              // 0–100 percentile
  stability: number                   // 0–100 percentile
  environmentalFit: number            // 0–100 percentile
  genomicConfidence: number           // 0–100 percentile
  novelty?: number                    // Optional — not yet in pipeline; demo-only
  overallScore: number                // Composite 0–100
}

/** Full breeding profile. Shown on the Breeding Passport page. */
export interface BreedingPassport {
  lineId: string
  cluster: string
  status: CandidateStatus

  // Metrics shown on passport header
  metrics: CandidateScores

  // Performance data
  predictedYield: number
  observedPerformance?: number
  confidenceInterval?: [number, number]

  // Environment fit
  bestEnvironments?: string[]
  worstEnvironments?: string[]
  gxeScore?: number                   // GxE interaction score from s07c4

  // Concerns and highlights
  mainConcern?: string
  keyStrength?: string

  // Related lines
  similarLines?: string[]             // IDs of genetically similar lines
  parentLines?: string[]

  recommendation: string
  _source: 'mock' | 'api'
}

/** Hidden gem — line with high genomic potential vs lower observed performance. */
export interface HiddenGem {
  lineId: string
  observedPercentile: number          // Low-to-medium phenotypic rank
  genomicPercentile: number           // High genomic prediction rank
  potentialGap: number                // genomicPercentile - observedPercentile
  rationale: string
  tags: HiddenGemTag[]
  _source: 'mock' | 'api'
}

export type HiddenGemTag = 'high_potential' | 'underperforming_observed' | 'novel_genetics' | 'high_uncertainty'

/** Human × AI disagreement record. */
export interface Disagreement {
  lineId: string
  humanDecision: HumanDecision
  aiRecommendation: AIRecommendation
  aiConfidence: number
  reason: string
  priority: 'high' | 'medium' | 'low'
}

/** Cohort recommendation from s08d / s08f allocation engine. */
export interface CohortRecommendation {
  strategy: SelectionStrategy
  budget: number                      // Max lines to advance
  selectedLines: SelectedLine[]
  expectedPerformance: number         // Expected mean yield improvement %
  confidence: number                  // Overall cohort confidence 0–1
  geneticDiversity?: number           // Diversity score 0–1 (if available)
  environmentalCoverage?: number      // Fraction of target environments covered
  metadata: {
    generatedAt: string
    modelVersion: string
    totalCandidates: number
    _source: 'mock' | 'api'
  }
}

export interface SelectedLine {
  lineId: string
  rank: number
  score: number
  predictedYield: number
  confidence: number
  rationale: string
  population: Population
}

/** Model performance metrics. Maps to s05 / s07b3 evaluation outputs. */
export interface ModelMetrics {
  modelVersion: string
  validationStrategy: string
  trainingCoverage: number            // Fraction of lines with genomic data
  pearsonR: number                    // Pearson correlation on validation set
  rmse: number
  mae: number
  temporalValidationR?: number        // r from temporal hold-out
  locationGeneralizationR?: number    // r from location hold-out (s08e)
  populationMetrics: Record<Population, PopulationMetrics>
  _source: 'mock' | 'api'
}

export interface PopulationMetrics {
  population: Population
  n: number                           // Number of lines
  pearsonR: number
  rmse: number
  coverage: number                    // Fraction with full genomic data
}

// ─── UI state types ───────────────────────────────────────────────────────────

export interface CopilotState {
  currentIndex: number
  totalQueue: number
  decisions: Record<string, HumanDecision>
  advanced: string[]
  watched: string[]
  dropped: string[]
}

export interface DemoState {
  isActive: boolean
  step: number
  totalSteps: number
}
