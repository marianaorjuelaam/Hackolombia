import { useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Layers, Download, Trash2, CheckCircle, Dna, TrendingUp, Users, Globe, ChevronRight } from 'lucide-react'
import { allocationService } from '@/services/allocationService'
import type { CohortRecommendation, SelectionStrategy, SelectedLine } from '@/types'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { ProgressBar } from '@/components/ui/ProgressBar'
import { brand } from '@/config/brand'
import { cn, formatYield, formatConfidence } from '@/lib/utils'

const STRATEGIES: { key: SelectionStrategy; label: string; desc: string }[] = [
  { key: 'maximize_performance', label: 'Maximize Performance', desc: 'Select lines with highest predicted yield potential.' },
  { key: 'balanced', label: 'Balanced Selection', desc: 'Optimize composite score across yield, stability, and confidence.' },
  { key: 'prioritize_stability', label: 'Prioritize Stability', desc: 'Favor lines with consistent cross-environment performance.' },
  { key: 'preserve_diversity', label: 'Preserve Diversity', desc: 'Balance selection across genetic backgrounds and populations.' },
]

export default function BuildCohortPage() {
  const [budget, setBudget] = useState(50)
  const [strategy, setStrategy] = useState<SelectionStrategy>('balanced')
  const [cohort, setCohort] = useState<CohortRecommendation | null>(null)
  const [building, setBuilding] = useState(false)
  const [removed, setRemoved] = useState<Set<string>>(new Set())

  const buildCohort = useCallback(async () => {
    setBuilding(true)
    setCohort(null)
    setRemoved(new Set())
    await new Promise(r => setTimeout(r, 800)) // Simulate computation
    const result = await allocationService.buildCohort(strategy, budget)
    setCohort(result)
    setBuilding(false)
  }, [strategy, budget])

  const removeFromCohort = (id: string) => {
    setRemoved(s => new Set([...s, id]))
  }

  const visibleLines = cohort?.selectedLines.filter(l => !removed.has(l.lineId)) ?? []

  const exportCSV = () => {
    if (!cohort) return
    const rows = [
      ['Rank', 'Line ID', 'Population', 'Score', 'Predicted Yield (t/ha)', 'Confidence', 'Rationale'],
      ...visibleLines.map(l => [
        l.rank,
        l.lineId,
        l.population,
        l.score,
        l.predictedYield.toFixed(2),
        (l.confidence * 100).toFixed(0) + '%',
        `"${l.rationale}"`,
      ]),
    ]
    const csv = rows.map(r => r.join(',')).join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `maizevr_cohort_${strategy}_${budget}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="min-h-screen bg-surface-0 px-4 md:px-8 py-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-10">
          <div className="flex items-center gap-2 mb-3">
            <Layers size={16} className="text-brand-400" />
            <span className="text-brand-400 text-xs font-mono tracking-widest uppercase">Cohort Builder</span>
          </div>
          <h1 className="text-3xl md:text-5xl font-black text-text-primary mb-3 leading-tight">
            {brand.copy.cohortHeadline}
          </h1>
          <p className="text-text-secondary text-lg">{brand.copy.cohortSub}</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Controls */}
          <div className="space-y-5">
            {/* Budget slider */}
            <div className="bg-surface-2 border border-border-default rounded-xl p-5">
              <div className="text-text-muted text-xs font-mono uppercase tracking-widest mb-4">Lines to Advance</div>
              <div className="flex items-center justify-between mb-4">
                <span className="text-5xl font-black text-brand-400 tabular-nums">{budget}</span>
                <span className="text-text-muted text-sm">of 500</span>
              </div>
              <input
                type="range"
                min={10} max={100} step={5}
                value={budget}
                onChange={e => setBudget(Number(e.target.value))}
                className="w-full accent-green-400 cursor-pointer"
              />
              <div className="flex justify-between text-text-muted text-xs font-mono mt-2">
                <span>10</span>
                <span>55</span>
                <span>100</span>
              </div>
            </div>

            {/* Strategy selection */}
            <div className="bg-surface-2 border border-border-default rounded-xl p-5">
              <div className="text-text-muted text-xs font-mono uppercase tracking-widest mb-4">Selection Strategy</div>
              <div className="space-y-2">
                {STRATEGIES.map(s => (
                  <button
                    key={s.key}
                    onClick={() => setStrategy(s.key)}
                    className={cn(
                      'w-full text-left p-3 rounded-lg border transition-all',
                      strategy === s.key
                        ? 'border-brand-400/30 bg-brand-400/5 text-text-primary'
                        : 'border-border-subtle bg-surface-3 text-text-secondary hover:border-border-default'
                    )}
                  >
                    <div className="flex items-start gap-2">
                      <div className={cn(
                        'w-4 h-4 rounded-full border-2 mt-0.5 flex-shrink-0 transition-colors',
                        strategy === s.key ? 'border-brand-400 bg-brand-400' : 'border-text-muted'
                      )} />
                      <div>
                        <div className="text-sm font-semibold">{s.label}</div>
                        <div className="text-text-muted text-xs mt-0.5">{s.desc}</div>
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* Build button */}
            <Button
              variant="primary"
              size="xl"
              className="w-full"
              onClick={buildCohort}
              disabled={building}
            >
              {building ? (
                <>
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                    className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full"
                  />
                  Optimizing cohort...
                </>
              ) : (
                <>
                  <Dna size={16} />
                  Build Optimal Cohort
                  <ChevronRight size={16} />
                </>
              )}
            </Button>

            <div className="text-text-muted text-xs font-mono text-center">
              Future: connects to s08f_cultiva_allocation_engine.py
            </div>
          </div>

          {/* Results */}
          <div className="lg:col-span-2">
            <AnimatePresence mode="wait">
              {!cohort && !building && (
                <motion.div
                  key="empty"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="h-full flex flex-col items-center justify-center py-20 text-center"
                >
                  <div className="w-16 h-16 rounded-full bg-surface-3 border border-border-default flex items-center justify-center mb-4">
                    <Layers size={24} className="text-text-muted" />
                  </div>
                  <h3 className="text-text-primary font-bold mb-2">Configure and Build</h3>
                  <p className="text-text-muted text-sm max-w-xs">
                    Set your advancement budget and selection strategy, then generate the optimal cohort.
                  </p>
                </motion.div>
              )}

              {building && (
                <motion.div
                  key="building"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="h-full flex flex-col items-center justify-center py-20 text-center"
                >
                  <motion.div
                    animate={{ scale: [1, 1.1, 1] }}
                    transition={{ duration: 1.5, repeat: Infinity }}
                    className="w-16 h-16 rounded-full bg-brand-400/10 border border-brand-400/20 flex items-center justify-center mb-6"
                  >
                    <Dna size={24} className="text-brand-400" />
                  </motion.div>
                  <div className="text-text-primary font-bold mb-2">Optimizing selection...</div>
                  <div className="text-text-muted text-sm">Ranking {budget} best candidates from 500</div>
                </motion.div>
              )}

              {cohort && !building && (
                <motion.div
                  key="results"
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.4 }}
                >
                  {/* Impact summary */}
                  <CohortSummary cohort={cohort} visibleCount={visibleLines.length} />

                  {/* Line table */}
                  <div className="bg-surface-2 border border-border-subtle rounded-xl mt-4 overflow-hidden">
                    <div className="flex items-center justify-between px-4 py-3 border-b border-border-subtle">
                      <div className="text-text-primary text-sm font-semibold">
                        {visibleLines.length} Selected Lines
                        {removed.size > 0 && (
                          <span className="text-text-muted ml-2 text-xs">({removed.size} removed manually)</span>
                        )}
                      </div>
                      <Button variant="secondary" size="sm" onClick={exportCSV}>
                        <Download size={13} />
                        Export CSV
                      </Button>
                    </div>

                    <div className="overflow-y-auto max-h-96">
                      <table className="w-full">
                        <thead className="sticky top-0 bg-surface-2 z-10">
                          <tr className="border-b border-border-subtle">
                            {['#', 'Line', 'Pop.', 'Score', 'Yield', 'Conf.', ''].map(h => (
                              <th key={h} className="text-left px-3 py-2 text-text-muted text-[10px] font-mono uppercase tracking-wider">{h}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          <AnimatePresence>
                            {visibleLines.map((line) => (
                              <motion.tr
                                key={line.lineId}
                                layout
                                exit={{ opacity: 0, height: 0 }}
                                className="border-b border-border-subtle/50 hover:bg-surface-3 transition-colors group"
                              >
                                <td className="px-3 py-2.5">
                                  <span className="text-text-muted text-xs font-mono">{line.rank}</span>
                                </td>
                                <td className="px-3 py-2.5">
                                  <span className="text-text-primary text-sm font-mono font-bold">{line.lineId}</span>
                                </td>
                                <td className="px-3 py-2.5">
                                  <span className="text-text-muted text-xs font-mono">{line.population}</span>
                                </td>
                                <td className="px-3 py-2.5">
                                  <span className="text-brand-400 text-xs font-mono font-bold tabular-nums">{line.score}</span>
                                </td>
                                <td className="px-3 py-2.5">
                                  <span className="text-text-primary text-xs font-mono tabular-nums">{formatYield(line.predictedYield)}</span>
                                </td>
                                <td className="px-3 py-2.5">
                                  <span className="text-text-secondary text-xs font-mono tabular-nums">{formatConfidence(line.confidence)}</span>
                                </td>
                                <td className="px-3 py-2.5">
                                  <button
                                    onClick={() => removeFromCohort(line.lineId)}
                                    className="opacity-0 group-hover:opacity-100 text-text-muted hover:text-red-400 transition-all"
                                  >
                                    <Trash2 size={12} />
                                  </button>
                                </td>
                              </motion.tr>
                            ))}
                          </AnimatePresence>
                        </tbody>
                      </table>
                    </div>
                  </div>

                  <div className="mt-3 text-[10px] text-text-muted font-mono">
                    DEMO DATA · Future integration: s08f_cultiva_allocation_engine.py ·
                    Model version: {cohort.metadata.modelVersion}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </div>
  )
}

function CohortSummary({ cohort, visibleCount }: { cohort: CohortRecommendation; visibleCount: number }) {
  const metrics = [
    {
      icon: CheckCircle,
      label: 'Lines Selected',
      value: visibleCount.toString(),
      sub: `of ${cohort.budget} requested`,
      color: 'text-brand-400',
    },
    {
      icon: TrendingUp,
      label: 'Expected Improvement',
      value: `+${cohort.expectedPerformance.toFixed(1)}%`,
      sub: 'vs. population mean yield',
      color: 'text-brand-400',
    },
    {
      icon: Dna,
      label: 'Cohort Confidence',
      value: formatConfidence(cohort.confidence),
      sub: 'mean model confidence',
      color: cohort.confidence >= 0.75 ? 'text-brand-400' : 'text-amber-400',
    },
    ...(cohort.geneticDiversity !== undefined ? [{
      icon: Users,
      label: 'Genetic Diversity',
      value: `${(cohort.geneticDiversity * 100).toFixed(0)}%`,
      sub: 'cross-population balance',
      color: 'text-text-primary',
    }] : []),
    ...(cohort.environmentalCoverage !== undefined ? [{
      icon: Globe,
      label: 'Env. Coverage',
      value: `${(cohort.environmentalCoverage * 100).toFixed(0)}%`,
      sub: 'target environments',
      color: 'text-text-primary',
    }] : []),
  ]

  return (
    <div className="bg-surface-2 border border-border-default rounded-xl p-5">
      <div className="flex items-center gap-2 mb-4">
        <CheckCircle size={14} className="text-brand-400" />
        <span className="text-text-primary font-bold text-sm">Cohort Generated</span>
        <Badge variant="mock" className="ml-auto">DEMO DATA</Badge>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {metrics.map(m => (
          <div key={m.label} className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-lg bg-surface-3 flex items-center justify-center flex-shrink-0">
              <m.icon size={14} className={m.color} />
            </div>
            <div>
              <div className={cn('text-xl font-black tabular-nums', m.color)}>{m.value}</div>
              <div className="text-text-muted text-[10px] font-mono">{m.label}</div>
              <div className="text-text-muted text-[10px]">{m.sub}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
