'use client'
import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import AppLayout from '@/components/layout/AppLayout'
import PageHeader from '@/components/layout/PageHeader'
import { Save, RefreshCw, ChevronDown, ChevronUp, CheckCircle, AlertTriangle } from 'lucide-react'
import toast from 'react-hot-toast'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const H = () => ({ Authorization: `Bearer ${localStorage.getItem('raven_token')}`, 'Content-Type': 'application/json' })

// ── Field components ──────────────────────────────────────────────────────────

function Toggle({ label, hint, field, value, onChange }: any) {
  return (
    <div className="flex items-center justify-between py-2.5 border-b border-border last:border-0">
      <div>
        <div className="text-sm text-ink">{label}</div>
        {hint && <div className="text-xs text-ink-mid mt-0.5">{hint}</div>}
      </div>
      <div className="flex gap-2">
        {[true, false, null].map((v) => (
          <button
            key={String(v)}
            onClick={() => onChange(field, v)}
            className={`text-xs px-3 py-1 rounded border transition-colors ${
              value === v
                ? v === true  ? 'bg-teal text-white border-teal'
                : v === false ? 'bg-red/80 text-white border-red'
                : 'bg-ink text-surface border-ink'
                : 'border-border text-ink-mid hover:border-ink'
            }`}
          >
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
        <input
          type="number"
          value={value ?? ''}
          min={min}
          max={max}
          step={step ?? 1}
          onChange={e => onChange(field, e.target.value === '' ? null : Number(e.target.value))}
          className="w-28 border border-border rounded px-2.5 py-1 text-sm text-right focus:outline-none focus:border-ink font-mono"
          placeholder="—"
        />
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
      <select
        value={value ?? ''}
        onChange={e => onChange(field, e.target.value || null)}
        className="border border-border rounded px-2.5 py-1 text-sm focus:outline-none focus:border-ink bg-white w-40"
      >
        <option value="">Unknown</option>
        {options.map((o: any) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </div>
  )
}

// ── Score dimension display ───────────────────────────────────────────────────

function DimensionBar({ label, score, weight }: { label: string; score?: number | null; weight: number }) {
  if (score == null) return (
    <div className="flex items-center gap-3 py-1.5">
      <div className="text-xs text-ink-mid w-28 flex-shrink-0">{label}</div>
      <div className="flex-1 h-1.5 bg-surface-2 rounded-full" />
      <div className="text-xs font-mono text-ink-mid w-8 text-right">—</div>
      <div className="text-xs text-ink-mid w-12 text-right">{(weight * 100).toFixed(0)}%</div>
    </div>
  )
  const color = score >= 75 ? '#2A7C6F' : score >= 55 ? '#E67E22' : '#C0392B'
  return (
    <div className="flex items-center gap-3 py-1.5">
      <div className="text-xs text-ink-mid w-28 flex-shrink-0">{label}</div>
      <div className="flex-1 h-1.5 bg-surface-2 rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all duration-500" style={{ width: `${score}%`, background: color }} />
      </div>
      <div className="text-xs font-mono font-medium w-8 text-right" style={{ color }}>{score.toFixed(0)}</div>
      <div className="text-xs text-ink-mid w-12 text-right">{(weight * 100).toFixed(0)}%</div>
    </div>
  )
}

// ── Accordion section ─────────────────────────────────────────────────────────

function Section({ title, num, color, completeness, children }: any) {
  const [open, setOpen] = useState(true)
  return (
    <div className="card overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-5 py-3.5 border-b border-border hover:bg-surface-2/30 transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className="font-mono text-[10px] text-ink-mid">{num}</span>
          <span className="text-sm font-medium" style={{ color }}>{title}</span>
          <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${
            completeness === 'complete' ? 'bg-teal/10 text-teal' :
            completeness === 'partial'  ? 'bg-amber/10 text-amber' :
            'bg-surface-2 text-ink-mid'
          }`}>
            {completeness === 'complete' ? '✓ Complete' :
             completeness === 'partial'  ? '~ Partial' : 'Empty'}
          </span>
        </div>
        {open ? <ChevronUp className="w-4 h-4 text-ink-mid" /> : <ChevronDown className="w-4 h-4 text-ink-mid" />}
      </button>
      {open && <div className="px-5 py-3">{children}</div>}
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function CounterpartyDetailPage() {
  const { id }    = useParams()
  const router    = useRouter()
  const [cp, setCp]       = useState<any>(null)
  const [score, setScore] = useState<any>(null)
  const [enrich, setEnrich] = useState<any>({})
  const [loading, setLoading]   = useState(true)
  const [saving, setSaving]     = useState(false)
  const [rescoring, setRescoring] = useState(false)
  const [dirty, setDirty]       = useState(false)

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
    } catch { toast.error('Failed to load counterparty') }
    finally { setLoading(false) }
  }

  useEffect(() => { if (id) load() }, [id])

  const update = (field: string, value: any) => {
    setEnrich((prev: any) => ({ ...prev, [field]: value }))
    setDirty(true)
  }

  const save = async () => {
    setSaving(true)
    try {
      const r = await fetch(`${API}/api/v1/counterparties/${id}/enrichment`, {
        method: 'POST',
        headers: H(),
        body: JSON.stringify(enrich),
      })
      const d = await r.json()
      if (!r.ok) throw new Error(d.detail)
      setDirty(false)
      toast.success(`Saved ${d.fields_updated.length} fields — rescoring in background`)
      // Poll for updated score
      setTimeout(async () => {
        setRescoring(true)
        await load()
        setRescoring(false)
      }, 8000)
    } catch (e: any) {
      toast.error(e.message)
    } finally { setSaving(false) }
  }

  // Completeness helpers
  const regFields   = ['license_active', 'enforcement_actions_12m']
  const finFields   = ['is_publicly_listed', 'has_audited_financials', 'equity_ratio', 'revenue_stability', 'debt_level']
  const opFields    = ['has_soc2', 'has_iso27001', 'has_insurance', 'major_security_incidents', 'years_in_operation']
  const liqFields   = ['por_ratio', 'reserve_quality', 'withdrawal_restrictions_history']
  const chainFields = ['onchain_reserve_trend_30d']
  const repFields   = ['industry_reputation_score', 'leadership_concerns']

  const getCompleteness = (fields: string[]) => {
    const filled = fields.filter(f => enrich[f] != null).length
    if (filled === 0) return 'empty'
    if (filled === fields.length) return 'complete'
    return 'partial'
  }

  if (loading) return <AppLayout><div className="p-8 text-sm text-ink-mid">Loading…</div></AppLayout>
  if (!cp)     return <AppLayout><div className="p-8 text-sm text-red">Counterparty not found</div></AppLayout>

  const tierColor = {
    LOW: '#2A7C6F', MEDIUM: '#E67E22', HIGH: '#C0392B', CRITICAL: '#7B1010'
  }[cp.current_risk_tier as string] || '#6B6560'

  return (
    <AppLayout>
      <PageHeader
        title={cp.display_name}
        subtitle={`${cp.entity_type} · ${cp.jurisdiction ?? '—'} · ${cp.regulator ?? 'No regulator'}`}
        action={
          <div className="flex items-center gap-2">
            {rescoring && (
              <span className="text-xs text-ink-mid flex items-center gap-1.5">
                <RefreshCw className="w-3 h-3 animate-spin" /> Rescoring…
              </span>
            )}
            <button
              onClick={save}
              disabled={!dirty || saving}
              className="btn-primary text-xs flex items-center gap-1.5 disabled:opacity-50"
            >
              <Save className="w-3.5 h-3.5" />
              {saving ? 'Saving…' : dirty ? 'Save & Rescore' : 'Saved'}
            </button>
          </div>
        }
      />

      <div className="p-8 grid grid-cols-3 gap-6">

        {/* Left: Score breakdown */}
        <div className="space-y-4">
          {/* Current score card */}
          <div className="card p-5">
            <div className="label mb-3">Current Risk Score</div>
            <div className="flex items-end gap-3 mb-4">
              <div className="text-5xl font-light" style={{ color: tierColor }}>
                {score?.composite_score?.toFixed(0) ?? '—'}
              </div>
              <div className="pb-1">
                <div className="text-xs font-mono px-2 py-0.5 rounded border mb-1" style={{
                  color: tierColor,
                  borderColor: tierColor + '40',
                  backgroundColor: tierColor + '10',
                }}>
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

            {score?.is_overridden && (
              <div className="mt-3 text-xs text-amber flex items-center gap-1.5">
                <AlertTriangle className="w-3 h-3" /> Score has manual overrides
              </div>
            )}
          </div>

          {/* Entity profile */}
          <div className="card p-5">
            <div className="label mb-3">Entity Profile</div>
            <div className="space-y-2 text-xs">
              {[
                ['Type',        cp.entity_type],
                ['Jurisdiction', cp.jurisdiction],
                ['Regulator',   cp.regulator],
                ['License',     cp.license_number],
                ['Website',     cp.website],
              ].map(([k, v]) => v ? (
                <div key={k} className="flex justify-between">
                  <span className="text-ink-mid">{k}</span>
                  <span className="text-ink font-mono text-[11px]">{v}</span>
                </div>
              ) : null)}
            </div>
          </div>

          {/* Enrichment status */}
          <div className="card p-5">
            <div className="label mb-3">Data Completeness</div>
            {[
              { label: 'Regulatory',  fields: regFields },
              { label: 'Financial',   fields: finFields },
              { label: 'Operational', fields: opFields },
              { label: 'Liquidity',   fields: liqFields },
              { label: 'On-Chain',    fields: chainFields },
              { label: 'Reputation',  fields: repFields },
            ].map(({ label, fields }) => {
              const c = getCompleteness(fields)
              return (
                <div key={label} className="flex items-center justify-between py-1.5">
                  <span className="text-xs text-ink-mid">{label}</span>
                  <span className={`text-[10px] font-mono ${
                    c === 'complete' ? 'text-teal' :
                    c === 'partial'  ? 'text-amber' : 'text-ink-mid'
                  }`}>
                    {c === 'complete' ? '✓ Complete' : c === 'partial' ? '~ Partial' : '○ Empty'}
                  </span>
                </div>
              )
            })}
          </div>
        </div>

        {/* Right: Enrichment form */}
        <div className="col-span-2 space-y-3">
          <div className="text-xs text-ink-mid mb-1">
            Fill in data signals below. Each field directly affects the score. Click <strong>Save & Rescore</strong> to apply. Fields marked Unknown use scoring engine defaults.
          </div>

          {/* 01 Regulatory */}
          <Section title="Regulatory Standing" num="01" color="#C9A84C" completeness={getCompleteness(regFields)}>
            <Toggle label="License Active" hint="Is the entity's primary operating licence currently active and in good standing?"
              field="license_active" value={enrich.license_active} onChange={update} />
            <NumberInput label="Enforcement Actions (12m)" hint="Number of regulatory enforcement actions, fines, or sanctions in the last 12 months"
              field="enforcement_actions_12m" value={enrich.enforcement_actions_12m} onChange={update} min={0} max={20} />
          </Section>

          {/* 02 Financial */}
          <Section title="Financial Strength" num="02" color="#3AA896" completeness={getCompleteness(finFields)}>
            <Toggle label="Publicly Listed" hint="Is the entity listed on a regulated stock exchange?"
              field="is_publicly_listed" value={enrich.is_publicly_listed} onChange={update} />
            <Toggle label="Audited Financials" hint="Has the entity published audited financial statements in the last 12 months?"
              field="has_audited_financials" value={enrich.has_audited_financials} onChange={update} />
            <NumberInput label="Equity Ratio" hint="Total equity / total assets. Higher = stronger balance sheet. E.g. 0.35 = 35%"
              field="equity_ratio" value={enrich.equity_ratio} onChange={update} min={0} max={1} step={0.01} suffix="ratio" />
            <SelectInput label="Revenue Stability" hint="Assessment of revenue consistency and predictability"
              field="revenue_stability" value={enrich.revenue_stability} onChange={update}
              options={[{ value: 'stable', label: 'Stable' }, { value: 'volatile', label: 'Volatile' }]} />
            <SelectInput label="Debt Level" hint="Assessment of total debt relative to assets"
              field="debt_level" value={enrich.debt_level} onChange={update}
              options={[{ value: 'low', label: 'Low' }, { value: 'moderate', label: 'Moderate' }, { value: 'high', label: 'High' }]} />
          </Section>

          {/* 03 Operational */}
          <Section title="Operational Resilience" num="03" color="#4A9EE0" completeness={getCompleteness(opFields)}>
            <Toggle label="SOC 2 Certified" hint="Has the entity achieved SOC 2 Type II certification?"
              field="has_soc2" value={enrich.has_soc2} onChange={update} />
            <Toggle label="ISO 27001 Certified" hint="Does the entity hold ISO/IEC 27001 information security certification?"
              field="has_iso27001" value={enrich.has_iso27001} onChange={update} />
            <Toggle label="Crime / Custody Insurance" hint="Does the entity hold insurance covering cyber crime or asset custody?"
              field="has_insurance" value={enrich.has_insurance} onChange={update} />
            <NumberInput label="Major Security Incidents" hint="Number of material security breaches or hacks in entity history"
              field="major_security_incidents" value={enrich.major_security_incidents} onChange={update} min={0} max={10} />
            <NumberInput label="Years in Operation" hint="Years since the entity began commercial operations"
              field="years_in_operation" value={enrich.years_in_operation} onChange={update} min={0} max={30} suffix="yrs" />
          </Section>

          {/* 04 Liquidity */}
          <Section title="Liquidity & Reserves" num="04" color="#9B59B6" completeness={getCompleteness(liqFields)}>
            <NumberInput label="Proof of Reserves Ratio" hint="Verified assets / customer liabilities. 1.0 = fully backed, >1.0 = overcollateralised. E.g. 1.05"
              field="por_ratio" value={enrich.por_ratio} onChange={update} min={0} max={2} step={0.01} suffix="×" />
            <SelectInput label="Reserve Quality" hint="Composition quality of reserves — high = BTC/ETH/stablecoins, low = illiquid altcoins"
              field="reserve_quality" value={enrich.reserve_quality} onChange={update}
              options={[{ value: 'high', label: 'High' }, { value: 'medium', label: 'Medium' }, { value: 'low', label: 'Low' }]} />
            <Toggle label="Withdrawal Restrictions History" hint="Has the entity ever restricted or halted customer withdrawals?"
              field="withdrawal_restrictions_history" value={enrich.withdrawal_restrictions_history} onChange={update} />
          </Section>

          {/* 05 On-Chain */}
          <Section title="On-Chain Health" num="05" color="#2A7C6F" completeness={getCompleteness(chainFields)}>
            <SelectInput label="Reserve Trend (30d)" hint="Direction of on-chain wallet reserves over the past 30 days. Use Nansen or DefiLlama."
              field="onchain_reserve_trend_30d" value={enrich.onchain_reserve_trend_30d} onChange={update}
              options={[
                { value: 'increasing',     label: 'Increasing ↑' },
                { value: 'stable',         label: 'Stable →' },
                { value: 'declining',      label: 'Declining ↓' },
                { value: 'critical_outflow', label: 'Critical Outflow ↓↓' },
              ]} />
            <NumberInput label="TVL Change 30d" hint="DeFi only: % change in Total Value Locked. E.g. 0.15 = +15%, -0.20 = -20%"
              field="tvl_change_30d_pct" value={enrich.tvl_change_30d_pct} onChange={update} min={-1} max={5} step={0.01} suffix="%" />
            <NumberInput label="Smart Contract Audits" hint="DeFi only: number of independent security audits by reputable firms"
              field="audit_count" value={enrich.audit_count} onChange={update} min={0} max={20} />
          </Section>

          {/* 06 Reputation */}
          <Section title="Reputation & Market Signals" num="06" color="#C0392B" completeness={getCompleteness(repFields)}>
            <NumberInput label="Industry Reputation Score" hint="Analyst assessment of industry standing. 0 = severely damaged, 100 = exceptional. NewsAPI sentiment auto-computed separately."
              field="industry_reputation_score" value={enrich.industry_reputation_score} onChange={update} min={0} max={100} suffix="/100" />
            <Toggle label="Leadership Concerns" hint="Are there material concerns about executive leadership quality, stability, or integrity?"
              field="leadership_concerns" value={enrich.leadership_concerns} onChange={update} />
          </Section>

          {/* Analyst notes */}
          <div className="card p-5">
            <div className="label mb-3">Analyst Notes</div>
            <textarea
              value={enrich.analyst_notes ?? ''}
              onChange={e => update('analyst_notes', e.target.value || null)}
              rows={4}
              placeholder="Internal notes on this counterparty — not included in client reports…"
              className="w-full border border-border rounded px-3 py-2 text-sm resize-none focus:outline-none focus:border-ink"
            />
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
      </div>
    </AppLayout>
  )
}
