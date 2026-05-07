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

// AI analysis polling - defined at module level to avoid TSX parser issues
function pollForAiResult(
  portfolioId: string,
  setter: (v: any) => void,
  setRunning: (v: boolean) => void
) {
  let remaining = 12
  const pollId = setInterval(function() {
    remaining = remaining - 1
    fetch(API + '/api/v1/portfolios/' + portfolioId + '/ai-analysis', { headers: H() })
      .then(function(r: any) { return r.json() })
      .then(function(data: any) {
        if (data && data.status === 'ready' && data.analysis) {
          setter(data.analysis)
          setRunning(false)
          clearInterval(pollId)
        }
      })
      .catch(function() {})
    if (!remaining) { clearInterval(pollId); setRunning(false) }
  }, 5000)
}

function fmtChf(n: number | null | undefined): string {
  if (n == null) return '-'
  return 'CHF ' + n.toLocaleString('de-CH', { maximumFractionDigits: 0 })
}
function fmtPct(n: number | null | undefined): string {
  if (n == null) return '-'
  return (n * 100).toFixed(2) + '%'
}
function fmt(n: number | null | undefined, decimals: number = 2, prefix: string = ''): string {
  if (n == null) return '-'
  return prefix + n.toFixed(decimals)
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
  const [runningAll, setRunningAll] = useState(false)
  const [aiResult, setAiResult]       = useState<any>(null)
  const [aiRunning, setAiRunning]     = useState(false)

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
      if (mRes.ok) setMetrics(await mRes.json())
      if (posRes.ok) setPositions(await posRes.json())
      if (scRes.ok) setScenarios(await scRes.json())
      if (srRes.ok) setStressResults(await srRes.json())
      if (rRes.ok)  setRisk(await rRes.json())
      const aiResp = await fetch(API + '/api/v1/portfolios/' + id + '/ai-analysis', { headers: H() })
      if (aiResp.ok) { const d = await aiResp.json(); if (d.status === 'ready') setAiResult(d.analysis) }
    } catch {} finally { setLoading(false) }
  }

  useEffect(() => { if (id) load() }, [id])

  function startAiAnalysis() {
    setAiRunning(true)
    setAiResult(null)
    fetch(API + '/api/v1/portfolios/' + id + '/ai-analysis', { method: 'POST', headers: H() })
      .then(function() { pollForAiResult(id as string, setAiResult, setAiRunning) })
      .catch(function() { setAiRunning(false) })
  }

  const runStress = async (scenario_id: string, name: string) => {
    setRunning(scenario_id)
    try {
      const r = await fetch(API + '/api/v1/portfolios/' + id + '/stress', {
        method: 'POST',
        headers: H(),
        body: JSON.stringify({ scenario_id }),
      })
      if (r.ok) {
        const result = await r.json()
        const merged = Object.assign({}, result, {
          scenario_id: result.scenario_id || result.slug || scenario_id,
          portfolio_pnl_pct: result.pnl_pct != null ? result.pnl_pct / 100 : null,
          portfolio_pnl_chf: result.pnl_chf,
          pre_shock_nav_chf: result.pre_nav_chf,
          post_shock_nav_chf: result.post_nav_chf,
        })
        setStressResults(function(prev: any[]) {
          const filtered = prev.filter(function(x: any) {
            return x.scenario_id !== merged.scenario_id && x.scenario_id !== scenario_id
          })
          return [merged].concat(filtered)
        })
        const pct = result.pnl_pct != null ? result.pnl_pct.toFixed(1) + '%' : 'done'
        toast.success(name + ': ' + pct)
      } else {
        const err = await r.json().catch(function() { return {} })
        toast.error('Failed: ' + (err.detail || 'server error'))
      }
    } catch(e) { toast.error('Connection error') }
    finally { setRunning(null) }
  }

  const runAllStress = async () => {
    setRunningAll(true)
    try {
      await fetch(API + '/api/v1/portfolios/' + id + '/stress/run-all', {
        method: 'POST', headers: H(),
      })
      toast.success('All 15 scenarios running in background - refresh in 60s')
      setTimeout(function() { load(); setRunningAll(false) }, 65000)
    } catch(e) { toast.error('Failed'); setRunningAll(false) }
  }

  return (
    <AppLayout>
      <PageHeader
        title={portfolio?.display_name ?? 'Portfolio'}
        subtitle={`${portfolio?.portfolio_ref ?? ''} - ${portfolio?.clients?.display_name ?? ''}`}
        action={
          <div className="flex gap-2">
            <button onClick={startAiAnalysis} disabled={aiRunning}
              className="btn-secondary text-xs flex items-center gap-1.5 disabled:opacity-50">
              <Zap className={`w-3.5 h-3.5 ${aiRunning ? 'animate-pulse' : ''}`} />
              {aiRunning ? 'Analysing...' : aiResult ? 'Re-analyse' : 'AI Analysis'}
            </button>
            <Link href={`/reports?portfolio=${id}&client=${portfolio?.client_id}`}>
              <button className="btn-primary text-xs flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5" /> Generate Report
              </button>
            </Link>
          </div>
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
            <MetricCard label="Top Custodian" value={metrics?.top_custodian_name ?? '-'} sub={fmtPct(metrics?.top_custodian_pct) + ' of AuM'} accent={(metrics?.top_custodian_pct ?? 0) > 0.5} />
            <MetricCard label="Market Risk Score" value={metrics?.risk_score_composite ? metrics.risk_score_composite + '/100' : '-'} sub={(metrics?.risk_tier ?? 'MEDIUM') + ' - VaR + volatility'} />
            <MetricCard
              label="Counterparty Risk Score"
              value={risk != null && risk.weighted_risk_score != null ? risk.weighted_risk_score.toFixed(0) + '/100' : '-'}
              sub={risk != null && risk.weighted_risk_score != null ? 'exposure-weighted counterparty' : 'click Recompute Risk'}
              accent={risk != null && risk.weighted_risk_score != null && risk.weighted_risk_score < 55}
            />
          </div>
          {!metrics && !loading && (
            <div className="mt-3 text-xs text-ink-mid bg-surface-2 rounded p-3">
              Metrics are computed in the background after upload. If this is a new portfolio, refresh in 30 seconds.
            </div>
          )}
        </div>


        {(aiRunning || aiResult) && (
          <div className="border border-border rounded-lg overflow-hidden">
            <div className="px-6 py-4 bg-ink flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Zap className="w-4 h-4 text-gold" />
                <span className="text-sm font-medium text-white">AI Risk Analysis</span>
              </div>
              {aiResult && aiResult.overall_assessment && (
                <span className={`text-xs font-mono px-2.5 py-1 rounded border ${
                  aiResult.overall_assessment === 'LOW'    ? 'bg-teal/20 text-teal border-teal/30' :
                  aiResult.overall_assessment === 'MEDIUM' ? 'bg-amber/20 text-amber border-amber/30' :
                  'bg-red/20 text-red border-red/30'
                }`}>{aiResult.overall_assessment} RISK</span>
              )}
            </div>
            {aiRunning && !aiResult && (
              <div className="px-6 py-10 text-center">
                <Zap className="w-6 h-6 text-ink-mid mx-auto mb-3 animate-pulse" />
                <p className="text-sm text-ink font-medium">Analysing portfolio...</p>
                <p className="text-xs text-ink-mid mt-1">Claude is reviewing your positions, stress tests and counterparty scores. Ready in 20-30s.</p>
              </div>
            )}
            {aiResult && (
              <div className="divide-y divide-border">
                <div className="px-6 py-5">
                  <p className="text-sm text-ink leading-relaxed">{aiResult.risk_verdict}</p>
                </div>
                <div className="grid grid-cols-2 divide-x divide-border">
                  <div className="px-6 py-5">
                    <div className="text-[10px] font-mono text-ink-mid uppercase tracking-widest mb-3">Key Risk Drivers</div>
                    <div className="space-y-3">
                      {(aiResult.key_risk_drivers || []).map(function(d: any, i: number) {
                        return (
                          <div key={i} className="flex gap-3">
                            <div className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 text-[10px] font-bold mt-0.5 ${d.severity === 'HIGH' ? 'bg-red/10 text-red' : 'bg-amber/10 text-amber'}`}>{i + 1}</div>
                            <div>
                              <div className="text-xs font-medium">{d.driver}</div>
                              <div className="text-xs text-ink-mid mt-0.5">{d.description}</div>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                  <div className="px-6 py-5">
                    <div className="text-[10px] font-mono text-ink-mid uppercase tracking-widest mb-3">Action Items</div>
                    <div className="space-y-2">
                      {(aiResult.action_items || []).map(function(a: any, i: number) {
                        return (
                          <div key={i} className={`p-3 rounded border-l-2 ${a.priority === 'IMMEDIATE' ? 'border-red bg-red/5' : a.priority === 'SHORT_TERM' ? 'border-amber bg-amber/5' : 'border-border bg-surface-2/30'}`}>
                            <div className={`text-[10px] font-mono mb-0.5 ${a.priority === 'IMMEDIATE' ? 'text-red' : a.priority === 'SHORT_TERM' ? 'text-amber' : 'text-ink-mid'}`}>{a.priority} - {a.deadline}</div>
                            <div className="text-xs font-medium">{a.action}</div>
                            <div className="text-xs text-ink-mid mt-0.5">{a.rationale}</div>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                </div>
                {(aiResult.rebalancing_suggestions || []).length > 0 && (
                  <div className="px-6 py-5">
                    <div className="text-[10px] font-mono text-ink-mid uppercase tracking-widest mb-3">Rebalancing</div>
                    <div className="space-y-2">
                      {(aiResult.rebalancing_suggestions || []).map(function(r: any, i: number) {
                        return (
                          <div key={i} className="flex items-center gap-3 p-2.5 bg-surface-2/50 rounded text-xs">
                            <span className="font-medium">{r.from_counterparty}</span>
                            <ChevronRight className="w-3 h-3 text-ink-mid" />
                            <span className="font-medium text-teal">{r.to_counterparty}</span>
                            <span className="font-mono ml-1">CHF {Number(r.amount_chf).toLocaleString('de-CH', {maximumFractionDigits: 0})}</span>
                            <span className="text-ink-mid flex-1">{r.rationale}</span>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )}
                {aiResult.client_communication && (
                  <div className="px-6 py-5">
                    <div className="text-[10px] font-mono text-ink-mid uppercase tracking-widest mb-3">Client Communication Draft</div>
                    <div className="bg-surface-2/50 rounded p-4 border border-border">
                      <p className="text-xs text-ink leading-relaxed whitespace-pre-line">{aiResult.client_communication}</p>
                    </div>
                  </div>
                )}
                {aiResult.analyst_notes && (
                  <div className="px-6 py-5 bg-surface-2/20">
                    <div className="text-[10px] font-mono text-ink-mid uppercase tracking-widest mb-2">Analyst Notes</div>
                    <p className="text-xs text-ink-mid leading-relaxed">{aiResult.analyst_notes}</p>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        <div className="grid grid-cols-2 gap-6">
          {/* Positions */
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
                      <td className="px-4 py-2 text-xs">{p.market_value_chf ? Number(p.market_value_chf).toLocaleString('de-CH', {maximumFractionDigits:0}) : '-'}</td>
                      <td className="px-4 py-2 text-xs">{p.weight_pct ? `${(p.weight_pct*100).toFixed(1)}%` : '-'}</td>
                      <td className="px-4 py-2 text-xs text-ink-mid">{p.custodian_name ?? '-'}</td>
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
            </div>
            <div className="p-4 space-y-3">
              {scenarios.map((s: any) => {
                const result = stressResults.find((r: any) => r.scenario_id === s.scenario_id)
                return (
                  <div key={s.scenario_id} className="flex items-center justify-between p-3 bg-surface-2 rounded">
                    <div>
                      <div className="text-sm font-medium">{s.display_name}</div>
                      {result && (
                        <div className={`text-xs mt-0.5 font-mono ${(result.portfolio_pnl_pct ?? 0) < -0.2 ? 'text-red' : 'text-ink-mid'}`}>
                          {result.portfolio_pnl_pct != null ? `${(result.portfolio_pnl_pct*100).toFixed(1)}% - ${fmtChf(result.portfolio_pnl_chf)}` : ''}
                        </div>
                      )}
                    </div>
                    <button
                      onClick={() => runStress(s.scenario_id, s.display_name)}
                      disabled={running === s.scenario_id}
                      className="btn-secondary text-xs flex items-center gap-1 py-1 disabled:opacity-50"
                    >
                      <Zap className="w-3 h-3" />
                      {running === s.scenario_id ? 'Running...' : result ? 'Re-run' : 'Run'}
                    </button>
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
