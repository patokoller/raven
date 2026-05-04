'use client'

import { useEffect, useState } from 'react'
import { AlertTriangle, TrendingDown, TrendingUp, Minus, RefreshCw, FileText, Shield, Activity } from 'lucide-react'
import { counterparties, alerts, portfolios, agents } from '@/lib/api'
import toast from 'react-hot-toast'

// ── Helpers ───────────────────────────────────────────────────

function TierPill({ tier }: { tier: string }) {
  const classes: Record<string, string> = {
    LOW: 'bg-teal/10 text-teal border-teal/20',
    MEDIUM: 'bg-amber/10 text-amber border-amber/20',
    HIGH: 'bg-red/10 text-red border-red/20',
    CRITICAL: 'bg-red text-white border-red',
  }
  return (
    <span className={`text-xs font-mono px-2 py-0.5 rounded border ${classes[tier] || 'bg-surface-2 border-border text-ink-mid'}`}>
      {tier || '—'}
    </span>
  )
}

function ScoreDelta({ delta }: { delta: number | null }) {
  if (delta === null || delta === undefined) return <span className="text-ink-mid text-xs">—</span>
  if (Math.abs(delta) < 0.5) return <span className="text-ink-mid text-xs flex items-center gap-1"><Minus className="w-3 h-3" />{delta.toFixed(1)}</span>
  if (delta > 0) return <span className="text-teal text-xs flex items-center gap-1"><TrendingUp className="w-3 h-3" />+{delta.toFixed(1)}</span>
  return <span className="text-red text-xs flex items-center gap-1"><TrendingDown className="w-3 h-3" />{delta.toFixed(1)}</span>
}

function ScoreBar({ score }: { score: number | null }) {
  if (!score) return <div className="w-16 h-1.5 bg-surface-2 rounded-full" />
  const color = score >= 75 ? '#2A7C6F' : score >= 55 ? '#E67E22' : '#C0392B'
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 bg-surface-2 rounded-full overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${score}%`, background: color }} />
      </div>
      <span className="text-xs font-mono text-ink-mid w-6">{score?.toFixed(0)}</span>
    </div>
  )
}

// ── Main Dashboard ────────────────────────────────────────────

export default function DashboardPage() {
  const [cps, setCps] = useState<any[]>([])
  const [openAlerts, setOpenAlerts] = useState<any[]>([])
  const [portfolioList, setPortfolioList] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [scoring, setScoring] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const [cpData, alertData, pfData] = await Promise.all([
        counterparties.list(),
        alerts.list(),
        portfolios.list(),
      ])
      setCps(cpData)
      setOpenAlerts(alertData)
      setPortfolioList(pfData)
    } catch (e: any) {
      toast.error(e.message || 'Failed to load dashboard')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const triggerScoring = async () => {
    setScoring(true)
    try {
      await agents.runAllScores()
      toast.success('Scoring pipeline started — refresh in 60s')
    } catch (e: any) {
      toast.error(e.message)
    } finally {
      setScoring(false)
    }
  }

  // Summary stats
  const criticalCount = cps.filter(c => c.current_risk_tier === 'CRITICAL').length
  const highCount = cps.filter(c => c.current_risk_tier === 'HIGH').length
  const criticalAlerts = openAlerts.filter(a => a.severity === 'CRITICAL').length

  return (
    <div className="min-h-screen bg-surface">
      {/* Top bar */}
      <header className="border-b border-border bg-white px-6 py-4 flex items-center justify-between sticky top-0 z-10">
        <div className="flex items-center gap-3">
          <Shield className="w-5 h-5 text-gold" />
          <span className="font-mono text-sm tracking-widest uppercase text-ink">Raven</span>
          <span className="text-border">|</span>
          <span className="text-xs text-ink-mid">Risk & Portfolio Intelligence</span>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={load} className="btn-secondary flex items-center gap-1.5 text-xs">
            <RefreshCw className="w-3.5 h-3.5" /> Refresh
          </button>
          <button onClick={triggerScoring} disabled={scoring} className="btn-primary flex items-center gap-1.5 text-xs">
            <Activity className="w-3.5 h-3.5" />
            {scoring ? 'Running...' : 'Run Scoring'}
          </button>
        </div>
      </header>

      <main className="p-6 max-w-[1400px] mx-auto space-y-6">

        {/* KPI row */}
        <div className="grid grid-cols-4 gap-4">
          {[
            { label: 'Monitored Entities', value: cps.length, sub: 'counterparties', color: 'text-ink' },
            { label: 'Critical Risk', value: criticalCount, sub: 'entities CRITICAL tier', color: 'text-red' },
            { label: 'High Risk', value: highCount, sub: 'entities HIGH tier', color: 'text-amber' },
            { label: 'Open Alerts', value: criticalAlerts, sub: `${openAlerts.length} total open`, color: 'text-red' },
          ].map(kpi => (
            <div key={kpi.label} className="card p-4">
              <div className="label mb-2">{kpi.label}</div>
              <div className={`text-3xl font-light ${kpi.color}`}>{loading ? '—' : kpi.value}</div>
              <div className="text-xs text-ink-mid mt-1">{kpi.sub}</div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-3 gap-6">
          {/* Counterparty Watchlist */}
          <div className="col-span-2 card">
            <div className="px-5 py-3 border-b border-border flex items-center justify-between">
              <span className="label">Counterparty Watchlist</span>
              <span className="text-xs text-ink-mid">{cps.length} entities</span>
            </div>
            <div className="overflow-auto max-h-[480px]">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-surface-2">
                  <tr>
                    {['Entity', 'Type', 'Score', '7d', '30d', 'Tier', 'Updated'].map(h => (
                      <th key={h} className="label text-left px-4 py-2 font-normal">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    Array.from({ length: 8 }).map((_, i) => (
                      <tr key={i} className="border-t border-border">
                        <td colSpan={7} className="px-4 py-3"><div className="h-3 bg-surface-2 rounded animate-pulse" /></td>
                      </tr>
                    ))
                  ) : (
                    cps.sort((a, b) => {
                      const tierOrder = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 }
                      return (tierOrder[a.current_risk_tier as keyof typeof tierOrder] ?? 4) -
                             (tierOrder[b.current_risk_tier as keyof typeof tierOrder] ?? 4)
                    }).map(cp => (
                      <tr key={cp.counterparty_id} className="border-t border-border hover:bg-surface-2/50 transition-colors cursor-pointer">
                        <td className="px-4 py-2.5">
                          <div className="font-medium text-sm">{cp.display_name}</div>
                          <div className="text-xs text-ink-mid">{cp.jurisdiction || '—'}</div>
                        </td>
                        <td className="px-4 py-2.5">
                          <span className="text-xs font-mono text-ink-mid">{cp.entity_type}</span>
                        </td>
                        <td className="px-4 py-2.5">
                          <ScoreBar score={cp.composite_score} />
                        </td>
                        <td className="px-4 py-2.5"><ScoreDelta delta={cp.score_delta_7d} /></td>
                        <td className="px-4 py-2.5"><ScoreDelta delta={cp.score_delta_30d} /></td>
                        <td className="px-4 py-2.5"><TierPill tier={cp.current_risk_tier} /></td>
                        <td className="px-4 py-2.5 text-xs text-ink-mid">
                          {cp.scored_at ? new Date(cp.scored_at).toLocaleDateString() : '—'}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Alert Queue */}
          <div className="card">
            <div className="px-5 py-3 border-b border-border flex items-center justify-between">
              <span className="label">Alert Queue</span>
              {criticalAlerts > 0 && (
                <span className="bg-red text-white text-xs font-mono px-1.5 py-0.5 rounded">{criticalAlerts} CRITICAL</span>
              )}
            </div>
            <div className="overflow-auto max-h-[480px]">
              {loading ? (
                <div className="p-4 space-y-3">
                  {Array.from({ length: 4 }).map((_, i) => (
                    <div key={i} className="h-14 bg-surface-2 rounded animate-pulse" />
                  ))}
                </div>
              ) : openAlerts.length === 0 ? (
                <div className="p-8 text-center text-ink-mid text-sm">No open alerts</div>
              ) : (
                openAlerts.map(alert => (
                  <div key={alert.alert_id} className="px-4 py-3 border-b border-border last:border-0">
                    <div className="flex items-start gap-2">
                      <AlertTriangle className={`w-3.5 h-3.5 mt-0.5 flex-shrink-0 ${
                        alert.severity === 'CRITICAL' ? 'text-red' : alert.severity === 'HIGH' ? 'text-amber' : 'text-ink-mid'
                      }`} />
                      <div>
                        <div className="text-xs font-medium leading-snug">{alert.title}</div>
                        <div className="text-xs text-ink-mid mt-0.5">
                          {new Date(alert.triggered_at).toLocaleDateString()}
                        </div>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Report Workflow Queue */}
        <div className="card">
          <div className="px-5 py-3 border-b border-border flex items-center justify-between">
            <span className="label">Report Workflow Queue</span>
            <a href="/reports/new" className="btn-primary text-xs flex items-center gap-1.5">
              <FileText className="w-3.5 h-3.5" /> Generate Report
            </a>
          </div>
          <div className="px-5 py-8 text-center text-ink-mid text-sm">
            No reports yet. Upload a portfolio and trigger report generation to get started.
          </div>
        </div>

      </main>
    </div>
  )
}
