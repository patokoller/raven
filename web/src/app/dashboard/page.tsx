'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import {
  AlertTriangle, TrendingDown, TrendingUp, Minus,
  RefreshCw, FileText, Shield, Activity, LogOut, Server
} from 'lucide-react'
import { createClient } from '@/lib/supabase'
import toast from 'react-hot-toast'

// ── Helpers ───────────────────────────────────────────────────

function TierPill({ tier }: { tier?: string }) {
  if (!tier) return <span className="text-ink-mid text-xs">—</span>
  const classes: Record<string, string> = {
    LOW:      'bg-teal/10 text-teal border-teal/20',
    MEDIUM:   'bg-amber/10 text-amber border-amber/20',
    HIGH:     'bg-red/10 text-red border-red/20',
    CRITICAL: 'bg-red text-white border-red',
  }
  return (
    <span className={`text-xs font-mono px-2 py-0.5 rounded border ${classes[tier] ?? 'bg-surface-2 border-border text-ink-mid'}`}>
      {tier}
    </span>
  )
}

function ScoreDelta({ delta }: { delta?: number | null }) {
  if (delta == null) return <span className="text-ink-mid text-xs font-mono">—</span>
  if (Math.abs(delta) < 0.5)
    return <span className="text-ink-mid text-xs font-mono flex items-center gap-1"><Minus className="w-3 h-3" />{delta.toFixed(1)}</span>
  if (delta > 0)
    return <span className="text-teal text-xs font-mono flex items-center gap-1"><TrendingUp className="w-3 h-3" />+{delta.toFixed(1)}</span>
  return <span className="text-red text-xs font-mono flex items-center gap-1"><TrendingDown className="w-3 h-3" />{delta.toFixed(1)}</span>
}

function ScoreBar({ score }: { score?: number | null }) {
  if (!score) return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 bg-surface-2 rounded-full" />
      <span className="text-xs font-mono text-ink-mid">—</span>
    </div>
  )
  const color = score >= 75 ? '#2A7C6F' : score >= 55 ? '#E67E22' : '#C0392B'
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 bg-surface-2 rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all" style={{ width: `${score}%`, background: color }} />
      </div>
      <span className="text-xs font-mono text-ink-mid">{score.toFixed(0)}</span>
    </div>
  )
}

function Skeleton() {
  return <div className="h-3 bg-surface-2 rounded animate-pulse w-full" />
}

// ── API Banner ────────────────────────────────────────────────

function ApiNotDeployedBanner() {
  return (
    <div className="bg-amber/5 border border-amber/20 rounded-lg px-4 py-3 flex items-start gap-3">
      <Server className="w-4 h-4 text-amber mt-0.5 flex-shrink-0" />
      <div>
        <div className="text-sm font-medium text-amber">API not yet deployed</div>
        <div className="text-xs text-ink-mid mt-0.5">
          Counterparty scores and portfolio data will appear once the FastAPI backend is deployed to Fly.io.
          The dashboard structure and auth are working correctly.
        </div>
      </div>
    </div>
  )
}

// ── Dashboard ─────────────────────────────────────────────────

export default function DashboardPage() {
  const router = useRouter()
  const [user, setUser] = useState<any>(null)
  const [cps, setCps] = useState<any[]>([])
  const [openAlerts, setOpenAlerts] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [apiReachable, setApiReachable] = useState<boolean | null>(null)

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

  // Check auth on mount
  useEffect(() => {
    const supabase = createClient()
    supabase.auth.getUser().then(({ data }) => {
      if (!data.user) {
        router.replace('/login')
      } else {
        setUser(data.user)
        checkApiAndLoad()
      }
    })
  }, [])

  const checkApiAndLoad = async () => {
    setLoading(true)
    try {
      const resp = await fetch(`${apiUrl}/health`, { signal: AbortSignal.timeout(4000) })
      if (resp.ok) {
        setApiReachable(true)
        await loadData()
      } else {
        setApiReachable(false)
      }
    } catch {
      setApiReachable(false)
    } finally {
      setLoading(false)
    }
  }

  const loadData = async () => {
    const token = localStorage.getItem('raven_token')
    const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }
    try {
      const [cpRes, alertRes] = await Promise.all([
        fetch(`${apiUrl}/api/v1/counterparties`, { headers }),
        fetch(`${apiUrl}/api/v1/alerts`, { headers }),
      ])
      if (cpRes.ok) setCps(await cpRes.json())
      if (alertRes.ok) setOpenAlerts(await alertRes.json())
    } catch (e) {
      toast.error('Failed to load data from API')
    }
  }

  const handleLogout = async () => {
    const supabase = createClient()
    await supabase.auth.signOut()
    localStorage.removeItem('raven_token')
    router.push('/login')
  }

  const criticalCount = cps.filter(c => c.current_risk_tier === 'CRITICAL').length
  const highCount     = cps.filter(c => c.current_risk_tier === 'HIGH').length
  const scoredCount   = cps.filter(c => c.composite_score != null).length

  const sortedCps = [...cps].sort((a, b) => {
    const order = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 }
    return (order[a.current_risk_tier as keyof typeof order] ?? 4) -
           (order[b.current_risk_tier as keyof typeof order] ?? 4)
  })

  return (
    <div className="min-h-screen bg-surface">
      {/* Header */}
      <header className="border-b border-border bg-white px-6 py-3.5 flex items-center justify-between sticky top-0 z-10">
        <div className="flex items-center gap-3">
          <Shield className="w-4 h-4 text-gold" />
          <span className="font-mono text-xs tracking-widest uppercase text-ink">Raven</span>
          <span className="text-border mx-1">|</span>
          <span className="text-xs text-ink-mid">Risk & Portfolio Intelligence</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-ink-mid font-mono">{user?.email}</span>
          <button onClick={checkApiAndLoad} className="btn-secondary flex items-center gap-1.5 text-xs py-1.5">
            <RefreshCw className="w-3 h-3" /> Refresh
          </button>
          <button onClick={handleLogout} className="btn-secondary flex items-center gap-1.5 text-xs py-1.5">
            <LogOut className="w-3 h-3" /> Sign out
          </button>
        </div>
      </header>

      <main className="p-6 max-w-[1400px] mx-auto space-y-5">

        {/* API status banner */}
        {apiReachable === false && <ApiNotDeployedBanner />}

        {/* KPI row */}
        <div className="grid grid-cols-4 gap-4">
          {[
            { label: 'Monitored Entities', value: apiReachable ? cps.length : '—', sub: 'counterparties in registry' },
            { label: 'Scored',             value: apiReachable ? scoredCount : '—', sub: 'with current risk score' },
            { label: 'Critical / High',    value: apiReachable ? `${criticalCount} / ${highCount}` : '—', sub: 'elevated risk entities', accent: (criticalCount + highCount) > 0 },
            { label: 'Open Alerts',        value: apiReachable ? openAlerts.length : '—', sub: 'requiring attention', accent: openAlerts.length > 0 },
          ].map(kpi => (
            <div key={kpi.label} className="card p-4">
              <div className="label mb-2">{kpi.label}</div>
              <div className={`text-3xl font-light ${kpi.accent ? 'text-red' : 'text-ink'}`}>{kpi.value}</div>
              <div className="text-xs text-ink-mid mt-1">{kpi.sub}</div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-3 gap-5">
          {/* Counterparty Watchlist */}
          <div className="col-span-2 card">
            <div className="px-5 py-3 border-b border-border flex items-center justify-between">
              <span className="label">Counterparty Watchlist</span>
              <span className="text-xs text-ink-mid">
                {apiReachable ? `${cps.length} entities` : 'API offline'}
              </span>
            </div>
            <div className="overflow-auto" style={{ maxHeight: 460 }}>
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-surface-2 z-10">
                  <tr>
                    {['Entity', 'Type', 'Score', '7d Δ', '30d Δ', 'Tier', 'Updated'].map(h => (
                      <th key={h} className="label text-left px-4 py-2 font-normal whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    Array.from({ length: 8 }).map((_, i) => (
                      <tr key={i} className="border-t border-border">
                        <td colSpan={7} className="px-4 py-3"><Skeleton /></td>
                      </tr>
                    ))
                  ) : apiReachable === false ? (
                    <tr>
                      <td colSpan={7} className="px-4 py-12 text-center text-ink-mid text-sm">
                        Deploy the API to Fly.io to see counterparty data
                      </td>
                    </tr>
                  ) : cps.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-4 py-12 text-center text-ink-mid text-sm">
                        No counterparties yet — run the scoring pipeline
                      </td>
                    </tr>
                  ) : sortedCps.map(cp => (
                    <tr key={cp.counterparty_id}
                      className="border-t border-border hover:bg-surface-2/60 transition-colors cursor-pointer">
                      <td className="px-4 py-2.5">
                        <div className="font-medium text-sm leading-tight">{cp.display_name}</div>
                        <div className="text-xs text-ink-mid mt-0.5">{cp.jurisdiction ?? '—'}</div>
                      </td>
                      <td className="px-4 py-2.5">
                        <span className="text-xs font-mono text-ink-mid">{cp.entity_type}</span>
                      </td>
                      <td className="px-4 py-2.5"><ScoreBar score={cp.composite_score} /></td>
                      <td className="px-4 py-2.5"><ScoreDelta delta={cp.score_delta_7d} /></td>
                      <td className="px-4 py-2.5"><ScoreDelta delta={cp.score_delta_30d} /></td>
                      <td className="px-4 py-2.5"><TierPill tier={cp.current_risk_tier} /></td>
                      <td className="px-4 py-2.5 text-xs text-ink-mid whitespace-nowrap">
                        {cp.scored_at ? new Date(cp.scored_at).toLocaleDateString('en-CH') : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Right column */}
          <div className="space-y-5">
            {/* Alert Queue */}
            <div className="card">
              <div className="px-5 py-3 border-b border-border flex items-center justify-between">
                <span className="label">Alert Queue</span>
                {openAlerts.filter(a => a.severity === 'CRITICAL').length > 0 && (
                  <span className="bg-red text-white text-xs font-mono px-1.5 py-0.5 rounded">
                    {openAlerts.filter(a => a.severity === 'CRITICAL').length} CRITICAL
                  </span>
                )}
              </div>
              <div style={{ maxHeight: 200, overflowY: 'auto' }}>
                {apiReachable === false || openAlerts.length === 0 ? (
                  <div className="px-5 py-6 text-center text-ink-mid text-xs">
                    {apiReachable === false ? 'API offline' : 'No open alerts'}
                  </div>
                ) : openAlerts.map(alert => (
                  <div key={alert.alert_id} className="px-4 py-3 border-b border-border last:border-0">
                    <div className="flex items-start gap-2">
                      <AlertTriangle className={`w-3.5 h-3.5 mt-0.5 flex-shrink-0 ${
                        alert.severity === 'CRITICAL' ? 'text-red' :
                        alert.severity === 'HIGH' ? 'text-amber' : 'text-ink-mid'
                      }`} />
                      <div>
                        <div className="text-xs font-medium leading-snug">{alert.title}</div>
                        <div className="text-xs text-ink-mid mt-0.5">
                          {new Date(alert.triggered_at).toLocaleDateString('en-CH')}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Quick Actions */}
            <div className="card">
              <div className="px-5 py-3 border-b border-border">
                <span className="label">Quick Actions</span>
              </div>
              <div className="p-4 space-y-2">
                <button
                  disabled={!apiReachable}
                  onClick={async () => {
                    const token = localStorage.getItem('raven_token')
                    await fetch(`${apiUrl}/api/v1/agents/score/run-all`, {
                      method: 'POST',
                      headers: { Authorization: `Bearer ${token}` },
                    })
                    toast.success('Scoring pipeline started')
                  }}
                  className="w-full btn-primary text-xs flex items-center justify-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  <Activity className="w-3.5 h-3.5" /> Run Scoring Pipeline
                </button>
                <button
                  disabled={!apiReachable}
                  className="w-full btn-secondary text-xs flex items-center justify-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  <FileText className="w-3.5 h-3.5" /> Generate Report
                </button>
              </div>
            </div>
          </div>
        </div>

      </main>
    </div>
  )
}
