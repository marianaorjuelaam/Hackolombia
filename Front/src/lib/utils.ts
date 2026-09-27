import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatYield(value: number): string {
  return `${value.toFixed(1)} t/ha`
}

export function formatPercent(value: number, decimals = 0): string {
  return `${value.toFixed(decimals)}%`
}

export function formatConfidence(value: number): string {
  return `${Math.round(value * 100)}%`
}

export function percentileLabel(p: number): string {
  if (p >= 90) return 'Top 10%'
  if (p >= 75) return 'Top 25%'
  if (p >= 50) return 'Above Median'
  if (p >= 25) return 'Below Median'
  return 'Bottom 25%'
}

export function statusColor(status: string): string {
  switch (status) {
    case 'elite': return 'text-brand-400'
    case 'promising': return 'text-green-400'
    case 'hidden_gem': return 'text-amber-400'
    case 'watch': return 'text-yellow-500'
    case 'uncertain': return 'text-orange-500'
    default: return 'text-text-secondary'
  }
}

export function statusBg(status: string): string {
  switch (status) {
    case 'elite': return 'bg-brand-400/10 text-brand-400 border-brand-400/20'
    case 'promising': return 'bg-green-400/10 text-green-400 border-green-400/20'
    case 'hidden_gem': return 'bg-amber-400/10 text-amber-400 border-amber-400/20'
    case 'watch': return 'bg-yellow-500/10 text-yellow-500 border-yellow-500/20'
    case 'uncertain': return 'bg-orange-500/10 text-orange-500 border-orange-500/20'
    default: return 'bg-surface-3 text-text-secondary border-border-default'
  }
}

export function statusLabel(status: string): string {
  switch (status) {
    case 'elite': return 'ELITE CANDIDATE'
    case 'promising': return 'PROMISING'
    case 'hidden_gem': return 'HIDDEN GEM'
    case 'watch': return 'WATCH'
    case 'uncertain': return 'UNCERTAIN'
    default: return 'UNKNOWN'
  }
}

export function recommendationColor(rec: string): string {
  switch (rec) {
    case 'advance': return 'text-brand-400'
    case 'watch': return 'text-amber-400'
    case 'drop': return 'text-red-400'
    default: return 'text-text-secondary'
  }
}
