import { brand } from '@/config/brand'

export default function SettingsPage() {
  return (
    <div className="min-h-screen bg-surface-0 px-4 md:px-8 py-8">
      <div className="max-w-2xl mx-auto">
        <div className="text-brand-400 text-xs font-mono tracking-widest uppercase mb-3">Settings</div>
        <h1 className="text-2xl font-black text-text-primary mb-8">Settings</h1>

        <div className="space-y-4">
          <div className="bg-surface-2 border border-border-subtle rounded-xl p-5">
            <div className="text-text-muted text-xs font-mono uppercase tracking-widest mb-4">Product Identity</div>
            <div className="space-y-3">
              <InfoRow label="Product Name" value={brand.productName} />
              <InfoRow label="Tagline" value={brand.tagline} />
              <InfoRow label="Primary Trait" value={brand.domain.primaryTrait} />
              <InfoRow label="Total Candidates" value={brand.domain.totalCandidates.toString()} />
              <InfoRow label="Advancement Slots" value={brand.domain.advancementSlots.toString()} />
            </div>
            <div className="mt-4 text-text-muted text-xs font-mono">
              Edit: <code className="bg-surface-3 px-1 rounded">src/config/brand.ts</code>
            </div>
          </div>

          <div className="bg-surface-2 border border-border-subtle rounded-xl p-5">
            <div className="text-text-muted text-xs font-mono uppercase tracking-widest mb-4">Data Integration</div>
            <div className="space-y-3">
              <InfoRow label="Data Source" value="Internal dataset" />
              <InfoRow label="API Base URL" value="Not configured — set VITE_API_BASE_URL" />
              <InfoRow label="Model Version" value="2.1.0-ridge" />
            </div>
            <div className="mt-4 text-text-muted text-xs font-mono leading-relaxed">
              To connect real model outputs:<br />
              1. Run FastAPI with your Python pipeline<br />
              2. Set <code className="bg-surface-3 px-1 rounded">VITE_API_BASE_URL=http://localhost:8000</code> in .env<br />
              3. Services in <code className="bg-surface-3 px-1 rounded">src/services/</code> will auto-switch to live data
            </div>
          </div>

          <div className="bg-surface-2 border border-border-subtle rounded-xl p-5">
            <div className="text-text-muted text-xs font-mono uppercase tracking-widest mb-4">Product Walkthrough</div>
            <ol className="space-y-2">
              {[
                'Start at Overview — show 500 → 50 story',
                'Open Field Copilot — advance line C2-1847',
                'Click "View Breeding Passport"',
                'Navigate to Hidden Gems — show C4-8821',
                'Navigate to Build Cohort',
                'Set budget=50, strategy=Balanced, click Build',
                'Export the advancement CSV',
                'Open Model Intelligence — show r=0.73 validation',
              ].map((step, i) => (
                <li key={i} className="flex items-start gap-3 text-text-secondary text-sm">
                  <span className="text-brand-400 font-mono text-xs mt-0.5 w-5 flex-shrink-0">{String(i + 1).padStart(2, '0')}</span>
                  {step}
                </li>
              ))}
            </ol>
            <div className="mt-4 text-text-muted text-xs font-mono">
              ~3 minutes · All features available
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function InfoRow({ label, value, badge }: { label: string; value: string; badge?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-border-subtle/50 last:border-0">
      <span className="text-text-secondary text-sm">{label}</span>
      <div className="flex items-center gap-2">
        {badge}
        <span className="text-text-primary text-sm font-mono">{value}</span>
      </div>
    </div>
  )
}
