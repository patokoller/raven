'use client'
import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import AppLayout from '@/components/layout/AppLayout'
import PageHeader from '@/components/layout/PageHeader'
import { CheckCircle, Clock, Edit3 } from 'lucide-react'
import toast from 'react-hot-toast'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const H = () => ({ Authorization: `Bearer ${localStorage.getItem('raven_token')}`, 'Content-Type': 'application/json' })

const SECTIONS = [
  { key: 'executive_summary',     label: 'Executive Summary' },
  { key: 'portfolio_composition', label: 'Portfolio Composition' },
  { key: 'risk_scorecard',        label: 'Risk Scorecard' },
  { key: 'counterparty_analysis', label: 'Counterparty Analysis' },
  { key: 'stress_test_results',   label: 'Stress Test Results' },
  { key: 'recommendations',       label: 'Recommendations' },
]

function SectionPanel({ sectionKey, label, data, reportStatus, onEdit }: any) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft]     = useState('')

  if (!data) return (
    <div className="card p-5">
      <div className="label mb-2">{label}</div>
      <div className="flex items-center gap-2 text-ink-mid text-sm"><Clock className="w-4 h-4 animate-spin" /> Generating…</div>
    </div>
  )

  const mainText = data.narrative || data.overall_assessment || data.var_interpretation || data.headline || JSON.stringify(data, null, 2)
  const canEdit  = ['DRAFT','IN_REVIEW'].includes(reportStatus)

  return (
    <div className="card p-5">
      <div className="flex items-center justify-between mb-3">
        <div className="label">{label}</div>
        {canEdit && !editing && (
          <button onClick={() => { setDraft(mainText); setEditing(true) }}
            className="text-xs text-ink-mid hover:text-ink flex items-center gap-1">
            <Edit3 className="w-3 h-3" /> Edit
          </button>
        )}
      </div>

      {/* Key findings / headline */}
      {data.headline && <div className="text-sm font-medium text-ink mb-3 pb-3 border-b border-border">{data.headline}</div>}
      {data.risk_indicator && (
        <span className={`inline-block text-xs font-mono px-2 py-0.5 rounded mb-3 ${
          data.risk_indicator === 'RED' ? 'bg-red/10 text-red border border-red/20' :
          data.risk_indicator === 'AMBER' ? 'bg-amber/10 text-amber border border-amber/20' :
          'bg-teal/10 text-teal border border-teal/20'
        }`}>{data.risk_indicator}</span>
      )}

      {editing ? (
        <div className="space-y-3">
          <textarea value={draft} onChange={e => setDraft(e.target.value)}
            className="w-full border border-border rounded p-3 text-sm resize-none focus:outline-none focus:border-ink"
            rows={8} />
          <div className="flex gap-2">
            <button onClick={async () => {
              await onEdit(sectionKey, { ...data, narrative: draft, overall_assessment: draft })
              setEditing(false)
              toast.success('Section saved')
            }} className="btn-primary text-xs">Save</button>
            <button onClick={() => setEditing(false)} className="btn-secondary text-xs">Cancel</button>
          </div>
        </div>
      ) : (
        <div className="prose-sm text-sm text-ink-mid leading-relaxed whitespace-pre-wrap">{mainText}</div>
      )}

      {/* Key findings list */}
      {data.key_findings && data.key_findings.length > 0 && (
        <div className="mt-4 pt-4 border-t border-border">
          <div className="label mb-2">Key Findings</div>
          <ul className="space-y-1.5">
            {data.key_findings.map((f: string, i: number) => (
              <li key={i} className="text-xs text-ink-mid flex items-start gap-2">
                <span className="text-gold mt-0.5 flex-shrink-0">›</span>{f}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Immediate actions */}
      {(data.immediate_actions || data.immediate) && (
        <div className="mt-4 pt-4 border-t border-border">
          <div className="label mb-2">Immediate Actions</div>
          {(data.immediate_actions || data.immediate || []).map((a: any, i: number) => (
            <div key={i} className="text-xs text-ink-mid mb-1.5 flex items-start gap-2">
              <span className="text-red mt-0.5 flex-shrink-0">!</span>
              {typeof a === 'string' ? a : `[${a.priority}] ${a.action} — ${a.timeline}`}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function ReportDetailPage() {
  const { id }          = useParams()
  const [report, setReport]     = useState<any>(null)
  const [loading, setLoading]   = useState(true)
  const [approving, setApproving] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const r = await fetch(`${API}/api/v1/reports/${id}`, { headers: H() })
      if (r.ok) setReport(await r.json())
    } catch {} finally { setLoading(false) }
  }

  useEffect(() => {
    if (id) {
      load()
      // Poll every 15s while DRAFT (generating)
      const interval = setInterval(() => {
        if (report?.status === 'DRAFT') load()
      }, 15000)
      return () => clearInterval(interval)
    }
  }, [id])

  const editSection = async (section: string, content: any) => {
    await fetch(`${API}/api/v1/reports/${id}/sections`, {
      method: 'PATCH', headers: H(),
      body: JSON.stringify({ section, content }),
    })
    load()
  }

  const approve = async () => {
    setApproving(true)
    try {
      const r = await fetch(`${API}/api/v1/reports/${id}/approve`, { method: 'POST', headers: H() })
      if (r.ok) { toast.success('Report approved'); load() }
      else {
        const d = await r.json()
        toast.error(d.detail || 'Approval failed')
      }
    } catch { toast.error('Approval failed') }
    finally { setApproving(false) }
  }

  if (loading) return <AppLayout><div className="p-8 text-sm text-ink-mid">Loading report…</div></AppLayout>
  if (!report) return <AppLayout><div className="p-8 text-sm text-red">Report not found</div></AppLayout>

  return (
    <AppLayout>
      <PageHeader
        title={report.title}
        subtitle={`${report.report_ref} · ${report.report_period} · Status: ${report.status}`}
        action={
          report.status === 'IN_REVIEW' ? (
            <button onClick={approve} disabled={approving}
              className="btn-primary text-xs flex items-center gap-1.5 disabled:opacity-50">
              <CheckCircle className="w-3.5 h-3.5" />
              {approving ? 'Approving…' : 'Approve Report'}
            </button>
          ) : report.status === 'DRAFT' ? (
            <div className="flex items-center gap-2 text-xs text-ink-mid">
              <Clock className="w-3.5 h-3.5 animate-spin" /> Generating… auto-refreshing
            </div>
          ) : (
            <span className="text-xs font-mono text-teal flex items-center gap-1.5">
              <CheckCircle className="w-3.5 h-3.5" /> {report.status}
            </span>
          )
        }
      />

      <div className="p-8 space-y-4">
        {report.generation_error && (
          <div className="bg-red/5 border border-red/20 rounded p-4 text-sm text-red">
            Generation error: {report.generation_error}
          </div>
        )}

        {SECTIONS.map(({ key, label }) => (
          <SectionPanel
            key={key}
            sectionKey={key}
            label={label}
            data={report[`section_${key}`]}
            reportStatus={report.status}
            onEdit={editSection}
          />
        ))}

        {report.status === 'APPROVED' && (
          <div className="card p-5">
            <div className="label mb-3">Deliver Report</div>
            <div className="flex gap-3">
              {['email','secure_link','portal'].map(ch => (
                <button key={ch} onClick={async () => {
                  await fetch(`${API}/api/v1/reports/${id}/deliver`, {
                    method: 'POST', headers: H(),
                    body: JSON.stringify({ channel: ch }),
                  })
                  toast.success(`Marked as delivered via ${ch}`)
                  load()
                }} className="btn-secondary text-xs capitalize">{ch.replace('_',' ')}</button>
              ))}
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  )
}
