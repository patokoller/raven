'use client'
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import AppLayout from '@/components/layout/AppLayout'
import PageHeader from '@/components/layout/PageHeader'
import { Activity, Plus, RefreshCw } from 'lucide-react'
import Link from 'next/link'
import toast from 'react-hot-toast'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const H = () => ({ Authorization: `Bearer ${localStorage.getItem('raven_token')}`, 'Content-Type': 'application/json' })

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

export default function CounterpartiesPage() {
  const router            = useRouter()
  const [cps, setCps]     = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter]   = useState('')
  const [scoring, setScoring] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const r = await fetch(`${API}/api/v1/counterparties`, { headers: H() })
      if (r.ok) setCps(await r.json())
    } catch {} finally { setLoading(false) }
  }

  useEffect(() => {
    load()
    // Auto-refresh every 30s to pick up new scores from background rescoring
    const interval = setInterval(load, 30000)
    return () => clearInterval(interval)
  }, [])

  const runAll = async () => {
    setScoring(true)
    try {
      await fetch(`${API}/api/v1/agents/score/run-all`, { method: 'POST', headers: H() })
      toast.success('Scoring pipeline started — refresh in 60s')
    } catch { toast.error('Failed') } finally { setScoring(false) }
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
              placeholder="Filter by name or tier…"
              className="border border-border rounded px-3 py-1.5 text-xs focus:outline-none focus:border-ink w-48"
            />
            <button onClick={load} className="btn-secondary text-xs flex items-center gap-1.5">
              <RefreshCw className="w-3.5 h-3.5" /> Refresh
            </button>
            <Link href="/counterparties/new">
              <button className="btn-secondary text-xs flex items-center gap-1.5">
                <Plus className="w-3.5 h-3.5" /> Add Counterparty
              </button>
            </Link>
            <button
              onClick={runAll}
              disabled={scoring}
              className="btn-primary text-xs flex items-center gap-1.5 disabled:opacity-50"
            >
              <Activity className="w-3.5 h-3.5" />
              {scoring ? 'Running…' : 'Run Scoring'}
            </button>
          </div>
        }
      />

      <div className="p-8">
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-surface-2">
              <tr>
                {['Entity', 'Jurisdiction', 'Regulator', 'Type', 'Score', 'Tier', 'Last Scored'].map(h => (
                  <th key={h} className="label text-left px-5 py-3 font-normal">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading
                ? Array.from({ length: 8 }).map((_, i) => (
                    <tr key={i} className="border-t border-border">
                      <td colSpan={7} className="px-5 py-3">
                        <div className="h-3 bg-surface-2 rounded animate-pulse" />
                      </td>
                    </tr>
                  ))
                : filtered.map((cp: any) => (
                    <tr
                      key={cp.counterparty_id}
                      onClick={() => router.push(`/counterparties/${cp.counterparty_id}`)}
                      className="border-t border-border hover:bg-amber/5 cursor-pointer transition-colors"
                    >
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
                              <div
                                className="h-full rounded-full"
                                style={{
                                  width: `${cp.composite_score}%`,
                                  background: cp.composite_score >= 75 ? '#2A7C6F'
                                    : cp.composite_score >= 55 ? '#E67E22' : '#C0392B',
                                }}
                              />
                            </div>
                            <span className="text-xs font-mono">{cp.composite_score.toFixed(0)}</span>
                          </div>
                        ) : (
                          <span className="text-ink-mid text-xs">—</span>
                        )}
                      </td>
                      <td className="px-5 py-3"><TierPill tier={cp.current_risk_tier} /></td>
                      <td className="px-5 py-3 text-xs text-ink-mid">
                        {cp.scored_at ? new Date(cp.scored_at).toLocaleDateString('en-CH') : '—'}
                      </td>
                    </tr>
                  ))}
            </tbody>
          </table>
        </div>
      </div>
    </AppLayout>
  )
}
