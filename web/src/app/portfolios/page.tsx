'use client'
import { useEffect, useState, useCallback } from 'react'
import Link from 'next/link'
import AppLayout from '@/components/layout/AppLayout'
import PageHeader from '@/components/layout/PageHeader'
import {
  RefreshCw, Plus, Trash2, AlertTriangle,
  TrendingDown, TrendingUp, Shield, Globe,
  BarChart3, ChevronRight, FileText, Bell
} from 'lucide-react'
import toast from 'react-hot-toast'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const H = () => ({ Authorization: `Bearer ${localStorage.getItem('raven_token')}`, 'Content-Type': 'application/json' })

function TierBar({ breakdown, nav }: { breakdown: any, nav: number }) {
  if (!breakdown || !nav) return null
  const tiers = [
    { key: 'LOW',      color: 'bg-teal' },
    { key: 'MEDIUM',   color: 'bg-amber' },
    { key: 'HIGH',     color: 'bg-orange-500' },
    { key: 'CRITICAL', color: 'bg-red' },
  ]
  return (
    <div className="flex rounded overflow-hidden h-1.5 w-full gap-px">
      {tiers.map(({ key, color }) => {
        const val = breakdown[key] || 0
        const pct = (val / nav) * 100
        if (pct < 1) return null
        return <div key={key} className={`${color} transition-all`} style={{ width: `${pct}%` }} title={`${key}: ${pct.toFixed(0)}%`} />
      })}
    </div>
  )
}

function ScoreDelta({ delta }: { delta: number }) {
  if (!delta && delta !== 0) return null
  if (Math.abs(delta) < 0.1) return <span className="text-[10px] text-ink-mid font-mono">—</span>
  const up = delta > 0
  return (
    <span className={`text-[10px] font-mono flex items-center gap-0.5 ${up ? 'text-teal' : 'text-red'}`}>
      {up ? <TrendingUp className="w-2.5 h-2.5" /> : <TrendingDown className="w-2.5 h-2.5" />}
      {up ? '+' : ''}{delta.toFixed(1)}
    </span>
  )
}

function RiskScore({ score }: { score: number }) {
  const color = score >= 75 ? 'text-teal' : score >= 55 ? 'text-amber' : score >= 35 ? 'text-orange-500' : 'text-red'
  const tier  = score >= 75 ? 'LOW' : score >= 55 ? 'MEDIUM' : score >= 35 ? 'HIGH' : 'CRITICAL'
  return (
    <div className="text-right">
      <div className={`text-2xl font-light tabular-nums ${color}`}>{score.toFixed(0)}</div>
      <div className={`text-[10px] font-mono ${color}`}>{tier}</div>
    </div>
  )
}

function PortfolioCard({ pf, risk, onDelete, deleting }: any) {
  const nav    = pf.total_nav_chf || 0
  const score  = risk?.weighted_risk_score
  const alerts = risk?.open_alert_count || 0
  const warnings = risk?.concentration_warnings || []
  const finma  = risk?.finma_compliant
  const breaches = risk?.limit_breaches || []
  const corr   = risk?.correlation_groups || []

  const fmtChf = (v: number) => v >= 1e6
    ? `CHF ${(v / 1e6).toFixed(1)}M`
    : v >= 1e3 ? `CHF ${(v / 1e3).toFixed(0)}K` : `CHF ${v.toFixed(0)}`

  return (
    <div className="card p-0 overflow-hidden hover:shadow-md transition-shadow">
      <div className="px-5 pt-4 pb-3 border-b border-border">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-0.5">
              <span className="text-xs text-ink-mid font-mono">{pf.portfolio_ref}</span>
              {breaches.length > 0 && (
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-red/10 text-red border border-red/20">
                  {breaches.length} limit{breaches.length > 1 ? 's' : ''} breached
                </span>
              )}
            </div>
            <h3 className="font-medium text-sm text-ink truncate">{pf.display_name}</h3>
            <div className="text-xs text-ink-mid mt-0.5">{fmtChf(nav)}</div>
          </div>
          <div className="flex items-center gap-2">
            {score != null && (
              <div className="flex items-center gap-1.5">
                <RiskScore score={score} />
                <div className="flex flex-col gap-0.5">
                  <ScoreDelta delta={risk?.score_delta_7d} />
                  <span className="text-[10px] text-ink-mid/60">7d</span>
                </div>
              </div>
            )}
            <button
              onClick={e => {
                e.preventDefault()
                if (!confirm(`Delete "${pf.display_name}"? This cannot be undone.`)) return
                onDelete(pf.portfolio_id)
              }}
              disabled={deleting === pf.portfolio_id}
              className="p-1.5 rounded text-ink-mid hover:text-red hover:border-red/30 border border-border bg-white transition-colors disabled:opacity-50"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
        {risk?.risk_tier_breakdown && nav > 0 && (
          <div className="mt-3">
            <TierBar breakdown={risk.risk_tier_breakdown} nav={nav} />
            <div className="flex justify-between mt-1">
              {Object.entries(risk.risk_tier_breakdown).map(([tier, val]: any) =>
                val > 0 ? (
                  <div key={tier} className="text-[10px] text-ink-mid">
                    {tier}: {((val / nav) * 100).toFixed(0)}%
                  </div>
                ) : null
              )}
            </div>
          </div>
        )}
      </div>

      <div className="px-5 py-2.5 flex items-center gap-3 border-b border-border bg-surface-2/30 flex-wrap">
        <div className={`flex items-center gap-1 text-[10px] font-mono ${finma === false ? 'text-red' : finma === true ? 'text-teal' : 'text-ink-mid'}`}>
          <Shield className="w-3 h-3" />
          {finma === false ? 'FINMA non-compliant' : finma === true ? 'FINMA compliant' : 'Not assessed'}
        </div>
        {alerts > 0 && (
          <div className="flex items-center gap-1 text-[10px] font-mono text-amber">
            <Bell className="w-3 h-3" />
            {alerts} alert{alerts > 1 ? 's' : ''}
          </div>
        )}
        {corr.length > 0 && (
          <div className="flex items-center gap-1 text-[10px] font-mono text-amber">
            <BarChart3 className="w-3 h-3" />
            {corr.length} correlation group{corr.length > 1 ? 's' : ''}
          </div>
        )}
        {risk?.latest_report_status && (
          <div className="flex items-center gap-1 text-[10px] font-mono text-ink-mid ml-auto">
            <FileText className="w-3 h-3" />
            Report: {risk.latest_report_status}
          </div>
        )}
      </div>

      {warnings.length > 0 && (
        <div className="px-5 py-2.5 space-y-1 border-b border-border">
          {warnings.slice(0, 3).map((w: any) => (
            <div key={w.name} className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <AlertTriangle className={`w-3 h-3 flex-shrink-0 ${w.severity === 'CRITICAL' ? 'text-red' : 'text-amber'}`} />
                <span className="text-xs text-ink truncate max-w-[160px]">{w.name}</span>
              </div>
              <span className={`text-xs font-mono ${w.severity === 'CRITICAL' ? 'text-red' : 'text-amber'}`}>{w.pct}%</span>
            </div>
          ))}
          {warnings.length > 3 && <div className="text-[10px] text-ink-mid">+{warnings.length - 3} more</div>}
        </div>
      )}

      {risk?.jurisdiction_breakdown && Object.keys(risk.jurisdiction_breakdown).length > 0 && nav > 0 && (
        <div className="px-5 py-2.5 border-b border-border">
          <div className="flex items-center gap-1.5 mb-1.5">
            <Globe className="w-3 h-3 text-ink-mid" />
            <span className="text-[10px] font-mono text-ink-mid uppercase tracking-wide">Jurisdiction</span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(risk.jurisdiction_breakdown)
              .sort((a: any, b: any) => b[1] - a[1])
              .slice(0, 4)
              .map(([j, v]: any) => (
                <span key={j} className="text-[10px] font-mono bg-surface-2 px-1.5 py-0.5 rounded">
                  {j}: {((v / nav) * 100).toFixed(0)}%
                </span>
              ))}
          </div>
        </div>
      )}

      <Link href={`/portfolios/${pf.portfolio_id}`}>
        <div className="px-5 py-2.5 flex items-center justify-between hover:bg-surface-2/50 transition-colors cursor-pointer">
          <span className="text-xs text-ink-mid">View detail</span>
          <ChevronRight className="w-3.5 h-3.5 text-ink-mid" />
        </div>
      </Link>
    </div>
  )
}

export default function PortfoliosPage() {
  const [portfolios, setPortfolios]         = useState<any[]>([])
  const [risks, setRisks]                   = useState<Record<string, any>>({})
  const [clients, setClients]               = useState<any[]>([])
  const [loading, setLoading]               = useState(true)
  const [uploading, setUploading]           = useState(false)
  const [showUpload, setShowUpload]         = useState(false)
  const [deleting, setDeleting]             = useState<string | null>(null)
  const [refreshing, setRefreshing]         = useState(false)
  const [riskRefreshing, setRiskRefreshing] = useState(false)
  const [selectedClient, setSelectedClient] = useState<string>('all')
  const [file, setFile]                     = useState<File | null>(null)
  const [form, setForm] = useState({ display_name: '', portfolio_ref: '', base_currency: 'CHF', client_id: '' })

  const load = useCallback(async () => {
    try {
      const [pfRes, clientRes] = await Promise.all([
        fetch(`${API}/api/v1/portfolios`, { headers: H() }),
        fetch(`${API}/api/v1/portfolios/clients-list`, { headers: H() }),
      ])
      if (pfRes.ok) {
        const pfs = await pfRes.json()
        setPortfolios(pfs)
        const riskResults = await Promise.allSettled(
          pfs.map((pf: any) =>
            fetch(`${API}/api/v1/portfolios/${pf.portfolio_id}/risk`, { headers: H() })
              .then(r => r.ok ? r.json() : null)
          )
        )
        const riskMap: Record<string, any> = {}
        pfs.forEach((pf: any, i: number) => {
          const res = riskResults[i]
          if (res.status === 'fulfilled' && res.value) riskMap[pf.portfolio_id] = res.value
        })
        setRisks(riskMap)
      }
      if (clientRes.ok) setClients(await clientRes.json())
    } catch {} finally { setLoading(false) }
  }, [])

  useEffect(() => {
    load()
    const interval = setInterval(load, 60000)
    return () => clearInterval(interval)
  }, [load])

  const handleDelete = async (portfolio_id: string) => {
    setDeleting(portfolio_id)
    try {
      const r = await fetch(`${API}/api/v1/portfolios/${portfolio_id}`, { method: 'DELETE', headers: H() })
      const d = await r.json()
      if (!r.ok) throw new Error(d.detail)
      toast.success('Portfolio deleted')
      setPortfolios(prev => prev.filter(p => p.portfolio_id !== portfolio_id))
    } catch (e: any) { toast.error(e.message) }
    finally { setDeleting(null) }
  }

  const handleUpload = async () => {
    if (!file || !form.display_name || !form.portfolio_ref || !form.client_id) {
      toast.error('Please fill all fields and select a file'); return
    }
    setUploading(true)
    const fd = new FormData()
    fd.append('file', file)
    fd.append('display_name', form.display_name)
    fd.append('portfolio_ref', form.portfolio_ref)
    fd.append('base_currency', form.base_currency)
    fd.append('client_id', form.client_id)
    try {
      const r = await fetch(`${API}/api/v1/portfolios/upload`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${localStorage.getItem('raven_token')}` },
        body: fd,
      })
      const d = await r.json()
      if (!r.ok) throw new Error(d.detail)
      toast.success('Portfolio uploaded')
      setShowUpload(false); setFile(null)
      setForm({ display_name: '', portfolio_ref: '', base_currency: 'CHF', client_id: '' })
      await load()
    } catch (e: any) { toast.error(e.message) }
    finally { setUploading(false) }
  }

  const handleRefreshRisk = async () => {
    setRiskRefreshing(true)
    await Promise.allSettled(
      portfolios.map(pf =>
        fetch(`${API}/api/v1/portfolios/${pf.portfolio_id}/risk/refresh`, { method: 'POST', headers: H() })
      )
    )
    toast.success('Risk analytics refreshing — updates in ~30s')
    setTimeout(async () => { await load(); setRiskRefreshing(false) }, 35000)
  }

  const filtered = selectedClient === 'all' ? portfolios : portfolios.filter(p => p.client_id === selectedClient)
  const totalNav     = filtered.reduce((s, p) => s + (p.total_nav_chf || 0), 0)
  const avgScore     = filtered.length > 0 ? filtered.reduce((s, p) => s + (risks[p.portfolio_id]?.weighted_risk_score || 50), 0) / filtered.length : 0
  const totalAlerts  = filtered.reduce((s, p) => s + (risks[p.portfolio_id]?.open_alert_count || 0), 0)
  const nonCompliant = filtered.filter(p => risks[p.portfolio_id]?.finma_compliant === false).length
  const limitBreaches = filtered.reduce((s, p) => s + (risks[p.portfolio_id]?.limit_breaches?.length || 0), 0)
  const fmtChf = (v: number) => v >= 1e9 ? `CHF ${(v/1e9).toFixed(2)}B` : v >= 1e6 ? `CHF ${(v/1e6).toFixed(1)}M` : `CHF ${(v/1e3).toFixed(0)}K`

  return (
    <AppLayout>
      <PageHeader
        title="Portfolios"
        subtitle="Risk management across all client mandates"
        action={
          <div className="flex gap-2">
            <button onClick={async () => { setRefreshing(true); await load(); setRefreshing(false) }}
              disabled={refreshing} className="btn-secondary text-xs flex items-center gap-1.5 disabled:opacity-50">
              <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
              {refreshing ? 'Refreshing…' : 'Refresh'}
            </button>
            <button onClick={handleRefreshRisk} disabled={riskRefreshing}
              className="btn-secondary text-xs flex items-center gap-1.5 disabled:opacity-50">
              <BarChart3 className="w-3.5 h-3.5" /> {riskRefreshing ? 'Computing…' : 'Recompute Risk'}
            </button>
            <button onClick={() => setShowUpload(!showUpload)} className="btn-primary text-xs flex items-center gap-1.5">
              <Plus className="w-3.5 h-3.5" /> Upload Portfolio
            </button>
          </div>
        }
      />

      <div className="p-8 space-y-6">
        <div className="grid grid-cols-5 gap-3">
          {[
            { label: 'Total AUM', value: fmtChf(totalNav), color: 'text-ink' },
            { label: 'Avg Risk Score', value: avgScore.toFixed(0), color: avgScore >= 75 ? 'text-teal' : avgScore >= 55 ? 'text-amber' : 'text-red' },
            { label: 'Open Alerts', value: totalAlerts, color: totalAlerts > 0 ? 'text-amber' : 'text-ink-mid' },
            { label: 'Limit Breaches', value: limitBreaches, color: limitBreaches > 0 ? 'text-red' : 'text-ink-mid' },
            { label: 'FINMA Issues', value: nonCompliant, color: nonCompliant > 0 ? 'text-red' : 'text-teal' },
          ].map(({ label, value, color }) => (
            <div key={label} className="card p-4 text-center">
              <div className={`text-2xl font-light ${color}`}>{value}</div>
              <div className="text-xs text-ink-mid mt-0.5">{label}</div>
            </div>
          ))}
        </div>

        {clients.length > 1 && (
          <div className="flex gap-2 border-b border-border pb-4 flex-wrap">
            <button onClick={() => setSelectedClient('all')}
              className={`text-xs px-3 py-1.5 rounded border transition-colors ${selectedClient === 'all' ? 'bg-ink text-white border-ink' : 'border-border text-ink-mid hover:text-ink'}`}>
              All clients ({portfolios.length})
            </button>
            {clients.map((c: any) => (
              <button key={c.client_id} onClick={() => setSelectedClient(c.client_id)}
                className={`text-xs px-3 py-1.5 rounded border transition-colors ${selectedClient === c.client_id ? 'bg-ink text-white border-ink' : 'border-border text-ink-mid hover:text-ink'}`}>
                {c.display_name}
              </button>
            ))}
          </div>
        )}

        {showUpload && (
          <div className="card p-5 border-gold/30 border-2">
            <div className="label mb-3">Upload Portfolio</div>
            <div className="grid grid-cols-2 gap-3 mb-3">
              <div>
                <label className="text-xs text-ink-mid mb-1 block">Client</label>
                <select value={form.client_id} onChange={e => setForm(f => ({ ...f, client_id: e.target.value }))}
                  className="w-full border border-border rounded px-2.5 py-1.5 text-sm focus:outline-none focus:border-ink">
                  <option value="">Select client…</option>
                  {clients.map((c: any) => <option key={c.client_id} value={c.client_id}>{c.display_name}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-ink-mid mb-1 block">Portfolio Name</label>
                <input value={form.display_name} onChange={e => setForm(f => ({ ...f, display_name: e.target.value }))}
                  placeholder="e.g. Digital Asset Portfolio A"
                  className="w-full border border-border rounded px-2.5 py-1.5 text-sm focus:outline-none focus:border-ink" />
              </div>
              <div>
                <label className="text-xs text-ink-mid mb-1 block">Reference</label>
                <input value={form.portfolio_ref} onChange={e => setForm(f => ({ ...f, portfolio_ref: e.target.value }))}
                  placeholder="e.g. HC-001"
                  className="w-full border border-border rounded px-2.5 py-1.5 text-sm focus:outline-none focus:border-ink" />
              </div>
              <div>
                <label className="text-xs text-ink-mid mb-1 block">Base Currency</label>
                <select value={form.base_currency} onChange={e => setForm(f => ({ ...f, base_currency: e.target.value }))}
                  className="w-full border border-border rounded px-2.5 py-1.5 text-sm focus:outline-none focus:border-ink">
                  {['CHF','USD','EUR','GBP'].map(c => <option key={c}>{c}</option>)}
                </select>
              </div>
            </div>
            <div className="mb-3">
              <label className="text-xs text-ink-mid mb-1 block">CSV / Excel file</label>
              <input type="file" accept=".csv,.xlsx,.xls" onChange={e => setFile(e.target.files?.[0] || null)} className="text-sm" />
            </div>
            <div className="flex gap-2">
              <button onClick={handleUpload} disabled={uploading} className="btn-primary text-xs disabled:opacity-50">
                {uploading ? 'Uploading…' : 'Upload & Analyse'}
              </button>
              <button onClick={() => setShowUpload(false)} className="btn-secondary text-xs">Cancel</button>
            </div>
          </div>
        )}

        {loading ? (
          <div className="text-sm text-ink-mid">Loading…</div>
        ) : filtered.length === 0 ? (
          <div className="card p-8 text-center">
            <BarChart3 className="w-8 h-8 text-ink-mid mx-auto mb-3" />
            <div className="text-sm font-medium mb-1">No portfolios yet</div>
            <p className="text-xs text-ink-mid">Upload a portfolio CSV to start analysing counterparty risk.</p>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-4">
            {filtered.map(pf => (
              <PortfolioCard key={pf.portfolio_id} pf={pf} risk={risks[pf.portfolio_id]} onDelete={handleDelete} deleting={deleting} />
            ))}
          </div>
        )}
      </div>
    </AppLayout>
  )
}
