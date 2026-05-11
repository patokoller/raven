'use client'
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import AppLayout from '@/components/layout/AppLayout'
import PageHeader from '@/components/layout/PageHeader'
import { Activity, Plus, RefreshCw, Pencil, Trash2, X, Check } from 'lucide-react'
import Link from 'next/link'
import toast from 'react-hot-toast'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const H = () => ({ Authorization: `Bearer ${localStorage.getItem('raven_token')}`, 'Content-Type': 'application/json' })

const ENTITY_TYPES = ['exchange','custodian','otc_desk','defi_protocol','prime_broker','market_maker','lender']
const JURISDICTIONS = [
  'US','GB','CH','DE','FR','LU','NL','SG','JP','AU','CA','KY','AE','MT','ES','AT','IT','IE','HK','BM',
]

function TierPill({ tier }: { tier?: string }) {
  if (!tier) return <span className="text-ink-mid text-xs">—</span>
  const cls: Record<string,string> = {
    LOW:      'bg-teal/10 text-teal border-teal/20',
    MEDIUM:   'bg-amber/10 text-amber border-amber/20',
    HIGH:     'bg-red/10 text-red border-red/20',
    CRITICAL: 'bg-red text-white border-red',
  }
  return <span className={`text-xs font-mono px-2 py-0.5 rounded border ${cls[tier] ?? ''}`}>{tier}</span>
}

// EditRow - defined at module level to prevent remount
function EditRow({ cp, onSave, onCancel }: { cp: any, onSave: (id: string, data: any) => Promise<void>, onCancel: () => void }) {
  const [displayName, setDisplayName] = useState(cp.display_name ?? '')
  const [entityType, setEntityType]   = useState(cp.entity_type ?? 'exchange')
  const [jurisdiction, setJurisdiction] = useState(cp.jurisdiction ?? '')
  const [regulator, setRegulator]     = useState(cp.regulator ?? '')
  const [saving, setSaving]           = useState(false)

  async function save() {
    setSaving(true)
    await onSave(cp.counterparty_id, { display_name: displayName, entity_type: entityType, jurisdiction, regulator })
    setSaving(false)
  }

  return (
    <tr className="border-t border-amber/30 bg-amber/5">
      <td className="px-5 py-2">
        <input value={displayName} onChange={e => setDisplayName(e.target.value)}
          className="w-full border border-border rounded px-2 py-1 text-sm focus:outline-none focus:border-ink" />
      </td>
      <td className="px-5 py-2">
        <select value={jurisdiction} onChange={e => setJurisdiction(e.target.value)}
          className="w-full border border-border rounded px-2 py-1 text-xs bg-white focus:outline-none">
          <option value="">—</option>
          {JURISDICTIONS.map(j => <option key={j} value={j}>{j}</option>)}
        </select>
      </td>
      <td className="px-5 py-2">
        <input value={regulator} onChange={e => setRegulator(e.target.value)}
          className="w-full border border-border rounded px-2 py-1 text-xs focus:outline-none focus:border-ink" />
      </td>
      <td className="px-5 py-2">
        <select value={entityType} onChange={e => setEntityType(e.target.value)}
          className="w-full border border-border rounded px-2 py-1 text-xs bg-white focus:outline-none">
          {ENTITY_TYPES.map(t => <option key={t} value={t}>{t.replace(/_/g,' ')}</option>)}
        </select>
      </td>
      <td className="px-5 py-2" />
      <td className="px-5 py-2" />
      <td className="px-5 py-2" />
      <td className="px-5 py-2">
        <div className="flex gap-1.5">
          <button onClick={save} disabled={saving}
            className="flex items-center gap-1 px-2 py-1 rounded bg-teal text-white text-xs disabled:opacity-50">
            <Check className="w-3 h-3" />{saving ? '...' : 'Save'}
          </button>
          <button onClick={onCancel}
            className="flex items-center gap-1 px-2 py-1 rounded border border-border text-xs text-ink-mid hover:bg-surface-2">
            <X className="w-3 h-3" />Cancel
          </button>
        </div>
      </td>
    </tr>
  )
}

export default function CounterpartiesPage() {
  const router                          = useRouter()
  const [cps, setCps]                   = useState<any[]>([])
  const [loading, setLoading]           = useState(true)
  const [filter, setFilter]             = useState('')
  const [scoring, setScoring]           = useState(false)
  const [refreshing, setRefreshing]     = useState(false)
  const [editingId, setEditingId]       = useState<string | null>(null)
  const [deletingId, setDeletingId]     = useState<string | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)

  async function load() {
    setLoading(true)
    try {
      const r = await fetch(`${API}/api/v1/counterparties`, { headers: H() })
      if (r.ok) setCps(await r.json())
    } catch {} finally { setLoading(false) }
  }

  useEffect(function() {
    load()
    const interval = setInterval(load, 30000)
    return function() { clearInterval(interval) }
  }, [])

  async function runAll() {
    setScoring(true)
    try {
      await fetch(`${API}/api/v1/agents/score/run-all`, { method: 'POST', headers: H() })
      toast.success('Scoring pipeline started — refresh in 60s')
    } catch { toast.error('Failed') } finally { setScoring(false) }
  }

  async function saveEdit(id: string, data: any) {
    try {
      const r = await fetch(`${API}/api/v1/admin/counterparties/${id}`, {
        method: 'PATCH', headers: H(), body: JSON.stringify(data),
      })
      if (!r.ok) throw new Error((await r.json()).detail)
      setCps(prev => prev.map(cp => cp.counterparty_id === id ? { ...cp, ...data } : cp))
      setEditingId(null)
      toast.success('Counterparty updated')
    } catch (e: any) { toast.error(e.message || 'Update failed') }
  }

  async function doDelete(id: string, name: string) {
    setDeletingId(id)
    try {
      const r = await fetch(`${API}/api/v1/admin/counterparties/${id}`, {
        method: 'DELETE', headers: H(),
      })
      if (!r.ok) throw new Error((await r.json()).detail)
      setCps(prev => prev.filter(cp => cp.counterparty_id !== id))
      setDeleteConfirm(null)
      toast.success(`${name} removed`)
    } catch (e: any) { toast.error(e.message || 'Delete failed') }
    finally { setDeletingId(null) }
  }

  const filtered = cps
    .filter(c =>
      !filter ||
      c.display_name.toLowerCase().includes(filter.toLowerCase()) ||
      c.entity_type.includes(filter.toLowerCase()) ||
      (c.current_risk_tier ?? '').toLowerCase() === filter.toLowerCase()
    )
    .sort((a, b) => {
      const o: Record<string,number> = { CRITICAL:0, HIGH:1, MEDIUM:2, LOW:3 }
      return (o[a.current_risk_tier] ?? 4) - (o[b.current_risk_tier] ?? 4)
    })

  return (
    <AppLayout>
      <PageHeader
        title="Counterparties"
        subtitle={`${cps.length} monitored entities — click any row to view detail and input data`}
        action={
          <div className="flex gap-2">
            <input
              value={filter}
              onChange={e => setFilter(e.target.value)}
              placeholder="Filter by name or tier..."
              className="border border-border rounded px-3 py-1.5 text-xs focus:outline-none focus:border-ink w-48"
            />
            <button onClick={async function() { setRefreshing(true); await load(); setRefreshing(false) }}
              disabled={refreshing}
              className="btn-secondary text-xs flex items-center gap-1.5 disabled:opacity-50">
              <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
              {refreshing ? 'Refreshing...' : 'Refresh'}
            </button>
            <Link href="/counterparties/new">
              <button className="btn-secondary text-xs flex items-center gap-1.5">
                <Plus className="w-3.5 h-3.5" /> Add Counterparty
              </button>
            </Link>
            <button onClick={runAll} disabled={scoring}
              className="btn-primary text-xs flex items-center gap-1.5 disabled:opacity-50">
              <Activity className="w-3.5 h-3.5" />
              {scoring ? 'Running...' : 'Run Scoring'}
            </button>
          </div>
        }
      />

      {/* Delete confirm modal */}
      {deleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-lg shadow-xl p-6 max-w-sm w-full mx-4 space-y-4">
            <div className="text-sm font-medium text-ink">Remove counterparty?</div>
            <div className="text-xs text-ink-mid">
              <span className="font-medium text-ink">{cps.find(c => c.counterparty_id === deleteConfirm)?.display_name}</span> will be
              removed from the registry. This cannot be undone.
            </div>
            <div className="flex gap-2 justify-end">
              <button onClick={function() { setDeleteConfirm(null) }}
                className="btn-secondary text-xs">Cancel</button>
              <button
                onClick={function() {
                  const cp = cps.find(c => c.counterparty_id === deleteConfirm)
                  if (cp) doDelete(cp.counterparty_id, cp.display_name)
                }}
                disabled={deletingId === deleteConfirm}
                className="px-3 py-1.5 rounded bg-red text-white text-xs font-medium disabled:opacity-50">
                {deletingId === deleteConfirm ? 'Removing...' : 'Remove'}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="p-8">
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-surface-2">
              <tr>
                {['Entity','Jurisdiction','Regulator','Type','Score','Tier','Last Scored',''].map(h => (
                  <th key={h} className="label text-left px-5 py-3 font-normal">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading
                ? Array.from({ length: 8 }).map(function(_, i) {
                    return (
                      <tr key={i} className="border-t border-border">
                        <td colSpan={8} className="px-5 py-3">
                          <div className="h-3 bg-surface-2 rounded animate-pulse" />
                        </td>
                      </tr>
                    )
                  })
                : filtered.map(function(cp: any) {
                    if (editingId === cp.counterparty_id) {
                      return <EditRow key={cp.counterparty_id} cp={cp} onSave={saveEdit} onCancel={function() { setEditingId(null) }} />
                    }
                    return (
                      <tr key={cp.counterparty_id}
                        onClick={function() { router.push(`/counterparties/${cp.counterparty_id}`) }}
                        className="border-t border-border hover:bg-amber/5 cursor-pointer transition-colors group">
                        <td className="px-5 py-3">
                          <div className="font-medium">{cp.display_name}</div>
                          <div className="text-xs text-ink-mid font-mono">{cp.slug}</div>
                        </td>
                        <td className="px-5 py-3 text-xs text-ink-mid">{cp.jurisdiction ?? '—'}</td>
                        <td className="px-5 py-3 text-xs text-ink-mid">{cp.regulator ?? '—'}</td>
                        <td className="px-5 py-3 text-xs font-mono text-ink-mid">{cp.entity_type}</td>
                        <td className="px-5 py-3">
                          {cp.composite_score != null ? (
                            <div className="flex items-center gap-2">
                              <div className="w-20 h-1.5 bg-surface-2 rounded-full overflow-hidden">
                                <div className="h-full rounded-full" style={{
                                  width: `${cp.composite_score}%`,
                                  background: cp.composite_score >= 75 ? '#2A7C6F' : cp.composite_score >= 55 ? '#E67E22' : '#C0392B',
                                }} />
                              </div>
                              <span className="text-xs font-mono">{cp.composite_score.toFixed(0)}</span>
                            </div>
                          ) : <span className="text-ink-mid text-xs">—</span>}
                        </td>
                        <td className="px-5 py-3"><TierPill tier={cp.current_risk_tier} /></td>
                        <td className="px-5 py-3 text-xs text-ink-mid">
                          {cp.scored_at ? new Date(cp.scored_at).toLocaleDateString('en-CH') : '—'}
                        </td>
                        <td className="px-5 py-3">
                          <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity"
                            onClick={function(e) { e.stopPropagation() }}>
                            <button
                              onClick={function(e) { e.stopPropagation(); setEditingId(cp.counterparty_id) }}
                              className="p-1.5 rounded hover:bg-surface-2 text-ink-mid hover:text-ink transition-colors"
                              title="Edit">
                              <Pencil className="w-3.5 h-3.5" />
                            </button>
                            <button
                              onClick={function(e) { e.stopPropagation(); setDeleteConfirm(cp.counterparty_id) }}
                              className="p-1.5 rounded hover:bg-red/10 text-ink-mid hover:text-red transition-colors"
                              title="Delete">
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
            </tbody>
          </table>
        </div>
      </div>
    </AppLayout>
  )
}
