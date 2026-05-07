'use client'
import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import AppLayout from '@/components/layout/AppLayout'
import PageHeader from '@/components/layout/PageHeader'
import { Zap, FileText } from 'lucide-react'
import Link from 'next/link'
import toast from 'react-hot-toast'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const H = () => ({ Authorization: `Bearer ${localStorage.getItem('raven_token')}`, 'Content-Type': 'application/json' })

function MetricCard({ label, value, sub, accent }: any) {
  return (
    <div className="card p-4">
      <div className="label mb-2">{label}</div>
      <div className={`text-2xl font-light ${accent ? 'text-red' : 'text-ink'}`}>{value ?? '\u2014'}</div>
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
      const [pfRes, mRes, posRes, scRes, srRes, rRes] = await Promise.all([
        fetch(`${API}/api/v1/portfolios`, { headers: H() }),
        fetch(`${API}/api/v1/portfolios/${id}/metrics`, { headers: H() }),
        fetch(`${API}/api/v1/portfolios/${id}/positions`, { headers: H() }),
        fetch(`${API}/api/v1/stress/scenarios`, { headers: H() }),
        fetch(`${API}/api/v1/stress/results/${id}`, { headers: H() }),
        fetch(`${API}/api/v1/portfolios/${id}/risk`, { headers: H() }),
      ])
      const pfs = pfRes.ok ? await pfRes.json() : []
      setPortfolio(pfs.find((p: any) => p.portfolio_id === id) ?? null)
      if (mRes.ok)  setMetrics(await mRes.json())
      if (posRes.ok) setPositions(await posRes.json())
      if (scRes.ok) setScenarios(await scRes.json())
      if (srRes.ok) setStressResults(await srRes.json())
      if (rRes.ok)  setRisk(await rRes.json())
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
        const result = await r.json()
        setStressResults(prev => {
          const filtered = prev.filter((x: any) => x.scenario_id !== result.scenario_id)
          return [result, ...filtered]
        })
        toast.success(`${name}: ${result.pnl_pct > 0 ? '+' : ''}${result.pnl_pct?.toFixed(1)}%`)
      } else {
        const err = await r.json()
        toast.error(err.detail || 'Stress test failed')
      }
    } catch { toast.error('Failed to run stress test') }
    finally { setRunning(null) }
  }

  const fmtChf = (n: number | null | undefined) =>
    n != null ? `CHF ${n.toLocaleString('de-CH', { maximumFractionDigits: 0 })}` : '\u2014'

  const fmtPct = (n: number | null | undefined) =>
    n != null ? `${(n * 100).toFixed(2)}%` : '\u2014'

  const fmt = (n: number | null | undefined, decimals = 2) =>
    n != null ? n.toFixed(decimals) : '\u2014'

  const scoreColor = (s: number) =>
    s >= 75 ? 'text-teal' : s >= 55 ? 'text-amber' : s >= 35 ? 'text-orange-500' : 'text-red'

  const scoreTier = (s: number) =>
    s >= 75 ? 'LOW' : s >= 55 ? 'MEDIUM' : s >= 35 ? 'HIGH' : 'CRITICAL'

  const catLabels: Record<string, string> = {
    crypto: 'Crypto & Custody', macro: 'Macro & Rates',
    equity: 'Equity Markets',   tail:  'Tail Risk',
  }
  const catIcons: Record<string, string> = {
    crypto: '\u26d3', macro: '\ud83d\udcca', equity: '\ud83d\udcc8', tail: '\u26a0',
  }

  return (
    <AppLayout>
      <PageHeader
        title={portfolio?.display_name ?? 'Portfolio'}
        subtitle={`${portfolio?.portfolio_ref ?? ''} \u00b7 ${portfolio?.clients?.display_name ?? ''}`}
        action={
          <Link href={`/reports?portfolio=${id}&client=${portfolio?.client_id}`}>
            <button className="btn-primary text-xs flex items-center gap-1.5">
              <FileText className="w-3.5 h-3.5" /> Generate Report
            </button>
          </Link>
        }
      />

      <div className="p-8 space-y-6">
        {/* Risk Metrics */}
        <div>
          <div className="label mb-3">Risk Metrics</div>
          <div className="grid grid-cols-4 gap-4">
            <MetricCard label="Portfolio NAV"      value={fmtChf(portfolio?.total_nav_chf)} sub="base currency CHF" />
            <MetricCard label="VaR 95% (1-day)"   value={fmtChf(metrics?.var_95_1d)}       sub="historical simulation" accent={metrics?.var_95_1d > (portfolio?.total_nav_chf ?? 0) * 0.05} />
            <MetricCard label="Max Drawdown 30d"  value={fmtPct(metrics?.max_drawdown_30d)} sub="peak-to-trough" accent={(metrics?.max_drawdown_30d ?? 0) < -0.15} />
            <MetricCard label="Sharpe Ratio"       value={fmt(metrics?.sharpe_ratio_30d)}   sub="30d annualised" />
          </div>
          <div className="grid grid-cols-5 gap-4 mt-4">
            <MetricCard label="Volatility 30d"      value={fmtPct(metrics?.volatility_30d)}  sub="annualised" />
            <MetricCard label="Concentration (HHI)" value={fmt(metrics?.hhi, 4)}              sub="1.0 = fully concentrated" accent={(metrics?.hhi ?? 0) > 0.25} />
            <MetricCard label="Top Custodian"        value={metrics?.top_custodian_name ?? '\u2014'} sub={fmtPct(metrics?.top_custodian_pct) + ' of AuM'} accent={(metrics?.top_custodian_pct ?? 0) > 0.5} />
            <MetricCard
              label="Market Risk Score"
              value={metrics?.risk_score_composite ? `${metrics.risk_score_composite}/100` : '\u2014'}
              sub={metrics?.risk_tier ? `${metrics.risk_tier} \u00b7 VaR + volatility` : 'VaR + volatility'}
            />
            <MetricCard
              label="Counterparty Risk Score"
              value={risk?.weighted_risk_score != null ? `${risk.weighted_risk_score.toFixed(0)}/100` : '\u2014'}
              sub={
                risk?.weighted_risk_score != null
                  ? `${scoreTier(risk.weighted_risk_score)} \u00b7 exposure-weighted`
                  : 'click Recompute Risk'
              }
              accent={risk?.weighted_risk_score != null && risk.weighted_risk_score < 55}
            />
          </div>
          {!metrics && !loading && (
            <div className="mt-3 text-xs text-ink-mid bg-surface-2 rounded p-3">
              Metrics computed in background. Refresh in 30 seconds if this is a new portfolio.
            </div>
          )}
        </div>

        {/* Risk analytics: concentration, jurisdiction, FINMA, correlation */}
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
                  if (pct < 0.5) return null
                  return (
                    <div key={tier}>
                      <div className="flex justify-between text-xs mb-1">
                        <span className="text-ink-mid">{tier}</span>
                        <span className="font-mono">CHF {(val/1e6).toFixed(1)}M ({pct.toFixed(0)}%)</span>
                      </div>
                      <div className="h-1.5 bg-surface-2 rounded overflow-hidden">
                        <div className={`h-full ${colors[tier]}`} style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                  )
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
            {(risk.concentration_warnings?.length ?? 0) > 0 && (
              <div className="card p-4">
                <div className="label mb-3">Concentration Warnings</div>
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
            {(risk.limit_breaches?.length ?? 0) > 0 && (
              <div className="card p-4">
                <div className="label mb-3">Limit Breaches</div>
                <div className="space-y-2">
                  {risk.limit_breaches.map((b: any, i: number) => (
                    <div key={i} className="flex items-center justify-between p-2 bg-red/5 border border-red/20 rounded">
                      <div>
                        <div className="text-xs font-medium capitalize">{b.type} {b.key}</div>
                        <div className="text-[10px] text-ink-mid">Limit: {b.limit_pct}% &middot; Actual: {b.actual_pct}%</div>
                      </div>
                      <span className="text-[10px] font-mono text-red bg-red/10 px-1.5 py-0.5 rounded">{b.status}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* FINMA flags */}
            {(risk.finma_flags?.length ?? 0) > 0 && (
              <div className="card p-4 col-span-2">
                <div className="label mb-3 text-red">FINMA Compliance Issues</div>
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
            {(risk.correlation_groups?.length ?? 0) > 0 && (
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

        {/* Positions + Stress tests side by side */}
        <div className="grid grid-cols-2 gap-6">

          {/* LEFT: Positions */}
          <div className="card overflow-hidden">
            <div className="px-5 py-3 border-b border-border flex items-center justify-between">
              <span className="label">Positions</span>
              <span className="text-xs text-ink-mid">{positions.length} holdings</span>
            </div>
            <div className="overflow-auto" style={{ maxHeight: 520 }}>
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-surface-2">
                  <tr>
                    {['Asset', 'Class', 'Value CHF', 'Weight', 'Custodian'].map(h => (
                      <th key={h} className="label text-left px-4 py-2.5 font-normal text-[10px]">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {positions.map((p: any) => (
                    <tr key={p.position_id} className="border-t border-border hover:bg-surface-2/30 transition-colors">
                      <td className="px-4 py-2.5 font-mono text-xs font-semibold">{p.asset_symbol}</td>
                      <td className="px-4 py-2.5">
                        <span className="text-[10px] font-mono bg-surface-2 px-1.5 py-0.5 rounded text-ink-mid">{p.asset_class}</span>
                      </td>
                      <td className="px-4 py-2.5 text-xs font-mono">
                        {p.market_value_chf ? Number(p.market_value_chf).toLocaleString('de-CH', { maximumFractionDigits: 0 }) : '\u2014'}
                      </td>
                      <td className="px-4 py-2.5 text-xs text-ink-mid">
                        {p.weight_pct ? `${(p.weight_pct * 100).toFixed(1)}%` : '\u2014'}
                      </td>
                      <td className="px-4 py-2.5 text-xs text-ink-mid">{p.custodian_name ?? '\u2014'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* RIGHT: Stress tests */}
          <div className="card overflow-hidden flex flex-col">
            <div className="px-5 py-3 border-b border-border">
              <div className="flex items-center justify-between">
                <span className="label">Stress Tests</span>
                <span className="text-xs text-ink-mid">{stressResults.length} run</span>
              </div>
              <p className="text-xs text-ink-mid mt-0.5">15 scenarios across crypto, macro, equity and tail risk</p>
            </div>
            <div className="overflow-auto flex-1 p-4 space-y-4" style={{ maxHeight: 520 }}>
              {(['crypto', 'macro', 'equity', 'tail'] as const).map(cat => {
                const catScenarios = scenarios.filter((s: any) => s.category === cat)
                if (!catScenarios.length) return null
                return (
                  <div key={cat}>
                    <div className="flex items-center gap-1.5 mb-2">
                      <span className="text-[10px] font-mono text-ink-mid uppercase tracking-widest">{catLabels[cat]}</span>
                    </div>
                    <div className="space-y-1.5">
                      {catScenarios.map((s: any) => {
                        const result = stressResults.find((r: any) =>
                          r.scenario_id === s.scenario_id || r.scenario_id === s.slug
                        )
                        const pnlPct: number | null = result?.portfolio_pnl_pct ?? null
                        const pnlChf: number | null = result?.portfolio_pnl_chf ?? null
                        const sevColor = pnlPct != null
                          ? pnlPct < -0.30 ? 'text-red'
                          : pnlPct < -0.15 ? 'text-orange-500'
                          : pnlPct < -0.05 ? 'text-amber'
                          : 'text-teal'
                          : ''
                        return (
                          <div
                            key={s.scenario_id}
                            className={`rounded border p-3 ${result ? 'border-border bg-surface-2/50' : 'border-border/50 bg-white'}`}
                          >
                            <div className="flex items-start justify-between gap-2">
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 flex-wrap">
                                  <span className="text-xs font-medium text-ink">{s.display_name}</span>
                                  {result && pnlPct != null && (
                                    <span className={`text-xs font-mono font-semibold ${sevColor}`}>
                                      {(pnlPct * 100).toFixed(1)}%
                                    </span>
                                  )}
                                </div>
                                {result ? (
                                  <div className="mt-1 space-y-0.5">
                                    {pnlChf != null && (
                                      <div className={`text-xs font-mono ${sevColor}`}>
                                        {pnlChf >= 0 ? '+' : ''}CHF {Math.abs(pnlChf).toLocaleString('de-CH', { maximumFractionDigits: 0 })}
                                        {result.post_shock_nav_chf != null && (
                                          <span className="text-ink-mid font-normal ml-2">
                                            post: CHF {result.post_shock_nav_chf.toLocaleString('de-CH', { maximumFractionDigits: 0 })}
                                          </span>
                                        )}
                                      </div>
                                    )}
                                    {result.worst_positions?.length > 0 && (
                                      <div className="text-[10px] text-ink-mid">
                                        {result.worst_positions.slice(0, 3).map((p: any) =>
                                          `${p.asset_symbol} ${p.shock_pct > 0 ? '+' : ''}${p.shock_pct?.toFixed(0)}%`
                                        ).join(' \u00b7 ')}
                                      </div>
                                    )}
                                  </div>
                                ) : (
                                  <div className="text-[10px] text-ink-mid mt-0.5 line-clamp-1">{s.description}</div>
                                )}
                              </div>
                              <button
                                onClick={() => runStress(s.scenario_id, s.display_name)}
                                disabled={running === s.scenario_id}
                                className="btn-secondary text-[10px] py-1 px-2 flex items-center gap-1 flex-shrink-0 disabled:opacity-50"
                              >
                                <Zap className="w-3 h-3" />
                                {running === s.scenario_id ? '\u2026' : result ? 'Re-run' : 'Run'}
                              </button>
                            </div>
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
      </div>
    </AppLayout>
  )
}
