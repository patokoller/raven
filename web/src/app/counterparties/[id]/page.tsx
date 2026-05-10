'use client'
import { useEffect, useState, useRef } from 'react'
import { useParams } from 'next/navigation'
import AppLayout from '@/components/layout/AppLayout'
import PageHeader from '@/components/layout/PageHeader'
import {
  Save, RefreshCw, ChevronDown, ChevronUp,
  AlertTriangle, Sparkles, CheckCircle, XCircle,
  Clock, Database, Globe, Search
} from 'lucide-react'
import toast from 'react-hot-toast'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const H = () => ({ Authorization: `Bearer ${localStorage.getItem('raven_token')}`, 'Content-Type': 'application/json' })

// ── Field form components ─────────────────────────────────────

function Toggle({ label, hint, field, value, onChange }: any) {
  return (
    <div className="flex items-center justify-between py-2.5 border-b border-border last:border-0">
      <div>
        <div className="text-sm text-ink">{label}</div>
        {hint && <div className="text-xs text-ink-mid mt-0.5">{hint}</div>}
      </div>
      <div className="flex gap-1.5">
        {[true, false, null].map((v) => (
          <button key={String(v)} onClick={() => onChange(field, v)}
            className={`text-xs px-3 py-1 rounded border transition-colors ${
              value === v
                ? v === true  ? 'bg-teal text-white border-teal'
                : v === false ? 'bg-red/80 text-white border-red'
                : 'bg-ink text-surface border-ink'
                : 'border-border text-ink-mid hover:border-ink'
            }`}>
            {v === true ? 'Yes' : v === false ? 'No' : 'Unknown'}
          </button>
        ))}
      </div>
    </div>
  )
}

function NumberInput({ label, hint, field, value, onChange, min, max, step, suffix }: any) {
  return (
    <div className="flex items-center justify-between py-2.5 border-b border-border last:border-0">
      <div>
        <div className="text-sm text-ink">{label}</div>
        {hint && <div className="text-xs text-ink-mid mt-0.5">{hint}</div>}
      </div>
      <div className="flex items-center gap-2">
        <input type="number" value={value ?? ''} min={min} max={max} step={step ?? 1}
          onChange={e => onChange(field, e.target.value === '' ? null : Number(e.target.value))}
          className="w-28 border border-border rounded px-2.5 py-1 text-sm text-right focus:outline-none focus:border-ink font-mono"
          placeholder="—" />
        {suffix && <span className="text-xs text-ink-mid w-8">{suffix}</span>}
      </div>
    </div>
  )
}

function SelectInput({ label, hint, field, value, onChange, options }: any) {
  return (
    <div className="flex items-center justify-between py-2.5 border-b border-border last:border-0">
      <div>
        <div className="text-sm text-ink">{label}</div>
        {hint && <div className="text-xs text-ink-mid mt-0.5">{hint}</div>}
      </div>
      <select value={value ?? ''} onChange={e => onChange(field, e.target.value || null)}
        className="border border-border rounded px-2.5 py-1 text-sm focus:outline-none focus:border-ink bg-white w-40">
        <option value="">Unknown</option>
        {options.map((o: any) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  )
}

// ── Score dimension bars ──────────────────────────────────────

function DimensionBar({ label, score, weight }: any) {
  const color = !score ? '#D8D2C6' : score >= 75 ? '#2A7C6F' : score >= 55 ? '#E67E22' : '#C0392B'
  return (
    <div className="flex items-center gap-3 py-1.5">
      <div className="text-xs text-ink-mid w-28 flex-shrink-0">{label}</div>
      <div className="flex-1 h-1.5 bg-surface-2 rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all duration-700"
          style={{ width: `${score ?? 0}%`, background: color }} />
      </div>
      <div className="text-xs font-mono w-8 text-right" style={{ color }}>
        {score != null ? score.toFixed(0) : '—'}
      </div>
      <div className="text-xs text-ink-mid w-12 text-right">{(weight*100).toFixed(0)}%</div>
    </div>
  )
}

// ── Research finding card ─────────────────────────────────────

function stripCitations(text: string): string {
  if (!text) return text
  return text
    .replace(/<cite[^>]*>/g, '')
    .replace(/<\/cite>/g, '')
    .replace(/  +/g, ' ')
    .trim()
}

function FindingCard({ dimKey, fieldKey, finding, selected, onToggle, onApplySingle }: any) {
  const [expanded, setExpanded] = useState(false)
  const hasValue = finding?.value !== null && finding?.value !== undefined
  const conf = finding?.confidence || 'none'
  const confColor = conf === 'high' ? 'text-teal bg-teal/10 border-teal/20'
    : conf === 'medium' ? 'text-amber bg-amber/10 border-amber/20'
    : conf === 'low'    ? 'text-red/70 bg-red/5 border-red/10'
    : 'text-ink-mid bg-surface-2 border-border'

  const label = fieldKey
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c: string) => c.toUpperCase())

  const valueDisplay = () => {
    if (!hasValue) return <span className="text-ink-mid">No data</span>
    const v = finding.value
    if (typeof v === 'boolean') return v
      ? <span className="text-teal font-medium">Yes</span>
      : <span className="text-red font-medium">No</span>
    if (typeof v === 'number') return <span className="font-mono font-medium">{v}</span>
    return <span className="font-medium capitalize">{String(v)}</span>
  }

  return (
    <div className={`p-3 rounded border transition-colors ${
      hasValue
        ? selected
          ? 'border-teal/40 bg-teal/5'
          : 'border-border hover:border-ink/30'
        : 'border-border/50 bg-surface-2/30 opacity-60'
    }`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-2 flex-1 min-w-0">
          {hasValue && (
            <input type="checkbox" checked={selected} onChange={() => onToggle(fieldKey)}
              className="mt-0.5 flex-shrink-0 accent-teal" />
          )}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-medium text-ink">{label}</span>
              <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${confColor}`}>
                {conf}
              </span>
            </div>
            <div className="text-sm mb-1.5">{valueDisplay()}</div>
            {finding?.evidence && (
              <div>
                <p className={`text-xs text-ink-mid leading-relaxed ${expanded ? '' : 'line-clamp-3'}`}>
                  {stripCitations(finding.evidence)}
                </p>
                {finding.evidence.length > 200 && (
                  <button
                    onClick={e => { e.stopPropagation(); setExpanded(!expanded) }}
                    className="text-[10px] text-gold hover:text-ink mt-1 font-medium"
                  >
                    {expanded ? 'Show less ↑' : 'Read more ↓'}
                  </button>
                )}
              </div>
            )}
            {finding?.source && (
              <div className="flex items-center gap-1 mt-1.5">
                <Globe className="w-3 h-3 text-ink-mid flex-shrink-0" />
                <span className="text-[10px] text-ink-mid">{stripCitations(finding.source)}</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Research panel ────────────────────────────────────────────

const DIMENSION_CONFIG = [
  { key: 'regulatory',  label: 'Regulatory Standing',      color: '#C9A84C' },
  { key: 'financial',   label: 'Financial Strength',       color: '#3AA896' },
  { key: 'operational', label: 'Operational Resilience',   color: '#4A9EE0' },
  { key: 'liquidity',   label: 'Liquidity & Reserves',     color: '#9B59B6' },
  { key: 'onchain',     label: 'On-Chain Health',          color: '#2A7C6F' },
  { key: 'reputation',  label: 'Reputation & Signals',     color: '#C0392B' },
]

function ResearchPanel({ counterpartyId, entityName, onApplied }: any) {
  const [research, setResearch]     = useState<any>(null)
  const [status, setStatus]         = useState<string>('none')
  const [selected, setSelected]     = useState<Set<string>>(new Set())
  const [applying, setApplying]     = useState(false)
  const [running, setRunning]       = useState(false)
  const pollRef = useRef<NodeJS.Timeout>()

  const loadResearch = async () => {
    const r = await fetch(`${API}/api/v1/counterparties/${counterpartyId}/research`, { headers: H() })
    if (r.ok) {
      const d = await r.json()
      setStatus(d.research_status || 'none')
      if (d.research_data) setResearch(d.research_data)
      // Stop polling when done
      if (['complete','error'].includes(d.research_status) && pollRef.current) {
        clearInterval(pollRef.current)
        setRunning(false)
      }
    }
  }

  useEffect(() => {
    loadResearch()
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [counterpartyId])

  const startResearch = async () => {
    setRunning(true)
    setResearch(null)
    setSelected(new Set())
    try {
      const r = await fetch(`${API}/api/v1/counterparties/${counterpartyId}/research`, {
        method: 'POST', headers: H()
      })
      if (!r.ok) {
        const d = await r.json()
        toast.error(d.detail || 'Failed to start research')
        setRunning(false)
        return
      }
      toast.success(`Researching ${entityName} — this takes 2-3 minutes`)
      setStatus('running')
      pollRef.current = setInterval(loadResearch, 10000)
    } catch { toast.error('Failed to start research'); setRunning(false) }
  }

  const toggleField = (fieldKey: string) => {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(fieldKey)) next.delete(fieldKey)
      else next.add(fieldKey)
      return next
    })
  }

  const selectAll = () => {
    const allFields: string[] = []
    DIMENSION_CONFIG.forEach(dim => {
      const dimFindings = research?.findings?.[dim.key] || {}
      Object.entries(dimFindings).forEach(([field, data]: any) => {
        if (data?.value !== null && data?.value !== undefined) {
          allFields.push(field)
        }
      })
    })
    setSelected(new Set(allFields))
  }

  const applySelected = async (applyAll = false) => {
    setApplying(true)
    try {
      const r = await fetch(`${API}/api/v1/counterparties/${counterpartyId}/research/apply`, {
        method: 'POST', headers: H(),
        body: JSON.stringify(
          applyAll
            ? { apply_all: true }
            : { fields: Array.from(selected) }
        ),
      })
      const d = await r.json()
      if (!r.ok) throw new Error(d.detail)
      toast.success(`Applied ${d.fields_applied.length} fields — rescoring in background`)
      onApplied()
    } catch (e: any) { toast.error(e.message) }
    finally { setApplying(false) }
  }

  // Count total fields found
  const foundCount = research ? DIMENSION_CONFIG.reduce((acc, dim) => {
    const dimData = research.findings?.[dim.key] || {}
    return acc + Object.values(dimData).filter((f: any) => f?.value !== null && f?.value !== undefined).length
  }, 0) : 0

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="card p-5">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-gold" />
            <span className="font-medium text-sm">AI Research Agent</span>
          </div>
          <button onClick={startResearch} disabled={running || status === 'running'}
            className="btn-primary text-xs flex items-center gap-1.5 disabled:opacity-50">
            {running || status === 'running'
              ? <><RefreshCw className="w-3 h-3 animate-spin" /> Researching…</>
              : <><Search className="w-3 h-3" /> {research ? 'Re-research' : 'Research with AI'}</>
            }
          </button>
        </div>

        {status === 'none' && !research && (
          <p className="text-xs text-ink-mid">
            The agent will search regulatory registers, financial filings, news sources,
            on-chain data (DefiLlama), and security databases to populate all scoring fields automatically.
            Takes 2–3 minutes. You review and approve before any data is applied.
          </p>
        )}

        {(running || status === 'running') && (
          <div className="bg-gold/5 border border-gold/20 rounded p-3 mt-2">
            <div className="flex items-center gap-2 text-xs text-amber mb-2">
              <Clock className="w-3.5 h-3.5 animate-pulse" />
              <span className="font-medium">Agent running — searching web, regulatory databases, on-chain data…</span>
            </div>
            <div className="space-y-1">
              {[
                'Checking regulatory registers (FINMA, FCA, SEC, CFTC, OCC)…',
                'Searching financial filings and annual reports…',
                'Looking up security incidents on rekt.news…',
                'Fetching on-chain data from DefiLlama…',
                'Analysing news sentiment from last 30 days…',
              ].map((step, i) => (
                <div key={i} className="flex items-center gap-2 text-xs text-ink-mid">
                  <div className="w-1.5 h-1.5 rounded-full bg-gold/40 animate-pulse" />
                  {step}
                </div>
              ))}
            </div>
            <div className="text-xs text-ink-mid mt-2">Auto-refreshing every 10 seconds…</div>
          </div>
        )}

        {status === 'error' && research?.error && (
          <div className="bg-red/5 border border-red/20 rounded p-3 mt-2 text-xs text-red">
            Research failed: {research.error}
          </div>
        )}

        {status === 'complete' && research && (
          <div className="flex items-center justify-between mt-2">
            <div className="flex items-center gap-2 text-xs text-teal">
              <CheckCircle className="w-3.5 h-3.5" />
              <span>Found data for <strong>{foundCount}</strong> fields · {research.data_gaps?.length ?? 0} gaps · Last researched: {new Date(research.researched_at).toLocaleString('en-CH')}</span>
            </div>
            <div className="flex gap-2">
              <button onClick={selectAll} className="btn-secondary text-xs py-1">Select All</button>
              <button onClick={() => applySelected(false)} disabled={selected.size === 0 || applying}
                className="btn-secondary text-xs py-1 disabled:opacity-50">
                Apply Selected ({selected.size})
              </button>
              <button onClick={() => applySelected(true)} disabled={applying}
                className="btn-primary text-xs py-1 flex items-center gap-1 disabled:opacity-50">
                <Database className="w-3 h-3" />
                {applying ? 'Applying…' : 'Apply All & Rescore'}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Research summary */}
      {status === 'complete' && research?.research_summary && (
        <div className="card p-5">
          <div className="label mb-2">Research Summary</div>
          <p className="text-sm text-ink-mid leading-relaxed">{research.research_summary}</p>
          {research.data_gaps?.length > 0 && (
            <div className="mt-3 pt-3 border-t border-border">
              <div className="label mb-1.5 text-amber">Data Gaps</div>
              <div className="flex flex-wrap gap-1.5">
                {research.data_gaps.map((gap: string) => (
                  <span key={gap} className="text-xs bg-amber/10 text-amber border border-amber/20 px-2 py-0.5 rounded font-mono">
                    {gap}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Findings per dimension */}
      {status === 'complete' && research?.findings && DIMENSION_CONFIG.map(dim => {
        const dimFindings = research.findings[dim.key]
        if (!dimFindings) return null
        const fields = Object.entries(dimFindings)
        const foundInDim = fields.filter(([, d]: any) => d?.value !== null && d?.value !== undefined).length

        return (
          <div key={dim.key} className="card overflow-hidden">
            <div className="px-5 py-3 border-b border-border flex items-center justify-between"
              style={{ borderLeftWidth: 3, borderLeftColor: dim.color }}>
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium" style={{ color: dim.color }}>{dim.label}</span>
                <span className="text-xs text-ink-mid">
                  {foundInDim}/{fields.length} fields found
                </span>
              </div>
              <button
                onClick={() => fields.forEach(([field, data]: any) => {
                  if (data?.value !== null && data?.value !== undefined) {
                    setSelected(prev => new Set(Array.from(prev).concat(field)))
                  }
                })}
                className="text-xs text-ink-mid hover:text-ink"
              >
                Select all in section
              </button>
            </div>
            <div className="p-4 grid grid-cols-2 gap-3">
              {fields.map(([field, finding]: any) => (
                <FindingCard
                  key={field}
                  dimKey={dim.key}
                  fieldKey={field}
                  finding={finding}
                  selected={selected.has(field)}
                  onToggle={toggleField}
                  onApplySingle={() => {}}
                />
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ── Enrichment form section ───────────────────────────────────

function EnrichSection({ title, num, color, completeness, children }: any) {
  const [open, setOpen] = useState(false)
  return (
    <div className="card overflow-hidden">
      <button onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-5 py-3.5 border-b border-border hover:bg-surface-2/30 transition-colors">
        <div className="flex items-center gap-3">
          <span className="font-mono text-[10px] text-ink-mid">{num}</span>
          <span className="text-sm font-medium" style={{ color }}>{title}</span>
          <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${
            completeness === 'complete' ? 'bg-teal/10 text-teal' :
            completeness === 'partial'  ? 'bg-amber/10 text-amber' :
            'bg-surface-2 text-ink-mid'}`}>
            {completeness === 'complete' ? '✓ Complete' : completeness === 'partial' ? '~ Partial' : 'Empty'}
          </span>
        </div>
        {open ? <ChevronUp className="w-4 h-4 text-ink-mid" /> : <ChevronDown className="w-4 h-4 text-ink-mid" />}
      </button>
      {open && <div className="px-5 py-3">{children}</div>}
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────

export default function CounterpartyDetailPage() {
  const { id }                = useParams()
  const [cp, setCp]           = useState<any>(null)
  const [score, setScore]     = useState<any>(null)
  const [enrich, setEnrich]   = useState<any>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving]   = useState(false)
  const [dirty, setDirty]     = useState(false)
  const [dataSources, setDataSources] = useState<any>(null)
  const [loadingSources, setLoadingSources] = useState(false)
  const [tab, setTab]         = useState<'research'|'manual'>('research')

  const load = async () => {
    setLoading(true)
    try {
      const [cpRes, enrichRes] = await Promise.all([
        fetch(`${API}/api/v1/counterparties/${id}`, { headers: H() }),
        fetch(`${API}/api/v1/counterparties/${id}/enrichment`, { headers: H() }),
      ])
      if (cpRes.ok) {
        const data = await cpRes.json()
        setCp(data)
        setScore(data.latest_score)
      }
      if (enrichRes.ok) {
        const e = await enrichRes.json()
        setEnrich(e.enrichment_data || {})
      }
    } catch { toast.error('Failed to load') }
    finally { setLoading(false) }
  }

  const fetchDataSources = async () => {
    setLoadingSources(true)
    try {
      const r = await fetch(`${API}/api/v1/counterparties/${id}/data-sources`, { headers: H() })
      if (r.ok) setDataSources(await r.json())
    } catch {} finally { setLoadingSources(false) }
  }

  useEffect(() => { if (id) { load(); fetchDataSources() } }, [id])

  const update = (field: string, value: any) => {
    setEnrich((prev: any) => ({ ...prev, [field]: value }))
    setDirty(true)
  }

  const save = async () => {
    setSaving(true)
    try {
      const r = await fetch(`${API}/api/v1/counterparties/${id}/enrichment`, {
        method: 'POST', headers: H(), body: JSON.stringify(enrich),
      })
      const d = await r.json()
      if (!r.ok) throw new Error(d.detail)
      setDirty(false)
      toast.success(`Saved ${d.fields_updated.length} fields — rescoring`)
      setTimeout(load, 8000)
    } catch (e: any) { toast.error(e.message) }
    finally { setSaving(false) }
  }

  const getC = (fields: string[]) => {
    const n = fields.filter(f => enrich[f] != null).length
    return n === 0 ? 'empty' : n === fields.length ? 'complete' : 'partial'
  }

  const tierColors: Record<string,string> = { LOW:'#2A7C6F', MEDIUM:'#E67E22', HIGH:'#C0392B', CRITICAL:'#7B1010' }
  const tierColor = tierColors[cp?.current_risk_tier as string] || '#6B6560'

  if (loading) return <AppLayout><div className="p-8 text-sm text-ink-mid">Loading…</div></AppLayout>
  if (!cp)     return <AppLayout><div className="p-8 text-sm text-red">Not found</div></AppLayout>

  return (
    <AppLayout>
      <PageHeader
        title={cp.display_name}
        subtitle={`${cp.entity_type} · ${cp.jurisdiction ?? '—'} · ${cp.regulator ?? 'No regulator on record'}`}
        action={
          <div className="flex items-center gap-2">
            {tab === 'manual' && dirty && (
              <button onClick={save} disabled={saving}
                className="btn-primary text-xs flex items-center gap-1.5 disabled:opacity-50">
                <Save className="w-3.5 h-3.5" />
                {saving ? 'Saving…' : 'Save & Rescore'}
              </button>
            )}
          </div>
        }
      />

      <div className="p-8 grid grid-cols-3 gap-6">

        {/* Left: score + profile */}
        <div className="space-y-4">
          <div className="card p-5">
            <div className="label mb-3">Current Risk Score</div>
            <div className="flex items-end gap-3 mb-4">
              <div className="text-5xl font-light" style={{ color: tierColor }}>
                {score?.composite_score?.toFixed(0) ?? '—'}
              </div>
              <div className="pb-1">
                <div className="text-xs font-mono px-2 py-0.5 rounded border mb-1"
                  style={{ color: tierColor, borderColor: tierColor+'40', backgroundColor: tierColor+'10' }}>
                  {cp.current_risk_tier ?? '—'}
                </div>
                <div className="text-xs text-ink-mid">out of 100</div>
              </div>
            </div>
            <div className="space-y-0.5">
              <DimensionBar label="Regulatory"  score={score?.regulatory_score}  weight={0.25} />
              <DimensionBar label="Financial"   score={score?.financial_score}   weight={0.20} />
              <DimensionBar label="Operational" score={score?.operational_score} weight={0.20} />
              <DimensionBar label="Liquidity"   score={score?.liquidity_score}   weight={0.15} />
              <DimensionBar label="On-Chain"    score={score?.onchain_score}     weight={0.10} />
              <DimensionBar label="Reputation"  score={score?.reputation_score}  weight={0.10} />
            </div>
          </div>

          <div className="card p-5">
            <div className="label mb-3">Entity Profile</div>
            <div className="space-y-2 text-xs">
              {[['Type', cp.entity_type],['Jurisdiction', cp.jurisdiction],
                ['Regulator', cp.regulator],['License', cp.license_number],
                ['Website', cp.website]].map(([k,v]) => v ? (
                <div key={k} className="flex justify-between">
                  <span className="text-ink-mid">{k}</span>
                  <span className="text-ink font-mono text-[11px]">{v}</span>
                </div>
              ) : null)}
            </div>
          </div>

          <div className="card p-5">
            <div className="label mb-3">Data Completeness</div>
            {[
              { label:'Regulatory',  fields:['license_active','enforcement_actions_12m'] },
              { label:'Financial',   fields:['is_publicly_listed','has_audited_financials','equity_ratio','revenue_stability','debt_level'] },
              { label:'Operational', fields:['has_soc2','has_iso27001','has_insurance','major_security_incidents','years_in_operation'] },
              { label:'Liquidity',   fields:['por_ratio','reserve_quality','withdrawal_restrictions_history'] },
              { label:'On-Chain',    fields:['onchain_reserve_trend_30d'] },
              { label:'Reputation',  fields:['industry_reputation_score','leadership_concerns'] },
            ].map(({ label, fields }) => {
              const c = getC(fields)
              return (
                <div key={label} className="flex items-center justify-between py-1.5">
                  <span className="text-xs text-ink-mid">{label}</span>
                  <span className={`text-[10px] font-mono ${c==='complete'?'text-teal':c==='partial'?'text-amber':'text-ink-mid'}`}>
                    {c==='complete'?'✓ Complete':c==='partial'?'~ Partial':'○ Empty'}
                  </span>
                </div>
              )
            })}
          </div>
          {/* Data Sources panel */}
          <div className="card p-5">
            <div className="label mb-3 flex items-center justify-between">
              Data Sources
              <button onClick={fetchDataSources} className="text-ink-mid hover:text-ink">
                <RefreshCw className={`w-3 h-3 ${loadingSources ? 'animate-spin' : ''}`} />
              </button>
            </div>
            {!dataSources ? (
              <div className="text-xs text-ink-mid">Loading…</div>
            ) : (
              <div className="space-y-2">
                {Object.entries(dataSources.sources || {}).map(([key, src]: any) => {
                  const fields = Object.keys(src.data || {}).filter(k =>
                    !['source','available','fetched_at','note'].includes(k) &&
                    src.data[k] !== null && src.data[k] !== undefined
                  ).length
                  return (
                    <div key={key}>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                            src.available ? 'bg-teal' : 'bg-surface-2 border border-border'
                          }`} />
                          <span className="text-xs">{src.name}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          {src.available ? (
                            <>
                              <span className="text-[10px] font-mono text-teal">
                                {fields > 0 ? `${fields} fields` : 'connected'}
                              </span>
                              {src.url && (
                                <a href={src.url} target="_blank" rel="noreferrer"
                                  className="text-[10px] text-ink-mid hover:text-ink underline">
                                  view →
                                </a>
                              )}
                            </>
                          ) : (
                            <span className="text-[10px] text-ink-mid italic">
                              unavailable
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  )
                })}
                <div className="pt-2 border-t border-border mt-2">
                  <p className="text-[10px] text-ink-mid leading-relaxed">
                    Sources marked "unavailable" could not be accessed at this time. AI web search fills these gaps during research.
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right: tabs */}
        <div className="col-span-2 space-y-4">

          {/* Tab switcher */}
          <div className="flex border-b border-border">
            <button onClick={() => setTab('research')}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                tab === 'research' ? 'border-gold text-ink' : 'border-transparent text-ink-mid hover:text-ink'}`}>
              <span className="flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5" /> AI Research
              </span>
            </button>
            <button onClick={() => setTab('manual')}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                tab === 'manual' ? 'border-gold text-ink' : 'border-transparent text-ink-mid hover:text-ink'}`}>
              <span className="flex items-center gap-1.5">
                <Database className="w-3.5 h-3.5" /> Manual Input
              </span>
            </button>
          </div>

          {/* AI Research tab */}
          {tab === 'research' && (
            <ResearchPanel
              counterpartyId={id}
              entityName={cp.display_name}
              onApplied={() => { setTimeout(load, 8000) }}
            />
          )}

          {/* Manual Input tab */}
          {tab === 'manual' && (
            <div className="space-y-3">
              <div className="text-xs text-ink-mid">
                Fill in data signals manually. Each field directly affects the score. Click <strong>Save & Rescore</strong> when done.
              </div>

              <EnrichSection title="Regulatory Standing" num="01" color="#C9A84C" completeness={getC(['license_active','enforcement_actions_12m'])}>
                <Toggle label="License Active" hint="Primary operating licence currently active and in good standing"
                  field="license_active" value={enrich.license_active} onChange={update} />
                <NumberInput label="Enforcement Actions (12m)" hint="Regulatory enforcement actions, fines, or sanctions in the last 12 months"
                  field="enforcement_actions_12m" value={enrich.enforcement_actions_12m} onChange={update} min={0} max={20} />
              </EnrichSection>

              <EnrichSection title="Financial Strength" num="02" color="#3AA896" completeness={getC(['is_publicly_listed','has_audited_financials','equity_ratio','revenue_stability','debt_level'])}>
                <Toggle label="Publicly Listed" field="is_publicly_listed" value={enrich.is_publicly_listed} onChange={update} />
                <Toggle label="Audited Financials" hint="Published audited financial statements in the last 12 months"
                  field="has_audited_financials" value={enrich.has_audited_financials} onChange={update} />
                <NumberInput label="Equity Ratio" hint="Total equity / total assets. E.g. 0.35 = 35%"
                  field="equity_ratio" value={enrich.equity_ratio} onChange={update} min={0} max={1} step={0.01} suffix="ratio" />
                <SelectInput label="Revenue Stability" field="revenue_stability" value={enrich.revenue_stability} onChange={update}
                  options={[{value:'stable',label:'Stable'},{value:'volatile',label:'Volatile'}]} />
                <SelectInput label="Debt Level" field="debt_level" value={enrich.debt_level} onChange={update}
                  options={[{value:'low',label:'Low'},{value:'moderate',label:'Moderate'},{value:'high',label:'High'}]} />
              </EnrichSection>

              <EnrichSection title="Operational Resilience" num="03" color="#4A9EE0" completeness={getC(['has_soc2','has_iso27001','has_insurance','major_security_incidents','years_in_operation'])}>
                <Toggle label="SOC 2 Certified" field="has_soc2" value={enrich.has_soc2} onChange={update} />
                <Toggle label="ISO 27001 Certified" field="has_iso27001" value={enrich.has_iso27001} onChange={update} />
                <Toggle label="Crime / Custody Insurance" field="has_insurance" value={enrich.has_insurance} onChange={update} />
                <NumberInput label="Major Security Incidents" field="major_security_incidents" value={enrich.major_security_incidents} onChange={update} min={0} max={10} />
                <NumberInput label="Years in Operation" field="years_in_operation" value={enrich.years_in_operation} onChange={update} min={0} max={30} suffix="yrs" />
              </EnrichSection>

              <EnrichSection title="Liquidity & Reserves" num="04" color="#9B59B6" completeness={getC(['por_ratio','reserve_quality','withdrawal_restrictions_history'])}>
                <NumberInput label="Proof of Reserves Ratio" hint="Verified assets / liabilities. E.g. 1.05 = 105% backed"
                  field="por_ratio" value={enrich.por_ratio} onChange={update} min={0} max={2} step={0.01} suffix="×" />
                <SelectInput label="Reserve Quality" field="reserve_quality" value={enrich.reserve_quality} onChange={update}
                  options={[{value:'high',label:'High'},{value:'medium',label:'Medium'},{value:'low',label:'Low'}]} />
                <Toggle label="Withdrawal Restrictions History" hint="Has the entity ever restricted or halted withdrawals"
                  field="withdrawal_restrictions_history" value={enrich.withdrawal_restrictions_history} onChange={update} />
              </EnrichSection>

              <EnrichSection title="On-Chain Health" num="05" color="#2A7C6F" completeness={getC(['onchain_reserve_trend_30d'])}>
                <SelectInput label="Reserve Trend (30d)" field="onchain_reserve_trend_30d" value={enrich.onchain_reserve_trend_30d} onChange={update}
                  options={[{value:'increasing',label:'Increasing ↑'},{value:'stable',label:'Stable →'},{value:'declining',label:'Declining ↓'},{value:'critical_outflow',label:'Critical Outflow ↓↓'}]} />
                <NumberInput label="TVL Change 30d" hint="DeFi only. E.g. 0.15 = +15%"
                  field="tvl_change_30d_pct" value={enrich.tvl_change_30d_pct} onChange={update} min={-1} max={5} step={0.01} suffix="%" />
                <NumberInput label="Smart Contract Audits" hint="DeFi only: number of independent security audits"
                  field="audit_count" value={enrich.audit_count} onChange={update} min={0} max={20} />
              </EnrichSection>

              <EnrichSection title="Reputation & Market Signals" num="06" color="#C0392B" completeness={getC(['industry_reputation_score','leadership_concerns'])}>
                <NumberInput label="Industry Reputation Score" hint="0 = severely damaged, 100 = exceptional"
                  field="industry_reputation_score" value={enrich.industry_reputation_score} onChange={update} min={0} max={100} suffix="/100" />
                <Toggle label="Leadership Concerns" hint="Material concerns about executive leadership quality or integrity"
                  field="leadership_concerns" value={enrich.leadership_concerns} onChange={update} />
              </EnrichSection>

              <div className="card p-5">
                <div className="label mb-3">Analyst Notes</div>
                <textarea value={enrich.analyst_notes ?? ''} onChange={e => update('analyst_notes', e.target.value || null)}
                  rows={4} placeholder="Internal notes — not included in client reports…"
                  className="w-full border border-border rounded px-3 py-2 text-sm resize-none focus:outline-none focus:border-ink" />
              </div>

              {dirty && (
                <div className="flex justify-end">
                  <button onClick={save} disabled={saving}
                    className="btn-primary flex items-center gap-1.5 disabled:opacity-50">
                    <Save className="w-4 h-4" />
                    {saving ? 'Saving & Rescoring…' : 'Save & Rescore'}
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </AppLayout>
  )
}
