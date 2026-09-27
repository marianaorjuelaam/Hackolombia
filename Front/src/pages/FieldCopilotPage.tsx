import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { CheckCircle, Eye, XCircle, ChevronRight, ArrowUpRight, Keyboard, Dna, TrendingUp, MapPin, AlertTriangle } from 'lucide-react'
import { brand } from '@/config/brand'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { ProgressBar, ScoreRing } from '@/components/ui/ProgressBar'
import { candidateService } from '@/services/candidateService'
import type { CandidateLine, HumanDecision } from '@/types'
import { cn, formatYield, formatConfidence, statusBg, statusLabel } from '@/lib/utils'

type Direction = 'advance' | 'watch' | 'drop' | null

export default function FieldCopilotPage() {
  const navigate = useNavigate()
  const [queue, setQueue] = useState<CandidateLine[]>([])
  const [currentIdx, setCurrentIdx] = useState(0)
  const [decisions, setDecisions] = useState<Record<string, HumanDecision>>({})
  const [exitDirection, setExitDirection] = useState<Direction>(null)
  const [loading, setLoading] = useState(true)
  const [showKeyboard, setShowKeyboard] = useState(false)

  useEffect(() => {
    candidateService.getCopilotQueue().then(lines => {
      setQueue(lines)
      setLoading(false)
    })
  }, [])

  const current = queue[currentIdx]
  const upcoming = queue.slice(currentIdx + 1, currentIdx + 4)
  const reviewed = currentIdx
  const total = queue.length

  const makeDecision = useCallback((decision: HumanDecision) => {
    if (!current) return
    setDecisions(d => ({ ...d, [current.id]: decision }))
    setExitDirection(decision === 'advance' ? 'advance' : decision === 'watch' ? 'watch' : 'drop')
    setTimeout(() => {
      setExitDirection(null)
      setCurrentIdx(i => i + 1)
    }, 380)
  }, [current])

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'a' || e.key === 'ArrowRight') makeDecision('advance')
      if (e.key === 'w' || e.key === 'ArrowUp') makeDecision('watch')
      if (e.key === 'd' || e.key === 'ArrowDown') makeDecision('drop')
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [makeDecision])

  const advancedCount = Object.values(decisions).filter(d => d === 'advance').length
  const watchedCount = Object.values(decisions).filter(d => d === 'watch').length
  const droppedCount = Object.values(decisions).filter(d => d === 'drop').length

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full min-h-screen">
        <div className="text-text-muted text-sm font-mono">Loading queue...</div>
      </div>
    )
  }

  const isDone = currentIdx >= queue.length

  return (
    <div className="min-h-screen bg-surface-0 px-4 md:px-8 py-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="text-brand-400 text-xs font-mono tracking-widest uppercase mb-2">Field Copilot</div>
          <h1 className="text-2xl md:text-3xl font-black text-text-primary mb-2">{brand.copy.copilotHeadline}</h1>
          <p className="text-text-secondary text-sm">{brand.copy.copilotSub}</p>
        </div>

        {/* Progress bar */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-2">
            <span className="text-text-muted text-xs font-mono">
              {reviewed} / {total} reviewed
            </span>
            <div className="flex items-center gap-4 text-xs font-mono">
              <span className="text-brand-400">↑ {advancedCount} advanced</span>
              <span className="text-amber-400">⊙ {watchedCount} watching</span>
              <span className="text-red-400">↓ {droppedCount} dropped</span>
            </div>
          </div>
          <ProgressBar value={reviewed} max={total} size="md" />
        </div>

        {isDone ? (
          <DoneState decisions={decisions} queue={queue} onReview={() => { setCurrentIdx(0); setDecisions({}) }} />
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Main card */}
            <div className="lg:col-span-2">
              <AnimatePresence mode="wait">
                {current && (
                  <motion.div
                    key={current.id}
                    initial={{ opacity: 0, x: 40, rotateY: 5 }}
                    animate={{ opacity: 1, x: 0, rotateY: 0 }}
                    exit={
                      exitDirection === 'advance'
                        ? { opacity: 0, x: -80, rotateY: -8 }
                        : exitDirection === 'drop'
                        ? { opacity: 0, y: 40, scale: 0.95 }
                        : { opacity: 0, x: 80, rotateY: 8 }
                    }
                    transition={{ duration: 0.35, ease: 'easeInOut' }}
                  >
                    <CandidateCard
                      line={current}
                      onDecision={makeDecision}
                      onViewPassport={() => navigate(`/lines/${current.id}`)}
                    />
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Action buttons */}
              <AnimatePresence>
                {current && !exitDirection && (
                  <motion.div
                    key="actions"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    className="mt-4 flex gap-3"
                  >
                    <Button variant="drop" size="lg" className="flex-1" onClick={() => makeDecision('drop')}>
                      <XCircle size={16} />
                      Drop
                      <kbd className="text-[10px] opacity-50 ml-1 font-mono">D</kbd>
                    </Button>
                    <Button variant="watch" size="lg" className="flex-1" onClick={() => makeDecision('watch')}>
                      <Eye size={16} />
                      Watch
                      <kbd className="text-[10px] opacity-50 ml-1 font-mono">W</kbd>
                    </Button>
                    <Button variant="advance" size="lg" className="flex-1" onClick={() => makeDecision('advance')}>
                      <CheckCircle size={16} />
                      Advance
                      <kbd className="text-[10px] opacity-50 ml-1 font-mono">A</kbd>
                    </Button>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Keyboard hint */}
              <div className="mt-3 flex items-center gap-2 text-text-muted text-xs">
                <Keyboard size={12} />
                <span>Keyboard: A = Advance · W = Watch · D = Drop</span>
              </div>
            </div>

            {/* Upcoming queue */}
            <div className="space-y-3">
              <div className="text-text-muted text-xs font-mono tracking-widest uppercase mb-4">Up Next</div>
              {upcoming.map((line, i) => (
                <motion.div
                  key={line.id}
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1 - i * 0.25, x: 0 }}
                  transition={{ delay: i * 0.05 }}
                  className="bg-surface-2 border border-border-subtle rounded-lg p-3 flex items-center gap-3"
                >
                  <div className="flex-1 min-w-0">
                    <div className="text-text-primary text-sm font-mono font-bold truncate">{line.id}</div>
                    <div className="text-text-muted text-xs">{formatYield(line.prediction.predictedValue)}</div>
                  </div>
                  <div className={cn('text-xs px-2 py-0.5 rounded border', statusBg(line.status))}>
                    {formatConfidence(line.prediction.confidence)}
                  </div>
                </motion.div>
              ))}

              {upcoming.length === 0 && currentIdx < queue.length && (
                <div className="text-text-muted text-xs text-center py-4">Last candidate</div>
              )}

              {/* Stats */}
              <div className="mt-6 bg-surface-2 border border-border-subtle rounded-xl p-4 space-y-3">
                <div className="text-text-muted text-xs font-mono uppercase tracking-widest">Session</div>
                <div className="flex justify-between text-sm">
                  <span className="text-text-secondary">Remaining</span>
                  <span className="text-text-primary font-mono font-bold">{total - reviewed}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-text-secondary">Advanced</span>
                  <span className="text-brand-400 font-mono font-bold">{advancedCount}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-text-secondary">Watching</span>
                  <span className="text-amber-400 font-mono font-bold">{watchedCount}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-text-secondary">Dropped</span>
                  <span className="text-red-400 font-mono font-bold">{droppedCount}</span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function CandidateCard({ line, onDecision, onViewPassport }: {
  line: CandidateLine
  onDecision: (d: HumanDecision) => void
  onViewPassport: () => void
}) {
  const reasons = [
    line.scores.yieldPotential >= 80 && 'High genomic yield potential',
    line.prediction.confidence >= 0.85 && 'High model confidence',
    line.isHiddenGem && 'Hidden gem — genomic evidence exceeds observed performance',
    line.scores.stability >= 75 && 'Strong cross-environment stability',
    line.scores.environmentalFit >= 80 && 'Excellent environmental fit',
    line.prediction.confidence < 0.60 && '⚠ Model uncertainty — human review valuable',
  ].filter(Boolean) as string[]

  return (
    <div className="bg-surface-2 border border-border-default rounded-2xl overflow-hidden">
      {/* Card header */}
      <div className="px-6 pt-6 pb-4 border-b border-border-subtle bg-surface-3/30">
        <div className="flex items-start justify-between mb-3">
          <div>
            <div className="text-text-muted text-xs font-mono tracking-widest uppercase mb-1">Candidate Line</div>
            <h2 className="text-3xl font-black text-text-primary tracking-tight font-mono">{line.id}</h2>
            <div className="text-text-secondary text-sm mt-1">Population {line.population} · Family {line.family}</div>
          </div>
          <div className="flex flex-col items-end gap-2">
            <Badge variant={line.status === 'elite' ? 'elite' : line.status === 'hidden_gem' ? 'gem' : line.status === 'watch' ? 'watch' : 'default'}>
              {statusLabel(line.status)}
            </Badge>
            {line.isHiddenGem && (
              <Badge variant="gem">◆ HIDDEN GEM</Badge>
            )}
          </div>
        </div>

        {/* AI recommendation */}
        <div className="flex items-center gap-2 mt-2">
          <span className="text-text-muted text-xs font-mono">AI Recommendation:</span>
          <span className={cn(
            'text-xs font-mono font-bold uppercase tracking-wider',
            line.aiRecommendation === 'advance' ? 'text-brand-400' :
            line.aiRecommendation === 'watch' ? 'text-amber-400' : 'text-red-400'
          )}>
            {line.aiRecommendation.toUpperCase()}
          </span>
          <span className="text-text-muted text-xs font-mono">·</span>
          <span className="text-text-muted text-xs font-mono">
            {formatConfidence(line.prediction.confidence)} confidence
          </span>
        </div>
      </div>

      {/* Metrics grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-border-subtle">
        <MetricCell
          label="Predicted Yield"
          value={formatYield(line.prediction.predictedValue)}
          sub={`CI: ${formatYield(line.prediction.confidenceInterval[0])}–${formatYield(line.prediction.confidenceInterval[1])}`}
          icon={TrendingUp}
        />
        <MetricCell
          label="Model Confidence"
          value={formatConfidence(line.prediction.confidence)}
          sub={line.prediction.confidence >= 0.80 ? 'High confidence' : line.prediction.confidence >= 0.60 ? 'Moderate' : 'Uncertain'}
          icon={Dna}
          highlight={line.prediction.confidence >= 0.85}
        />
        <MetricCell
          label="Observed BLUE"
          value={line.observedBlue ? formatYield(line.observedBlue) : 'N/A'}
          sub={line.observedPercentile !== undefined ? `${line.observedPercentile}th percentile` : ''}
          icon={MapPin}
        />
        <div className="bg-surface-2 p-4 flex flex-col items-center justify-center gap-2">
          <ScoreRing value={line.scores.overallScore} size={56} />
          <span className="text-text-muted text-[10px] font-mono uppercase tracking-wider">Overall</span>
        </div>
      </div>

      {/* Score bars */}
      <div className="px-6 py-4 grid grid-cols-2 gap-x-8 gap-y-3">
        {[
          { label: 'Yield Potential', value: line.scores.yieldPotential },
          { label: 'Stability', value: line.scores.stability },
          { label: 'Env. Fit', value: line.scores.environmentalFit },
          { label: 'Genomic Conf.', value: line.scores.genomicConfidence },
        ].map(s => (
          <div key={s.label}>
            <div className="flex justify-between mb-1">
              <span className="text-text-secondary text-xs">{s.label}</span>
              <span className="text-text-primary text-xs font-mono font-bold">{s.value}</span>
            </div>
            <ProgressBar
              value={s.value}
              color={s.value >= 80 ? 'brand' : s.value >= 60 ? 'amber' : 'neutral'}
              size="sm"
            />
          </div>
        ))}
      </div>

      {/* Why am I seeing this */}
      <div className="px-6 pb-6">
        <div className="bg-surface-3/50 rounded-xl p-4 border border-border-subtle">
          <div className="text-text-muted text-xs font-mono uppercase tracking-widest mb-3 flex items-center gap-2">
            <AlertTriangle size={11} />
            Why am I seeing this?
          </div>
          <ul className="space-y-1.5">
            {reasons.slice(0, 3).map((r, i) => (
              <li key={i} className="flex items-start gap-2 text-text-secondary text-xs">
                <span className="text-brand-400 mt-0.5">·</span>
                {r}
              </li>
            ))}
          </ul>
        </div>

        {/* Disagreement warning */}
        {line.hasDisagreement && (
          <div className="mt-3 bg-amber-400/5 border border-amber-400/20 rounded-xl p-4 flex items-start gap-3">
            <AlertTriangle size={14} className="text-amber-400 mt-0.5 flex-shrink-0" />
            <div>
              <div className="text-amber-400 text-xs font-mono font-bold uppercase tracking-wider mb-1">
                Disagreement Detected
              </div>
              <div className="text-text-secondary text-xs">
                Your previous decision differs from the AI recommendation.
                AI confidence: {formatConfidence(line.prediction.confidence)}.
              </div>
            </div>
          </div>
        )}

        {/* View passport */}
        <button
          onClick={onViewPassport}
          className="mt-4 flex items-center gap-2 text-text-muted hover:text-brand-400 text-xs font-mono transition-colors"
        >
          <ArrowUpRight size={12} />
          View Full Breeding Passport
          <ChevronRight size={12} />
        </button>
      </div>
    </div>
  )
}

function MetricCell({ label, value, sub, icon: Icon, highlight }: {
  label: string; value: string; sub?: string; icon: React.ElementType; highlight?: boolean
}) {
  return (
    <div className="bg-surface-2 p-4 flex flex-col gap-1">
      <div className="flex items-center gap-1.5 text-text-muted">
        <Icon size={11} />
        <span className="text-[10px] font-mono uppercase tracking-wider">{label}</span>
      </div>
      <div className={cn('text-xl font-black tabular-nums', highlight ? 'text-brand-400' : 'text-text-primary')}>
        {value}
      </div>
      {sub && <div className="text-text-muted text-[10px]">{sub}</div>}
    </div>
  )
}

function DoneState({ decisions, queue, onReview }: {
  decisions: Record<string, HumanDecision>
  queue: CandidateLine[]
  onReview: () => void
}) {
  const navigate = useNavigate()
  const advanced = Object.values(decisions).filter(d => d === 'advance').length
  const watched = Object.values(decisions).filter(d => d === 'watch').length
  const dropped = Object.values(decisions).filter(d => d === 'drop').length

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="text-center py-16"
    >
      <div className="w-16 h-16 rounded-full bg-brand-400/10 border border-brand-400/20 flex items-center justify-center mx-auto mb-6">
        <CheckCircle size={28} className="text-brand-400" />
      </div>
      <h2 className="text-2xl font-black text-text-primary mb-2">Queue Complete</h2>
      <p className="text-text-secondary mb-8">You reviewed {queue.length} candidates.</p>

      <div className="flex gap-6 justify-center mb-10">
        <div className="text-center">
          <div className="text-3xl font-black text-brand-400">{advanced}</div>
          <div className="text-text-muted text-xs font-mono uppercase mt-1">Advanced</div>
        </div>
        <div className="text-center">
          <div className="text-3xl font-black text-amber-400">{watched}</div>
          <div className="text-text-muted text-xs font-mono uppercase mt-1">Watching</div>
        </div>
        <div className="text-center">
          <div className="text-3xl font-black text-red-400">{dropped}</div>
          <div className="text-text-muted text-xs font-mono uppercase mt-1">Dropped</div>
        </div>
      </div>

      <div className="flex gap-3 justify-center">
        <Button variant="primary" size="lg" onClick={() => navigate('/cohort')}>
          Build Optimal Cohort
          <ChevronRight size={16} />
        </Button>
        <Button variant="secondary" size="lg" onClick={onReview}>
          Review Again
        </Button>
      </div>
    </motion.div>
  )
}
