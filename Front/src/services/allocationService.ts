/**
 * Allocation service — wraps s08f_cultiva_allocation_engine.py output.
 *
 * TO REPLACE WITH REAL DATA:
 *   POST /api/cohort/build  { strategy, budget } → CohortRecommendation
 *   This endpoint should run the Python allocation engine and return results.
 */

import type { CohortRecommendation, SelectionStrategy, CandidateLine } from '@/types'
import { ALL_CANDIDATES } from '@/data/mockCandidates'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? null

export async function buildCohort(
  strategy: SelectionStrategy,
  budget: number
): Promise<CohortRecommendation> {
  if (API_BASE) {
    const res = await fetch(`${API_BASE}/api/cohort/build`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ strategy, budget }),
    })
    if (!res.ok) throw new Error('Allocation engine error')
    return res.json()
  }
  return mockBuildCohort(strategy, budget)
}

function mockBuildCohort(strategy: SelectionStrategy, budget: number): CohortRecommendation {
  let sorted = [...ALL_CANDIDATES]

  switch (strategy) {
    case 'maximize_performance':
      sorted.sort((a, b) => b.prediction.predictedValue - a.prediction.predictedValue)
      break
    case 'balanced':
      sorted.sort((a, b) => b.scores.overallScore - a.scores.overallScore)
      break
    case 'prioritize_stability':
      sorted.sort((a, b) => b.scores.stability - a.scores.stability)
      break
    case 'preserve_diversity': {
      // Alternate between C1 and C2, sorted by score
      const c1 = sorted.filter(c => c.population === 'C1').sort((a, b) => b.scores.overallScore - a.scores.overallScore)
      const c2 = sorted.filter(c => c.population === 'C2').sort((a, b) => b.scores.overallScore - a.scores.overallScore)
      sorted = []
      const half = Math.ceil(budget / 2)
      sorted.push(...c1.slice(0, half), ...c2.slice(0, half))
      break
    }
  }

  const selected = sorted.slice(0, budget)

  const avgYield = selected.reduce((s, l) => s + l.prediction.predictedValue, 0) / selected.length
  const avgConf = selected.reduce((s, l) => s + l.prediction.confidence, 0) / selected.length

  // Simulated improvement vs population mean
  const populationMeanYield = 7.2
  const expectedImprovement = ((avgYield - populationMeanYield) / populationMeanYield) * 100

  const c1Count = selected.filter(l => l.population === 'C1').length
  const c2Count = selected.filter(l => l.population === 'C2').length
  const diversityScore = Math.min(c1Count, c2Count) / (budget / 2)

  return {
    strategy,
    budget,
    selectedLines: selected.map((line, i) => ({
      lineId: line.id,
      rank: i + 1,
      score: line.scores.overallScore,
      predictedYield: line.prediction.predictedValue,
      confidence: line.prediction.confidence,
      rationale: buildRationale(line, strategy),
      population: line.population,
    })),
    expectedPerformance: +expectedImprovement.toFixed(1),
    confidence: +avgConf.toFixed(3),
    geneticDiversity: +diversityScore.toFixed(2),
    environmentalCoverage: +(0.72 + diversityScore * 0.2).toFixed(2),
    metadata: {
      generatedAt: new Date().toISOString(),
      modelVersion: '2.1.0-ridge',
      totalCandidates: ALL_CANDIDATES.length,
      _source: 'mock',
    },
  }
}

function buildRationale(line: CandidateLine, strategy: SelectionStrategy): string {
  if (line.status === 'elite') return 'Elite candidate — top genomic and phenotypic performance'
  if (line.isHiddenGem) return 'Hidden gem — genomic evidence exceeds observed performance'
  if (strategy === 'prioritize_stability') return `Stability score ${line.scores.stability}th percentile`
  if (strategy === 'maximize_performance') return `Predicted yield ${line.prediction.predictedValue} t/ha`
  return `Composite score ${line.scores.overallScore}/100`
}

export const allocationService = { buildCohort }
