'use client'
import { useEffect, useState, useRef } from 'react'
import { useParams } from 'next/navigation'
import AppLayout from '@/components/layout/AppLayout'
import PageHeader from '@/components/layout/PageHeader'
import dynamic from 'next/dynamic'

const DownloadButton = dynamic(() => import('@/components/pdf/DownloadButton'), { ssr: false })
import { CheckCircle, Clock, Edit3, AlertTriangle, TrendingDown } from 'lucide-react'
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

// ── Prose renderer — turns any section JSON into readable content ─────────────

function Prose({ text }: { text: string }) {
  if (!text) return null
  return <p className="text-sm text-ink-mid leading-relaxed mb-3 last:mb-0">{text}</p>
}

function FindingsList({ items, color = 'text-gold' }: { items: string[]; color?: string }) {
  if (!items?.length) return null
  return (
    <ul className="space-y-1.5 mt-3">
      {items.map((f, i) => (
        <li key={i} className="text-xs text-ink-mid flex items-start gap-2">
          <span className={`${color} mt-0.5 flex-shrink-0`}>›</span>{f}
        </li>
      ))}
    </ul>
  )
}

function ActionsList({ items }: { items: any[] }) {
  if (!items?.length) return null
  return (
    <div className="space-y-2 mt-3">
      {items.map((a, i) => {
        const text = typeof a === 'string' ? a : null
        const structured = typeof a === 'object' ? a : null
        return (
          <div key={i} className="flex items-start gap-2 text-xs">
            <span className={`flex-shrink-0 mt-0.5 font-mono text-[10px] px-1.5 py-0.5 rounded ${
              (structured?.priority || '') === 'HIGH' ? 'bg-red/10 text-red' :
              (structured?.priority || '') === 'MEDIUM' ? 'bg-amber/10 text-amber' :
              'bg-surface-2 text-ink-mid'
            }`}>
              {structured?.priority || '!'}
            </span>
            <div>
              <span className="text-ink font-medium">{structured?.action || text}</span>
              {structured?.timeline && <span className="text-ink-mid ml-1">— {structured.timeline}</span>}
              {structured?.rationale && <p className="text-ink-mid mt-0.5">{structured.rationale}</p>}
            </div>
          </div>
        )
      })}
    </div>
  )
}

function MonitoringList({ items }: { items: any[] }) {
  if (!items?.length) return null
  return (
    <div className="space-y-2 mt-3">
      {items.map((m, i) => (
        <div key={i} className="flex items-start gap-2 text-xs">
          <span className="text-ink-mid flex-shrink-0 mt-0.5">·</span>
          <div>
            <span className="text-ink font-medium">{m.item}</span>
            {m.threshold && <span className="text-ink-mid"> — Alert if: {m.threshold}</span>}
          </div>
        </div>
      ))}
    </div>
  )
}

function SectionContent({ sectionKey, data }: { sectionKey: string; data: any }) {
  if (!data) return null

  // Executive Summary
  if (sectionKey === 'executive_summary') return (
    <>
      {data.headline && <h3 className="text-sm font-semibold text-ink mb-3 pb-3 border-b border-border">{data.headline}</h3>}
      {data.risk_indicator && (
        <span className={`inline-block text-xs font-mono px-2 py-0.5 rounded mb-4 ${
          data.risk_indicator === 'RED' ? 'bg-red/10 text-red border border-red/20' :
          data.risk_indicator === 'AMBER' ? 'bg-amber/10 text-amber border border-amber/20' :
          'bg-teal/10 text-teal border border-teal/20'
        }`}>{data.risk_indicator}</span>
      )}
      {data.overall_assessment && <Prose text={data.overall_assessment} />}
      {data.key_findings?.length > 0 && (
        <div className="mt-4 pt-4 border-t border-border">
          <div className="label mb-2">Key Findings</div>
          <FindingsList items={data.key_findings} />
        </div>
      )}
      {data.immediate_actions?.length > 0 && (
        <div className="mt-4 pt-4 border-t border-border">
          <div className="label mb-2">Immediate Actions</div>
          {data.immediate_actions.map((a: string, i: number) => (
            <div key={i} className="text-xs text-ink-mid flex items-start gap-2 mb-1.5">
              <AlertTriangle className="w-3 h-3 text-red mt-0.5 flex-shrink-0" />{a}
            </div>
          ))}
        </div>
      )}
    </>
  )

  // Portfolio Composition
  if (sectionKey === 'portfolio_composition') return (
    <>
      {data.narrative && <Prose text={data.narrative} />}
      {data.concentration_assessment && (
        <div className="mt-4 pt-4 border-t border-border">
          <div className="label mb-2">Concentration Assessment</div>
          <Prose text={data.concentration_assessment} />
        </div>
      )}
      {data.key_exposures?.length > 0 && (
        <div className="mt-4 pt-4 border-t border-border">
          <div className="label mb-2">Key Exposures</div>
          <FindingsList items={data.key_exposures} />
        </div>
      )}
      {data.diversification_score && (
        <div className="mt-3">
          <span className="label">Diversification: </span>
          <span className={`text-xs font-mono ${data.diversification_score === 'LOW' ? 'text-red' : data.diversification_score === 'HIGH' ? 'text-teal' : 'text-amber'}`}>
            {data.diversification_score}
          </span>
        </div>
      )}
    </>
  )

  // Risk Scorecard
  if (sectionKey === 'risk_scorecard') return (
    <>
      {data.narrative && <Prose text={data.narrative} />}
      <div className="grid grid-cols-2 gap-4 mt-4">
        {data.var_interpretation && (
          <div className="bg-surface-2 rounded p-3">
            <div className="label mb-1">VaR Interpretation</div>
            <p className="text-xs text-ink-mid">{data.var_interpretation}</p>
          </div>
        )}
        {data.volatility_assessment && (
          <div className="bg-surface-2 rounded p-3">
            <div className="label mb-1">Volatility</div>
            <p className="text-xs text-ink-mid">{data.volatility_assessment}</p>
          </div>
        )}
        {data.sharpe_assessment && (
          <div className="bg-surface-2 rounded p-3">
            <div className="label mb-1">Risk-Adjusted Returns</div>
            <p className="text-xs text-ink-mid">{data.sharpe_assessment}</p>
          </div>
        )}
        {data.trend_assessment && (
          <div className="bg-surface-2 rounded p-3">
            <div className="label mb-1">Trend</div>
            <p className="text-xs text-ink-mid">{data.trend_assessment}</p>
          </div>
        )}
      </div>
    </>
  )

  // Counterparty Analysis
  if (sectionKey === 'counterparty_analysis') return (
    <>
      {data.narrative && <Prose text={data.narrative} />}
      {data.custodian_concentration_risk && (
        <div className="mt-4 pt-4 border-t border-border">
          <div className="label mb-2">Custodian Concentration</div>
          <Prose text={data.custodian_concentration_risk} />
        </div>
      )}
      {data.highlighted_concerns?.length > 0 && (
        <div className="mt-4 pt-4 border-t border-border">
          <div className="label mb-2">Highlighted Concerns</div>
          <FindingsList items={data.highlighted_concerns} color="text-red" />
        </div>
      )}
      {data.watchlist?.length > 0 && (
        <div className="mt-4 pt-4 border-t border-border">
          <div className="label mb-2">Watchlist</div>
          <div className="flex flex-wrap gap-2">
            {data.watchlist.map((w: string, i: number) => (
              <span key={i} className="text-xs font-mono bg-amber/10 text-amber border border-amber/20 px-2 py-0.5 rounded">{w}</span>
            ))}
          </div>
        </div>
      )}
      {data.overall_counterparty_assessment && (
        <div className="mt-4 pt-3 border-t border-border">
          <span className="label">Overall Assessment: </span>
          <span className={`text-xs font-mono ml-1 ${
            data.overall_counterparty_assessment === 'CRITICAL' ? 'text-red' :
            data.overall_counterparty_assessment === 'HIGH' ? 'text-red' :
            data.overall_counterparty_assessment === 'MEDIUM' ? 'text-amber' : 'text-teal'
          }`}>{data.overall_counterparty_assessment}</span>
        </div>
      )}
    </>
  )

  // Stress Tests
  if (sectionKey === 'stress_test_results') return (
    <>
      {data.narrative && <Prose text={data.narrative} />}
      <div className="grid grid-cols-2 gap-4 mt-4">
        {data.worst_scenario && (
          <div className="bg-red/5 border border-red/10 rounded p-3">
            <div className="label mb-1 text-red">Worst Scenario</div>
            <p className="text-xs text-ink-mid">{data.worst_scenario}</p>
          </div>
        )}
        {data.resilience_assessment && (
          <div className="bg-surface-2 rounded p-3">
            <div className="label mb-1">Resilience</div>
            <p className="text-xs text-ink-mid">{data.resilience_assessment}</p>
          </div>
        )}
      </div>
      {data.tail_risk_commentary && (
        <div className="mt-4 pt-4 border-t border-border">
          <div className="label mb-2">Tail Risk</div>
          <Prose text={data.tail_risk_commentary} />
        </div>
      )}
    </>
  )

  // Recommendations — the section that was showing raw JSON
  if (sectionKey === 'recommendations') return (
    <>
      {data.immediate?.length > 0 && (
        <div className="mb-5">
          <div className="label mb-3 text-red">Immediate Actions</div>
          <ActionsList items={data.immediate} />
        </div>
      )}
      {data.short_term?.length > 0 && (
        <div className="mb-5 pt-4 border-t border-border">
          <div className="label mb-3 text-amber">Short-Term Actions</div>
          <ActionsList items={data.short_term} />
        </div>
      )}
      {data.monitoring?.length > 0 && (
        <div className="mb-5 pt-4 border-t border-border">
          <div className="label mb-3">Ongoing Monitoring</div>
          <MonitoringList items={data.monitoring} />
        </div>
      )}
      {data.disclaimer && (
        <div className="mt-4 pt-4 border-t border-border">
          <p className="text-[11px] text-ink-mid leading-relaxed italic">{data.disclaimer}</p>
        </div>
      )}
    </>
  )

  // Fallback for any unexpected structure
  const mainText = data.narrative || data.overall_assessment || data.text || ''
  return <Prose text={mainText} />
}

// ── Section panel with edit ───────────────────────────────────────────────────

function SectionPanel({ sectionKey, label, data, reportStatus, onEdit }: any) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft]     = useState('')
  const canEdit = ['DRAFT','IN_REVIEW'].includes(reportStatus)

  if (!data) return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-2">
        <div className="label">{label}</div>
      </div>
      <div className="flex items-center gap-2 text-ink-mid text-sm py-4">
        <Clock className="w-4 h-4 animate-spin" /> Generating this section…
      </div>
    </div>
  )

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="label">{label}</div>
        {canEdit && !editing && (
          <button
            onClick={() => {
              const mainText = data.narrative || data.overall_assessment || ''
              setDraft(mainText)
              setEditing(true)
            }}
            className="text-xs text-ink-mid hover:text-ink flex items-center gap-1 transition-colors"
          >
            <Edit3 className="w-3 h-3" /> Edit narrative
          </button>
        )}
      </div>

      {editing ? (
        <div className="space-y-3">
          <textarea
            value={draft}
            onChange={e => setDraft(e.target.value)}
            className="w-full border border-border rounded p-3 text-sm resize-none focus:outline-none focus:border-ink"
            rows={8}
          />
          <div className="flex gap-2">
            <button onClick={async () => {
              const updated = { ...data, narrative: draft, overall_assessment: draft }
              await onEdit(sectionKey, updated)
              setEditing(false)
              toast.success('Section updated')
            }} className="btn-primary text-xs">Save changes</button>
            <button onClick={() => setEditing(false)} className="btn-secondary text-xs">Cancel</button>
          </div>
        </div>
      ) : (
        <SectionContent sectionKey={sectionKey} data={data} />
      )}
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function ReportDetailPage() {
  const { id }            = useParams()
  const [report, setReport]       = useState<any>(null)
  const [loading, setLoading]     = useState(true)
  const [approving, setApproving] = useState(false)
  const pollRef = useRef<NodeJS.Timeout>()

  const load = async () => {
    try {
      const r = await fetch(`${API}/api/v1/reports/${id}`, { headers: H() })
      if (r.ok) {
        const data = await r.json()
        setReport(data)
        // Stop polling once out of DRAFT
        if (data.status !== 'DRAFT' && pollRef.current) {
          clearInterval(pollRef.current)
        }
      }
    } catch {}
    finally { setLoading(false) }
  }

  useEffect(() => {
    if (!id) return
    load()
    pollRef.current = setInterval(load, 20000) // poll every 20s
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
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
      const d = await r.json()
      if (r.ok) { toast.success('Report approved ✓'); load() }
      else toast.error(d.detail || 'Approval failed')
    } catch { toast.error('Approval failed') }
    finally { setApproving(false) }
  }

  if (loading) return <AppLayout><div className="p-8 text-sm text-ink-mid">Loading report…</div></AppLayout>
  if (!report)  return <AppLayout><div className="p-8 text-sm text-red">Report not found</div></AppLayout>

  const isDraft    = report.status === 'DRAFT'
  const isReview   = report.status === 'IN_REVIEW'
  const isApproved = report.status === 'APPROVED'
  const isDelivered = report.status === 'DELIVERED'

  return (
    <AppLayout>
      <PageHeader
        title={report.title}
        subtitle={`${report.report_ref} · ${report.report_period} · ${report.status}`}
        action={
          <div className="flex items-center gap-2">
            {!isDraft && <DownloadButton report={report} clientName="" />}
            {isDraft ? (
              <div className="flex items-center gap-2 text-xs text-ink-mid">
                <Clock className="w-3.5 h-3.5 animate-spin" /> Generating…
              </div>
            ) : isReview ? (
              <button onClick={approve} disabled={approving}
                className="btn-primary text-xs flex items-center gap-1.5 disabled:opacity-50">
                <CheckCircle className="w-3.5 h-3.5" />
                {approving ? 'Approving…' : 'Approve Report'}
              </button>
            ) : (
              <span className={`text-xs font-mono flex items-center gap-1.5 ${isApproved ? 'text-teal' : 'text-ink-mid'}`}>
                <CheckCircle className="w-3.5 h-3.5" /> {report.status}
              </span>
            )}
          </div>
        }
      />

      <div className="p-8 space-y-4 max-w-5xl">
        {report.generation_error && (
          <div className="bg-red/5 border border-red/20 rounded p-4 text-sm text-red">
            <strong>Generation error:</strong> {report.generation_error}
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

        {isApproved && (
          <div className="card p-5">
            <div className="label mb-3">Mark as Delivered</div>
            <div className="flex gap-3">
              {['email', 'secure_link', 'portal'].map(ch => (
                <button key={ch} onClick={async () => {
                  await fetch(`${API}/api/v1/reports/${id}/deliver`, {
                    method: 'POST', headers: H(),
                    body: JSON.stringify({ channel: ch }),
                  })
                  toast.success(`Marked as delivered via ${ch.replace('_', ' ')}`)
                  load()
                }} className="btn-secondary text-xs capitalize">
                  {ch.replace('_', ' ')}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  )
}
