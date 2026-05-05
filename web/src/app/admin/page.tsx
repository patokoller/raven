'use client'
import { useEffect, useState, useRef } from 'react'
import AppLayout from '@/components/layout/AppLayout'
import PageHeader from '@/components/layout/PageHeader'
import {
  Save, RotateCcw, Activity, Sparkles,
  CheckCircle, Clock, AlertTriangle, RefreshCw,
  Database, ChevronDown, ChevronUp
} from 'lucide-react'
import toast from 'react-hot-toast'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const H = () => ({ Authorization: `Bearer ${localStorage.getItem('raven_token')}`, 'Content-Type': 'application/json' })

const DEFAULT_WEIGHTS = {
  regulatory: 0.25, financial: 0.20, operational: 0.20,
  liquidity: 0.15, onchain: 0.10, reputation: 0.10,
}

const DIMENSIONS = [
  { key: 'regulatory',  label: 'Regulatory Standing', color: '#C9A84C' },
  { key: 'financial',   label: 'Financial Strength',  color: '#3AA896' },
  { key: 'operational', label: 'Operational Resilience', color: '#4A9EE0' },
  { key: 'liquidity',   label: 'Liquidity & Reserves',  color: '#9B59B6' },
  { key: 'onchain',     label: 'On-Chain Health',       color: '#2A7C6F' },
  { key: 'reputation',  label: 'Reputation & Market',   color: '#C0392B' },
]

function TierPill({ tier }: { tier?: string }) {
  if (!tier) return <span className="text-ink-mid text-xs">—</span>
  const cls: Record<string,string> = {
    LOW: 'bg-teal/10 text-teal border-teal/20',
    MEDIUM: 'bg-amber/10 text-amber border-amber/20',
    HIGH: 'bg-red/10 text-red border-red/20',
    CRITICAL: 'bg-red text-white border-red',
  }
  return <span className={`text-xs font-mono px-2 py-0.5 rounded border ${cls[tier]??''}`}>{tier}</span>
}

function scoreTier(s: number) {
  return s >= 75 ? 'LOW' : s >= 55 ? 'MEDIUM' : s >= 35 ? 'HIGH' : 'CRITICAL'
}

function previewScore(cp: any, weights: Record<string,number>): number | null {
  const s = cp.latest_score
  if (!s) return null
  const keys: Record<string,string> = {
    regulatory:'regulatory_score', financial:'financial_score',
    operational:'operational_score', liquidity:'liquidity_score',
    onchain:'onchain_score', reputation:'reputation_score',
  }
  let total = 0
  for (const [dim, k] of Object.entries(keys)) {
    if (s[k] == null) return null
    total += s[k] * (weights[dim] ?? 0)
  }
  return Math.round(total * 10) / 10
}

// ── Research Status Panel ─────────────────────────────────────

function ResearchPanel() {
  const [status, setStatus]       = useState<any>(null)
  const [loading, setLoading]     = useState(false)
  const [running, setRunning]     = useState(false)
  const [applying, setApplying]   = useState(false)
  const [rescoring, setRescoring] = useState(false)
  const [showBreakdown, setShowBreakdown] = useState(false)
  const pollRef = useRef<NodeJS.Timeout>()

  const loadStatus = async () => {
    const r = await fetch(`${API}/api/v1/admin/research/status`, { headers: H() })
    if (r.ok) {
      const d = await r.json()
      setStatus(d)
      if (d.running === 0 && running) {
        setRunning(false)
        clearInterval(pollRef.current)
        toast.success(`Research complete — ${d.complete}/${d.total} counterparties researched`)
      }
    }
  }

  useEffect(() => { loadStatus() }, [])

  const startBatch = async () => {
    setRunning(true)
    try {
      const r = await fetch(`${API}/api/v1/admin/research/batch`, { method: 'POST', headers: H() })
      const d = await r.json()
      if (!r.ok) throw new Error(d.detail)
      toast.success(`Researching ${d.queued} counterparties — ~${Math.ceil(d.queued * 3)} minutes`)
      pollRef.current = setInterval(loadStatus, 15000)
    } catch (e: any) { toast.error(e.message); setRunning(false) }
  }

  const applyAll = async () => {
    setApplying(true)
    try {
      const r = await fetch(`${API}/api/v1/admin/research/apply-all`, { method: 'POST', headers: H() })
      const d = await r.json()
      if (!r.ok) throw new Error(d.detail)
      toast.success(`Applied to ${d.applied} counterparties — rescoring now (~60s)`)
      setRescoring(true)
      // Reload score table after rescoring completes
      setTimeout(async () => {
        await loadCps()  // refresh counterparty scores
        setRescoring(false)
        toast.success('Scores updated — check the preview table')
      }, 70000)
    } catch (e: any) { toast.error(e.message) }
    finally { setApplying(false) }
  }

  const pct = status?.pct_complete ?? 0

  return (
    <div className="card p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-gold" />
          <span className="font-medium">AI Research — Batch Mode</span>
        </div>
        <div className="flex gap-2">
          <button onClick={loadStatus} className="btn-secondary text-xs flex items-center gap-1.5 py-1.5">
            <RefreshCw className="w-3 h-3" /> Refresh
          </button>
          {status?.complete > 0 && (
            <button onClick={applyAll} disabled={applying || rescoring}
              className="btn-secondary text-xs flex items-center gap-1.5 py-1.5 disabled:opacity-50">
              <Database className="w-3 h-3" />
              {applying ? 'Applying…' : rescoring ? 'Rescoring…' : `Apply All & Rescore (${status.complete})`}
            </button>
          )}
          <button onClick={startBatch} disabled={running || (status?.not_started === 0 && status?.error === 0)}
            className="btn-primary text-xs flex items-center gap-1.5 py-1.5 disabled:opacity-50">
            {running
              ? <><RefreshCw className="w-3 h-3 animate-spin" /> Researching…</>
              : status?.error > 0 && status?.not_started === 0
                ? <><Sparkles className="w-3 h-3" /> Retry {status.error} Failed</>
                : <><Sparkles className="w-3 h-3" /> Research All Counterparties</>
            }
          </button>
        </div>
      </div>

      {status && (
        <>
          {/* Progress bar */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-ink-mid">
                {status.complete}/{status.total} counterparties researched
              </span>
              <span className="text-xs font-mono text-ink">{pct}%</span>
            </div>
            <div className="w-full h-2 bg-surface-2 rounded-full overflow-hidden">
              <div className="h-full bg-teal rounded-full transition-all duration-500"
                style={{ width: `${pct}%` }} />
            </div>
          </div>

          {/* Status summary */}
          <div className="grid grid-cols-4 gap-3">
            {[
              { label: 'Complete',     count: status.complete,    icon: CheckCircle, color: 'text-teal' },
              { label: 'Running',      count: status.running,     icon: Clock,       color: 'text-amber' },
              { label: 'Error',        count: status.error,       icon: AlertTriangle, color: 'text-red' },
              { label: 'Not Started',  count: status.not_started, icon: RefreshCw,   color: 'text-ink-mid' },
            ].map(({ label, count, icon: Icon, color }) => (
              <div key={label} className="bg-surface-2 rounded p-3 text-center">
                <Icon className={`w-4 h-4 ${color} mx-auto mb-1`} />
                <div className={`text-xl font-light ${color}`}>{count}</div>
                <div className="text-xs text-ink-mid">{label}</div>
              </div>
            ))}
          </div>

          {running && (
            <div className="bg-gold/5 border border-gold/20 rounded p-3 text-xs text-amber">
              <div className="font-medium mb-1.5">Agent running — searching web, regulatory registers, on-chain data…</div>
              <div className="text-ink-mid">Auto-refreshing every 15 seconds. Each counterparty takes ~2-3 minutes.</div>
            </div>
          )}

          {/* Breakdown toggle */}
          <button onClick={() => setShowBreakdown(s => !s)}
            className="text-xs text-ink-mid hover:text-ink flex items-center gap-1">
            {showBreakdown ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            {showBreakdown ? 'Hide' : 'Show'} entity breakdown
          </button>

          {showBreakdown && (
            <div className="space-y-3">
              {['complete','running','error','none'].map(statusKey => {
                const items = status.breakdown[statusKey] || []
                if (!items.length) return null
                return (
                  <div key={statusKey}>
                    <div className="label mb-2 capitalize">{statusKey === 'none' ? 'Not Started' : statusKey}</div>
                    <div className="grid grid-cols-2 gap-1.5">
                      {items.map((cp: any) => (
                        <div key={cp.name}
                          className="flex items-center justify-between bg-surface-2 rounded px-3 py-1.5">
                          <div>
                            <span className="text-xs font-medium">{cp.name}</span>
                            <span className="text-xs text-ink-mid ml-2 font-mono">{cp.entity_type}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            {cp.enrichment_fields > 0 && (
                              <span className="text-[10px] text-teal font-mono">{cp.enrichment_fields} fields</span>
                            )}
                            <TierPill tier={cp.risk_tier} />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </>
      )}

      <div className="pt-3 border-t border-border">
        <div className="text-xs text-ink-mid space-y-1">
          <p><strong className="text-ink">How it works:</strong> The AI research agent searches regulatory registers (FINMA, FCA, SEC, OCC), financial filings, security databases (rekt.news), on-chain data (DefiLlama), and news for each counterparty.</p>
          <p>After research completes, click <strong className="text-ink">Apply All & Rescore</strong> to push all findings into the scoring engine simultaneously. Scores will update within 60 seconds.</p>
        </div>
      </div>
    </div>
  )
}

// ── Score Calibration ─────────────────────────────────────────

export default function AdminPage() {
  const [weights, setWeights]     = useState<Record<string,number>>(DEFAULT_WEIGHTS)
  const [savedWeights, setSaved]  = useState<Record<string,number>>(DEFAULT_WEIGHTS)
  const [cps, setCps]             = useState<any[]>([])
  const [loading, setLoading]     = useState(true)
  const [saving, setSaving]       = useState(false)
  const [rescoring, setRescoring] = useState(false)

  const total    = Object.values(weights).reduce((a,b) => a+b, 0)
  const isValid  = Math.abs(total - 1.0) < 0.001
  const hasChanges = JSON.stringify(weights) !== JSON.stringify(savedWeights)

  const loadCps = async () => {
    try {
      const cpRes = await fetch(`${API}/api/v1/counterparties`, { headers: H() })
      if (cpRes.ok) {
        const cpData = await cpRes.json()
        const detailed = await Promise.all(
          cpData.map(async (cp: any) => {
            const r = await fetch(`${API}/api/v1/counterparties/${cp.counterparty_id}`, { headers: H() })
            return r.ok ? r.json() : cp
          })
        )
        setCps(detailed)
      }
    } catch {}
  }

  const load = async () => {
    setLoading(true)
    try {
      const [cpRes, wRes] = await Promise.all([
        fetch(`${API}/api/v1/counterparties`, { headers: H() }),
        fetch(`${API}/api/v1/admin/weights`, { headers: H() }),
      ])
      if (cpRes.ok) {
        const cpData = await cpRes.json()
        const detailed = await Promise.all(
          cpData.map(async (cp: any) => {
            const r = await fetch(`${API}/api/v1/counterparties/${cp.counterparty_id}`, { headers: H() })
            return r.ok ? r.json() : cp
          })
        )
        setCps(detailed)
      }
      if (wRes.ok) {
        const w = await wRes.json()
        setWeights(w.weights)
        setSaved(w.weights)
      }
    } catch {} finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const updateWeight = (dim: string, val: number) =>
    setWeights(prev => ({ ...prev, [dim]: Math.round(val * 1000) / 1000 }))

  const normalize = () => {
    const t = Object.values(weights).reduce((a,b) => a+b, 0)
    if (!t) return
    const n = Object.fromEntries(Object.entries(weights).map(([k,v]) => [k, Math.round(v/t*1000)/1000]))
    const adj = 1.0 - Object.values(n).reduce((a,b) => a+b, 0)
    n[Object.keys(n)[0]] = Math.round((n[Object.keys(n)[0]] + adj) * 1000) / 1000
    setWeights(n)
  }

  const save = async (rescore = false) => {
    if (!isValid) return toast.error('Weights must sum to 100%')
    rescore ? setRescoring(true) : setSaving(true)
    try {
      const r = await fetch(`${API}/api/v1/admin/weights`, {
        method: 'POST', headers: H(),
        body: JSON.stringify({ weights, rescore }),
      })
      if (!r.ok) throw new Error((await r.json()).detail)
      setSaved(weights)
      toast.success(rescore ? 'Saved — rescoring all counterparties in background' : 'Weights saved')
    } catch (e: any) { toast.error(e.message) }
    finally { setSaving(false); setRescoring(false) }
  }

  const sortedCps = [...cps].sort((a,b) => {
    const sa = previewScore(a, weights) ?? 0
    const sb = previewScore(b, weights) ?? 0
    return sb - sa
  })

  return (
    <AppLayout>
      <PageHeader
        title="Intelligence Engine"
        subtitle="AI batch research · Score calibration · Registry management"
      />

      <div className="p-8 space-y-6">

        {/* Batch Research Panel */}
        <ResearchPanel />

        {/* Score Calibration */}
        <div className="grid grid-cols-5 gap-6">
          <div className="col-span-2 space-y-4">
            <div className="card p-5">
              <div className="flex items-center justify-between mb-4">
                <div className="label">Dimension Weights</div>
                <div className="flex gap-1.5">
                  <button onClick={() => setWeights(DEFAULT_WEIGHTS)}
                    className="btn-secondary text-xs py-1 flex items-center gap-1">
                    <RotateCcw className="w-3 h-3" /> Reset
                  </button>
                  <button onClick={normalize} className="btn-secondary text-xs py-1">Normalize</button>
                </div>
              </div>

              <div className={`text-xs font-mono mb-4 px-3 py-1.5 rounded border ${
                isValid ? 'bg-teal/10 text-teal border-teal/20' : 'bg-red/10 text-red border-red/20'
              }`}>
                Total: {(total*100).toFixed(1)}% {isValid ? '✓' : '— must equal 100%'}
              </div>

              <div className="space-y-5">
                {DIMENSIONS.map(({ key, label, color }) => (
                  <div key={key}>
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full" style={{ background: color }} />
                        <span className="text-sm">{label}</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <input type="number" min={0} max={100} step={1}
                          value={Math.round(weights[key]*100)}
                          onChange={e => updateWeight(key, Number(e.target.value)/100)}
                          className="w-14 border border-border rounded px-2 py-0.5 text-xs text-right font-mono focus:outline-none focus:border-ink" />
                        <span className="text-xs text-ink-mid">%</span>
                      </div>
                    </div>
                    <input type="range" min={0} max={50} step={1}
                      value={Math.round(weights[key]*100)}
                      onChange={e => updateWeight(key, Number(e.target.value)/100)}
                      className="w-full h-1.5 rounded-full appearance-none cursor-pointer"
                      style={{ accentColor: color }} />
                  </div>
                ))}
              </div>

              <div className="flex gap-2 mt-5 pt-4 border-t border-border">
                <button onClick={() => save(false)} disabled={!hasChanges||saving||!isValid}
                  className="btn-secondary text-xs flex items-center gap-1.5 disabled:opacity-50 flex-1 justify-center py-1.5">
                  <Save className="w-3 h-3" /> {saving ? 'Saving…' : 'Save'}
                </button>
                <button onClick={() => save(true)} disabled={!hasChanges||rescoring||!isValid}
                  className="btn-primary text-xs flex items-center gap-1.5 disabled:opacity-50 flex-1 justify-center py-1.5">
                  <Activity className="w-3 h-3" /> {rescoring ? 'Rescoring…' : 'Save & Rescore All'}
                </button>
              </div>
            </div>

            {hasChanges && (
              <div className="card p-4">
                <div className="label mb-3">Changes from Saved</div>
                {DIMENSIONS.map(({ key, label }) => {
                  const delta = Math.round((weights[key] - savedWeights[key]) * 100)
                  if (!delta) return null
                  return (
                    <div key={key} className="flex items-center justify-between text-xs py-1">
                      <span className="text-ink-mid">{label}</span>
                      <span className={`font-mono ${delta > 0 ? 'text-teal' : 'text-red'}`}>
                        {delta > 0 ? '+' : ''}{delta}%
                      </span>
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          {/* Score preview table */}
          <div className="col-span-3 card overflow-hidden">
            <div className="px-5 py-3 border-b border-border flex items-center justify-between">
              <span className="label">Live Score Preview — All {cps.length} Counterparties</span>
              <span className="text-xs text-ink-mid">
                {hasChanges ? '⚡ New weights applied' : 'Current scores'}
              </span>
            </div>
            {loading ? (
              <div className="p-8 text-center text-sm text-ink-mid">Loading…</div>
            ) : (
              <div className="overflow-auto" style={{ maxHeight: 560 }}>
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-surface-2 z-10">
                    <tr>
                      {['Entity','Type','Current','Preview','Δ','New Tier'].map(h => (
                        <th key={h} className="label text-left px-4 py-2 font-normal">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {sortedCps.map(cp => {
                      const current = cp.composite_score ?? cp.latest_score?.composite_score
                      const preview = previewScore(cp, weights)
                      const delta   = preview != null && current != null
                        ? Math.round((preview - current) * 10) / 10 : null
                      const newTier = preview != null ? scoreTier(preview) : null
                      const changed = newTier && cp.current_risk_tier && newTier !== cp.current_risk_tier
                      return (
                        <tr key={cp.counterparty_id}
                          className={`border-t border-border ${changed ? 'bg-amber/5' : 'hover:bg-surface-2/40'} transition-colors`}>
                          <td className="px-4 py-2">
                            <div className="font-medium text-sm">{cp.display_name}</div>
                          </td>
                          <td className="px-4 py-2 text-xs font-mono text-ink-mid">{cp.entity_type}</td>
                          <td className="px-4 py-2 text-sm font-mono">{current?.toFixed(0) ?? '—'}</td>
                          <td className="px-4 py-2">
                            <span className={`text-sm font-mono font-medium ${
                              !preview ? 'text-ink-mid' :
                              preview>=75?'text-teal':preview>=55?'text-amber':'text-red'}`}>
                              {preview?.toFixed(0) ?? '—'}
                            </span>
                          </td>
                          <td className="px-4 py-2">
                            {delta != null && Math.abs(delta) > 0.05 ? (
                              <span className={`text-xs font-mono ${delta>0?'text-teal':'text-red'}`}>
                                {delta>0?'+':''}{delta.toFixed(1)}
                              </span>
                            ) : <span className="text-xs text-ink-mid">—</span>}
                          </td>
                          <td className="px-4 py-2">
                            <div className="flex items-center gap-1.5">
                              <TierPill tier={newTier ?? cp.current_risk_tier} />
                              {changed && (
                                <span className="text-[10px] text-amber font-mono">was {cp.current_risk_tier}</span>
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
      </div>
    </AppLayout>
  )
}
