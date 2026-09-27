import { useContext } from 'react'
import { ThemeContext } from '@/components/ThemeProvider'

export type Theme = 'light' | 'dark'

export function useTheme() {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider')
  return ctx
}
