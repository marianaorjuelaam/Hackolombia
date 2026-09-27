import { useEffect, useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Search, Filter, ArrowUpDown, Dna } from 'lucide-react'
import { candidateService } from '@/services/candidateService'
import type { CandidateLine } from '@/types'
import { Badge } from '@/components/ui/Badge'
import { ProgressBar } from '@/components/ui/ProgressBar'
import { cn, formatYield, formatConfidence, statusBg, statusLabel } from '@/lib/utils'

type SortKey = 'id' | 'predictedValue' | 'confidence' | 'overallScore' | 'observedPercentile'

export default function LinesPage() {
  const navigate = useNavigate()
  const [all, setAll] = useState<CandidateLine[]>([])
  const [search, setSearch] = useState('')
  const [popFilter, setPopFilter] = useState<'all' | 'C1' | 'C2'>('all')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [sortKey, setSortKey] = useState<SortKey>('overallScore')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  const [page, setPage] = useState(0)
  const PAGE_SIZE = 20

  useEffect(() => {
    candidateService.getCandidates().then(setAll)
  }, [])

  const filtered = useMemo(() => {
    let list = all

    if (search) {
      const q = search.toLowerCase()
      list = list.filter(l => l.id.toLowerCase().includes(q) || l.family?.toLowerCase().includes(q))
    }
    if (popFilter !== 'all') list = list.filter(l => l.population === popFilter)
    if (statusFilter !== 'all') list = list.filter(l => l.status === statusFilter)

    list = [...list].sort((a, b) => {
      let av = 0, bv = 0
      switch (sortKey) {
        case 'id': return sortDir === 'asc' ? a.id.localeCompare(b.id) : b.id.localeCompare(a.id)
        case 'predictedValue': av = a.prediction.predictedValue; bv = b.prediction.predictedValue; break
        case 'confidence': av = a.prediction.confidence; bv = b.prediction.confidence; break
        case 'overallScore': av = a.scores.overallScore; bv = b.scores.overallScore; break
        case 'observedPercentile': av = a.observedPercentile ?? 0; bv = b.observedPercentile ?? 0; break
      }
      return sortDir === 'asc' ? av - bv : bv - av
    })

    return list
  }, [all, search, popFilter, statusFilter, sortKey, sortDir])

  const paginated = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)
  const totalPages = Math.ceil(filtered.length / PAGE_SIZE)

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('desc') }
    setPage(0)
  }

  const statuses = ['all', 'elite', 'promising', 'hidden_gem', 'watch', 'uncertain']

  return (
    <div className="min-h-screen bg-surface-0 px-4 md:px-8 py-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="text-brand-400 text-xs font-mono tracking-widest uppercase mb-2">Candidate Lines</div>
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
            <div>
              <h1 className="text-2xl md:text-3xl font-black text-text-primary">
                {all.length.toLocaleString()} Candidates
              </h1>
              <p className="text-text-secondary text-sm mt-1">
                {filtered.length} matching · Page {page + 1} of {totalPages}
              </p>
            </div>
            <div className="flex items-center gap-2 text-text-muted text-xs font-mono">
              <Dna size={12} />
              Ridge regression predictions
            </div>
          </div>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap gap-3 mb-6">
          {/* Search */}
          <div className="relative flex-1 min-w-48">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
            <input
              type="text"
              placeholder="Search by line ID or family..."
              value={search}
              onChange={e => { setSearch(e.target.value); setPage(0) }}
              className="w-full bg-surface-2 border border-border-default text-text-primary text-sm rounded-lg py-2.5 pl-9 pr-4 placeholder-text-muted focus:outline-none focus:border-brand-400/50 transition-colors"
            />
          </div>

          {/* Population filter */}
          <div className="flex items-center gap-1 bg-surface-2 border border-border-default rounded-lg p-1">
            {(['all', 'C1', 'C2'] as const).map(p => (
              <button
                key={p}
                onClick={() => { setPopFilter(p); setPage(0) }}
                className={cn(
                  'px-3 py-1.5 text-xs font-mono rounded-md transition-colors',
                  popFilter === p ? 'bg-brand-400/15 text-brand-400' : 'text-text-muted hover:text-text-secondary'
                )}
              >
                {p === 'all' ? 'All Pops.' : p}
              </button>
            ))}
          </div>

          {/* Status filter */}
          <div className="flex items-center gap-1 bg-surface-2 border border-border-default rounded-lg p-1 overflow-x-auto">
            {statuses.map(s => (
              <button
                key={s}
                onClick={() => { setStatusFilter(s); setPage(0) }}
                className={cn(
                  'px-3 py-1.5 text-xs font-mono rounded-md transition-colors whitespace-nowrap',
                  statusFilter === s ? 'bg-brand-400/15 text-brand-400' : 'text-text-muted hover:text-text-secondary'
                )}
              >
                {s === 'all' ? 'All Status' : statusLabel(s)}
              </button>
            ))}
          </div>
        </div>

        {/* Table */}
        <div className="bg-surface-2 border border-border-subtle rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border-subtle">
                  {[
                    { key: 'id' as SortKey, label: 'Line ID', width: 'w-32' },
                    { key: null, label: 'Pop.', width: 'w-16' },
                    { key: null, label: 'Status', width: 'w-32' },
                    { key: 'predictedValue' as SortKey, label: 'Predicted Yield', width: 'w-32' },
                    { key: 'confidence' as SortKey, label: 'Confidence', width: 'w-28' },
                    { key: 'observedPercentile' as SortKey, label: 'Obs. Pct.', width: 'w-24' },
                    { key: 'overallScore' as SortKey, label: 'Score', width: 'w-32' },
                    { key: null, label: 'AI Rec.', width: 'w-24' },
                  ].map(col => (
                    <th
                      key={col.label}
                      className={cn(
                        'text-left px-4 py-3 text-text-muted text-xs font-mono uppercase tracking-wider',
                        col.key && 'cursor-pointer hover:text-text-secondary select-none',
                        col.width
                      )}
                      onClick={() => col.key && toggleSort(col.key)}
                    >
                      <span className="flex items-center gap-1">
                        {col.label}
                        {col.key && sortKey === col.key && (
                          <ArrowUpDown size={10} className="text-brand-400" />
                        )}
                      </span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {paginated.map((line, i) => (
                  <motion.tr
                    key={line.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: i * 0.015 }}
                    onClick={() => navigate(`/lines/${line.id}`)}
                    className="border-b border-border-subtle/50 hover:bg-surface-3 cursor-pointer transition-colors group"
                  >
                    <td className="px-4 py-3">
                      <span className="text-text-primary font-mono font-bold text-sm group-hover:text-brand-400 transition-colors">
                        {line.id}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-text-muted text-xs font-mono">{line.population}</span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={cn('text-xs px-2 py-0.5 rounded border font-mono', statusBg(line.status))}>
                        {statusLabel(line.status)}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-text-primary text-sm font-mono tabular-nums">
                        {formatYield(line.prediction.predictedValue)}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <ProgressBar
                          value={line.prediction.confidence * 100}
                          size="sm"
                          color={line.prediction.confidence >= 0.80 ? 'brand' : line.prediction.confidence >= 0.60 ? 'amber' : 'neutral'}
                          className="w-16"
                        />
                        <span className="text-text-secondary text-xs font-mono tabular-nums">
                          {formatConfidence(line.prediction.confidence)}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-text-secondary text-xs font-mono tabular-nums">
                        {line.observedPercentile !== undefined ? `${line.observedPercentile}th` : '—'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <ProgressBar
                          value={line.scores.overallScore}
                          size="sm"
                          color={line.scores.overallScore >= 80 ? 'brand' : line.scores.overallScore >= 60 ? 'amber' : 'neutral'}
                          className="w-16"
                        />
                        <span className="text-text-primary text-xs font-mono font-bold tabular-nums">
                          {line.scores.overallScore}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className={cn(
                        'text-xs font-mono font-bold uppercase',
                        line.aiRecommendation === 'advance' ? 'text-brand-400' :
                        line.aiRecommendation === 'watch' ? 'text-amber-400' : 'text-red-400'
                      )}>
                        {line.aiRecommendation}
                      </span>
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between px-4 py-3 border-t border-border-subtle">
            <span className="text-text-muted text-xs font-mono">
              {filtered.length} results · showing {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, filtered.length)}
            </span>
            <div className="flex items-center gap-2">
              <button
                disabled={page === 0}
                onClick={() => setPage(p => p - 1)}
                className="px-3 py-1.5 text-xs bg-surface-3 border border-border-default rounded-lg text-text-secondary hover:text-text-primary disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                Previous
              </button>
              <span className="text-text-muted text-xs font-mono">{page + 1} / {totalPages}</span>
              <button
                disabled={page >= totalPages - 1}
                onClick={() => setPage(p => p + 1)}
                className="px-3 py-1.5 text-xs bg-surface-3 border border-border-default rounded-lg text-text-secondary hover:text-text-primary disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                Next
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
