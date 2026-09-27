/**
 * Candidate service — the single point of truth for candidate data in the UI.
 *
 * CURRENT IMPLEMENTATION: Returns mock data.
 *
 * TO REPLACE WITH REAL DATA:
 *   1. Set VITE_API_BASE_URL in your .env file (e.g. http://localhost:8000)
 *   2. Replace the functions below to call your FastAPI endpoints:
 *      GET /api/candidates            → getCandidates()
 *      GET /api/candidates/:id        → getCandidateById()
 *      GET /api/candidates/:id/passport → getPassport()
 *   3. Ensure your API returns the same TypeScript shapes defined in src/types/index.ts
 *
 * Expected FastAPI → Python pipeline data flow:
 *   s04_line_values.py (BLUEs)
 *   + s07b3_genomic_ridge_predictions.py (genomic EBVs)
 *   + s08b_2008_blind_prediction.py (2008 predictions)
 *   + s08c_family_selection_score.py (composite scores)
 *   ──────────────────────────────────────────────────
 *   FastAPI endpoint → this service → UI components
 */

import type { CandidateLine, BreedingPassport, HiddenGem } from '@/types'
import { ALL_CANDIDATES, HIDDEN_GEMS, SHOWCASE_LINES } from '@/data/mockCandidates'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? null

// ─── Internal fetch helper (used when API_BASE is set) ────────────────────────
async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`)
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`)
  return res.json() as Promise<T>
}

// ─── Public service functions ─────────────────────────────────────────────────

export async function getCandidates(): Promise<CandidateLine[]> {
  if (API_BASE) return apiFetch<CandidateLine[]>('/api/candidates')
  return Promise.resolve(ALL_CANDIDATES)
}

export async function getCandidateById(id: string): Promise<CandidateLine | null> {
  if (API_BASE) return apiFetch<CandidateLine>(`/api/candidates/${id}`)
  return Promise.resolve(ALL_CANDIDATES.find(c => c.id === id) ?? null)
}

export async function getPassport(id: string): Promise<BreedingPassport | null> {
  if (API_BASE) return apiFetch<BreedingPassport>(`/api/candidates/${id}/passport`)
  const line = ALL_CANDIDATES.find(c => c.id === id)
  return Promise.resolve(line?.passport ?? null)
}

export async function getHiddenGems(): Promise<HiddenGem[]> {
  if (API_BASE) return apiFetch<HiddenGem[]>('/api/hidden-gems')
  return Promise.resolve(HIDDEN_GEMS)
}

export async function getCopilotQueue(): Promise<CandidateLine[]> {
  if (API_BASE) return apiFetch<CandidateLine[]>('/api/copilot/queue')
  // Return showcase lines + a few more for copilot queue
  const extras = ALL_CANDIDATES
    .filter(c => !SHOWCASE_LINES.find(s => s.id === c.id))
    .filter(c => c.scores.overallScore >= 65)
    .slice(0, 31)
  return Promise.resolve([...SHOWCASE_LINES, ...extras])
}

export async function getDisagreements(): Promise<CandidateLine[]> {
  if (API_BASE) return apiFetch<CandidateLine[]>('/api/disagreements')
  return Promise.resolve(ALL_CANDIDATES.filter(c => c.hasDisagreement))
}

export const candidateService = {
  getCandidates,
  getCandidateById,
  getPassport,
  getHiddenGems,
  getCopilotQueue,
  getDisagreements,
}
