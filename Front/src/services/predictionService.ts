/**
 * Prediction & model metrics service.
 * Maps to s07b3_genomic_ridge.py + s08b predictions + s05 validation metrics.
 *
 * TO REPLACE: GET /api/model/metrics → ModelMetrics
 */

import type { ModelMetrics } from '@/types'
import { MODEL_METRICS } from '@/data/mockCandidates'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? null

export async function getModelMetrics(): Promise<ModelMetrics> {
  if (API_BASE) {
    const res = await fetch(`${API_BASE}/api/model/metrics`)
    if (!res.ok) throw new Error('Model metrics error')
    return res.json()
  }
  return Promise.resolve(MODEL_METRICS)
}

export const predictionService = { getModelMetrics }
