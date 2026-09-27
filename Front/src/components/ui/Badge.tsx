import { cn } from '@/lib/utils'

interface BadgeProps {
  children: React.ReactNode
  variant?: 'default' | 'elite' | 'gem' | 'watch' | 'uncertain' | 'advance' | 'drop' | 'demo' | 'mock'
  className?: string
}

export function Badge({ children, variant = 'default', className }: BadgeProps) {
  const variants = {
    default: 'bg-surface-3 text-text-secondary border-border-default',
    elite: 'bg-brand-400/10 text-brand-400 border-brand-400/20',
    gem: 'bg-amber-400/10 text-amber-400 border-amber-400/20',
    watch: 'bg-yellow-500/10 text-yellow-500 border-yellow-500/20',
    uncertain: 'bg-orange-500/10 text-orange-500 border-orange-500/20',
    advance: 'bg-brand-400/15 text-brand-400 border-brand-400/25',
    drop: 'bg-red-500/10 text-red-400 border-red-400/20',
    demo: 'bg-purple-500/10 text-purple-400 border-purple-400/20',
    mock: 'bg-blue-500/5 text-blue-400/60 border-blue-400/10',
  }

  return (
    <span className={cn(
      'inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-medium tracking-wider border',
      variants[variant],
      className
    )}>
      {children}
    </span>
  )
}
