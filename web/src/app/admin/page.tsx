'use client'
import { useEffect, useState } from 'react'
import AppLayout from '@/components/layout/AppLayout'
import PageHeader from '@/components/layout/PageHeader'
import { Save, RefreshCw, RotateCcw, Activity } from 'lucide-react'
import toast from 'react-hot-toast'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const H = () => ({ Authorization: `Bearer ${localStorage.getItem('raven_token')}`, 'Content-Type': 'application/json' })

const DEFAULT_WEIGHTS = {
  regulatory:  0.25,
  financial:   0.20,
  operational: 0.20,
  liquidity:   0.15,
  onchain:     0.10,
  reputation:  0.10,
}

const DIMENSION_META = [
  { key: 'regulatory',  label: 'Regulatory Standing', color: '#C9A84C', description: 'Licence status, regulator tier, jurisdiction, enforcement actions' },
  { key: 'financial',   label: 'Financial Strength',  color: '#3AA896', description: 'Public listing, audited financials, equity ratio, debt level' },
  { key: 'operational', label: 'Operational Resilience', color: '#4A9EE0', description: 'SOC2/ISO27001, security incidents, insurance, years in operation' },
  { key: 'liquidity',   label: 'Liquidity & Reserves',  color: '#9B59B6', description: 'Proof of Reserves ratio, reserve quality, withdrawal history' },
  { key: 'onchain',     label: 'On-Chain Health',       color: '#2A7C6F', description: 'Reserve trends, TVL changes, smart contract audits' },
  { key: 'reputation',  label: 'Reputation & Market',   color: '#C0392B', description: 'News sentiment, industry reputation, leadership concerns' },
]

function TierBadge({ tier }: { tier?: string }) {
  if (!tier) return <span className="text-ink-mid text-xs">—</span>
  const cls: Record<string,string> = {
    LOW: 'bg-teal/10 text-teal border-teal/20',
    MEDIUM: 'bg-amber/10 text-amber border-amber/20',
    HIGH: 'bg-red/10 text-red border-red/20',
    CRITICAL: 'bg-red text-white border-red',
  }
  return <span className={`text-xs font-mono px-2 py-0.5 rounded border ${cls[tier] ?? ''}`}>{tier}</span>
}

function scoreTier(score: number): string {
  if (score >= 75) return 'LOW'
  if (score >= 55) return 'MEDIUM'
  if (score >= 35) return 'HIGH'
  return 'CRITICAL'
}

function previewScore(cp: any, weights: Record<string,number>): number | null {
  const s = cp.latest_score
  if (!s) return null
  const dims: Record<string,string> = {
    regulatory: 'regulatory_score', financial: 'financial_score',
    operational: 'operational_score', liquidity: 'liquidity_score',
    onchain: 'onchain_score', reputation: 'reputation_score',
  }
  let total = 0
  for (const [dim, scoreKey] of Object.entries(dims)) {
    const dimScore = s[scoreKey]
    if (dimScore == null) return null
    total += dimScore * (weights[dim] ?? 0)
  }
  return Math.round(total * 10) / 10
}

export default function CalibrationPage() {
  const [weights, setWeights]       = useState<Record<string,number>>(DEFAULT_WEIGHTS)
  const [savedWeights, setSavedWeights] = useState<Record<string,number>>(DEFAULT_WEIGHTS)
  const [cps, setCps]               = useState<any[]>([])
  const [loading, setLoading]       = useState(true)
  const [saving, setSaving]         = useState(false)
  const [rescoring, setRescoring]   = useState(false)

  const total = Object.values(weights).reduce((a,b) => a+b, 0)
  const isValid = Math.abs(total - 1.0) < 0.001

  const load = async () => {
    setLoading(true)
    try {
      // Load current weights from API
      const [cpRes, wRes] = await Promise.all([
        fetch(`${API}/api/v1/counterparties`, { headers: H() }),
        fetch(`${API}/api/v1/admin/weights`, { headers: H() }),
      ])
      if (cpRes.ok) {
        const cpData = await cpRes.json()
        // Also fetch full score details for each CP
        const detailed = await Promise.all(
          cpData.slice(0, 24).map(async (cp: any) => {
            const r = await fetch(`${API}/api/v1/counterparties/${cp.counterparty_id}`, { headers: H() })
            return r.ok ? r.json() : cp
          })
        )
        setCps(detailed)
      }
      if (wRes.ok) {
        const w = await wRes.json()
        setWeights(w.weights)
        setSavedWeights(w.weights)
      }
    } catch {} finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const updateWeight = (dim: string, value: number) => {
    setWeights(prev => ({ ...prev, [dim]: Math.round(value * 1000) / 1000 }))
  }

  const normalize = () => {
    const t = Object.values(weights).reduce((a,b) => a+b, 0)
    if (t === 0) return
    const normalized = Object.fromEntries(
      Object.entries(weights).map(([k,v]) => [k, Math.round((v/t) * 1000) / 1000])
    )
    // Fix rounding to ensure exact 1.0
    const adj = 1.0 - Object.values(normalized).reduce((a,b) => a+b, 0)
    const firstKey = Object.keys(normalized)[0]
    normalized[firstKey] = Math.round((normalized[firstKey] + adj) * 1000) / 1000
    setWeights(normalized)
  }

  const reset = () => setWeights(DEFAULT_WEIGHTS)

  const save = async () => {
    if (!isValid) return toast.error('Weights must sum to 100%')
    setSaving(true)
    try {
      const r = await fetch(`${API}/api/v1/admin/weights`, {
        method: 'POST', headers: H(),
        body: JSON.stringify({ weights }),
      })
      if (!r.ok) throw new Error((await r.json()).detail)
      setSavedWeights(weights)
      toast.success('Weights saved')
    } catch (e: any) { toast.error(e.message) }
    finally { setSaving(false) }
  }

  const saveAndRescore = async () => {
    if (!isValid) return toast.error('Weights must sum to 100%')
    setRescoring(true)
    try {
      const r = await fetch(`${API}/api/v1/admin/weights`, {
        method: 'POST', headers: H(),
        body: JSON.stringify({ weights, rescore: true }),
      })
      if (!r.ok) throw new Error((await r.json()).detail)
      setSavedWeights(weights)
      toast.success('Weights saved — rescoring all counterparties in background (~60s)')
    } catch (e: any) { toast.error(e.message) }
    finally { setRescoring(false) }
  }

  const hasChanges = JSON.stringify(weights) !== JSON.stringify(savedWeights)

  // Sort CPs by preview score descending
  const sortedCps = [...cps].sort((a, b) => {
    const sa = previewScore(a, weights) ?? 0
    const sb = previewScore(b, weights) ?? 0
    return sb - sa
  })

  return (
    <AppLayout>
      <PageHeader
        title="Score Calibration"
        subtitle="Adjust dimension weights — scores update live in the preview below"
        action={
          <div className="flex items-center gap-2">
            <button onClick={reset} className="btn-secondary text-xs flex items-center gap-1.5">
              <RotateCcw className="w-3 h-3" /> Reset to Defaults
            </button>
            <button onClick={normalize} className="btn-secondary text-xs">
              Auto-normalize
            </button>
            <button onClick={save} disabled={!hasChanges || saving || !isValid}
              className="btn-secondary text-xs flex items-center gap-1.5 disabled:opacity-50">
              <Save className="w-3.5 h-3.5" /> Save
            </button>
            <button onClick={saveAndRescore} disabled={!hasChanges || rescoring || !isValid}
              className="btn-primary text-xs flex items-center gap-1.5 disabled:opacity-50">
              <Activity className="w-3.5 h-3.5" />
              {rescoring ? 'Rescoring…' : 'Save & Rescore All'}
            </button>
          </div>
        }
      />

      <div className="p-8 grid grid-cols-5 gap-6">

        {/* Weight sliders */}
        <div className="col-span-2 space-y-4">
          <div className="card p-5">
            <div className="label mb-4">Dimension Weights</div>

            <div className={`text-xs font-mono mb-4 px-3 py-2 rounded border ${
              isValid ? 'bg-teal/10 text-teal border-teal/20' : 'bg-red/10 text-red border-red/20'
            }`}>
              Total: {(total * 100).toFixed(1)}% {isValid ? '✓' : `— needs to equal 100%`}
            </div>

            <div className="space-y-5">
              {DIMENSION_META.map(({ key, label, color, description }) => (
                <div key={key}>
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: color }} />
                      <span className="text-sm font-medium">{label}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <input
                        type="number"
                        value={Math.round(weights[key] * 100)}
                        onChange={e => updateWeight(key, Number(e.target.value) / 100)}
                        min={0} max={100} step={1}
                        className="w-16 border border-border rounded px-2 py-0.5 text-xs text-right font-mono focus:outline-none focus:border-ink"
                      />
                      <span className="text-xs text-ink-mid">%</span>
                    </div>
                  </div>
                  <input
                    type="range"
                    min={0} max={50} step={1}
                    value={Math.round(weights[key] * 100)}
                    onChange={e => updateWeight(key, Number(e.target.value) / 100)}
                    className="w-full h-1.5 rounded-full appearance-none cursor-pointer"
                    style={{ accentColor: color }}
                  />
                  <div className="text-xs text-ink-mid mt-1">{description}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Saved vs current comparison */}
          {hasChanges && (
            <div className="card p-4">
              <div className="label mb-3">Changes from Saved</div>
              <div className="space-y-1.5">
                {DIMENSION_META.map(({ key, label, color }) => {
                  const curr = weights[key]
                  const saved = savedWeights[key]
                  const delta = Math.round((curr - saved) * 100)
                  if (delta === 0) return null
                  return (
                    <div key={key} className="flex items-center justify-between text-xs">
                      <span className="text-ink-mid">{label}</span>
                      <span className={`font-mono ${delta > 0 ? 'text-teal' : 'text-red'}`}>
                        {delta > 0 ? '+' : ''}{delta}%
                      </span>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>

        {/* Live score preview */}
        <div className="col-span-3 card overflow-hidden">
          <div className="px-5 py-3 border-b border-border flex items-center justify-between">
            <span className="label">Live Score Preview</span>
            <span className="text-xs text-ink-mid">
              {hasChanges ? '⚡ Preview with new weights' : 'Current saved scores'}
            </span>
          </div>

          {loading ? (
            <div className="p-8 text-center text-sm text-ink-mid">Loading counterparties…</div>
          ) : (
            <div className="overflow-auto" style={{ maxHeight: 600 }}>
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-surface-2 z-10">
                  <tr>
                    <th className="label text-left px-4 py-2 font-normal">Entity</th>
                    <th className="label text-left px-4 py-2 font-normal">Current</th>
                    <th className="label text-left px-4 py-2 font-normal">Preview</th>
                    <th className="label text-left px-4 py-2 font-normal">Δ</th>
                    <th className="label text-left px-4 py-2 font-normal">New Tier</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedCps.map(cp => {
                    const current = cp.composite_score ?? cp.latest_score?.composite_score
                    const preview = previewScore(cp, weights)
                    const delta   = preview != null && current != null
                      ? Math.round((preview - current) * 10) / 10
                      : null
                    const newTier = preview != null ? scoreTier(preview) : null
                    const tierChanged = newTier && cp.current_risk_tier && newTier !== cp.current_risk_tier

                    return (
                      <tr key={cp.counterparty_id}
                        className={`border-t border-border transition-colors ${tierChanged ? 'bg-amber/5' : 'hover:bg-surface-2/50'}`}>
                        <td className="px-4 py-2.5">
                          <div className="font-medium text-sm">{cp.display_name}</div>
                          <div className="text-xs text-ink-mid font-mono">{cp.entity_type}</div>
                        </td>
                        <td className="px-4 py-2.5">
                          <span className="text-sm font-mono">
                            {current != null ? current.toFixed(0) : '—'}
                          </span>
                        </td>
                        <td className="px-4 py-2.5">
                          <span className={`text-sm font-mono font-medium ${
                            preview == null ? 'text-ink-mid' :
                            preview >= 75 ? 'text-teal' :
                            preview >= 55 ? 'text-amber' : 'text-red'
                          }`}>
                            {preview != null ? preview.toFixed(0) : '—'}
                          </span>
                        </td>
                        <td className="px-4 py-2.5">
                          {delta != null && Math.abs(delta) > 0.05 ? (
                            <span className={`text-xs font-mono ${delta > 0 ? 'text-teal' : 'text-red'}`}>
                              {delta > 0 ? '+' : ''}{delta.toFixed(1)}
                            </span>
                          ) : <span className="text-xs text-ink-mid">—</span>}
                        </td>
                        <td className="px-4 py-2.5">
                          <div className="flex items-center gap-2">
                            <TierBadge tier={newTier ?? cp.current_risk_tier} />
                            {tierChanged && (
                              <span className="text-[10px] text-amber font-mono">
                                was {cp.current_risk_tier}
                              </span>
                            )}
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </AppLayout>
  )
}
