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
  const [runningAll, setRunningAll] = useState(false)
  const [aiAnalysis, setAiAnalysis]   = useState<any>(null)
  const [aiLoading, setAiLoading]     = useState(false)
  const [aiPolling, setAiPolling]     = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const [pfRes, mRes, posRes, scRes, srRes, rRes, aiRes] = await Promise.all([
        fetch(`${API}/api/v1/portfolios`, { headers: H() }),
        fetch(`${API}/api/v1/portfolios/${id}/metrics`, { headers: H() }),
        fetch(`${API}/api/v1/portfolios/${id}/positions`, { headers: H() }),
        fetch(`${API}/api/v1/stress/scenarios`, { headers: H() }),
        fetch(`${API}/api/v1/stress/results/${id}`, { headers: H() }),
        fetch(`${API}/api/v1/portfolios/${id}/risk`, { headers: H() }),
        fetch(`${API}/api/v1/portfolios/${id}/ai-analysis`, { headers: H() }),
      ])
      const pfs = pfRes.ok ? await pfRes.json() : []
      setPortfolio(pfs.find((p: any) => p.portfolio_id === id) ?? null)
      if (mRes.ok) setMetrics(await mRes.json())
      if (posRes.ok) setPositions(await posRes.json())
      if (scRes.ok) setScenarios(await scRes.json())
      if (srRes.ok) setStressResults(await srRes.json())
      if (rRes.ok)  setRisk(await rRes.json())
      if (aiRes.ok) { const a = await aiRes.json(); if (a.status === 'ready') setAiAnalysis(a.analysis) }
    } catch {} finally { setLoading(false) }
  }

  useEffect(() => { if (id) load() }, [id])

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

  const fmt = (n: number | null | undefined, decimals = 2, prefix = '') =>
    n != null ? `${prefix}${n.toFixed(decimals)}` : '-'


  const runAiAnalysis = async () => {
    setAiLoading(true)
    setAiAnalysis(null)
    try {
      await fetch(API + '/api/v1/portfolios/' + id + '/ai-analysis', {
        method: 'POST', headers: H(),
      })
      // Poll for result
      setAiPolling(true)
      let attempts = 0
      const poll = setInterval(async function() {
        attempts++
        try {
          const r = await fetch(API + '/api/v1/portfolios/' + id + '/ai-analysis', { headers: H() })
          if (r.ok) {
            const data = await r.json()
            if (data.status === 'ready' && data.analysis) {
              setAiAnalysis(data.analysis)
              setAiLoading(false)
              setAiPolling(false)
              clearInterval(poll)
              toast.success('AI analysis complete')
            }
          }
        } catch(e) {}
        if (attempts > 12) { clearInterval(poll); setAiLoading(false); setAiPolling(false) }
      }, 5000)
    } catch(e) {
      toast.error('Failed to start analysis')
      setAiLoading(false)
    }
  }

  const fmtChf = (n: number | null | undefined) =>
    n != null ? `CHF ${n.toLocaleString('en-CH', { maximumFractionDigits: 0 })}` : '-'

  const fmtPct = (n: number | null | undefined) =>
    n != null ? `${(n * 100).toFixed(2)}%` : '-'

  return (
    <AppLayout>
      <PageHeader
        title={portfolio?.display_name ?? 'Portfolio'}
        subtitle={`${portfolio?.portfolio_ref ?? ''} - ${portfolio?.clients?.display_name ?? ''}`}
        action={
          <div className="flex gap-2">
            <button
              onClick={runAiAnalysis}
              disabled={aiLoading}
              className="btn-secondary text-xs flex items-center gap-1.5 disabled:opacity-60"
            >
              <Sparkles className={`w-3.5 h-3.5 ${aiLoading ? 'animate-pulse' : ''}`} />
              {aiLoading ? 'Analysing...' : aiAnalysis ? 'Re-analyse' : 'AI Analysis'}
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

        <div className="grid grid-cols-2 gap-6">
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
