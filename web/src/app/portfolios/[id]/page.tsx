'use client'
import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import AppLayout from '@/components/layout/AppLayout'
import PageHeader from '@/components/layout/PageHeader'
import { BarChart2, Zap, FileText } from 'lucide-react'
import Link from 'next/link'
import toast from 'react-hot-toast'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const H = () => ({ Authorization: `Bearer ${localStorage.getItem('raven_token')}`, 'Content-Type': 'application/json' })

function MetricCard({ label, value, sub, accent }: any) {
  return (
    <div className="card p-4">
      <div className="label mb-2">{label}</div>
      <div className={`text-2xl font-light ${accent ? 'text-red' : 'text-ink'}`}>{value ?? '—'}</div>
      {sub && <div className="text-xs text-ink-mid mt-1">{sub}</div>}
    </div>
  )
}

export default function PortfolioDetailPage() {
  const { id }           = useParams()
  const [portfolio, setPortfolio] = useState<any>(null)
  const [metrics, setMetrics]     = useState<any>(null)
  const [risk, setRisk]           = useState<any>(null)
  const [positions, setPositions] = useState<any[]>([])
  const [scenarios, setScenarios] = useState<any[]>([])
  const [stressResults, setStressResults] = useState<any[]>([])
  const [loading, setLoading]     = useState(true)
  const [running, setRunning]     = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      const [pfRes, mRes, posRes, scRes, srRes] = await Promise.all([
        fetch(`${API}/api/v1/portfolios`, { headers: H() }),
        fetch(`${API}/api/v1/portfolios/${id}/metrics`, { headers: H() }),
        fetch(`${API}/api/v1/portfolios/${id}/positions`, { headers: H() }),
        fetch(`${API}/api/v1/stress/scenarios`, { headers: H() }),
        fetch(`${API}/api/v1/stress/results/${id}`, { headers: H() }),
      ])
      const pfs = pfRes.ok ? await pfRes.json() : []
      setPortfolio(pfs.find((p: any) => p.portfolio_id === id) ?? null)
      if (mRes.ok) setMetrics(await mRes.json())
      if (posRes.ok) setPositions(await posRes.json())
      if (scRes.ok) setScenarios(await scRes.json())
      if (srRes.ok) setStressResults(await srRes.json())
    } catch {} finally { setLoading(false) }
  }

  useEffect(() => { if (id) load() }, [id])

  const runStress = async (scenario_id: string, name: string) => {
    setRunning(scenario_id)
    try {
      const r = await fetch(`${API}/api/v1/portfolios/${id}/stress`, {
        method: 'POST',
        headers: H(),
        body: JSON.stringify({ scenario_id }),
      })
      if (r.ok) {
        toast.success(`${name} stress test queued — refresh in 30s`)
        setTimeout(load, 5000)
      }
    } catch { toast.error('Failed to run stress test') }
    finally { setRunning(null) }
  }

  const fmt = (n: number | null | undefined, decimals = 2, prefix = '') =>
    n != null ? `${prefix}${n.toFixed(decimals)}` : '—'

  const fmtChf = (n: number | null | undefined) =>
    n != null ? `CHF ${n.toLocaleString('en-CH', { maximumFractionDigits: 0 })}` : '—'

  const fmtPct = (n: number | null | undefined) =>
    n != null ? `${(n * 100).toFixed(2)}%` : '—'

  return (
    <AppLayout>
      <PageHeader
        title={portfolio?.display_name ?? 'Portfolio'}
        subtitle={`${portfolio?.portfolio_ref ?? ''} · ${portfolio?.clients?.display_name ?? ''}`}
        action={
          <Link href={`/reports?portfolio=${id}&client=${portfolio?.client_id}`}>
            <button className="btn-primary text-xs flex items-center gap-1.5">
              <FileText className="w-3.5 h-3.5" /> Generate Report
            </button>
          </Link>
        }
      />

      <div className="p-8 space-y-6">
        {/* Risk metrics */}
        <div>
          <div className="label mb-3">Risk Metrics</div>
          <div className="grid grid-cols-4 gap-4">
            <MetricCard label="Portfolio NAV" value={fmtChf(portfolio?.total_nav_chf)} sub="base currency CHF" />
            <MetricCard label="VaR 95% (1-day)" value={fmtChf(metrics?.var_95_1d)} sub="historical simulation" accent={metrics?.var_95_1d > (portfolio?.total_nav_chf ?? 0) * 0.05} />
            <MetricCard label="Max Drawdown 30d" value={fmtPct(metrics?.max_drawdown_30d)} sub="peak-to-trough" accent={(metrics?.max_drawdown_30d ?? 0) < -0.15} />
            <MetricCard label="Sharpe Ratio" value={fmt(metrics?.sharpe_ratio_30d)} sub="30d annualised" />
          </div>
          <div className="grid grid-cols-5 gap-4 mt-4">
            <MetricCard label="Volatility 30d" value={fmtPct(metrics?.volatility_30d)} sub="annualised" />
            <MetricCard label="Concentration (HHI)" value={fmt(metrics?.hhi, 4)} sub="1.0 = fully concentrated" accent={(metrics?.hhi ?? 0) > 0.25} />
            <MetricCard label="Top Custodian" value={metrics?.top_custodian_name ?? '—'} sub={fmtPct(metrics?.top_custodian_pct) + ' of AuM'} accent={(metrics?.top_custodian_pct ?? 0) > 0.5} />
            <MetricCard
              label="Market Risk Score"
              value={metrics?.risk_score_composite ? `${metrics.risk_score_composite}/100` : '—'}
              sub={metrics?.risk_tier ? `${metrics.risk_tier} · VaR + volatility` : 'VaR + volatility'}
            />
            <MetricCard
              label="Counterparty Risk Score"
              value={risk?.weighted_risk_score != null ? `${risk.weighted_risk_score.toFixed(0)}/100` : '—'}
              sub={risk ? (
                (risk.weighted_risk_score >= 75 ? 'LOW' : risk.weighted_risk_score >= 55 ? 'MEDIUM' : risk.weighted_risk_score >= 35 ? 'HIGH' : 'CRITICAL') +
                (risk.score_delta_7d && Math.abs(risk.score_delta_7d) >= 0.1
                  ? ` · ${risk.score_delta_7d > 0 ? '+' : ''}${risk.score_delta_7d.toFixed(1)} (7d)`
                  : ' · exposure-weighted')
              ) : 'click Recompute Risk'}
              accent={risk?.weighted_risk_score != null && risk.weighted_risk_score < 55}
            />
          </div>
          {!metrics && !loading && (
            <div className="mt-3 text-xs text-ink-mid bg-surface-2 rounded p-3">
              Metrics are computed in the background after upload. If this is a new portfolio, refresh in 30 seconds.
            </div>
          )}
        </div>

        <div className="grid grid-cols-2 gap-6">
          {/* Counterparty Risk Analytics */}
      {risk && (
        <div className="grid grid-cols-2 gap-4">
          {/* Tier breakdown */}
          <div className="card p-4">
            <div className="label mb-3">Risk Tier Breakdown</div>
            <div className="space-y-2">
              {Object.entries(risk.risk_tier_breakdown || {}).map(([tier, val]: any) => {
                const nav = risk.total_nav_chf || 1
                const pct = (val / nav) * 100
                const colors: any = { LOW: 'bg-teal', MEDIUM: 'bg-amber', HIGH: 'bg-orange-500', CRITICAL: 'bg-red' }
                return pct > 0 ? (
                  <div key={tier}>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-ink-mid">{tier}</span>
                      <span className="font-mono">CHF {(val/1e6).toFixed(1)}M ({pct.toFixed(0)}%)</span>
                    </div>
                    <div className="h-1.5 bg-surface-2 rounded overflow-hidden">
                      <div className={`h-full ${colors[tier]}`} style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                ) : null
              })}
            </div>
          </div>

          {/* Jurisdiction */}
          <div className="card p-4">
            <div className="label mb-3">Jurisdiction Concentration</div>
            <div className="space-y-2">
              {Object.entries(risk.jurisdiction_breakdown || {})
                .sort((a: any, b: any) => b[1] - a[1])
                .slice(0, 6)
                .map(([j, val]: any) => {
                  const pct = (val / (risk.total_nav_chf || 1)) * 100
                  return (
                    <div key={j} className="flex justify-between text-xs">
                      <span className="text-ink-mid">{j}</span>
                      <span className="font-mono">{pct.toFixed(0)}%</span>
                    </div>
                  )
                })}
            </div>
          </div>

          {/* Concentration warnings */}
          {risk.concentration_warnings?.length > 0 && (
            <div className="card p-4">
              <div className="label mb-3 flex items-center gap-2">
                Concentration Warnings
                <span className="text-[10px] font-mono bg-amber/10 text-amber px-1.5 py-0.5 rounded">{risk.concentration_warnings.length}</span>
              </div>
              <div className="space-y-2">
                {risk.concentration_warnings.map((w: any) => (
                  <div key={w.name} className="flex items-center justify-between p-2 bg-amber/5 border border-amber/20 rounded">
                    <span className="text-xs font-medium">{w.name}</span>
                    <span className={`text-xs font-mono ${w.severity === 'CRITICAL' ? 'text-red' : 'text-amber'}`}>{w.pct}%</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Limit breaches */}
          {risk.limit_breaches?.length > 0 && (
            <div className="card p-4">
              <div className="label mb-3 flex items-center gap-2">
                Limit Breaches
                <span className="text-[10px] font-mono bg-red/10 text-red px-1.5 py-0.5 rounded">{risk.limit_breaches.length}</span>
              </div>
              <div className="space-y-2">
                {risk.limit_breaches.map((b: any, i: number) => (
                  <div key={i} className="flex items-center justify-between p-2 bg-red/5 border border-red/20 rounded">
                    <div>
                      <div className="text-xs font-medium capitalize">{b.type} {b.key}</div>
                      <div className="text-[10px] text-ink-mid">Limit: {b.limit_pct}% · Actual: {b.actual_pct}%</div>
                    </div>
                    <span className="text-[10px] font-mono text-red bg-red/10 px-1.5 py-0.5 rounded">{b.status}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* FINMA flags */}
          {risk.finma_flags?.length > 0 && (
            <div className="card p-4 col-span-2">
              <div className="label mb-3 text-red flex items-center gap-1.5">
                ⚠ FINMA Compliance Issues
              </div>
              <div className="space-y-2">
                {risk.finma_flags.map((f: any) => (
                  <div key={f.name} className="p-2.5 bg-red/5 border border-red/20 rounded">
                    <div className="flex justify-between mb-0.5">
                      <span className="text-xs font-medium">{f.name}</span>
                      <span className="text-xs font-mono text-ink-mid">{f.pct}% of portfolio</span>
                    </div>
                    <p className="text-xs text-ink-mid">{f.reason}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Correlation groups */}
          {risk.correlation_groups?.length > 0 && (
            <div className="card p-4 col-span-2">
              <div className="label mb-3">Correlation Risk Groups</div>
              <div className="space-y-3">
                {risk.correlation_groups.map((g: any) => (
                  <div key={g.group} className="p-3 bg-amber/5 border border-amber/20 rounded">
                    <div className="flex justify-between mb-1">
                      <span className="text-xs font-medium">{g.group}</span>
                      <span className="text-xs font-mono text-amber">{g.combined_pct}% combined</span>
                    </div>
                    <p className="text-[10px] text-ink-mid mb-2">{g.description}</p>
                    <div className="flex flex-wrap gap-1.5">
                      {g.entities.map((e: any) => (
                        <span key={e.name} className="text-[10px] font-mono bg-surface-2 px-1.5 py-0.5 rounded">
                          {e.name} {e.pct}%
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Positions */}
          <div className="card">
            <div className="px-5 py-3 border-b border-border flex items-center justify-between">
              <span className="label">Positions</span>
              <span className="text-xs text-ink-mid">{positions.length} holdings</span>
            </div>
            <div className="overflow-auto" style={{ maxHeight: 400 }}>
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-surface-2">
                  <tr>{['Asset','Class','Quantity','Value CHF','Weight','Custodian'].map(h => (
                    <th key={h} className="label text-left px-4 py-2 font-normal text-[10px]">{h}</th>
                  ))}</tr>
                </thead>
                <tbody>
                  {positions.map((p: any) => (
                    <tr key={p.position_id} className="border-t border-border hover:bg-surface-2/50">
                      <td className="px-4 py-2 font-mono text-xs font-medium">{p.asset_symbol}</td>
                      <td className="px-4 py-2 text-xs text-ink-mid">{p.asset_class}</td>
                      <td className="px-4 py-2 text-xs font-mono">{Number(p.quantity).toLocaleString()}</td>
                      <td className="px-4 py-2 text-xs">{p.market_value_chf ? `${Number(p.market_value_chf).toLocaleString('en-CH', {maximumFractionDigits:0})}` : '—'}</td>
                      <td className="px-4 py-2 text-xs">{p.weight_pct ? `${(p.weight_pct*100).toFixed(1)}%` : '—'}</td>
                      <td className="px-4 py-2 text-xs text-ink-mid">{p.custodian_name ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Stress tests */}
          <div className="card">
            <div className="px-5 py-3 border-b border-border">
              <span className="label">Stress Test Scenarios</span>
              <p className="text-xs text-ink-mid mt-0.5">15 scenarios across crypto, macro, equity, and tail risk</p>
            </div>
            <div className="p-4 space-y-4">
              {(['crypto', 'macro', 'equity', 'tail'] as const).map(cat => {
                const catScenarios = scenarios.filter((s: any) => s.category === cat)
                if (!catScenarios.length) return null
                const catLabels: Record<string, string> = {
                  crypto: '⛓ Crypto & Custody',
                  macro:  '📊 Macro & Rates',
                  equity: '📈 Equity Markets',
                  tail:   '⚠ Tail Risk',
                }
                return (
                  <div key={cat}>
                    <div className="text-[10px] font-mono text-ink-mid uppercase tracking-widest mb-2">{catLabels[cat]}</div>
                    <div className="space-y-2">
                      {catScenarios.map((s: any) => {
                        const result = stressResults.find((r: any) =>
                          r.scenario_id === s.scenario_id || r.scenario_id === s.slug
                        )
                        const pnlPct = result?.portfolio_pnl_pct
                        const pnlChf = result?.portfolio_pnl_chf
                        const severity = pnlPct != null
                          ? pnlPct < -0.30 ? 'text-red' : pnlPct < -0.15 ? 'text-orange-500' : pnlPct < -0.05 ? 'text-amber' : 'text-teal'
                          : 'text-ink-mid'
                        return (
                          <div key={s.scenario_id} className={`flex items-start justify-between p-3 rounded border ${
                            result ? 'bg-surface-2 border-border' : 'bg-white border-border/60'
                          }`}>
                            <div className="flex-1 min-w-0 mr-3">
                              <div className="text-xs font-medium text-ink">{s.display_name}</div>
                              {s.description && !result && (
                                <div className="text-[10px] text-ink-mid mt-0.5 leading-relaxed line-clamp-2">{s.description}</div>
                              )}
                              {result && (
                                <div className="mt-1.5 space-y-1">
                                  <div className={`text-sm font-mono font-medium ${severity}`}>
                                    {pnlPct != null ? `${(pnlPct * 100).toFixed(1)}%` : '—'}
                                    {pnlChf != null && (
                                      <span className="text-xs ml-2 font-normal">
                                        {pnlChf >= 0 ? '+' : ''}{pnlChf.toLocaleString('de-CH', { style: 'currency', currency: 'CHF', maximumFractionDigits: 0 })}
                                      </span>
                                    )}
                                  </div>
                                  {result.worst_positions?.length > 0 && (
                                    <div className="text-[10px] text-ink-mid">
                                      Worst: {result.worst_positions.slice(0,3).map((p: any) => `${p.asset_symbol} ${p.shock_pct?.toFixed(0)}%`).join(' · ')}
                                    </div>
                                  )}
                                  {result.post_nav_chf != null && (
                                    <div className="text-[10px] text-ink-mid">
                                      Post-stress NAV: {result.post_nav_chf.toLocaleString('de-CH', { style: 'currency', currency: 'CHF', maximumFractionDigits: 0 })}
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                            <button
                              onClick={() => runStress(s.scenario_id, s.display_name)}
                              disabled={running === s.scenario_id}
                              className="btn-secondary text-xs flex items-center gap-1 py-1 flex-shrink-0 disabled:opacity-50"
                            >
                              <Zap className="w-3 h-3" />
                              {running === s.scenario_id ? 'Running…' : result ? 'Re-run' : 'Run'}
                            </button>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      </div>
    </AppLayout>
  )
}
