'use client'
import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import AppLayout from '@/components/layout/AppLayout'
import PageHeader from '@/components/layout/PageHeader'
import { Zap, FileText, Shield, AlertTriangle, ChevronDown, ChevronUp } from 'lucide-react'
import Link from 'next/link'
import toast from 'react-hot-toast'
import AiAnalysisPanel, { pollForAiResult } from './AiAnalysisPanel'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const H = () => ({ Authorization: 'Bearer ' + localStorage.getItem('raven_token'), 'Content-Type': 'application/json' })

function MetricCard({ label, value, sub, accent }: { label: string, value: any, sub?: string, accent?: boolean }) {
  return (
    <div className="card p-4">
      <div className="label mb-2">{label}</div>
      <div className={`text-2xl font-light ${accent ? 'text-red' : 'text-ink'}`}>{value ?? '-'}</div>
      {sub && <div className="text-xs text-ink-mid mt-1">{sub}</div>}
    </div>
  )
}

function TierBadge({ tier }: { tier: string }) {
  const cls = tier === 'LOW' ? 'bg-teal/10 text-teal'
    : tier === 'MEDIUM' ? 'bg-amber/10 text-amber'
    : tier === 'HIGH' ? 'bg-orange-500/10 text-orange-500'
    : 'bg-red/10 text-red'
  return <span className={'text-[10px] font-mono px-1.5 py-0.5 rounded ' + cls}>{tier}</span>
}

function ScoreBar({ score }: { score: number }) {
  const color = score >= 75 ? 'bg-teal' : score >= 55 ? 'bg-amber' : score >= 35 ? 'bg-orange-500' : 'bg-red'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1 bg-surface-2 rounded overflow-hidden">
        <div className={color + ' h-full rounded'} style={{ width: score + '%' }} />
      </div>
      <span className="text-xs font-mono w-6 text-right">{score}</span>
    </div>
  )
}

function fmtChf(n: number | null | undefined): string {
  if (n == null) return '-'
  return 'CHF ' + n.toLocaleString('de-CH', { maximumFractionDigits: 0 })
}

export default function PortfolioDetailPage() {
  const { id }                            = useParams()
  const [portfolio, setPortfolio]         = useState<any>(null)
  const [risk, setRisk]                   = useState<any>(null)
  const [scenarios, setScenarios]         = useState<any[]>([])
  const [stressResults, setStressResults] = useState<any[]>([])
  const [loading, setLoading]             = useState(true)
  const [running, setRunning]             = useState<string | null>(null)
  const [runningAll, setRunningAll]       = useState(false)
  const [aiResult, setAiResult]           = useState<any>(null)
  const [aiRunning, setAiRunning]         = useState(false)
  const [detailOpen, setDetailOpen]       = useState(false)

  async function load() {
    setLoading(true)
    try {
      const [pfRes, scRes, srRes, rRes] = await Promise.all([
        fetch(API + '/api/v1/portfolios', { headers: H() }),
        fetch(API + '/api/v1/stress/scenarios', { headers: H() }),
        fetch(API + '/api/v1/stress/results/' + id, { headers: H() }),
        fetch(API + '/api/v1/portfolios/' + id + '/risk', { headers: H() }),
      ])
      const pfs = pfRes.ok ? await pfRes.json() : []
      setPortfolio(pfs.find((p: any) => p.portfolio_id === id) ?? null)
      if (scRes.ok) setScenarios(await scRes.json())
      if (srRes.ok) setStressResults(await srRes.json())
      if (rRes.ok) setRisk(await rRes.json())
      const aiResp = await fetch(API + '/api/v1/portfolios/' + id + '/ai-analysis', { headers: H() })
      if (aiResp.ok) {
        const d = await aiResp.json()
        if (d.status === 'ready') setAiResult(d.analysis)
      }
    } catch(e) {} finally { setLoading(false) }
  }

  useEffect(function() { if (id) load() }, [id])

  function runAiAnalysis() {
    setAiRunning(true)
    setAiResult(null)
    const pid = id as string
    fetch(API + '/api/v1/portfolios/' + pid + '/ai-analysis', { method: 'POST', headers: H() })
      .then(function() { pollForAiResult(pid, setAiResult, setAiRunning) })
      .catch(function() { setAiRunning(false) })
  }

  async function runStress(scenario_id: string, name: string) {
    setRunning(scenario_id)
    try {
      const r = await fetch(API + '/api/v1/portfolios/' + id + '/stress', {
        method: 'POST', headers: H(), body: JSON.stringify({ scenario_id }),
      })
      if (r.ok) {
        const result = await r.json()
        const merged = Object.assign({}, result, {
          scenario_id: result.scenario_id || result.slug || scenario_id,
          portfolio_pnl_pct: result.pnl_pct != null ? result.pnl_pct / 100 : null,
          portfolio_pnl_chf: result.pnl_chf,
        })
        setStressResults(function(prev: any[]) {
          return [merged].concat(prev.filter(function(x: any) {
            return x.scenario_id !== merged.scenario_id && x.scenario_id !== scenario_id
          }))
        })
        toast.success(name + ': ' + (result.pnl_pct != null ? result.pnl_pct.toFixed(1) + '%' : 'done'))
      } else { toast.error('Stress test failed') }
    } catch(e) { toast.error('Connection error') }
    finally { setRunning(null) }
  }

  async function runAllStress() {
    setRunningAll(true)
    try {
      await fetch(API + '/api/v1/portfolios/' + id + '/stress/run-all', { method: 'POST', headers: H() })
      toast.success('All scenarios running - refresh in 60s')
      setTimeout(function() { load(); setRunningAll(false) }, 65000)
    } catch(e) { toast.error('Failed'); setRunningAll(false) }
  }

  const nav       = portfolio?.total_nav_chf || 0
  const cpScore   = risk?.weighted_risk_score
  const cpTier    = cpScore == null ? '-' : cpScore >= 75 ? 'LOW' : cpScore >= 55 ? 'MEDIUM' : cpScore >= 35 ? 'HIGH' : 'CRITICAL'
  const exposures = (risk?.counterparty_exposures || []) as any[]
  const finmaOk   = risk?.finma_compliant
  const alerts    = risk?.open_alert_count || 0
  const warnings  = risk?.concentration_warnings || []
  const breaches  = risk?.limit_breaches || []
  const corrGroups = risk?.correlation_groups || []
  const catLabels: any = { crypto: 'Crypto & Custody', macro: 'Macro & Rates', equity: 'Equity Markets', tail: 'Tail Risk' }

  return (
    <AppLayout>
      <PageHeader
        title={portfolio?.display_name ?? 'Portfolio'}
        subtitle={(portfolio?.portfolio_ref ?? '') + ' - ' + ((portfolio?.clients as any)?.display_name ?? '')}
        action={
          <div className="flex gap-2">
            <button onClick={runAiAnalysis} disabled={aiRunning}
              className="btn-secondary text-xs flex items-center gap-1.5 disabled:opacity-50">
              <Zap className={'w-3.5 h-3.5' + (aiRunning ? ' animate-pulse' : '')} />
              {aiRunning ? 'Analysing...' : aiResult ? 'Re-analyse' : 'AI Analysis'}
            </button>
            <Link href={'/reports?portfolio=' + id + '&client=' + portfolio?.client_id}>
              <button className="btn-primary text-xs flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5" /> Generate Report
              </button>
            </Link>
          </div>
        }
      />

      <div className="p-8 space-y-6">

        {/* Status bar */}
        <div className="flex items-center gap-4 py-3 px-5 bg-surface-2/50 rounded-lg border border-border text-xs">
          <div className={'flex items-center gap-1.5 ' + (finmaOk === false ? 'text-red' : 'text-teal')}>
            <Shield className="w-3.5 h-3.5" />
            <span className={finmaOk === false ? 'font-medium' : ''}>
              {finmaOk === false ? 'FINMA non-compliant' : 'FINMA compliant'}
            </span>
          </div>
          {alerts > 0 && (
            <div className="flex items-center gap-1.5 text-amber">
              <AlertTriangle className="w-3.5 h-3.5" />
              <span>{alerts} open alert{alerts !== 1 ? 's' : ''}</span>
            </div>
          )}
          {warnings.length > 0 && (
            <div className="flex items-center gap-1.5 text-amber">
              <AlertTriangle className="w-3.5 h-3.5" />
              <span>{warnings.length} concentration warning{warnings.length !== 1 ? 's' : ''}</span>
            </div>
          )}
          {breaches.length > 0 && (
            <div className="flex items-center gap-1.5 text-red font-medium">
              <AlertTriangle className="w-3.5 h-3.5" />
              <span>{breaches.length} limit breach{breaches.length !== 1 ? 'es' : ''}</span>
            </div>
          )}
          <div className="ml-auto text-ink-mid font-mono">{fmtChf(nav)} AUM</div>
        </div>

        {/* 5 counterparty-focused metrics */}
        <div className="grid grid-cols-5 gap-4">
          <MetricCard
            label="Counterparty Risk Score"
            value={cpScore != null ? cpScore.toFixed(0) + '/100' : '-'}
            sub={cpTier + (risk?.score_delta_7d ? ' - ' + (risk.score_delta_7d > 0 ? '+' : '') + risk.score_delta_7d.toFixed(1) + ' (7d)' : '')}
            accent={cpScore != null && cpScore < 55}
          />
          <MetricCard label="Counterparties" value={exposures.length || '-'} sub="custodians & protocols" />
          <MetricCard
            label="Largest Exposure"
            value={exposures[0] ? exposures[0].pct + '%' : '-'}
            sub={exposures[0] ? exposures[0].name : 'none'}
            accent={exposures[0] ? exposures[0].pct >= 25 : false}
          />
          <MetricCard
            label="Open Alerts"
            value={String(alerts)}
            sub={alerts > 0 ? 'requires attention' : 'all clear'}
            accent={alerts > 0}
          />
          <MetricCard
            label="Limit Breaches"
            value={String(breaches.length)}
            sub={breaches.length > 0 ? breaches[0].type + ' ' + breaches[0].key : 'within mandate'}
            accent={breaches.length > 0}
          />
        </div>

        {/* AI Analysis */}
        <AiAnalysisPanel aiResult={aiResult} aiRunning={aiRunning} />

        {/* Counterparty table + Stress tests */}
        <div className="grid grid-cols-2 gap-6">

          {/* Counterparty Exposure Table */}
          <div className="card overflow-hidden">
            <div className="px-5 py-3 border-b border-border flex items-center justify-between">
              <span className="label">Counterparty Exposures</span>
              {risk?.computed_at && (
                <span className="text-[10px] text-ink-mid font-mono">
                  updated {new Date(risk.computed_at).toLocaleTimeString()}
                </span>
              )}
            </div>
            {exposures.length === 0 ? (
              <div className="px-5 py-10 text-center">
                <p className="text-xs text-ink-mid">No counterparty data yet.</p>
                <p className="text-xs text-ink-mid mt-1">Go to Portfolios and click Recompute Risk.</p>
              </div>
            ) : (
              <div className="overflow-auto" style={{ maxHeight: 480 }}>
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-surface-2">
                    <tr>
                      {['Counterparty', 'Score', 'Tier', 'AUM', 'Weight'].map(function(h) {
                        return <th key={h} className="label text-left px-4 py-2.5 font-normal text-[10px]">{h}</th>
                      })}
                    </tr>
                  </thead>
                  <tbody>
                    {exposures.map(function(cp: any) {
                      const pctNum = parseFloat(cp.pct) || 0
                      const barColor = pctNum >= 40 ? 'bg-red' : pctNum >= 20 ? 'bg-amber' : 'bg-teal'
                      return (
                        <tr key={cp.counterparty_id} className="border-t border-border hover:bg-surface-2/30 transition-colors">
                          <td className="px-4 py-3">
                            <div className="text-xs font-medium text-ink">{cp.name}</div>
                            <div className="text-[10px] text-ink-mid mt-0.5">{cp.entity_type} - {cp.jurisdiction}</div>
                          </td>
                          <td className="px-4 py-3 w-24">
                            <ScoreBar score={cp.score || 50} />
                          </td>
                          <td className="px-4 py-3">
                            <TierBadge tier={cp.tier || 'MEDIUM'} />
                          </td>
                          <td className="px-4 py-3 text-xs font-mono whitespace-nowrap">{fmtChf(cp.value_chf)}</td>
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-1.5">
                              <div className="w-12 h-1 bg-surface-2 rounded overflow-hidden">
                                <div className={'h-full rounded ' + barColor} style={{ width: Math.min(pctNum, 100) + '%' }} />
                              </div>
                              <span className={'text-xs font-mono ' + (pctNum >= 25 ? 'text-red font-semibold' : 'text-ink')}>{cp.pct}%</span>
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

          {/* Stress Tests */}
          <div className="card overflow-hidden flex flex-col">
            <div className="px-5 py-3 border-b border-border flex items-center justify-between">
              <span className="label">Stress Tests</span>
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-ink-mid">{stressResults.length} run</span>
                <button onClick={runAllStress} disabled={runningAll}
                  className="btn-secondary text-[10px] py-1 px-2 disabled:opacity-50">
                  {runningAll ? 'Running...' : 'Run All'}
                </button>
              </div>
            </div>
            <div className="overflow-auto flex-1 p-4 space-y-4" style={{ maxHeight: 480 }}>
              {(['crypto', 'macro', 'equity', 'tail'] as const).map(function(cat) {
                const catScenarios = scenarios.filter(function(s: any) { return s.category === cat })
                if (!catScenarios.length) return null
                return (
                  <div key={cat}>
                    <div className="text-[10px] font-mono text-ink-mid uppercase tracking-widest mb-2">{catLabels[cat]}</div>
                    <div className="space-y-1.5">
                      {catScenarios.map(function(s: any) {
                        const result = stressResults.find(function(r: any) {
                          return r.scenario_id === s.scenario_id || r.scenario_id === s.slug
                        })
                        const pnlPct: number | null = result ? (result.portfolio_pnl_pct ?? null) : null
                        const pnlChf: number | null = result ? (result.portfolio_pnl_chf ?? null) : null
                        const sevColor = pnlPct == null ? '' : pnlPct < -0.30 ? 'text-red' : pnlPct < -0.15 ? 'text-orange-500' : pnlPct < -0.05 ? 'text-amber' : 'text-teal'
                        return (
                          <div key={s.scenario_id} className={'rounded border p-3 ' + (result ? 'border-border bg-surface-2/50' : 'border-border/50 bg-white')}>
                            <div className="flex items-start justify-between gap-2">
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 flex-wrap">
                                  <span className="text-xs font-medium text-ink">{s.display_name}</span>
                                  {result && pnlPct != null && (
                                    <span className={'text-xs font-mono font-semibold ' + sevColor}>
                                      {(pnlPct * 100).toFixed(1)}%
                                    </span>
                                  )}
                                </div>
                                {result && pnlChf != null && (
                                  <div className={'text-xs font-mono mt-0.5 ' + sevColor}>
                                    {pnlChf >= 0 ? '+' : ''}CHF {Math.abs(pnlChf).toLocaleString('de-CH', { maximumFractionDigits: 0 })}
                                  </div>
                                )}
                                {!result && <div className="text-[10px] text-ink-mid mt-0.5 line-clamp-1">{s.description}</div>}
                              </div>
                              <button onClick={function() { runStress(s.scenario_id, s.display_name) }}
                                disabled={running === s.scenario_id}
                                className="btn-secondary text-[10px] py-1 px-2 flex items-center gap-1 flex-shrink-0 disabled:opacity-50">
                                <Zap className="w-3 h-3" />
                                {running === s.scenario_id ? '...' : result ? 'Re-run' : 'Run'}
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

        {/* Risk Detail - collapsible */}
        {(warnings.length > 0 || breaches.length > 0 || corrGroups.length > 0) && (
          <div className="card overflow-hidden">
            <button onClick={function() { setDetailOpen(function(v) { return !v }) }}
              className="w-full px-5 py-3 flex items-center justify-between hover:bg-surface-2/30 transition-colors">
              <span className="label">Risk Detail</span>
              {detailOpen ? <ChevronUp className="w-4 h-4 text-ink-mid" /> : <ChevronDown className="w-4 h-4 text-ink-mid" />}
            </button>
            {detailOpen && (
              <div className="border-t border-border grid grid-cols-3 divide-x divide-border">
                <div className="p-4">
                  <div className="text-[10px] font-mono text-ink-mid uppercase tracking-widest mb-3">Concentration</div>
                  {warnings.length === 0 ? <p className="text-xs text-ink-mid">None</p>
                    : warnings.map(function(w: any) {
                      return (
                        <div key={w.name} className="flex justify-between text-xs py-0.5">
                          <span>{w.name}</span>
                          <span className={'font-mono ' + (w.severity === 'CRITICAL' ? 'text-red' : 'text-amber')}>{w.pct}%</span>
                        </div>
                      )
                    })}
                </div>
                <div className="p-4">
                  <div className="text-[10px] font-mono text-ink-mid uppercase tracking-widest mb-3">Limit Breaches</div>
                  {breaches.length === 0 ? <p className="text-xs text-ink-mid">None</p>
                    : breaches.map(function(b: any, i: number) {
                      return (
                        <div key={i} className="py-0.5">
                          <div className="text-xs font-medium text-red">{b.type} {b.key}</div>
                          <div className="text-[10px] text-ink-mid">limit {b.limit_pct}% - actual {b.actual_pct}%</div>
                        </div>
                      )
                    })}
                </div>
                <div className="p-4">
                  <div className="text-[10px] font-mono text-ink-mid uppercase tracking-widest mb-3">Correlation Groups</div>
                  {corrGroups.length === 0 ? <p className="text-xs text-ink-mid">None</p>
                    : corrGroups.map(function(g: any) {
                      return (
                        <div key={g.group} className="py-0.5">
                          <div className="text-xs font-medium">{g.group}</div>
                          <div className="text-[10px] text-amber font-mono">{g.combined_pct}% combined</div>
                        </div>
                      )
                    })}
                </div>
              </div>
            )}
          </div>
        )}

      </div>
    </AppLayout>
  )
}
