import { cn } from '@/lib/utils'

interface CardProps {
  children: React.ReactNode
  className?: string
  hover?: boolean
  onClick?: () => void
}

export function Card({ children, className, hover, onClick }: CardProps) {
  return (
    <div
      onClick={onClick}
      className={cn(
        'bg-surface-2 border border-border-subtle rounded-xl p-6',
        hover && 'cursor-pointer transition-all duration-200 hover:border-border-default hover:bg-surface-3 hover:shadow-lg hover:shadow-black/20',
        onClick && 'cursor-pointer',
        className
      )}
    >
      {children}
    </div>
  )
}

export function CardHeader({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn('mb-4', className)}>{children}</div>
}

export function CardTitle({ children, className }: { children: React.ReactNode; className?: string }) {
  return <h3 className={cn('text-text-primary font-semibold text-sm tracking-wide uppercase', className)}>{children}</h3>
}

export function CardValue({ children, className }: { children: React.ReactNode; className?: string }) {
  return <p className={cn('text-3xl font-bold text-text-primary tabular-nums', className)}>{children}</p>
}
