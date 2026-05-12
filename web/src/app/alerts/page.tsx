'use client'
import { useEffect, useState } from 'react'
import AppLayout from '@/components/layout/AppLayout'
import PageHeader from '@/components/layout/PageHeader'
import { AlertTriangle, CheckCircle, ArrowUpCircle, XCircle } from 'lucide-react'
import toast from 'react-hot-toast'
import dynamic from 'next/dynamic'
const AlertModal = dynamic(() => import('@/components/dashboard/AlertModal'), { ssr: false })

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const H = () => ({ Authorization: `Bearer ${localStorage.getItem('raven_token')}`, 'Content-Type': 'application/json' })

const SEV: Record<string, string> = {
  CRITICAL: 'bg-red text-white',
  HIGH:     'bg-red/10 text-red border border-red/20',
  WARNING:  'bg-amber/10 text-amber border border-amber/20',
  INFO:     'bg-surface-2 text-ink-mid border border-border',
}

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter]   = useState('open')
  const [selectedAlert, setSelectedAlert] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      const r = await fetch(`${API}/api/v1/alerts`, { headers: H() })
      if (r.ok) setAlerts(await r.json())
    } catch {} finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const action = async (alert_id: string, act: string) => {
    try {
      const r = await fetch(`${API}/api/v1/alerts/${alert_id}/action`, {
        method: 'POST', headers: H(),
        body: JSON.stringify({ action: act }),
      })
      if (r.ok) { toast.success(`Alert ${act}d`); load() }
    } catch { toast.error('Action failed') }
  }

  const visible = alerts.filter(a => {
    if (filter === 'open') return ['OPEN','ACKNOWLEDGED','ESCALATED'].includes(a.status)
    if (filter === 'resolved') return ['DISMISSED','RESOLVED'].includes(a.status)
    return true
  }).sort((a, b) => {
    const o = { CRITICAL: 0, HIGH: 1, WARNING: 2, INFO: 3 }
    return (o[a.severity as keyof typeof o] ?? 4) - (o[b.severity as keyof typeof o] ?? 4)
  })

  return (
    <AppLayout>
      <PageHeader
        title="Alerts"
        subtitle={`${alerts.filter(a => a.status === 'OPEN').length} open alerts`}
        action={
          <div className="flex gap-1 border border-border rounded p-0.5">
            {['open','resolved','all'].map(f => (
              <button key={f} onClick={() => setFilter(f)}
                className={`text-xs px-3 py-1 rounded capitalize transition-colors ${filter === f ? 'bg-ink text-surface' : 'text-ink-mid hover:text-ink'}`}>
                {f}
              </button>
            ))}
          </div>
        }
      />

      <div className="p-8">
        {loading ? (
          <div className="card p-8 text-center text-sm text-ink-mid">Loading alerts…</div>
        ) : visible.length === 0 ? (
          <div className="card p-12 text-center">
            <CheckCircle className="w-8 h-8 text-teal mx-auto mb-3" />
            <div className="text-sm font-medium">All clear</div>
            <div className="text-xs text-ink-mid mt-1">No {filter} alerts</div>
          </div>
        ) : (
          <div className="space-y-3">
            {visible.map((a: any) => (
              <div key={a.alert_id} className="card p-5 cursor-pointer hover:shadow-md transition-shadow" onClick={() => setSelectedAlert(a.alert_id)}>
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start gap-3 flex-1">
                    <AlertTriangle className={`w-4 h-4 mt-0.5 flex-shrink-0 ${
                      a.severity === 'CRITICAL' ? 'text-red' :
                      a.severity === 'HIGH' ? 'text-red' :
                      a.severity === 'WARNING' ? 'text-amber' : 'text-ink-mid'
                    }`} />
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <span className={`text-xs font-mono px-1.5 py-0.5 rounded ${SEV[a.severity] ?? SEV.INFO}`}>
                          {a.severity}
                        </span>
                        {(() => { const d = getDimension(a); return d ? (
                          <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded border border-current/20 ${d.color}`}>
                            {d.label}
                          </span>
                        ) : null })()}
                        <span className="font-medium text-sm">{a.title}</span>
                      </div>
                      <div className="text-xs text-ink-mid mb-2">{a.body}</div>
                      <div className="text-xs text-ink-mid font-mono">
                        {a.alert_type} · {new Date(a.triggered_at).toLocaleString('en-CH')} · {a.status}
                      </div>
                    </div>
                  </div>

                  {['OPEN','ACKNOWLEDGED'].includes(a.status) && (
                    <div className="flex gap-2 flex-shrink-0">
                      {a.status === 'OPEN' && (
                        <button onClick={() => action(a.alert_id, 'acknowledge')}
                          className="btn-secondary text-xs flex items-center gap-1 py-1">
                          <CheckCircle className="w-3 h-3" /> Acknowledge
                        </button>
                      )}
                      <button onClick={() => action(a.alert_id, 'escalate')}
                        className="btn-secondary text-xs flex items-center gap-1 py-1 text-amber border-amber/30">
                        <ArrowUpCircle className="w-3 h-3" /> Escalate
                      </button>
                      <button onClick={() => action(a.alert_id, 'dismiss')}
                        className="btn-secondary text-xs flex items-center gap-1 py-1">
                        <XCircle className="w-3 h-3" /> Dismiss
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
      {selectedAlert && (
        <AlertModal
          alertId={selectedAlert}
          onClose={() => setSelectedAlert(null)}
          onAction={load}
        />
      )}
    </AppLayout>
  )
}
