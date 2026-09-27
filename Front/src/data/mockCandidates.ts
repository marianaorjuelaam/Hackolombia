/**
 * MOCK DATA — Replace with real API responses from FastAPI + Python pipeline.
 * All values are plausible for maize breeding but are DEMO DATA.
 *
 * To replace: implement src/services/candidateService.ts to fetch from your API
 * endpoint instead of returning these arrays. UI components never import from
 * this file directly — they go through the service layer.
 *
 * Data source mapping:
 *   predictedValue → s08b_2008_blind_prediction.py (Ridge regression)
 *   observedBlue   → s04_line_values.py (BLUE estimates)
 *   scores         → s08c_family_selection_score.py
 */

import type { CandidateLine, HiddenGem, ModelMetrics } from '@/types'

// ─── Helper ───────────────────────────────────────────────────────────────────
function seed(str: string): number {
  let h = 0
  for (let i = 0; i < str.length; i++) h = (Math.imul(31, h) + str.charCodeAt(i)) | 0
  return Math.abs(h)
}
function pseudoRandom(id: string, offset = 0): number {
  return ((seed(id + offset) % 1000) / 1000)
}

// ─── Generate realistic mock lines ────────────────────────────────────────────
function makeLine(
  id: string,
  pop: 'C1' | 'C2',
  overrides: Partial<CandidateLine> = {}
): CandidateLine {
  const r = pseudoRandom(id)
  const r2 = pseudoRandom(id, 1)
  const r3 = pseudoRandom(id, 2)

  const predictedValue = 6.5 + r * 3.5
  const confidence = 0.62 + r2 * 0.35
  const observedBlue = 6.2 + r3 * 3.2
  const observedPercentile = Math.round(r3 * 100)
  const genomicPct = Math.round(r * 100)

  const yieldPotential = genomicPct
  const stability = Math.round(40 + r2 * 55)
  const environmentalFit = Math.round(35 + pseudoRandom(id, 3) * 60)
  const genomicConfidence = Math.round(confidence * 100)
  const overallScore = Math.round((yieldPotential * 0.4 + stability * 0.2 + environmentalFit * 0.2 + genomicConfidence * 0.2))

  const isHiddenGem = observedPercentile < 70 && genomicPct > 80
  const status: CandidateLine['status'] =
    overallScore >= 85 ? 'elite' :
    isHiddenGem ? 'hidden_gem' :
    overallScore >= 70 ? 'promising' :
    overallScore >= 50 ? 'watch' : 'uncertain'

  const aiRec: CandidateLine['aiRecommendation'] =
    overallScore >= 75 ? 'advance' :
    overallScore >= 50 ? 'watch' : 'drop'

  return {
    id,
    lineCode: id,
    population: pop,
    family: `${pop}.${Math.floor(seed(id) % 130 + 1)}`,
    year: 2008,
    prediction: {
      predictedValue: +predictedValue.toFixed(2),
      confidence: +confidence.toFixed(3),
      confidenceInterval: [+(predictedValue - 0.6).toFixed(2), +(predictedValue + 0.6).toFixed(2)],
      genomicEBV: +(predictedValue - 0.15).toFixed(2),
      reliability: +(0.55 + r2 * 0.4).toFixed(3),
      modelVersion: '2.1.0-ridge',
      _source: 'mock',
    },
    observedBlue: +observedBlue.toFixed(2),
    observedPercentile,
    scores: {
      yieldPotential,
      stability,
      environmentalFit,
      genomicConfidence,
      novelty: undefined, // Not yet in pipeline — demo-only if shown
      overallScore,
    },
    status,
    aiRecommendation: aiRec,
    humanDecision: 'pending',
    isHiddenGem,
    hasDisagreement: false,
    _source: 'mock',
    ...overrides,
  }
}

// ─── Curated showcase lines (used in demos and Copilot queue) ────────────────
export const SHOWCASE_LINES: CandidateLine[] = [
  {
    id: 'C2-1847',
    lineCode: 'C2-1847',
    population: 'C2',
    family: 'C2.47',
    year: 2008,
    prediction: {
      predictedValue: 8.7,
      confidence: 0.91,
      confidenceInterval: [8.1, 9.3],
      genomicEBV: 8.55,
      reliability: 0.88,
      modelVersion: '2.1.0-ridge',
      _source: 'mock',
    },
    observedBlue: 8.4,
    observedPercentile: 88,
    scores: {
      yieldPotential: 92,
      stability: 84,
      environmentalFit: 87,
      genomicConfidence: 91,
      novelty: undefined,
      overallScore: 89,
    },
    status: 'elite',
    aiRecommendation: 'advance',
    humanDecision: 'pending',
    isHiddenGem: false,
    hasDisagreement: false,
    _source: 'mock',
    passport: {
      lineId: 'C2-1847',
      cluster: 'C2',
      status: 'elite',
      metrics: { yieldPotential: 92, stability: 84, environmentalFit: 87, genomicConfidence: 91, overallScore: 89 },
      predictedYield: 8.7,
      observedPerformance: 8.4,
      confidenceInterval: [8.1, 9.3],
      bestEnvironments: ['Córdoba-Norte', 'Valle del Cauca', 'Tolima'],
      worstEnvironments: ['Sabana de Bogotá'],
      gxeScore: 0.72,
      mainConcern: 'Mild instability in high-altitude environments',
      keyStrength: 'Exceptional genomic-phenotypic alignment',
      similarLines: ['C2-1821', 'C2-1903', 'C2-2014'],
      parentLines: ['C2.47-P1', 'C2.47-P2'],
      recommendation: 'Strong advance candidate. High genomic confidence, consistent performance across lowland environments.',
      _source: 'mock',
    },
  },
  {
    id: 'C2-0334',
    lineCode: 'C2-0334',
    population: 'C2',
    family: 'C2.12',
    year: 2008,
    prediction: {
      predictedValue: 7.9,
      confidence: 0.78,
      confidenceInterval: [7.2, 8.6],
      genomicEBV: 7.7,
      reliability: 0.75,
      modelVersion: '2.1.0-ridge',
      _source: 'mock',
    },
    observedBlue: 7.4,
    observedPercentile: 72,
    scores: {
      yieldPotential: 81,
      stability: 76,
      environmentalFit: 79,
      genomicConfidence: 78,
      overallScore: 79,
    },
    status: 'promising',
    aiRecommendation: 'advance',
    humanDecision: 'pending',
    isHiddenGem: false,
    hasDisagreement: false,
    _source: 'mock',
  },
  {
    id: 'C4-8821',
    lineCode: 'C4-8821',
    population: 'C2',
    family: 'C2.88',
    year: 2008,
    prediction: {
      predictedValue: 8.1,
      confidence: 0.85,
      confidenceInterval: [7.5, 8.7],
      genomicEBV: 7.95,
      reliability: 0.82,
      modelVersion: '2.1.0-ridge',
      _source: 'mock',
    },
    observedBlue: 6.8,
    observedPercentile: 61,
    scores: {
      yieldPotential: 94,
      stability: 71,
      environmentalFit: 82,
      genomicConfidence: 85,
      overallScore: 87,
    },
    status: 'hidden_gem',
    aiRecommendation: 'advance',
    humanDecision: 'pending',
    isHiddenGem: true,
    hasDisagreement: false,
    _source: 'mock',
    passport: {
      lineId: 'C4-8821',
      cluster: 'C2',
      status: 'hidden_gem',
      metrics: { yieldPotential: 94, stability: 71, environmentalFit: 82, genomicConfidence: 85, overallScore: 87 },
      predictedYield: 8.1,
      observedPerformance: 6.8,
      confidenceInterval: [7.5, 8.7],
      bestEnvironments: ['Valle del Cauca', 'Antioquia'],
      gxeScore: 0.61,
      mainConcern: 'Moderate instability — may need environment-specific management',
      keyStrength: 'Strong genomic evidence not captured by phenotypic trials',
      similarLines: ['C2-0791', 'C2-1104'],
      recommendation: 'Hidden gem candidate. Genomic evidence substantially exceeds observed performance. Consider advancing for further validation.',
      _source: 'mock',
    },
  },
  {
    id: 'C1-2203',
    lineCode: 'C1-2203',
    population: 'C1',
    family: 'C1.22',
    year: 2008,
    prediction: {
      predictedValue: 7.2,
      confidence: 0.68,
      confidenceInterval: [6.3, 8.1],
      genomicEBV: 7.0,
      reliability: 0.64,
      modelVersion: '2.1.0-ridge',
      _source: 'mock',
    },
    observedBlue: 7.5,
    observedPercentile: 75,
    scores: {
      yieldPotential: 74,
      stability: 66,
      environmentalFit: 70,
      genomicConfidence: 68,
      overallScore: 71,
    },
    status: 'watch',
    aiRecommendation: 'watch',
    humanDecision: 'advance',
    isHiddenGem: false,
    hasDisagreement: true,  // Human says advance, AI says watch
    _source: 'mock',
  },
  {
    id: 'C1-0541',
    lineCode: 'C1-0541',
    population: 'C1',
    family: 'C1.54',
    year: 2008,
    prediction: {
      predictedValue: 9.1,
      confidence: 0.94,
      confidenceInterval: [8.6, 9.6],
      genomicEBV: 8.95,
      reliability: 0.91,
      modelVersion: '2.1.0-ridge',
      _source: 'mock',
    },
    observedBlue: 8.9,
    observedPercentile: 95,
    scores: {
      yieldPotential: 97,
      stability: 91,
      environmentalFit: 93,
      genomicConfidence: 94,
      overallScore: 95,
    },
    status: 'elite',
    aiRecommendation: 'advance',
    humanDecision: 'pending',
    isHiddenGem: false,
    hasDisagreement: false,
    _source: 'mock',
  },
  {
    id: 'C3-0291',
    lineCode: 'C3-0291',
    population: 'C1',
    family: 'C1.03',
    year: 2008,
    prediction: {
      predictedValue: 7.4,
      confidence: 0.52,
      confidenceInterval: [6.1, 8.7],
      genomicEBV: 7.1,
      reliability: 0.48,
      modelVersion: '2.1.0-ridge',
      _source: 'mock',
    },
    observedBlue: 6.9,
    observedPercentile: 58,
    scores: {
      yieldPotential: 71,
      stability: 55,
      environmentalFit: 63,
      genomicConfidence: 52,
      overallScore: 63,
    },
    status: 'uncertain',
    aiRecommendation: 'watch',
    humanDecision: 'pending',
    isHiddenGem: false,
    hasDisagreement: false,
    _source: 'mock',
  },
]

// ─── Generate full candidate pool (500 lines) ─────────────────────────────────
function generatePool(): CandidateLine[] {
  const pool: CandidateLine[] = [...SHOWCASE_LINES]
  const showcaseIds = new Set(SHOWCASE_LINES.map(l => l.id))

  for (let i = 1; i <= 247; i++) {
    const id = `C2-${String(i).padStart(4, '0')}`
    if (!showcaseIds.has(id)) pool.push(makeLine(id, 'C2'))
  }
  for (let i = 1; i <= 247; i++) {
    const id = `C1-${String(i).padStart(4, '0')}`
    if (!showcaseIds.has(id)) pool.push(makeLine(id, 'C1'))
  }

  return pool.slice(0, 500)
}

export const ALL_CANDIDATES: CandidateLine[] = generatePool()

// ─── Hidden gems subset ───────────────────────────────────────────────────────
export const HIDDEN_GEMS: HiddenGem[] = [
  {
    lineId: 'C4-8821',
    observedPercentile: 61,
    genomicPercentile: 94,
    potentialGap: 33,
    rationale: 'Moderate observed performance but strong genomic profile indicates potentially underestimated advancement value.',
    tags: ['high_potential', 'underperforming_observed'],
    _source: 'mock',
  },
  {
    lineId: 'C2-0174',
    observedPercentile: 54,
    genomicPercentile: 88,
    potentialGap: 34,
    rationale: 'Environmental stress in trial years likely masked genomic potential. Model predicts strong performance under normal conditions.',
    tags: ['high_potential', 'underperforming_observed', 'high_uncertainty'],
    _source: 'mock',
  },
  {
    lineId: 'C1-0312',
    observedPercentile: 67,
    genomicPercentile: 91,
    potentialGap: 24,
    rationale: 'Genomic markers indicate superior yield capacity. Trial data suggests environment-specific suppression.',
    tags: ['high_potential', 'novel_genetics'],
    _source: 'mock',
  },
  {
    lineId: 'C2-0067',
    observedPercentile: 48,
    genomicPercentile: 83,
    potentialGap: 35,
    rationale: 'Novel genetic background not well represented in training data. High potential with model uncertainty.',
    tags: ['novel_genetics', 'high_uncertainty'],
    _source: 'mock',
  },
  {
    lineId: 'C1-0891',
    observedPercentile: 72,
    genomicPercentile: 89,
    potentialGap: 17,
    rationale: 'Consistent genomic advantage across marker groups. Minor phenotypic gap likely attributable to year effects.',
    tags: ['high_potential'],
    _source: 'mock',
  },
  {
    lineId: 'C2-1104',
    observedPercentile: 55,
    genomicPercentile: 85,
    potentialGap: 30,
    rationale: 'Strong ridge regression signal. Observed trials had limited location coverage — genomic model suggests broader adaptability.',
    tags: ['high_potential', 'underperforming_observed'],
    _source: 'mock',
  },
]

// ─── Model metrics ────────────────────────────────────────────────────────────
export const MODEL_METRICS: ModelMetrics = {
  modelVersion: '2.1.0-ridge',
  validationStrategy: 'Temporal hold-out (2006–2007 train → 2008 test) + Leave-one-environment-out',
  trainingCoverage: 0.847,
  pearsonR: 0.73,
  rmse: 0.61,
  mae: 0.48,
  temporalValidationR: 0.71,
  locationGeneralizationR: 0.67,
  populationMetrics: {
    C1: { population: 'C1', n: 248, pearsonR: 0.76, rmse: 0.58, coverage: 0.91 },
    C2: { population: 'C2', n: 252, pearsonR: 0.70, rmse: 0.64, coverage: 0.80 },
  },
  _source: 'mock',
}
