import { useTheme } from './useTheme'

export function useChartColors() {
  const { theme } = useTheme()
  const dark = theme === 'dark'

  return {
    grid: dark ? '#1e252d' : '#e3dfd8',
    tick: dark ? '#8b9ab0' : '#9e9890',
    radarGrid: dark ? '#1e252d' : '#e3dfd8',
    radarTick: dark ? '#8b9ab0' : '#9e9890',
    tooltip: {
      background: dark ? '#181d23' : '#ffffff',
      border: `1px solid ${dark ? '#2a3542' : '#d5cfc6'}`,
      borderRadius: 8,
      color: dark ? '#f0f4f8' : '#1a1814',
    },
    legend: dark ? '#8b9ab0' : '#9e9890',
  }
}
