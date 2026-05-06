'use client'
import { useEffect, useState } from 'react'
import AppLayout from '@/components/layout/AppLayout'
import PageHeader from '@/components/layout/PageHeader'
import {
  FileText, RefreshCw, Plus, CheckCircle,
  AlertTriangle, ExternalLink, ChevronRight,
  Sparkles, Scale, Activity
} from 'lucide-react'
import toast from 'react-hot-toast'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const H = () => ({ Authorization: `Bearer ${localStorage.getItem('raven_token')}`, 'Content-Type': 'application/json' })

const CRIT_STYLE: Record<string,string> = {
  CRITICAL: 'bg-red text-white border-red',
  HIGH:     'bg-red/10 text-red border-red/20',
  MEDIUM:   'bg-amber/10 text-amber border-amber/20',
  LOW:      'bg-surface-2 text-ink-mid border-border',
}

const STATUS_STYLE: Record<string,string> = {
  new:       'bg-gold/10 text-amber border-gold/20',
  analysing: 'bg-blue-50 text-blue-600 border-blue-200',
  analysed:  'bg-teal/10 text-teal border-teal/20',
  reviewed:  'bg-teal/10 text-teal border-teal/20',
  applied:   'bg-ink/10 text-ink border-ink/20',
  dismissed: 'bg-surface-2 text-ink-mid border-border',
  error:     'bg-red/10 text-red border-red/20',
}

function DocCard({ doc, onClick }: any) {
  return (
    <div
      onClick={onClick}
      className="card p-5 cursor-pointer hover:shadow-md transition-shadow"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2 flex-wrap">
            <span className="text-xs font-mono text-ink-mid">{doc.regulator}</span>
            <span className="text-ink-mid">·</span>
            <span className="text-xs text-ink-mid capitalize">{doc.doc_type}</span>
            {doc.doc_ref && (
              <>
                <span className="text-ink-mid">·</span>
                <span className="text-xs font-mono text-ink-mid">{doc.doc_ref}</span>
              </>
            )}
            <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${STATUS_STYLE[doc.status] ?? ''}`}>
              {doc.status}
            </span>
            {doc.criticality && (
              <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${CRIT_STYLE[doc.criticality] ?? ''}`}>
                {doc.criticality}
              </span>
            )}
          </div>

          <h3 className="font-medium text-sm text-ink mb-2 leading-snug">{doc.title}</h3>

          {doc.summary && (
            <p className="text-xs text-ink-mid leading-relaxed line-clamp-2">{doc.summary}</p>
          )}

          {doc.affected_counterparties?.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-3">
              {doc.affected_counterparties.slice(0, 5).map((cp: string) => (
                <span key={cp} className="text-[10px] font-mono bg-amber/10 text-amber border border-amber/20 px-1.5 py-0.5 rounded">
                  {cp}
                </span>
              ))}
              {doc.affected_counterparties.length > 5 && (
                <span className="text-[10px] text-ink-mid">+{doc.affected_counterparties.length - 5} more</span>
              )}
            </div>
          )}
        </div>

        <div className="flex flex-col items-end gap-2 flex-shrink-0">
          {doc.published_date && (
            <span className="text-xs text-ink-mid">{doc.published_date}</span>
          )}
          <ChevronRight className="w-4 h-4 text-ink-mid" />
        </div>
      </div>
    </div>
  )
}

function DocModal({ doc: initialDoc, onClose, onUpdated }: any) {
  const [doc, setDoc]           = useState(initialDoc)
  const [applying, setApplying]     = useState(false)
  const [applyingCPs, setApplyingCPs] = useState(false)
  const [addUrl, setAddUrl]           = useState('')
  const analysis = doc.full_analysis

  const applyWeights = async () => {
    setApplying(true)
    try {
      const r = await fetch(`${API}/api/v1/regulations/${doc.doc_id}/apply-weights`, {
        method: 'POST', headers: H()
      })
      const d = await r.json()
      if (!r.ok) throw new Error(d.detail)
      toast.success(`Applied weight changes: ${d.changes?.join(', ')}`)
      onUpdated()
    } catch (e: any) { toast.error(e.message) }
    finally { setApplying(false) }
  }

  const markReviewed = async () => {
    await fetch(`${API}/api/v1/regulations/${doc.doc_id}/status`, {
      method: 'PATCH', headers: H(),
      body: JSON.stringify({ status: 'reviewed' })
    })
    toast.success('Marked as reviewed')
    onUpdated()
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center p-4 pt-8"
      onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="absolute inset-0 bg-ink/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-white rounded-xl shadow-2xl w-full max-w-3xl max-h-[88vh] overflow-hidden flex flex-col">

        {/* Header */}
        <div className="px-6 py-4 border-b border-border">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                <span className="text-xs font-mono text-ink-mid">{doc.regulator}</span>
                {doc.doc_ref && <span className="text-xs font-mono text-ink-mid">· {doc.doc_ref}</span>}
                {doc.criticality && (
                  <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${CRIT_STYLE[doc.criticality]}`}>
                    {doc.criticality}
                  </span>
                )}
              </div>
              <h2 className="font-medium text-ink leading-snug">{doc.title}</h2>
              {doc.published_date && (
                <div className="text-xs text-ink-mid mt-1">Published: {doc.published_date}</div>
              )}
            </div>
            <div className="flex items-center gap-2">
              <a href={doc.url} target="_blank" rel="noreferrer"
                className="btn-secondary text-xs flex items-center gap-1.5 py-1.5">
                <ExternalLink className="w-3 h-3" /> View PDF
              </a>
              <button onClick={onClose} className="text-ink-mid hover:text-ink text-lg leading-none">×</button>
            </div>
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-5">
          {doc.status === 'analysing' && (
            <div className="flex items-center gap-3 text-sm text-amber p-4 bg-amber/5 border border-amber/20 rounded">
              <RefreshCw className="w-4 h-4 animate-spin" />
              Claude is reading and analysing this document…
            </div>
          )}

          {/* Summary */}
          {analysis?.summary && (
            <div>
              <div className="label mb-2">Summary</div>
              <p className="text-sm text-ink-mid leading-relaxed whitespace-pre-line">{analysis.summary}</p>
              {analysis.criticality_rationale && (
                <p className="text-xs text-ink-mid mt-2 italic">{analysis.criticality_rationale}</p>
              )}
            </div>
          )}

          {/* Key requirements */}
          {analysis?.key_requirements?.length > 0 && (
            <div>
              <div className="label mb-2">Key Requirements</div>
              <ul className="space-y-1.5">
                {analysis.key_requirements.map((req: string, i: number) => (
                  <li key={i} className="text-xs text-ink-mid flex items-start gap-2">
                    <Scale className="w-3 h-3 text-gold flex-shrink-0 mt-0.5" />{req}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Affected counterparties */}
          {analysis?.affected_counterparties?.length > 0 && (
            <div>
              <div className="label mb-2">Affected Counterparties</div>
              <div className="space-y-2">
                {analysis.affected_counterparties.map((cp: any, i: number) => (
                  <div key={i} className="flex items-start gap-3 p-2.5 bg-surface-2 rounded">
                    <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded flex-shrink-0 ${
                      cp.impact === 'HIGH' ? 'bg-red/10 text-red' :
                      cp.impact === 'MEDIUM' ? 'bg-amber/10 text-amber' : 'bg-teal/10 text-teal'
                    }`}>{cp.impact}</span>
                    <div>
                      <span className="text-xs font-medium">{cp.name}</span>
                      <p className="text-xs text-ink-mid mt-0.5">{cp.reason}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Scoring dimension impacts */}
          {analysis?.scoring_dimension_impacts?.length > 0 && (
            <div>
              <div className="label mb-2">Recommended Weight Adjustments</div>
              <div className="space-y-2">
                {analysis.scoring_dimension_impacts.map((imp: any, i: number) => (
                  <div key={i} className="flex items-center gap-3 p-3 border border-border rounded">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="text-xs font-medium capitalize">{imp.dimension}</span>
                        <span className="text-xs text-ink-mid">
                          {imp.current_weight_pct}% → <strong className="text-ink">{imp.suggested_weight_pct}%</strong>
                        </span>
                        {imp.applies_to !== 'all' && (
                          <span className="text-[10px] font-mono text-ink-mid bg-surface-2 px-1.5 py-0.5 rounded">
                            {imp.applies_to} only
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-ink-mid">{imp.rationale}</p>
                    </div>
                    <div className={`text-xs font-mono font-medium ${
                      (imp.suggested_weight_pct - imp.current_weight_pct) > 0 ? 'text-teal' : 'text-red'
                    }`}>
                      {(imp.suggested_weight_pct - imp.current_weight_pct) > 0 ? '+' : ''}
                      {imp.suggested_weight_pct - imp.current_weight_pct}%
                    </div>
                  </div>
                ))}
              </div>
              <div className="flex gap-2 mt-3">
                {doc.status !== 'applied' && (
                  <button onClick={applyWeights} disabled={applying}
                    className="btn-primary text-xs flex items-center gap-1.5 disabled:opacity-50">
                    <Activity className="w-3 h-3" />
                    {applying ? 'Applying…' : 'Apply Weight Adjustments'}
                  </button>
                )}
                <button
                  onClick={async () => {
                    setApplyingCPs(true)
                    try {
                      const r = await fetch(`${API}/api/v1/regulations/${doc.doc_id}/apply-counterparties`, {
                        method: 'POST', headers: H()
                      })
                      const d = await r.json()
                      if (!r.ok) throw new Error(d.detail)
                      toast.success(`Updated ${d.updated?.length ?? 0} counterparties — rescoring`)
                      onUpdated()
                    } catch (e: any) { toast.error(e.message) }
                    finally { setApplyingCPs(false) }
                  }}
                  disabled={applyingCPs}
                  className="btn-secondary text-xs flex items-center gap-1.5 disabled:opacity-50">
                  <CheckCircle className="w-3 h-3" />
                  {applyingCPs ? 'Applying…' : 'Apply to Affected Counterparties'}
                </button>
              </div>
              {doc.status === 'applied' && (
                <div className="flex items-center gap-1.5 text-xs text-teal mt-2">
                  <CheckCircle className="w-3.5 h-3.5" /> Weight adjustments already applied
                </div>
              )}
            </div>
          )}

          {/* Compliance actions */}
          {analysis?.compliance_actions?.length > 0 && (
            <div>
              <div className="label mb-2">Compliance Actions</div>
              <div className="space-y-2">
                {analysis.compliance_actions.map((action: any, i: number) => (
                  <div key={i} className="flex items-start gap-2.5 text-xs">
                    <span className={`flex-shrink-0 font-mono text-[10px] px-1.5 py-0.5 rounded mt-0.5 ${
                      action.priority === 'IMMEDIATE' ? 'bg-red/10 text-red' :
                      action.priority === 'SHORT_TERM' ? 'bg-amber/10 text-amber' :
                      'bg-surface-2 text-ink-mid'
                    }`}>{action.priority}</span>
                    <div>
                      <span className="text-ink font-medium">{action.action}</span>
                      {action.deadline && <span className="text-ink-mid ml-1">— {action.deadline}</span>}
                      {action.rationale && <p className="text-ink-mid mt-0.5">{action.rationale}</p>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Exceptions */}
          {analysis?.exceptions_and_carve_outs?.length > 0 && (
            <div>
              <div className="label mb-2">Exceptions & Carve-outs</div>
              {analysis.exceptions_and_carve_outs.map((e: string, i: number) => (
                <p key={i} className="text-xs text-ink-mid leading-relaxed mb-1">· {e}</p>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-border bg-surface-2/50 flex items-center justify-between">
          <span className="text-xs text-ink-mid">Status: <span className="font-mono">{doc.status}</span></span>
          <div className="flex gap-2">
            {['analysed'].includes(doc.status) && (
              <button onClick={markReviewed} className="btn-secondary text-xs flex items-center gap-1.5 py-1.5">
                <CheckCircle className="w-3.5 h-3.5" /> Mark Reviewed
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default function RegulationsPage() {
  const [docs, setDocs]         = useState<any[]>([])
  const [stats, setStats]       = useState<any>(null)
  const [loading, setLoading]   = useState(true)
  const [selected, setSelected] = useState<any>(null)
  const [addUrl, setAddUrl]     = useState('')
  const [adding, setAdding]     = useState(false)
  const [monitoring, setMonitoring] = useState(false)
  const [filter, setFilter]     = useState('all')

  const load = async () => {
    setLoading(true)
    try {
      const [docsRes, statsRes] = await Promise.all([
        fetch(`${API}/api/v1/regulations`, { headers: H() }),
        fetch(`${API}/api/v1/regulations/stats`, { headers: H() }),
      ])
      if (docsRes.ok) setDocs(await docsRes.json())
      if (statsRes.ok) setStats(await statsRes.json())
    } catch {} finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const addDocument = async () => {
    if (!addUrl.trim()) return
    setAdding(true)
    try {
      const r = await fetch(`${API}/api/v1/regulations/add`, {
        method: 'POST', headers: H(),
        body: JSON.stringify({ url: addUrl.trim() }),
      })
      const d = await r.json()
      if (!r.ok) throw new Error(d.detail)
      toast.success('Document queued for analysis — takes ~30 seconds')
      setAddUrl('')
      setTimeout(load, 35000)
    } catch (e: any) { toast.error(e.message) }
    finally { setAdding(false) }
  }

  const runMonitor = async () => {
    setMonitoring(true)
    try {
      await fetch(`${API}/api/v1/regulations/monitor/run`, { method: 'POST', headers: H() })
      toast.success('Monitoring run started — checking FINMA, FCA, SEC for new publications')
      setTimeout(load, 180000)
    } catch { toast.error('Failed') }
    finally { setTimeout(() => setMonitoring(false), 5000) }
  }

  const filtered = filter === 'all' ? docs : docs.filter(d => d.status === filter)

  return (
    <AppLayout>
      <PageHeader
        title="Regulatory Intelligence"
        subtitle="Automated monitoring of FINMA, FCA, SEC — impact analysis powered by AI"
        action={
          <div className="flex gap-2">
            <button onClick={runMonitor} disabled={monitoring}
              className="btn-secondary text-xs flex items-center gap-1.5 disabled:opacity-50">
              <RefreshCw className={`w-3 h-3 ${monitoring ? 'animate-spin' : ''}`} />
              {monitoring ? 'Scanning…' : 'Scan Sources'}
            </button>
          </div>
        }
      />

      <div className="p-8 space-y-6">

        {/* URL input — always visible */}
        <div className="card p-4">
          <div className="label mb-2">Analyse a Regulatory Document</div>
          <div className="flex gap-2 items-center">
            <input
              value={addUrl}
              onChange={e => setAddUrl(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && addDocument()}
              placeholder="Paste a FINMA, FCA, or SEC document URL (PDF or HTML)…"
              className="flex-1 border border-border rounded px-3 py-2 text-sm focus:outline-none focus:border-ink"
            />
            <button
              onClick={addDocument}
              disabled={adding || !addUrl.trim()}
              className="btn-primary text-sm flex items-center gap-1.5 disabled:opacity-50 whitespace-nowrap"
            >
              {adding
                ? <><RefreshCw className="w-3.5 h-3.5 animate-spin" /> Analysing…</>
                : <><Plus className="w-3.5 h-3.5" /> Analyse Document</>
              }
            </button>
          </div>
          <p className="text-xs text-ink-mid mt-1.5">
            Try: <button onClick={() => setAddUrl('https://www.finma.ch/en/~/media/finma/dokumente/dokumentencenter/myfinma/4dokumentation/finma-aufsichtsmitteilungen/20260112-finma-aufsichtsmitteilung-01-2026.pdf?sc_lang=en&hash=D9301598FF6F909630F88578731A50DE')}
              className="text-gold hover:underline text-xs">FINMA Guidance 01/2026 — Custody of crypto-based assets</button>
          </p>
        </div>

        {/* Stats */}
        {stats && stats.total > 0 && (
          <div className="grid grid-cols-5 gap-3">
            {[
              { label: 'Total', value: stats.total, color: 'text-ink' },
              { label: 'Unreviewed', value: stats.new + stats.analysed, color: 'text-amber' },
              { label: 'Applied', value: stats.applied, color: 'text-teal' },
              { label: 'CRITICAL', value: stats.critical, color: 'text-red' },
              { label: 'HIGH', value: stats.high, color: 'text-red' },
            ].map(({ label, value, color }) => (
              <div key={label} className="card p-4 text-center">
                <div className={`text-2xl font-light ${color}`}>{value}</div>
                <div className="text-xs text-ink-mid mt-0.5">{label}</div>
              </div>
            ))}
          </div>
        )}

        {/* Filter tabs */}
        <div className="flex border-b border-border gap-1">
          {['all','new','analysed','applied','dismissed'].map(f => (
            <button key={f} onClick={() => setFilter(f)}
              className={`px-3 py-2 text-xs capitalize border-b-2 transition-colors ${
                filter === f ? 'border-gold text-ink font-medium' : 'border-transparent text-ink-mid hover:text-ink'
              }`}>
              {f} {f === 'all' ? `(${docs.length})` :
                   `(${docs.filter(d => d.status === f).length})`}
            </button>
          ))}
        </div>

        {/* Document list */}
        {loading ? (
          <div className="text-sm text-ink-mid">Loading…</div>
        ) : filtered.length === 0 ? (
          <div className="card p-8 text-center">
            <FileText className="w-8 h-8 text-ink-mid mx-auto mb-3" />
            <div className="text-sm font-medium mb-1">No documents yet</div>
            <p className="text-xs text-ink-mid mb-4">
              Paste a FINMA, FCA, or SEC document URL above to analyse it instantly.<br/>
              Or click "Scan Sources" to check for new publications.
            </p>
            <p className="text-xs text-gold">
              Try pasting the FINMA Guidance 01/2026 PDF URL to see a live analysis.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {filtered.map(doc => (
              <DocCard key={doc.doc_id} doc={doc} onClick={async () => {
                const r = await fetch(`${API}/api/v1/regulations/${doc.doc_id}`, { headers: H() })
                if (r.ok) setSelected(await r.json())
              }} />
            ))}
          </div>
        )}
      </div>

      {selected && (
        <DocModal
          doc={selected}
          onClose={() => setSelected(null)}
          onUpdated={() => { load(); setSelected(null) }}
        />
      )}
    </AppLayout>
  )
}
