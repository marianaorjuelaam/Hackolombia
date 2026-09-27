import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useChartColors } from '@/hooks/useChartColors'
import { motion } from 'framer-motion'
import { ArrowLeft, Dna, TrendingUp, MapPin, BarChart2, Network, Award, AlertCircle } from 'lucide-react'
import { candidateService } from '@/services/candidateService'
import type { CandidateLine } from '@/types'
import { Badge } from '@/components/ui/Badge'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { ProgressBar, ScoreRing } from '@/components/ui/ProgressBar'
import { cn, formatYield, formatConfidence, statusLabel } from '@/lib/utils'
import {
  RadarChart, PolarGrid, PolarAngleAxis, Radar,
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid
} from 'recharts'

const TABS = ['Overview', 'Performance', 'Env. Fit', 'Genomic Profile', 'Similar Lines']

export default function BreedingPassportPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [line, setLine] = useState<CandidateLine | null>(null)
  const [tab, setTab] = useState(0)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!id) return
    candidateService.getCandidateById(id).then(l => {
      setLine(l)
      setLoading(false)
    })
  }, [id])

  if (loading) return (
    <div className="flex items-center justify-center h-full min-h-screen">
      <div className="text-text-muted text-sm font-mono">Loading passport...</div>
    </div>
  )

  if (!line) return (
    <div className="flex flex-col items-center justify-center h-full min-h-screen gap-4">
      <div className="text-text-muted text-sm">Line not found: {id}</div>
      <Button variant="secondary" onClick={() => navigate('/lines')}>Back to Lines</Button>
    </div>
  )

  const passport = line.passport
  const statusVariant = line.status === 'elite' ? 'elite' : line.status === 'hidden_gem' ? 'gem' : line.status === 'watch' ? 'watch' : 'default'

  const radarData = [
    { subject: 'Yield', value: line.scores.yieldPotential },
    { subject: 'Stability', value: line.scores.stability },
    { subject: 'Env. Fit', value: line.scores.environmentalFit },
    { subject: 'Genomic', value: line.scores.genomicConfidence },
    { subject: 'Overall', value: line.scores.overallScore },
  ]

  return (
    <div className="min-h-screen bg-surface-0 px-4 md:px-8 py-8">
      <div className="max-w-5xl mx-auto">
        {/* Back */}
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-2 text-text-muted hover:text-text-primary text-sm font-mono mb-6 transition-colors"
        >
          <ArrowLeft size={14} />
          Back
        </button>

        {/* Passport header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-surface-2 border border-border-default rounded-2xl overflow-hidden mb-6"
        >
          <div className="px-6 md:px-10 py-8 bg-gradient-to-r from-surface-3 to-surface-2">
            <div className="flex flex-col md:flex-row md:items-start justify-between gap-6">
              <div className="flex-1">
                <div className="text-text-muted text-xs font-mono tracking-widest uppercase mb-2">
                  Breeding Passport · Population {line.population}
                </div>
                <h1 className="text-4xl md:text-5xl font-black text-text-primary font-mono mb-3 tracking-tight">
                  {line.id}
                </h1>
                <div className="flex flex-wrap items-center gap-2 mb-4">
                  <Badge variant={statusVariant}>{statusLabel(line.status)}</Badge>
                  {line.isHiddenGem && <Badge variant="gem">◆ HIDDEN GEM</Badge>}
                </div>
                <div className="text-text-secondary text-sm">
                  Family {line.family} · Year {line.year}
                  {passport?.cluster && ` · Cluster ${passport.cluster}`}
                </div>
              </div>

              <div className="flex items-center gap-6">
                <ScoreRing value={line.scores.overallScore} size={88} />
                <div className="space-y-1">
                  <div className="text-text-muted text-xs font-mono uppercase">Overall Score</div>
                  <div className="text-text-primary text-sm">Top {100 - line.scores.overallScore}% benchmark</div>
                </div>
              </div>
            </div>

            {/* Key metrics row */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6">
              <KeyMetric label="Predicted Yield" value={formatYield(line.prediction.predictedValue)} accent />
              <KeyMetric label="Model Confidence" value={formatConfidence(line.prediction.confidence)} />
              <KeyMetric label="Observed BLUE" value={line.observedBlue ? formatYield(line.observedBlue) : 'N/A'} />
              <KeyMetric label="AI Recommendation" value={line.aiRecommendation.toUpperCase()}
                color={line.aiRecommendation === 'advance' ? 'text-brand-400' : line.aiRecommendation === 'watch' ? 'text-amber-400' : 'text-red-400'}
              />
            </div>
          </div>

          {/* Tabs */}
          <div className="flex border-t border-border-subtle overflow-x-auto">
            {TABS.map((t, i) => (
              <button
                key={t}
                onClick={() => setTab(i)}
                className={cn(
                  'px-5 py-3 text-xs font-mono uppercase tracking-wider whitespace-nowrap border-b-2 transition-colors',
                  tab === i
                    ? 'border-brand-400 text-brand-400'
                    : 'border-transparent text-text-muted hover:text-text-secondary'
                )}
              >
                {t}
              </button>
            ))}
          </div>
        </motion.div>

        {/* Tab content */}
        <motion.div
          key={tab}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2 }}
        >
          {tab === 0 && <OverviewTab line={line} radarData={radarData} />}
          {tab === 1 && <PerformanceTab line={line} />}
          {tab === 2 && <EnvFitTab line={line} />}
          {tab === 3 && <GenomicTab line={line} />}
          {tab === 4 && <SimilarLinesTab line={line} />}
        </motion.div>
      </div>
    </div>
  )
}

function KeyMetric({ label, value, accent, color }: { label: string; value: string; accent?: boolean; color?: string }) {
  return (
    <div>
      <div className="text-text-muted text-[10px] font-mono uppercase tracking-wider mb-1">{label}</div>
      <div className={cn('text-lg md:text-xl font-black tabular-nums', accent ? 'text-brand-400' : color ?? 'text-text-primary')}>
        {value}
      </div>
    </div>
  )
}

function OverviewTab({ line, radarData }: { line: CandidateLine; radarData: object[] }) {
  const passport = line.passport
  const colors = useChartColors()

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {/* Radar chart */}
      <Card>
        <div className="text-text-muted text-xs font-mono uppercase tracking-widest mb-4 flex items-center gap-2">
          <Award size={12} />
          Performance Profile
        </div>
        <ResponsiveContainer width="100%" height={220}>
          <RadarChart data={radarData}>
            <PolarGrid stroke={colors.radarGrid} />
            <PolarAngleAxis dataKey="subject" tick={{ fill: colors.radarTick, fontSize: 11 }} />
            <Radar name="Score" dataKey="value" stroke="#4ade80" fill="#4ade80" fillOpacity={0.15} strokeWidth={2} />
          </RadarChart>
        </ResponsiveContainer>
      </Card>

      {/* Score breakdown */}
      <Card>
        <div className="text-text-muted text-xs font-mono uppercase tracking-widest mb-4 flex items-center gap-2">
          <BarChart2 size={12} />
          Score Breakdown
        </div>
        <div className="space-y-4">
          {[
            { label: 'Yield Potential', value: line.scores.yieldPotential, color: 'brand' as const },
            { label: 'Stability', value: line.scores.stability, color: 'brand' as const },
            { label: 'Env. Fit', value: line.scores.environmentalFit, color: 'brand' as const },
            { label: 'Genomic Conf.', value: line.scores.genomicConfidence, color: 'brand' as const },
          ].map(s => (
            <div key={s.label}>
              <div className="flex justify-between mb-1.5">
                <span className="text-text-secondary text-sm">{s.label}</span>
                <span className="text-text-primary text-sm font-mono font-bold">{s.value}<span className="text-text-muted text-xs">/100</span></span>
              </div>
              <ProgressBar value={s.value} color={s.value >= 80 ? 'brand' : s.value >= 60 ? 'amber' : 'neutral'} size="md" />
            </div>
          ))}
        </div>
      </Card>

      {/* Recommendation */}
      {passport?.recommendation && (
        <Card className="md:col-span-2">
          <div className="text-text-muted text-xs font-mono uppercase tracking-widest mb-3 flex items-center gap-2">
            <Dna size={12} />
            Model Recommendation
          </div>
          <p className="text-text-primary leading-relaxed">{passport.recommendation}</p>
          {passport.keyStrength && (
            <div className="mt-4 flex items-start gap-2 text-sm text-brand-400">
              <span className="mt-0.5">✓</span>
              <span>{passport.keyStrength}</span>
            </div>
          )}
          {passport.mainConcern && (
            <div className="mt-2 flex items-start gap-2 text-sm text-amber-400">
              <AlertCircle size={14} className="mt-0.5 flex-shrink-0" />
              <span>{passport.mainConcern}</span>
            </div>
          )}
        </Card>
      )}
    </div>
  )
}

function PerformanceTab({ line }: { line: CandidateLine }) {
  const colors = useChartColors()
  const barData = [
    { name: 'Predicted', value: line.prediction.predictedValue, fill: '#4ade80' },
    { name: 'Observed', value: line.observedBlue ?? 0, fill: '#fbbf24' },
    { name: 'CI High', value: line.prediction.confidenceInterval[1], fill: '#4ade8060' },
    { name: 'CI Low', value: line.prediction.confidenceInterval[0], fill: '#4ade8030' },
  ]

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      <Card>
        <div className="text-text-muted text-xs font-mono uppercase tracking-widest mb-4 flex items-center gap-2">
          <TrendingUp size={12} />
          Yield Comparison
        </div>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={barData}>
            <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} />
            <XAxis dataKey="name" tick={{ fill: colors.tick, fontSize: 11 }} />
            <YAxis tick={{ fill: colors.tick, fontSize: 11 }} domain={[0, 12]} />
            <Tooltip
              contentStyle={colors.tooltip}
              formatter={(v: number) => [`${v.toFixed(2)} t/ha`]}
            />
            <Bar dataKey="value" fill="#4ade80" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </Card>

      <Card>
        <div className="text-text-muted text-xs font-mono uppercase tracking-widest mb-4">Key Statistics</div>
        <div className="space-y-4">
          <StatRow label="Predicted Yield" value={formatYield(line.prediction.predictedValue)} accent />
          <StatRow label="95% CI Lower" value={formatYield(line.prediction.confidenceInterval[0])} />
          <StatRow label="95% CI Upper" value={formatYield(line.prediction.confidenceInterval[1])} />
          {line.observedBlue && <StatRow label="Observed BLUE" value={formatYield(line.observedBlue)} />}
          {line.observedPercentile !== undefined && (
            <StatRow label="Observed Percentile" value={`${line.observedPercentile}th`} />
          )}
          {line.prediction.genomicEBV && (
            <StatRow label="Genomic EBV" value={formatYield(line.prediction.genomicEBV)} />
          )}
          {line.prediction.reliability && (
            <StatRow label="Reliability (REL)" value={`${Math.round(line.prediction.reliability * 100)}%`} />
          )}
        </div>
        <div className="mt-4 text-[10px] text-text-muted font-mono border-t border-border-subtle pt-3">
          Source: s08b_2008_blind_prediction.py · {line.prediction.modelVersion}
        </div>
      </Card>
    </div>
  )
}

function EnvFitTab({ line }: { line: CandidateLine }) {
  const passport = line.passport

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      <Card>
        <div className="text-text-muted text-xs font-mono uppercase tracking-widest mb-4 flex items-center gap-2">
          <MapPin size={12} />
          Best Environments
        </div>
        {passport?.bestEnvironments ? (
          <div className="space-y-2">
            {passport.bestEnvironments.map(env => (
              <div key={env} className="flex items-center gap-2 py-2 border-b border-border-subtle last:border-0">
                <div className="w-2 h-2 rounded-full bg-brand-400" />
                <span className="text-text-primary text-sm">{env}</span>
                <Badge variant="elite" className="ml-auto">Favorable</Badge>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-text-muted text-sm">Environment data not available.</p>
        )}
      </Card>

      <Card>
        <div className="text-text-muted text-xs font-mono uppercase tracking-widest mb-4">Environmental Scores</div>
        <div className="space-y-4">
          <div>
            <div className="flex justify-between mb-1.5">
              <span className="text-text-secondary text-sm">Environmental Fit</span>
              <span className="text-text-primary font-mono font-bold">{line.scores.environmentalFit}/100</span>
            </div>
            <ProgressBar value={line.scores.environmentalFit} color="brand" size="md" />
          </div>
          {passport?.gxeScore !== undefined && (
            <div>
              <div className="flex justify-between mb-1.5">
                <span className="text-text-secondary text-sm">GxE Interaction Score</span>
                <span className="text-text-primary font-mono font-bold">{(passport.gxeScore * 100).toFixed(0)}/100</span>
              </div>
              <ProgressBar value={passport.gxeScore * 100} color="amber" size="md" />
              <div className="text-text-muted text-xs mt-1">Higher = more environment-specific response</div>
            </div>
          )}
          <div>
            <div className="flex justify-between mb-1.5">
              <span className="text-text-secondary text-sm">Stability</span>
              <span className="text-text-primary font-mono font-bold">{line.scores.stability}/100</span>
            </div>
            <ProgressBar value={line.scores.stability} color="brand" size="md" />
          </div>
        </div>
        <div className="mt-4 text-[10px] text-text-muted font-mono border-t border-border-subtle pt-3">
          Source: s07c4_gxe_interaction.py
        </div>
      </Card>
    </div>
  )
}

function GenomicTab({ line }: { line: CandidateLine }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      <Card>
        <div className="text-text-muted text-xs font-mono uppercase tracking-widest mb-4 flex items-center gap-2">
          <Dna size={12} />
          Genomic Profile
        </div>
        <div className="space-y-4">
          <StatRow label="Genomic EBV" value={line.prediction.genomicEBV ? formatYield(line.prediction.genomicEBV) : 'N/A'} accent />
          <StatRow label="Model Confidence" value={formatConfidence(line.prediction.confidence)} />
          {line.prediction.reliability && (
            <StatRow label="Reliability (REL)" value={`${Math.round(line.prediction.reliability * 100)}%`} />
          )}
          <StatRow label="Population" value={line.population} />
          <StatRow label="Model Version" value={line.prediction.modelVersion} />
        </div>
        <div className="mt-4 p-3 bg-surface-3 rounded-lg border border-border-subtle">
          <div className="text-text-muted text-[10px] font-mono uppercase tracking-wider mb-1">Note</div>
          <p className="text-text-secondary text-xs leading-relaxed">
            Genomic predictions use Ridge regression on {line.population === 'C1' ? '2,911' : '2,911'} SNP markers.
            Reliability reflects the fraction of genetic variance captured. Higher reliability indicates more precise estimation.
          </p>
        </div>
        <div className="mt-3 text-[10px] text-text-muted font-mono">
          Source: s07b3_genomic_ridge.py
        </div>
      </Card>

      <Card>
        <div className="text-text-muted text-xs font-mono uppercase tracking-widest mb-4">Confidence Interval</div>
        <div className="flex items-center justify-center h-40">
          <div className="relative w-full max-w-xs">
            <div className="h-3 bg-surface-4 rounded-full relative">
              <div
                className="absolute h-full bg-brand-400/20 rounded-full"
                style={{
                  left: `${(line.prediction.confidenceInterval[0] / 12) * 100}%`,
                  right: `${100 - (line.prediction.confidenceInterval[1] / 12) * 100}%`,
                }}
              />
              <div
                className="absolute top-1/2 -translate-y-1/2 w-4 h-4 bg-brand-400 rounded-full border-2 border-surface-0 shadow-lg shadow-brand-400/30"
                style={{ left: `calc(${(line.prediction.predictedValue / 12) * 100}% - 8px)` }}
              />
            </div>
            <div className="flex justify-between mt-2 text-text-muted text-xs font-mono">
              <span>0</span>
              <span>6</span>
              <span>12 t/ha</span>
            </div>
            <div className="text-center mt-4">
              <div className="text-brand-400 text-xl font-black">{formatYield(line.prediction.predictedValue)}</div>
              <div className="text-text-muted text-xs mt-1">
                95% CI: {formatYield(line.prediction.confidenceInterval[0])} – {formatYield(line.prediction.confidenceInterval[1])}
              </div>
            </div>
          </div>
        </div>
      </Card>
    </div>
  )
}

function SimilarLinesTab({ line }: { line: CandidateLine }) {
  const navigate = useNavigate()
  const similar = line.passport?.similarLines ?? []

  return (
    <Card>
      <div className="text-text-muted text-xs font-mono uppercase tracking-widest mb-4 flex items-center gap-2">
        <Network size={12} />
        Genetically Similar Lines
      </div>
      {similar.length > 0 ? (
        <div className="space-y-2">
          {similar.map(sid => (
            <div
              key={sid}
              onClick={() => navigate(`/lines/${sid}`)}
              className="flex items-center justify-between py-3 px-4 bg-surface-3 rounded-lg border border-border-subtle hover:border-border-default cursor-pointer transition-colors group"
            >
              <span className="text-text-primary font-mono font-bold group-hover:text-brand-400 transition-colors">{sid}</span>
              <span className="text-text-muted text-xs">View Passport →</span>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-8">
          <div className="text-text-muted text-sm mb-2">Similarity data not available for this line.</div>
          <div className="text-text-muted text-xs font-mono">Future: genetic distance matrix from s07b3 outputs</div>
        </div>
      )}
      <div className="mt-4 text-[10px] text-text-muted font-mono border-t border-border-subtle pt-3">
        Similarity based on genomic marker overlap
      </div>
    </Card>
  )
}

function StatRow({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-border-subtle last:border-0">
      <span className="text-text-secondary text-sm">{label}</span>
      <span className={cn('text-sm font-mono font-bold', accent ? 'text-brand-400' : 'text-text-primary')}>{value}</span>
    </div>
  )
}
