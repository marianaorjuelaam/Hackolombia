import { cn } from '@/lib/utils'
import { type ButtonHTMLAttributes } from 'react'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'advance' | 'watch' | 'drop'
  size?: 'sm' | 'md' | 'lg' | 'xl'
}

export function Button({ variant = 'secondary', size = 'md', className, children, ...props }: ButtonProps) {
  const variants = {
    primary: 'bg-brand-400 text-surface-0 hover:bg-brand-500 font-semibold shadow-lg shadow-brand-400/20',
    secondary: 'bg-surface-3 text-text-primary border border-border-default hover:bg-surface-4 hover:border-border-default',
    ghost: 'text-text-secondary hover:text-text-primary hover:bg-surface-3',
    danger: 'bg-red-500/10 text-red-400 border border-red-400/20 hover:bg-red-500/20',
    advance: 'bg-brand-400 text-surface-0 hover:bg-brand-500 font-bold tracking-wide shadow-lg shadow-brand-400/25',
    watch: 'bg-amber-400/10 text-amber-400 border border-amber-400/20 hover:bg-amber-400/20 font-bold tracking-wide',
    drop: 'bg-red-500/10 text-red-400 border border-red-400/20 hover:bg-red-500/20 font-bold tracking-wide',
  }

  const sizes = {
    sm: 'px-3 py-1.5 text-xs rounded-lg',
    md: 'px-4 py-2 text-sm rounded-lg',
    lg: 'px-6 py-3 text-sm rounded-xl',
    xl: 'px-8 py-4 text-base rounded-xl',
  }

  return (
    <button
      className={cn(
        'inline-flex items-center justify-center gap-2 transition-all duration-150 disabled:opacity-40 disabled:cursor-not-allowed',
        variants[variant],
        sizes[size],
        className
      )}
      {...props}
    >
      {children}
    </button>
  )
}
