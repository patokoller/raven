'use client'

import { useEffect, useState } from 'react'
import { TrendingDown, TrendingUp, Minus, RefreshCw, Activity, AlertTriangle } from 'lucide-react'
import AppLayout from '@/components/layout/AppLayout'
import PageHeader from '@/components/layout/PageHeader'
import toast from 'react-hot-toast'
import dynamic from 'next/dynamic'
const AlertModal = dynamic(() => import('@/components/dashboard/AlertModal'), { ssr: false })

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

function authHeaders() {
  const token = localStorage.getItem('raven_token')
  return { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }
}

function TierPill({ tier }: { tier?: string }) {
  if (!tier) return <span className="text-ink-mid text-xs">—</span>
  const cls: Record<string, string> = {
    LOW: 'bg-teal/10 text-teal border-teal/20',
    MEDIUM: 'bg-amber/10 text-amber border-amber/20',
    HIGH: 'bg-red/10 text-red border-red/20',
    CRITICAL: 'bg-red text-white border-red',
  }
  return <span className={`text-xs font-mono px-2 py-0.5 rounded border ${cls[tier] ?? 'bg-surface-2 border-border'}`}>{tier}</span>
}

function ScoreDelta({ delta }: { delta?: number | null }) {
  if (delta == null) return <span className="text-ink-mid text-xs font-mono">—</span>
  if (Math.abs(delta) < 0.5) return <span className="text-ink-mid text-xs font-mono flex items-center gap-1"><Minus className="w-3 h-3" />{delta.toFixed(1)}</span>
  if (delta > 0) return <span className="text-teal text-xs font-mono flex items-center gap-1"><TrendingUp className="w-3 h-3" />+{delta.toFixed(1)}</span>
  return <span className="text-red text-xs font-mono flex items-center gap-1"><TrendingDown className="w-3 h-3" />{delta.toFixed(1)}</span>
}

function ScoreBar({ score }: { score?: number | null }) {
  if (!score) return <div className="flex items-center gap-2"><div className="w-16 h-1.5 bg-surface-2 rounded-full" /><span className="text-xs font-mono text-ink-mid">—</span></div>
  const color = score >= 75 ? '#2A7C6F' : score >= 55 ? '#E67E22' : '#C0392B'
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 bg-surface-2 rounded-full overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${score}%`, background: color }} />
      </div>
      <span className="text-xs font-mono text-ink-mid">{score.toFixed(0)}</span>
    </div>
  )
}

export default function DashboardPage() {
  const [cps, setCps] = useState<any[]>([])
  const [alerts, setAlerts] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [scoring, setScoring] = useState(false)
  const [selectedAlert, setSelectedAlert] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      const [cpRes, alertRes] = await Promise.all([
        fetch(`${API}/api/v1/counterparties`, { headers: authHeaders() }),
        fetch(`${API}/api/v1/alerts`, { headers: authHeaders() }),
      ])
      if (cpRes.ok) setCps(await cpRes.json())
      if (alertRes.ok) setAlerts(await alertRes.json())
    } catch { toast.error('Failed to load data') }
    finally { setLoading(false) }
  }

  useEffect(() => {
    load()
    const interval = setInterval(load, 30000)
    return () => clearInterval(interval)
  }, [])

  const runScoring = async () => {
    setScoring(true)
    try {
      await fetch(`${API}/api/v1/agents/score/run-all`, { method: 'POST', headers: authHeaders() })
      toast.success('Scoring started — refresh in 60s')
    } catch { toast.error('Failed to start scoring') }
    finally { setScoring(false) }
  }

  const criticalCount = cps.filter(c => c.current_risk_tier === 'CRITICAL').length
  const highCount     = cps.filter(c => c.current_risk_tier === 'HIGH').length
  const scoredCount   = cps.filter(c => c.composite_score != null).length
  const sortedCps     = [...cps].sort((a, b) => {
    const o = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 }
    return (o[a.current_risk_tier as keyof typeof o] ?? 4) - (o[b.current_risk_tier as keyof typeof o] ?? 4)
  })

  return (
    <AppLayout>
      <PageHeader
        title="Dashboard"
        subtitle="Counterparty risk overview"
        action={
          <div className="flex gap-2">
            <button onClick={load} className="btn-secondary text-xs flex items-center gap-1.5 py-1.5">
              <RefreshCw className="w-3 h-3" /> Refresh
            </button>
            <button onClick={runScoring} disabled={scoring} className="btn-primary text-xs flex items-center gap-1.5 py-1.5">
              <Activity className="w-3 h-3" /> {scoring ? 'Running…' : 'Run Scoring'}
            </button>
          </div>
        }
      />

      <div className="p-8 space-y-6">
        {/* KPIs */}
        <div className="grid grid-cols-4 gap-4">
          {[
            { label: 'Monitored Entities', value: cps.length, sub: 'counterparties' },
            { label: 'Scored', value: scoredCount, sub: 'with current score' },
            { label: 'Critical / High', value: `${criticalCount} / ${highCount}`, sub: 'elevated risk', red: criticalCount + highCount > 0 },
            { label: 'Open Alerts', value: alerts.length, sub: 'requiring attention', red: alerts.length > 0 },
          ].map(k => (
            <div key={k.label} className="card p-4">
              <div className="label mb-2">{k.label}</div>
              <div className={`text-3xl font-light ${k.red ? 'text-red' : 'text-ink'}`}>{loading ? '—' : k.value}</div>
              <div className="text-xs text-ink-mid mt-1">{k.sub}</div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-3 gap-6">
          {/* Watchlist */}
          <div className="col-span-2 card">
            <div className="px-5 py-3 border-b border-border flex items-center justify-between">
              <span className="label">Counterparty Watchlist</span>
              <span className="text-xs text-ink-mid">{cps.length} entities</span>
            </div>
            <div className="overflow-auto" style={{ maxHeight: 480 }}>
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-surface-2 z-10">
                  <tr>{['Entity','Type','Score','7d Δ','30d Δ','Tier','Updated'].map(h => (
                    <th key={h} className="label text-left px-4 py-2 font-normal whitespace-nowrap">{h}</th>
                  ))}</tr>
                </thead>
                <tbody>
                  {loading ? Array.from({length:6}).map((_,i) => (
                    <tr key={i} className="border-t border-border">
                      <td colSpan={7} className="px-4 py-3"><div className="h-3 bg-surface-2 rounded animate-pulse" /></td>
                    </tr>
                  )) : sortedCps.map(cp => (
                    <tr key={cp.counterparty_id} className="border-t border-border hover:bg-surface-2/50 transition-colors">
                      <td className="px-4 py-2.5">
                        <div className="font-medium text-sm">{cp.display_name}</div>
                        <div className="text-xs text-ink-mid">{cp.jurisdiction ?? '—'}</div>
                      </td>
                      <td className="px-4 py-2.5 text-xs font-mono text-ink-mid">{cp.entity_type}</td>
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

          {/* Alert queue */}
          <div className="card">
            <div className="px-5 py-3 border-b border-border">
              <span className="label">Alert Queue</span>
            </div>
            {alerts.length === 0 ? (
              <div className="px-5 py-10 text-center text-ink-mid text-xs">No open alerts</div>
            ) : alerts.map(a => (
              <div key={a.alert_id} className="px-4 py-3 border-b border-border last:border-0">
                <div className="flex items-start gap-2">
                  <AlertTriangle className={`w-3.5 h-3.5 mt-0.5 flex-shrink-0 ${a.severity === 'CRITICAL' ? 'text-red' : a.severity === 'HIGH' ? 'text-amber' : 'text-ink-mid'}`} />
                  <div>
                    <div className="text-xs font-medium leading-snug">{a.title}</div>
                    <div className="text-xs text-ink-mid mt-0.5">{new Date(a.triggered_at).toLocaleDateString('en-CH')}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
      {selectedAlert && (
        <AlertModal
          alertId={selectedAlert}
          onClose={() => setSelectedAlert(null)}
          onAction={load}
        />
      )}
    </AppLayout>
  )
}
