import { useEffect, useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Gem, TrendingUp, Dna, ArrowRight, AlertTriangle } from 'lucide-react'
import { candidateService } from '@/services/candidateService'
import { ALL_CANDIDATES } from '@/data/mockCandidates'
import type { HiddenGem, HiddenGemTag } from '@/types'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { brand } from '@/config/brand'
import { cn } from '@/lib/utils'

type TagFilter = 'all' | HiddenGemTag

const TAG_LABELS: Record<HiddenGemTag, string> = {
  high_potential: 'High Potential',
  underperforming_observed: 'Underperforming Observed',
  novel_genetics: 'Novel Genetics',
  high_uncertainty: 'High Uncertainty',
}

export default function HiddenGemsPage() {
  const navigate = useNavigate()
  const [gems, setGems] = useState<HiddenGem[]>([])
  const [filter, setFilter] = useState<TagFilter>('all')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    candidateService.getHiddenGems().then(g => {
      setGems(g)
      setLoading(false)
    })
  }, [])

  const filtered = useMemo(() => {
    if (filter === 'all') return gems
    return gems.filter(g => g.tags.includes(filter))
  }, [gems, filter])

  const filters: TagFilter[] = ['all', 'high_potential', 'underperforming_observed', 'novel_genetics', 'high_uncertainty']

  return (
    <div className="min-h-screen bg-surface-0 px-4 md:px-8 py-8">
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="mb-10">
          <div className="flex items-center gap-2 mb-3">
            <Gem size={16} className="text-amber-400" />
            <span className="text-amber-400 text-xs font-mono tracking-widest uppercase">Hidden Gems</span>
          </div>
          <h1 className="text-3xl md:text-5xl font-black text-text-primary mb-4 leading-tight">
            {brand.copy.gemsHeadline}
          </h1>
          <p className="text-text-secondary text-lg max-w-2xl leading-relaxed">
            {brand.copy.gemsSub}
          </p>

          {/* Explainer */}
          <div className="mt-6 bg-amber-400/5 border border-amber-400/20 rounded-xl p-5 max-w-2xl">
            <div className="flex items-start gap-3">
              <AlertTriangle size={16} className="text-amber-400 mt-0.5 flex-shrink-0" />
              <div>
                <div className="text-amber-400 text-xs font-mono font-bold uppercase tracking-wider mb-1">
                  Definition
                </div>
                <p className="text-text-secondary text-sm leading-relaxed">
                  A hidden gem is a candidate whose <strong className="text-text-primary">genomic prediction rank</strong> substantially
                  exceeds its <strong className="text-text-primary">observed phenotypic rank</strong>.
                  Traditional selection methods may eliminate these lines too early.
                  The model suggests they carry genetic potential not fully expressed in historical trials.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap gap-2 mb-8">
          {filters.map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={cn(
                'px-4 py-2 text-xs font-mono rounded-lg border transition-all',
                filter === f
                  ? 'bg-amber-400/10 text-amber-400 border-amber-400/25'
                  : 'bg-surface-2 text-text-muted border-border-default hover:text-text-secondary'
              )}
            >
              {f === 'all' ? `All (${gems.length})` : `${TAG_LABELS[f as HiddenGemTag]}`}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="text-text-muted text-sm font-mono">Loading gems...</div>
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {filtered.map((gem, i) => (
                <motion.div
                  key={gem.lineId}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.08 }}
                >
                  <GemCard gem={gem} onView={() => navigate(`/lines/${gem.lineId}`)} />
                </motion.div>
              ))}
            </div>

            {filtered.length === 0 && (
              <div className="text-center py-16 text-text-muted">
                <Gem size={32} className="mx-auto mb-4 opacity-30" />
                <p>No gems match this filter.</p>
              </div>
            )}

            {/* Footer note */}
            <div className="mt-10 p-4 bg-surface-2 border border-border-subtle rounded-xl">
              <div className="text-text-muted text-xs font-mono">
                Hidden gem identification based on gap between genomic prediction percentile and observed BLUE percentile · Source: s07b3 + s04 outputs
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function GemCard({ gem, onView }: { gem: HiddenGem; onView: () => void }) {
  const line = ALL_CANDIDATES.find(c => c.id === gem.lineId)
  const gap = gem.potentialGap

  return (
    <div className="bg-surface-2 border border-border-subtle rounded-2xl overflow-hidden hover:border-amber-400/20 transition-all duration-200 group">
      {/* Top accent */}
      <div className="h-0.5 bg-gradient-to-r from-amber-400/60 via-amber-400/20 to-transparent" />

      <div className="p-6">
        {/* Header */}
        <div className="flex items-start justify-between mb-5">
          <div>
            <div className="text-text-muted text-[10px] font-mono tracking-widest uppercase mb-1">
              {line?.population ?? 'C2'} · Family {line?.family ?? '—'}
            </div>
            <h3 className="text-2xl font-black text-text-primary font-mono group-hover:text-amber-400 transition-colors">
              {gem.lineId}
            </h3>
          </div>
          <Badge variant="gem">◆ HIDDEN GEM</Badge>
        </div>

        {/* The gap visualization */}
        <div className="mb-5">
          <div className="flex items-end gap-6 mb-3">
            {/* Observed */}
            <div className="flex-1">
              <div className="text-text-muted text-[10px] font-mono uppercase tracking-wider mb-2">Observed Performance</div>
              <div className="flex items-end gap-2">
                <div className="text-2xl font-black text-text-secondary tabular-nums">{gem.observedPercentile}</div>
                <div className="text-text-muted text-xs mb-1 font-mono">th pct.</div>
              </div>
              <div className="h-2 bg-surface-4 rounded-full mt-2">
                <div
                  className="h-full bg-text-secondary/40 rounded-full transition-all duration-700"
                  style={{ width: `${gem.observedPercentile}%` }}
                />
              </div>
            </div>

            {/* Arrow */}
            <div className="pb-4">
              <ArrowRight size={16} className="text-amber-400" />
            </div>

            {/* Genomic */}
            <div className="flex-1">
              <div className="text-amber-400 text-[10px] font-mono uppercase tracking-wider mb-2">Genomic Potential</div>
              <div className="flex items-end gap-2">
                <div className="text-2xl font-black text-amber-400 tabular-nums">{gem.genomicPercentile}</div>
                <div className="text-amber-400/60 text-xs mb-1 font-mono">th pct.</div>
              </div>
              <div className="h-2 bg-surface-4 rounded-full mt-2">
                <div
                  className="h-full bg-amber-400 rounded-full transition-all duration-700"
                  style={{ width: `${gem.genomicPercentile}%` }}
                />
              </div>
            </div>
          </div>

          {/* Gap badge */}
          <div className="flex items-center gap-2 mt-2">
            <div className={cn(
              'text-xs font-mono font-bold px-2 py-1 rounded border',
              gap >= 30 ? 'bg-amber-400/15 text-amber-400 border-amber-400/25' : 'bg-surface-3 text-text-secondary border-border-default'
            )}>
              +{gap}pt potential gap
            </div>
            <div className="flex items-center gap-1">
              <TrendingUp size={11} className="text-amber-400" />
              <span className="text-text-muted text-xs">{gap >= 30 ? 'Significant' : 'Moderate'} undervaluation</span>
            </div>
          </div>
        </div>

        {/* Rationale */}
        <p className="text-text-secondary text-sm leading-relaxed mb-4">
          {gem.rationale}
        </p>

        {/* Tags */}
        <div className="flex flex-wrap gap-1.5 mb-4">
          {gem.tags.map(tag => (
            <span
              key={tag}
              className={cn(
                'text-[10px] font-mono px-2 py-0.5 rounded border',
                tag === 'high_potential' && 'bg-brand-400/10 text-brand-400 border-brand-400/15',
                tag === 'underperforming_observed' && 'bg-amber-400/10 text-amber-400/80 border-amber-400/15',
                tag === 'novel_genetics' && 'bg-purple-400/10 text-purple-400 border-purple-400/15',
                tag === 'high_uncertainty' && 'bg-orange-400/10 text-orange-400 border-orange-400/15',
              )}
            >
              {TAG_LABELS[tag]}
            </span>
          ))}
        </div>

        {/* Action */}
        <Button variant="ghost" size="sm" className="w-full justify-center border border-border-subtle hover:border-amber-400/20 hover:text-amber-400" onClick={onView}>
          <Dna size={13} />
          View Breeding Passport
        </Button>
      </div>
    </div>
  )
}
