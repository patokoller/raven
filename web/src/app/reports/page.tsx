'use client'
import { useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { Suspense } from 'react'
import AppLayout from '@/components/layout/AppLayout'
import PageHeader from '@/components/layout/PageHeader'
import Link from 'next/link'
import { FileText, Clock, CheckCircle, Send, AlertCircle } from 'lucide-react'
import toast from 'react-hot-toast'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const H = () => ({ Authorization: `Bearer ${localStorage.getItem('raven_token')}`, 'Content-Type': 'application/json' })

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: any }> = {
  DRAFT:             { label: 'Generating…',  color: 'text-ink-mid',  icon: Clock },
  IN_REVIEW:         { label: 'In Review',    color: 'text-amber',    icon: AlertCircle },
  CHANGES_REQUESTED: { label: 'Changes',      color: 'text-red',      icon: AlertCircle },
  APPROVED:          { label: 'Approved',     color: 'text-teal',     icon: CheckCircle },
  DELIVERED:         { label: 'Delivered',    color: 'text-ink-mid',  icon: Send },
}

function ReportsContent() {
  const searchParams  = useSearchParams()
  const [reports, setReports]   = useState<any[]>([])
  const [loading, setLoading]   = useState(true)
  const [generating, setGenerating] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({
    portfolio_id: searchParams.get('portfolio') ?? '',
    client_id:    searchParams.get('client') ?? '',
    report_period: `Q${Math.ceil((new Date().getMonth()+1)/3)} ${new Date().getFullYear()}`,
  })

  const load = async () => {
    setLoading(true)
    try {
      const r = await fetch(`${API}/api/v1/reports`, { headers: H() })
      if (r.ok) setReports(await r.json())
    } catch {} finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  useEffect(() => {
    if (searchParams.get('portfolio')) setShowForm(true)
  }, [searchParams])

  const generate = async () => {
    if (!form.portfolio_id || !form.client_id) return toast.error('Portfolio ID and Client ID required')
    setGenerating(true)
    try {
      const r = await fetch(`${API}/api/v1/reports/generate`, {
        method: 'POST', headers: H(),
        body: JSON.stringify(form),
      })
      const d = await r.json()
      if (!r.ok) throw new Error(d.detail)
      toast.success(`Report ${d.report_ref} generation started (~3 min)`)
      setShowForm(false)
      setTimeout(load, 5000)
      setInterval(load, 30000)
    } catch (e: any) { toast.error(e.message) }
    finally { setGenerating(false) }
  }

  return (
    <AppLayout>
      <PageHeader title="Reports" subtitle="AI-generated institutional risk reports"
        action={<button onClick={() => setShowForm(s => !s)} className="btn-primary text-xs flex items-center gap-1.5"><FileText className="w-3.5 h-3.5" /> Generate Report</button>}
      />
      <div className="p-8 space-y-6">

        {showForm && (
          <div className="card p-6 space-y-4">
            <div className="label">Generate New Report</div>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="label mb-1.5 block">Portfolio ID</label>
                <input value={form.portfolio_id} onChange={e => setForm(f => ({...f, portfolio_id: e.target.value}))}
                  placeholder="UUID from portfolios table"
                  className="w-full border border-border rounded px-3 py-2 text-sm focus:outline-none focus:border-ink" />
              </div>
              <div>
                <label className="label mb-1.5 block">Client ID</label>
                <input value={form.client_id} onChange={e => setForm(f => ({...f, client_id: e.target.value}))}
                  placeholder="UUID from clients table"
                  className="w-full border border-border rounded px-3 py-2 text-sm focus:outline-none focus:border-ink" />
              </div>
              <div>
                <label className="label mb-1.5 block">Report Period</label>
                <input value={form.report_period} onChange={e => setForm(f => ({...f, report_period: e.target.value}))}
                  placeholder="e.g. Q2 2025"
                  className="w-full border border-border rounded px-3 py-2 text-sm focus:outline-none focus:border-ink" />
              </div>
            </div>
            <div className="flex items-center gap-3">
              <button onClick={generate} disabled={generating} className="btn-primary text-sm disabled:opacity-50">
                {generating ? 'Starting generation…' : 'Generate Report (Claude claude-opus-4-5)'}
              </button>
              <span className="text-xs text-ink-mid">Takes ~3 minutes · 6 sections · FINMA-aligned</span>
            </div>
          </div>
        )}

        {loading ? (
          <div className="card p-8 text-center text-sm text-ink-mid">Loading reports…</div>
        ) : reports.length === 0 ? (
          <div className="card p-12 text-center">
            <FileText className="w-8 h-8 text-ink-mid mx-auto mb-3" />
            <div className="text-sm font-medium mb-1">No reports yet</div>
            <div className="text-xs text-ink-mid mb-4">Generate your first AI-powered risk report</div>
            <button onClick={() => setShowForm(true)} className="btn-primary text-xs">Generate First Report</button>
          </div>
        ) : (
          <div className="card overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-surface-2">
                <tr>{['Ref','Title','Period','Client','Status','Created',''].map(h => (
                  <th key={h} className="label text-left px-5 py-3 font-normal">{h}</th>
                ))}</tr>
              </thead>
              <tbody>
                {reports.map((r: any) => {
                  const cfg = STATUS_CONFIG[r.status] ?? STATUS_CONFIG.DRAFT
                  const Icon = cfg.icon
                  return (
                    <tr key={r.report_id} className="border-t border-border hover:bg-surface-2/50 transition-colors">
                      <td className="px-5 py-3 font-mono text-xs text-ink-mid">{r.report_ref}</td>
                      <td className="px-5 py-3 font-medium">{r.title}</td>
                      <td className="px-5 py-3 text-xs text-ink-mid">{r.report_period}</td>
                      <td className="px-5 py-3 text-xs">{r.clients?.display_name ?? '—'}</td>
                      <td className="px-5 py-3">
                        <span className={`flex items-center gap-1.5 text-xs ${cfg.color}`}>
                          <Icon className="w-3.5 h-3.5" /> {cfg.label}
                        </span>
                      </td>
                      <td className="px-5 py-3 text-xs text-ink-mid">{new Date(r.created_at).toLocaleDateString('en-CH')}</td>
                      <td className="px-5 py-3">
                        <Link href={`/reports/${r.report_id}`}>
                          <button className="btn-secondary text-xs py-1 px-3">
                            {r.status === 'IN_REVIEW' ? 'Review' : 'View'}
                          </button>
                        </Link>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </AppLayout>
  )
}

export default function ReportsPage() {
  return <Suspense><ReportsContent /></Suspense>
}
