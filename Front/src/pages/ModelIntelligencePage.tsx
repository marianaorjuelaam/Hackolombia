import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { useChartColors } from '@/hooks/useChartColors'
import { Brain, Activity, BarChart2, Shield, Clock, Globe, Dna } from 'lucide-react'
import { predictionService } from '@/services/predictionService'
import type { ModelMetrics } from '@/types'
import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { ProgressBar } from '@/components/ui/ProgressBar'
import { brand } from '@/config/brand'
import { cn } from '@/lib/utils'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  ScatterChart, Scatter, ReferenceLine, Line, LineChart, Legend
} from 'recharts'

export default function ModelIntelligencePage() {
  const [metrics, setMetrics] = useState<ModelMetrics | null>(null)
  const colors = useChartColors()

  useEffect(() => {
    predictionService.getModelMetrics().then(setMetrics)
  }, [])

  if (!metrics) return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="text-text-muted text-sm font-mono">Loading model metrics...</div>
    </div>
  )

  const popData = Object.values(metrics.populationMetrics).map(p => ({
    name: p.population,
    r: +p.pearsonR.toFixed(2),
    rmse: +p.rmse.toFixed(2),
    coverage: +(p.coverage * 100).toFixed(0),
    n: p.n,
  }))

  // Simulated validation curve data
  const validationData = [
    { year: '2003', train: 0.71, val: null },
    { year: '2004', train: 0.73, val: null },
    { year: '2005', train: 0.75, val: null },
    { year: '2006', train: 0.74, val: 0.69 },
    { year: '2007', train: 0.76, val: 0.71 },
    { year: '2008', train: null, val: 0.73 },
  ]

  const metricCards = [
    {
      icon: Activity,
      label: 'Pearson r',
      value: metrics.pearsonR.toFixed(2),
      sub: 'Temporal validation',
      desc: 'Correlation between predicted and observed yield',
      color: 'text-brand-400',
    },
    {
      icon: BarChart2,
      label: 'RMSE',
      value: `${metrics.rmse.toFixed(2)} t/ha`,
      sub: 'Root Mean Square Error',
      desc: 'Average prediction error on validation set',
      color: 'text-text-primary',
    },
    {
      icon: BarChart2,
      label: 'MAE',
      value: `${metrics.mae.toFixed(2)} t/ha`,
      sub: 'Mean Absolute Error',
      desc: 'Median prediction error — robust to outliers',
      color: 'text-text-primary',
    },
    {
      icon: Shield,
      label: 'Training Coverage',
      value: `${(metrics.trainingCoverage * 100).toFixed(0)}%`,
      sub: 'Lines with genomic data',
      desc: 'Fraction of candidates with complete SNP marker profile',
      color: 'text-brand-400',
    },
    {
      icon: Clock,
      label: 'Temporal Validation r',
      value: metrics.temporalValidationR?.toFixed(2) ?? 'N/A',
      sub: '2006-2007 → 2008 hold-out',
      desc: 'Prediction accuracy in forward time validation',
      color: 'text-text-primary',
    },
    {
      icon: Globe,
      label: 'Location Generalization r',
      value: metrics.locationGeneralizationR?.toFixed(2) ?? 'N/A',
      sub: 'Leave-one-location-out',
      desc: 'Prediction accuracy when training excludes target environment',
      color: 'text-text-primary',
    },
  ]

  return (
    <div className="min-h-screen bg-surface-0 px-4 md:px-8 py-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-10">
          <div className="flex items-center gap-2 mb-3">
            <Brain size={16} className="text-brand-400" />
            <span className="text-brand-400 text-xs font-mono tracking-widest uppercase">Model Intelligence</span>
          </div>
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
            <div>
              <h1 className="text-3xl md:text-4xl font-black text-text-primary mb-2">{brand.copy.intelligenceHeadline}</h1>
              <p className="text-text-secondary">{brand.copy.intelligenceSub}</p>
            </div>
            <div className="flex items-center gap-3">
              <Badge variant="mock">DEMO DATA</Badge>
              <div className="text-text-muted text-xs font-mono">
                v{metrics.modelVersion}
              </div>
            </div>
          </div>
        </div>

        {/* Model summary */}
        <div className="bg-surface-2 border border-border-default rounded-xl p-5 mb-8">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            <div>
              <div className="text-text-muted text-[10px] font-mono uppercase tracking-wider mb-1">Model</div>
              <div className="text-text-primary font-mono font-bold">Ridge Regression</div>
              <div className="text-text-muted text-xs">Genomic BLUP</div>
            </div>
            <div>
              <div className="text-text-muted text-[10px] font-mono uppercase tracking-wider mb-1">Version</div>
              <div className="text-text-primary font-mono font-bold">{metrics.modelVersion}</div>
            </div>
            <div>
              <div className="text-text-muted text-[10px] font-mono uppercase tracking-wider mb-1">Validation</div>
              <div className="text-text-primary font-mono text-sm leading-tight">{metrics.validationStrategy.split(' + ')[0]}</div>
            </div>
            <div>
              <div className="text-text-muted text-[10px] font-mono uppercase tracking-wider mb-1">Markers</div>
              <div className="text-text-primary font-mono font-bold">2,911 SNPs</div>
              <div className="text-text-muted text-xs">Post-QC</div>
            </div>
          </div>
        </div>

        {/* Metric cards */}
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-8">
          {metricCards.map((m, i) => (
            <motion.div
              key={m.label}
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.07 }}
            >
              <Card className="h-full">
                <div className="flex items-start gap-3 mb-3">
                  <div className="w-8 h-8 rounded-lg bg-surface-3 flex items-center justify-center flex-shrink-0">
                    <m.icon size={14} className={m.color} />
                  </div>
                  <div>
                    <div className="text-text-muted text-[10px] font-mono uppercase tracking-wider">{m.label}</div>
                    <div className={cn('text-2xl font-black tabular-nums mt-1', m.color)}>{m.value}</div>
                  </div>
                </div>
                <div className="text-text-secondary text-xs leading-relaxed">{m.desc}</div>
                <div className="text-text-muted text-[10px] font-mono mt-2">{m.sub}</div>
              </Card>
            </motion.div>
          ))}
        </div>

        {/* Charts row */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          {/* Per-population */}
          <Card>
            <div className="text-text-muted text-xs font-mono uppercase tracking-widest mb-4 flex items-center gap-2">
              <Dna size={12} />
              Performance by Population
            </div>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={popData}>
                <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} />
                <XAxis dataKey="name" tick={{ fill: colors.tick, fontSize: 11 }} />
                <YAxis tick={{ fill: colors.tick, fontSize: 11 }} domain={[0, 1]} />
                <Tooltip contentStyle={colors.tooltip} />
                <Bar dataKey="r" fill="#4ade80" name="Pearson r" radius={[4, 4, 0, 0]} />
                <Bar dataKey="rmse" fill="#fbbf24" name="RMSE" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
            <div className="text-text-muted text-[10px] font-mono mt-3">
              Source: s07b3 temporal validation · DEMO DATA
            </div>
          </Card>

          {/* Validation curve */}
          <Card>
            <div className="text-text-muted text-xs font-mono uppercase tracking-widest mb-4 flex items-center gap-2">
              <Clock size={12} />
              Temporal Validation
            </div>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={validationData}>
                <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} />
                <XAxis dataKey="year" tick={{ fill: colors.tick, fontSize: 11 }} />
                <YAxis tick={{ fill: colors.tick, fontSize: 11 }} domain={[0.5, 0.9]} />
                <Tooltip contentStyle={colors.tooltip} />
                <Legend wrapperStyle={{ fontSize: 11, color: colors.legend }} />
                <Line type="monotone" dataKey="train" stroke="#4ade80" name="Train r" dot={false} strokeWidth={2} connectNulls />
                <Line type="monotone" dataKey="val" stroke="#fbbf24" name="Validation r" dot={true} strokeWidth={2} connectNulls />
              </LineChart>
            </ResponsiveContainer>
            <div className="text-text-muted text-[10px] font-mono mt-3">
              Forward time validation: train on t–1, predict t · DEMO DATA
            </div>
          </Card>
        </div>

        {/* Per-population detail */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
          {Object.values(metrics.populationMetrics).map(pop => (
            <Card key={pop.population}>
              <div className="flex items-center justify-between mb-4">
                <div>
                  <div className="text-text-muted text-[10px] font-mono uppercase tracking-wider mb-1">Population</div>
                  <div className="text-text-primary font-black text-xl font-mono">{pop.population}</div>
                </div>
                <div className="text-right">
                  <div className="text-brand-400 text-2xl font-black tabular-nums">r = {pop.pearsonR.toFixed(2)}</div>
                  <div className="text-text-muted text-xs font-mono">{pop.n} lines</div>
                </div>
              </div>
              <div className="space-y-3">
                <div>
                  <div className="flex justify-between mb-1.5">
                    <span className="text-text-secondary text-xs">Genomic Coverage</span>
                    <span className="text-text-primary text-xs font-mono font-bold">{(pop.coverage * 100).toFixed(0)}%</span>
                  </div>
                  <ProgressBar value={pop.coverage * 100} color={pop.coverage > 0.85 ? 'brand' : 'amber'} size="md" />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <div className="text-text-muted text-[10px] font-mono uppercase">RMSE</div>
                    <div className="text-text-primary font-mono font-bold">{pop.rmse.toFixed(2)} t/ha</div>
                  </div>
                  <div>
                    <div className="text-text-muted text-[10px] font-mono uppercase">Pearson r</div>
                    <div className="text-text-primary font-mono font-bold">{pop.pearsonR.toFixed(2)}</div>
                  </div>
                </div>
              </div>
            </Card>
          ))}
        </div>

        {/* Pipeline description */}
        <div className="bg-surface-2 border border-border-subtle rounded-xl p-6">
          <div className="text-text-muted text-xs font-mono uppercase tracking-widest mb-4">Pipeline Architecture</div>
          <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
            {[
              { step: 's01–s04', label: 'Data Cleaning & BLUEs', desc: 'Phenotype cleaning, genotype encoding, BLUE estimation' },
              { step: 's05', label: 'CV Baselines', desc: 'Cross-validation benchmarks for model comparison' },
              { step: 's06–s07', label: 'Genomic Audit', desc: 'Coverage, integrity, Ridge regression predictions' },
              { step: 's08a–e', label: 'Candidate Universe', desc: 'Blind prediction, family scores, budget allocation' },
              { step: 's08f', label: 'Allocation Engine', desc: 'Cultiva allocation engine — cohort optimization' },
            ].map((s, i) => (
              <div key={s.step} className="bg-surface-3 rounded-lg p-3 relative">
                {i < 4 && (
                  <div className="hidden md:block absolute -right-1.5 top-1/2 -translate-y-1/2 text-text-muted z-10">›</div>
                )}
                <div className="text-brand-400/60 text-[10px] font-mono mb-1">{s.step}</div>
                <div className="text-text-primary text-xs font-semibold mb-1">{s.label}</div>
                <div className="text-text-muted text-[10px] leading-tight">{s.desc}</div>
              </div>
            ))}
          </div>
          <div className="mt-4 text-[10px] text-text-muted font-mono">
            All metrics shown are DEMO DATA · Real model outputs will replace mock data via API integration
          </div>
        </div>
      </div>
    </div>
  )
}
