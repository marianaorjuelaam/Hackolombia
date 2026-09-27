import { cn } from '@/lib/utils'

interface ProgressBarProps {
  value: number
  max?: number
  className?: string
  color?: 'brand' | 'amber' | 'red' | 'blue' | 'neutral'
  size?: 'sm' | 'md' | 'lg'
  showLabel?: boolean
}

export function ProgressBar({ value, max = 100, className, color = 'brand', size = 'md', showLabel }: ProgressBarProps) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100))

  const colors = {
    brand: 'bg-brand-400',
    amber: 'bg-amber-400',
    red: 'bg-red-400',
    blue: 'bg-blue-400',
    neutral: 'bg-text-secondary',
  }

  const heights = {
    sm: 'h-1',
    md: 'h-1.5',
    lg: 'h-2',
  }

  return (
    <div className={cn('flex items-center gap-3', className)}>
      <div className={cn('flex-1 bg-surface-4 rounded-full overflow-hidden', heights[size])}>
        <div
          className={cn('h-full rounded-full transition-all duration-700', colors[color])}
          style={{ width: `${pct}%` }}
        />
      </div>
      {showLabel && (
        <span className="text-xs text-text-secondary tabular-nums w-8 text-right">{Math.round(pct)}</span>
      )}
    </div>
  )
}

interface ScoreRingProps {
  value: number
  size?: number
  color?: string
  className?: string
}

export function ScoreRing({ value, size = 64, color = '#4ade80', className }: ScoreRingProps) {
  const radius = (size - 8) / 2
  const circ = 2 * Math.PI * radius
  const offset = circ - (value / 100) * circ

  return (
    <div className={cn('relative inline-flex items-center justify-center', className)}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="var(--ring-track)" strokeWidth={4} />
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke={color} strokeWidth={4}
          strokeDasharray={circ} strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 1s ease-out' }}
        />
      </svg>
      <span className="absolute text-sm font-bold text-text-primary tabular-nums">{Math.round(value)}</span>
    </div>
  )
}
