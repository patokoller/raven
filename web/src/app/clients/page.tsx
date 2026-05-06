'use client'
import { useEffect, useState, useCallback } from 'react'
import AppLayout from '@/components/layout/AppLayout'
import PageHeader from '@/components/layout/PageHeader'
import { RefreshCw, Users, AlertTriangle, Shield, BarChart3, ChevronRight, TrendingDown, TrendingUp } from 'lucide-react'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const H = () => ({ Authorization: `Bearer ${localStorage.getItem('raven_token')}`, 'Content-Type': 'application/json' })

const fmtChf = (v: number) => v >= 1e9 ? `CHF ${(v/1e9).toFixed(2)}B` : v >= 1e6 ? `CHF ${(v/1e6).toFixed(1)}M` : v >= 1e3 ? `CHF ${(v/1e3).toFixed(0)}K` : `CHF ${v?.toFixed(0) || 0}`

function ClientCard({ client, risk }: any) {
  const score = risk?.weighted_risk_score || 0
  const scoreColor = score >= 75 ? 'text-teal' : score >= 55 ? 'text-amber' : score >= 35 ? 'text-orange-500' : 'text-red'
  const tier = score >= 75 ? 'LOW' : score >= 55 ? 'MEDIUM' : score >= 35 ? 'HIGH' : 'CRITICAL'
  const warnings = risk?.cross_portfolio_warnings || []
  const alerts = risk?.total_open_alerts || 0

  return (
    <div className="card p-5 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between gap-4 mb-4">
        <div>
          <div className="text-xs text-ink-mid font-mono mb-0.5">{client.client_ref}</div>
          <h3 className="font-medium text-ink">{client.display_name}</h3>
          {client.domicile && <div className="text-xs text-ink-mid mt-0.5">{client.domicile}</div>}
        </div>
        <div className="text-right">
          <div className={`text-3xl font-light tabular-nums ${scoreColor}`}>{score.toFixed(0)}</div>
          <div className={`text-[10px] font-mono ${scoreColor}`}>{tier}</div>
        </div>
      </div>

      {/* AUM + portfolio count */}
      <div className="grid grid-cols-3 gap-3 mb-4">
        <div className="bg-surface-2 rounded p-2.5 text-center">
          <div className="text-sm font-medium text-ink">{fmtChf(risk?.total_aum_chf || 0)}</div>
          <div className="text-[10px] text-ink-mid">Total AUM</div>
        </div>
        <div className="bg-surface-2 rounded p-2.5 text-center">
          <div className={`text-sm font-medium ${alerts > 0 ? 'text-amber' : 'text-ink'}`}>{alerts}</div>
          <div className="text-[10px] text-ink-mid">Open Alerts</div>
        </div>
        <div className="bg-surface-2 rounded p-2.5 text-center">
          <div className="text-sm font-medium text-ink">{risk?.portfolio_count || 0}</div>
          <div className="text-[10px] text-ink-mid">Portfolios</div>
        </div>
      </div>

      {/* Cross-portfolio concentration warnings */}
      {warnings.length > 0 && (
        <div className="mb-3 space-y-1.5">
          <div className="text-[10px] font-mono text-ink-mid uppercase tracking-wide">Cross-portfolio concentration</div>
          {warnings.slice(0, 3).map((w: any) => (
            <div key={w.name} className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <AlertTriangle className="w-3 h-3 text-amber flex-shrink-0" />
                <span className="text-xs text-ink truncate max-w-[180px]">{w.name}</span>
              </div>
              <span className="text-xs font-mono text-amber">{w.pct}%</span>
            </div>
          ))}
        </div>
      )}

      {/* Per-portfolio breakdown */}
      {risk?.portfolios?.length > 0 && (
        <div className="space-y-1.5 border-t border-border pt-3">
          {risk.portfolios.map((pf: any) => {
            const pfScore = pf.risk?.weighted_risk_score
            const pfColor = !pfScore ? 'text-ink-mid' : pfScore >= 75 ? 'text-teal' : pfScore >= 55 ? 'text-amber' : 'text-red'
            const finma = pf.risk?.finma_compliant
            return (
              <div key={pf.portfolio_id} className="flex items-center justify-between text-xs">
                <span className="text-ink truncate max-w-[200px]">{pf.display_name}</span>
                <div className="flex items-center gap-2">
                  {finma === false && <Shield className="w-3 h-3 text-red" title="FINMA non-compliant" />}
                  {pf.risk?.limit_breaches?.length > 0 && (
                    <span className="text-[10px] font-mono text-red">{pf.risk.limit_breaches.length}B</span>
                  )}
                  <span className={`font-mono font-medium ${pfColor}`}>{pfScore?.toFixed(0) || '—'}</span>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default function ClientsPage() {
  const [clients, setClients] = useState<any[]>([])
  const [risks, setRisks]     = useState<Record<string, any>>({})
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const load = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/v1/portfolios/clients-list`, { headers: H() })
      if (!r.ok) return
      const cls = await r.json()
      setClients(cls)

      // Load risk for each client
      const riskResults = await Promise.allSettled(
        cls.map((c: any) =>
          fetch(`${API}/api/v1/portfolios/clients/${c.client_id}/risk`, { headers: H() })
            .then(r => r.ok ? r.json() : null)
        )
      )
      const riskMap: Record<string, any> = {}
      cls.forEach((c: any, i: number) => {
        const res = riskResults[i]
        if (res.status === 'fulfilled' && res.value) riskMap[c.client_id] = res.value
      })
      setRisks(riskMap)
    } catch {} finally { setLoading(false) }
  }, [])

  useEffect(() => {
    load()
    const interval = setInterval(load, 60000)
    return () => clearInterval(interval)
  }, [load])

  // Aggregate stats
  const totalAum = Object.values(risks).reduce((s: number, r: any) => s + (r?.total_aum_chf || 0), 0)
  const totalAlerts = Object.values(risks).reduce((s: number, r: any) => s + (r?.total_open_alerts || 0), 0)

  return (
    <AppLayout>
      <PageHeader
        title="Clients"
        subtitle="Aggregated risk across all client mandates and portfolios"
        action={
          <button onClick={async () => { setRefreshing(true); await load(); setRefreshing(false) }}
            disabled={refreshing} className="btn-secondary text-xs flex items-center gap-1.5 disabled:opacity-50">
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
            {refreshing ? 'Refreshing…' : 'Refresh'}
          </button>
        }
      />

      <div className="p-8 space-y-6">
        {/* Aggregate KPIs */}
        <div className="grid grid-cols-3 gap-3">
          {[
            { label: 'Total AUM', value: fmtChf(totalAum) },
            { label: 'Total Open Alerts', value: totalAlerts, color: totalAlerts > 0 ? 'text-amber' : '' },
            { label: 'Active Clients', value: clients.length },
          ].map(({ label, value, color }: any) => (
            <div key={label} className="card p-4 text-center">
              <div className={`text-2xl font-light ${color || 'text-ink'}`}>{value}</div>
              <div className="text-xs text-ink-mid mt-0.5">{label}</div>
            </div>
          ))}
        </div>

        {loading ? (
          <div className="text-sm text-ink-mid">Loading…</div>
        ) : clients.length === 0 ? (
          <div className="card p-8 text-center">
            <Users className="w-8 h-8 text-ink-mid mx-auto mb-3" />
            <div className="text-sm font-medium mb-1">No clients yet</div>
            <p className="text-xs text-ink-mid">Upload a portfolio to create client records automatically.</p>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-4">
            {clients.map(c => (
              <ClientCard key={c.client_id} client={c} risk={risks[c.client_id]} />
            ))}
          </div>
        )}
      </div>
    </AppLayout>
  )
}
