import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowRight, Dna, TrendingUp, Target, ChevronDown } from 'lucide-react'
import { brand } from '@/config/brand'
import { Button } from '@/components/ui/Button'

// Animated counter
function AnimatedNumber({ target, duration = 1500 }: { target: number; duration?: number }) {
  const [val, setVal] = useState(0)
  const started = useRef(false)
  const ref = useRef<HTMLSpanElement>(null)

  useEffect(() => {
    const observer = new IntersectionObserver(entries => {
      if (entries[0].isIntersecting && !started.current) {
        started.current = true
        const start = Date.now()
        const tick = () => {
          const elapsed = Date.now() - start
          const progress = Math.min(elapsed / duration, 1)
          const eased = 1 - Math.pow(1 - progress, 3)
          setVal(Math.round(eased * target))
          if (progress < 1) requestAnimationFrame(tick)
        }
        requestAnimationFrame(tick)
      }
    }, { threshold: 0.5 })
    if (ref.current) observer.observe(ref.current)
    return () => observer.disconnect()
  }, [target, duration])

  return <span ref={ref}>{val.toLocaleString()}</span>
}

// Genomic dot visualization
function GenomicViz() {
  const dots = Array.from({ length: 60 }, (_, i) => ({
    id: i,
    x: 10 + (i % 10) * 9,
    y: 10 + Math.floor(i / 10) * 14,
    active: Math.random() > 0.4,
    delay: Math.random() * 2,
  }))

  return (
    <div className="relative w-full h-full flex items-center justify-center overflow-hidden">
      {/* Background glow */}
      <div className="absolute inset-0 bg-gradient-radial from-brand-400/5 via-transparent to-transparent" />

      {/* Pipeline flow */}
      <div className="relative flex items-center gap-8 md:gap-16">
        {/* Genomic markers */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.3, duration: 0.8 }}
          className="flex flex-col items-center gap-3"
        >
          <div className="grid grid-cols-6 gap-1">
            {Array.from({ length: 36 }, (_, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0 }}
                animate={{ opacity: i % 3 === 0 ? 0.9 : 0.2 + Math.random() * 0.4 }}
                transition={{ delay: 0.5 + i * 0.02, duration: 0.3 }}
                className={`w-2.5 h-2.5 rounded-sm ${i % 3 === 0 ? 'bg-brand-400' : 'bg-surface-3'}`}
              />
            ))}
          </div>
          <span className="text-text-muted text-[10px] tracking-widest uppercase font-mono">2,911 Markers</span>
        </motion.div>

        {/* Arrow 1 */}
        <motion.div
          initial={{ opacity: 0, scaleX: 0 }}
          animate={{ opacity: 1, scaleX: 1 }}
          transition={{ delay: 1, duration: 0.5 }}
          className="flex flex-col items-center gap-1"
        >
          <div className="flex items-center">
            <div className="w-12 h-px bg-gradient-to-r from-brand-400/20 to-brand-400/60" />
            <ArrowRight size={12} className="text-brand-400/60 -ml-1" />
          </div>
          <span className="text-text-muted text-[9px] tracking-widest uppercase font-mono whitespace-nowrap">Ridge Model</span>
        </motion.div>

        {/* AI prediction brain */}
        <motion.div
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 1.3, duration: 0.6 }}
          className="flex flex-col items-center gap-3"
        >
          <div className="relative w-14 h-14 rounded-full border border-brand-400/30 bg-brand-400/5 flex items-center justify-center">
            <Dna size={24} className="text-brand-400/80" />
            <motion.div
              animate={{ scale: [1, 1.15, 1] }}
              transition={{ duration: 2, repeat: Infinity }}
              className="absolute inset-0 rounded-full border border-brand-400/15"
            />
          </div>
          <span className="text-text-muted text-[10px] tracking-widest uppercase font-mono">Genomic AI</span>
        </motion.div>

        {/* Arrow 2 */}
        <motion.div
          initial={{ opacity: 0, scaleX: 0 }}
          animate={{ opacity: 1, scaleX: 1 }}
          transition={{ delay: 1.8, duration: 0.5 }}
          className="flex flex-col items-center gap-1"
        >
          <div className="flex items-center">
            <div className="w-12 h-px bg-gradient-to-r from-brand-400/60 to-brand-400/20" />
            <ArrowRight size={12} className="text-brand-400/60 -ml-1" />
          </div>
          <span className="text-text-muted text-[9px] tracking-widest uppercase font-mono whitespace-nowrap">Decision</span>
        </motion.div>

        {/* Field decision */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 2.1, duration: 0.8 }}
          className="flex flex-col items-center gap-3"
        >
          <div className="flex flex-col gap-1">
            {['ADVANCE', 'WATCH', 'DROP'].map((label, i) => (
              <motion.div
                key={label}
                initial={{ opacity: 0, x: 10 }}
                animate={{ opacity: i === 0 ? 1 : 0.35, x: 0 }}
                transition={{ delay: 2.3 + i * 0.15 }}
                className={`px-3 py-1 rounded text-[10px] font-mono font-bold tracking-widest border ${
                  i === 0
                    ? 'bg-brand-400/15 text-brand-400 border-brand-400/25'
                    : i === 1
                    ? 'bg-amber-400/10 text-amber-400/60 border-amber-400/15'
                    : 'bg-red-400/10 text-red-400/50 border-red-400/15'
                }`}
              >
                {label}
              </motion.div>
            ))}
          </div>
          <span className="text-text-muted text-[10px] tracking-widest uppercase font-mono">Field Action</span>
        </motion.div>
      </div>
    </div>
  )
}

// Decision flow visual
function DecisionFlow() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.6, duration: 0.8 }}
      className="flex flex-col items-center gap-2"
    >
      <div className="flex items-center gap-4 md:gap-8">
        {/* 500 candidates */}
        <div className="flex flex-col items-center gap-1">
          <div className="text-4xl md:text-6xl font-black text-text-primary tabular-nums leading-none">
            <AnimatedNumber target={500} />
          </div>
          <div className="text-text-muted text-xs tracking-widest uppercase font-mono">Candidate Lines</div>
        </div>

        {/* Arrow */}
        <div className="flex flex-col items-center gap-1">
          <div className="flex flex-col items-center">
            <div className="w-px h-6 bg-gradient-to-b from-transparent to-brand-400/60" />
            <div className="w-3 h-px bg-brand-400/60" />
            <div className="w-px h-6 bg-gradient-to-b from-brand-400/60 to-transparent" />
          </div>
          <div className="text-text-muted text-[9px] tracking-wider uppercase font-mono mt-1">AI Filter</div>
        </div>

        {/* 50 slots */}
        <div className="flex flex-col items-center gap-1">
          <div className="text-4xl md:text-6xl font-black text-brand-400 tabular-nums leading-none">
            <AnimatedNumber target={50} duration={1000} />
          </div>
          <div className="text-text-muted text-xs tracking-widest uppercase font-mono">Can Advance</div>
        </div>

        {/* Question */}
        <div className="hidden md:flex flex-col items-center gap-1 ml-4">
          <div className="text-4xl font-black text-text-secondary leading-none">?</div>
          <div className="text-text-muted text-xs tracking-widest uppercase font-mono">Which ones</div>
        </div>
      </div>
    </motion.div>
  )
}

export default function HomePage() {
  const navigate = useNavigate()

  const stats = [
    { icon: Dna, label: 'Genomic Markers', value: '2,911', sub: 'Ridge regression model' },
    { icon: TrendingUp, label: 'Prediction Accuracy', value: 'r = 0.73', sub: 'Temporal validation hold-out' },
    { icon: Target, label: 'Advancement Precision', value: '89%', sub: 'Top-50 selection accuracy' },
  ]

  const steps = [
    { num: '01', label: 'Discover', desc: 'AI surfaces lines that deserve attention — based on genomic evidence, not just observed yields.' },
    { num: '02', label: 'Inspect', desc: 'Every candidate gets a full breeding passport. Understand why the model is confident or uncertain.' },
    { num: '03', label: 'Decide', desc: 'Advance, watch, or drop. You stay in control. The AI flags where your expertise matters most.' },
    { num: '04', label: 'Build', desc: 'Generate the optimal next-generation cohort. Export your advancement list instantly.' },
  ]

  return (
    <div className="min-h-screen bg-surface-0">
      {/* Hero */}
      <section className="relative min-h-screen flex flex-col justify-center px-6 md:px-12 lg:px-20 pt-12 pb-20 overflow-hidden">
        {/* Background elements */}
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_50%_at_50%_-20%,rgba(74,222,128,0.04),transparent)]" />
        <div className="absolute inset-0 bg-grid-subtle opacity-30" />

        <div className="relative max-w-5xl mx-auto w-full">
          {/* Eyebrow */}
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="flex items-center gap-2 mb-8"
          >
            <div className="w-1.5 h-1.5 rounded-full bg-brand-400 animate-pulse-subtle" />
            <span className="text-brand-400 text-xs font-mono tracking-widest uppercase">
              Genomic Decision Intelligence · {new Date().getFullYear()}
            </span>
          </motion.div>

          {/* Main headline */}
          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1, duration: 0.7 }}
            className="text-5xl md:text-7xl lg:text-8xl font-black text-text-primary leading-[0.95] tracking-tight mb-6"
          >
            From genomic<br />
            <span className="text-brand-400">data</span> to field<br />
            decisions.
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.25, duration: 0.7 }}
            className="text-lg md:text-xl text-text-secondary max-w-2xl leading-relaxed mb-12"
          >
            {brand.taglineSub}
          </motion.p>

          {/* Decision visual */}
          <div className="mb-12">
            <DecisionFlow />
          </div>

          {/* CTAs */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.8, duration: 0.6 }}
            className="flex flex-wrap gap-4"
          >
            <Button
              variant="primary"
              size="xl"
              onClick={() => navigate('/cohort')}
              className="group"
            >
              {brand.ctaPrimary}
              <ArrowRight size={18} className="transition-transform group-hover:translate-x-1" />
            </Button>
            <Button
              variant="secondary"
              size="xl"
              onClick={() => navigate('/copilot')}
            >
              {brand.ctaSecondary}
            </Button>
          </motion.div>

          {/* Scroll hint */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 2.5 }}
            className="absolute bottom-8 left-0 right-0 flex justify-center"
          >
            <motion.div
              animate={{ y: [0, 6, 0] }}
              transition={{ duration: 2, repeat: Infinity }}
              className="text-text-muted"
            >
              <ChevronDown size={20} />
            </motion.div>
          </motion.div>
        </div>

        {/* Right side viz — desktop only */}
        <div className="absolute right-0 top-0 bottom-0 w-80 lg:w-96 hidden xl:flex items-center pr-12">
          <div className="w-full h-64">
            <GenomicViz />
          </div>
        </div>
      </section>

      {/* Pipeline section */}
      <section className="px-6 md:px-12 lg:px-20 py-24 border-t border-border-subtle">
        <div className="max-w-5xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mb-16"
          >
            <div className="text-brand-400 text-xs font-mono tracking-widest uppercase mb-4">The decision workflow</div>
            <h2 className="text-3xl md:text-5xl font-black text-text-primary leading-tight">
              The model predicts.<br />
              <span className="text-text-secondary">The breeder decides.</span>
            </h2>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            {steps.map((step, i) => (
              <motion.div
                key={step.num}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="relative"
              >
                {i < steps.length - 1 && (
                  <div className="hidden md:block absolute top-6 left-full w-full h-px bg-gradient-to-r from-brand-400/20 to-transparent -z-0 translate-x-3" />
                )}
                <div className="bg-surface-2 border border-border-subtle rounded-xl p-5 hover:border-border-default transition-colors">
                  <div className="text-brand-400 text-xs font-mono mb-3 font-bold">{step.num}</div>
                  <div className="text-text-primary font-bold mb-2 text-sm tracking-wide uppercase">{step.label}</div>
                  <div className="text-text-secondary text-xs leading-relaxed">{step.desc}</div>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Stats section */}
      <section className="px-6 md:px-12 lg:px-20 py-20 bg-surface-1 border-t border-border-subtle">
        <div className="max-w-5xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {stats.map((stat, i) => (
              <motion.div
                key={stat.label}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.15 }}
                className="flex flex-col gap-3"
              >
                <div className="w-10 h-10 rounded-lg bg-brand-400/10 border border-brand-400/15 flex items-center justify-center">
                  <stat.icon size={18} className="text-brand-400" />
                </div>
                <div className="text-3xl font-black text-text-primary tabular-nums">{stat.value}</div>
                <div>
                  <div className="text-text-primary font-semibold text-sm">{stat.label}</div>
                  <div className="text-text-muted text-xs mt-1">{stat.sub}</div>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA bottom */}
      <section className="px-6 md:px-12 lg:px-20 py-24 border-t border-border-subtle">
        <div className="max-w-3xl mx-auto text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <h2 className="text-3xl md:text-5xl font-black text-text-primary mb-6 leading-tight">
              Know where the model is confident.<br />
              <span className="text-brand-400">And where it needs your eyes.</span>
            </h2>
            <p className="text-text-secondary mb-10 text-lg">
              Find the lines you might eliminate too early.
            </p>
            <div className="flex flex-wrap gap-4 justify-center">
              <Button variant="primary" size="xl" onClick={() => navigate('/copilot')}>
                Open Field Copilot
                <ArrowRight size={18} />
              </Button>
              <Button variant="secondary" size="xl" onClick={() => navigate('/gems')}>
                Discover Hidden Gems
              </Button>
            </div>
          </motion.div>
        </div>
      </section>
    </div>
  )
}
