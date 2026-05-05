'use client'
import { useEffect, useState } from 'react'
import {
  X, AlertTriangle, CheckCircle, ArrowUpCircle,
  XCircle, Sparkles, Clock, RefreshCw
} from 'lucide-react'
import toast from 'react-hot-toast'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const H = () => ({ Authorization: `Bearer ${localStorage.getItem('raven_token')}`, 'Content-Type': 'application/json' })

const SEV_COLOR: Record<string, string> = {
  CRITICAL: 'text-red bg-red/5 border-red/20',
  HIGH:     'text-red bg-red/5 border-red/10',
  WARNING:  'text-amber bg-amber/5 border-amber/20',
  INFO:     'text-ink-mid bg-surface-2 border-border',
}

const DIM_COLORS: Record<string, string> = {
  regulatory:  '#C9A84C',
  financial:   '#3AA896',
  operational: '#4A9EE0',
  liquidity:   '#9B59B6',
  onchain:     '#2A7C6F',
  reputation:  '#C0392B',
}

function ScoreBar({ label, score, color }: { label: string; score?: number; color: string }) {
  if (score == null) return null
  return (
    <div className="flex items-center gap-3">
      <div className="text-xs text-ink-mid w-24 flex-shrink-0">{label}</div>
      <div className="flex-1 h-1.5 bg-surface-2 rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all"
          style={{ width: `${score}%`, background: color }} />
      </div>
      <div className="text-xs font-mono w-7 text-right" style={{ color }}>
        {score.toFixed(0)}
      </div>
    </div>
  )
}

interface AlertModalProps {
  alertId: string
  onClose: () => void
  onAction: () => void
}

export default function AlertModal({ alertId, onClose, onAction }: AlertModalProps) {
  const [alert, setAlert]           = useState<any>(null)
  const [explanation, setExplanation] = useState<any>(null)
  const [loadingAlert, setLoadingAlert]       = useState(true)
  const [loadingExplain, setLoadingExplain]   = useState(false)
  const [actioning, setActioning]   = useState<string | null>(null)

  useEffect(() => {
    const load = async () => {
      setLoadingAlert(true)
      try {
        const r = await fetch(`${API}/api/v1/alerts/${alertId}`, { headers: H() })
        if (r.ok) setAlert(await r.json())
      } catch {}
      finally { setLoadingAlert(false) }
    }
    load()
  }, [alertId])

  const getExplanation = async () => {
    setLoadingExplain(true)
    try {
      const r = await fetch(`${API}/api/v1/alerts/${alertId}/explain`, {
        method: 'POST', headers: H()
      })
      if (r.ok) setExplanation(await r.json())
      else toast.error('Failed to generate explanation')
    } catch { toast.error('Failed to generate explanation') }
    finally { setLoadingExplain(false) }
  }

  const doAction = async (action: string) => {
    setActioning(action)
    try {
      const r = await fetch(`${API}/api/v1/alerts/${alertId}/action`, {
        method: 'POST', headers: H(),
        body: JSON.stringify({ action }),
      })
      if (r.ok) {
        toast.success(`Alert ${action}d`)
        onAction()
        onClose()
      }
    } catch { toast.error('Action failed') }
    finally { setActioning(null) }
  }

  const score = alert?.counterparty?.counterparty_scores

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="absolute inset-0 bg-ink/40 backdrop-blur-sm" onClick={onClose} />

      <div className="relative bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[85vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className={`px-6 py-4 border-b border-border flex items-start justify-between ${
          alert?.severity === 'CRITICAL' ? 'bg-red/5' : ''
        }`}>
          <div className="flex items-start gap-3 flex-1 min-w-0">
            <AlertTriangle className={`w-5 h-5 mt-0.5 flex-shrink-0 ${
              alert?.severity === 'CRITICAL' ? 'text-red' :
              alert?.severity === 'HIGH' ? 'text-red' : 'text-amber'
            }`} />
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className={`text-xs font-mono px-2 py-0.5 rounded border ${SEV_COLOR[alert?.severity] ?? SEV_COLOR.INFO}`}>
                  {alert?.severity}
                </span>
                {alert?.counterparty?.entity_type && (
                  <span className="text-xs font-mono text-ink-mid">{alert.counterparty.entity_type}</span>
                )}
              </div>
              <h2 className="font-medium text-ink mt-1 leading-snug">{alert?.title ?? 'Loading…'}</h2>
              <p className="text-xs text-ink-mid mt-0.5">
                {alert?.triggered_at ? new Date(alert.triggered_at).toLocaleString('en-CH') : ''}
                {alert?.counterparty?.jurisdiction ? ` · ${alert.counterparty.jurisdiction}` : ''}
                {alert?.counterparty?.regulator ? ` · ${alert.counterparty.regulator}` : ''}
              </p>
            </div>
          </div>
          <button onClick={onClose} className="text-ink-mid hover:text-ink ml-3 flex-shrink-0">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-5">
          {loadingAlert ? (
            <div className="text-sm text-ink-mid text-center py-8">Loading alert details…</div>
          ) : (
            <>
              {/* Alert body */}
              <div>
                <div className="label mb-2">Alert Details</div>
                <p className="text-sm text-ink-mid leading-relaxed">{alert?.body}</p>
                {alert?.metadata?.delta && (
                  <div className="mt-3 flex items-center gap-3">
                    <div className="bg-surface-2 rounded px-3 py-2 text-center">
                      <div className="text-xs text-ink-mid mb-0.5">Previous Score</div>
                      <div className="text-lg font-light font-mono">{alert.metadata.old_score?.toFixed(0)}</div>
                    </div>
                    <div className="text-red font-mono text-sm">→ −{alert.metadata.delta?.toFixed(1)}</div>
                    <div className="bg-red/10 rounded px-3 py-2 text-center border border-red/20">
                      <div className="text-xs text-red mb-0.5">New Score</div>
                      <div className="text-lg font-light font-mono text-red">{alert.metadata.new_score?.toFixed(0)}</div>
                    </div>
                  </div>
                )}
              </div>

              {/* Score breakdown */}
              {score && (
                <div>
                  <div className="label mb-3">Score Breakdown</div>
                  <div className="space-y-1.5">
                    {[
                      ['Regulatory',  'regulatory_score',  DIM_COLORS.regulatory],
                      ['Financial',   'financial_score',   DIM_COLORS.financial],
                      ['Operational', 'operational_score', DIM_COLORS.operational],
                      ['Liquidity',   'liquidity_score',   DIM_COLORS.liquidity],
                      ['On-Chain',    'onchain_score',     DIM_COLORS.onchain],
                      ['Reputation',  'reputation_score',  DIM_COLORS.reputation],
                    ].map(([label, key, color]) => (
                      <ScoreBar key={key} label={label as string} score={score[key as string]} color={color as string} />
                    ))}
                  </div>
                  <div className="mt-3 pt-3 border-t border-border flex items-center justify-between">
                    <span className="text-xs text-ink-mid">Composite Score</span>
                    <span className="text-xl font-light font-mono">
                      {score.composite_score?.toFixed(0)}/100
                    </span>
                  </div>
                </div>
              )}

              {/* Risk flags */}
              {alert?.metadata?.flags?.length > 0 && (
                <div>
                  <div className="label mb-2">Risk Flags</div>
                  <div className="flex flex-wrap gap-1.5">
                    {alert.metadata.flags.map((flag: string) => (
                      <span key={flag}
                        className="text-xs font-mono bg-red/5 text-red border border-red/15 px-2 py-0.5 rounded">
                        {flag.replace(/_/g, ' ')}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* AI Explanation */}
              <div className="border-t border-border pt-5">
                {!explanation ? (
                  <button onClick={getExplanation} disabled={loadingExplain}
                    className="w-full btn-secondary flex items-center justify-center gap-2 py-2.5 disabled:opacity-50">
                    {loadingExplain
                      ? <><RefreshCw className="w-3.5 h-3.5 animate-spin" /> Generating analysis…</>
                      : <><Sparkles className="w-3.5 h-3.5 text-gold" /> Explain this alert with AI</>
                    }
                  </button>
                ) : (
                  <div className="space-y-4">
                    <div className="flex items-center gap-2">
                      <Sparkles className="w-3.5 h-3.5 text-gold" />
                      <span className="label">AI Analysis</span>
                    </div>

                    {explanation.headline && (
                      <p className="text-sm font-medium text-ink leading-snug border-l-2 border-gold pl-3">
                        {explanation.headline}
                      </p>
                    )}

                    {explanation.explanation && (
                      <p className="text-sm text-ink-mid leading-relaxed whitespace-pre-line">
                        {explanation.explanation}
                      </p>
                    )}

                    {explanation.risk_drivers?.length > 0 && (
                      <div>
                        <div className="label mb-2">Risk Drivers</div>
                        <ul className="space-y-1">
                          {explanation.risk_drivers.map((d: string, i: number) => (
                            <li key={i} className="text-xs text-ink-mid flex items-start gap-2">
                              <span className="text-red mt-0.5 flex-shrink-0">›</span>{d}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {explanation.recommended_actions?.length > 0 && (
                      <div>
                        <div className="label mb-2">Recommended Actions</div>
                        <div className="space-y-2">
                          {explanation.recommended_actions.map((a: any, i: number) => (
                            <div key={i} className="flex items-start gap-2 text-xs">
                              <span className={`flex-shrink-0 font-mono text-[10px] px-1.5 py-0.5 rounded mt-0.5 ${
                                a.priority === 'HIGH'
                                  ? 'bg-red/10 text-red'
                                  : 'bg-amber/10 text-amber'
                              }`}>{a.priority}</span>
                              <div>
                                <span className="text-ink font-medium">{a.action}</span>
                                {a.timeline && <span className="text-ink-mid ml-1">— {a.timeline}</span>}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {explanation.context && (
                      <div className="bg-surface-2 rounded p-3">
                        <div className="label mb-1">Market Context</div>
                        <p className="text-xs text-ink-mid leading-relaxed">{explanation.context}</p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </>
          )}
        </div>

        {/* Footer actions */}
        {alert && ['OPEN', 'ACKNOWLEDGED'].includes(alert.status) && (
          <div className="px-6 py-4 border-t border-border bg-surface-2/50 flex items-center justify-between">
            <span className="text-xs text-ink-mid">Status: <span className="font-mono">{alert.status}</span></span>
            <div className="flex gap-2">
              {alert.status === 'OPEN' && (
                <button onClick={() => doAction('acknowledge')} disabled={!!actioning}
                  className="btn-secondary text-xs flex items-center gap-1.5 py-1.5 disabled:opacity-50">
                  <CheckCircle className="w-3.5 h-3.5" />
                  {actioning === 'acknowledge' ? 'Working…' : 'Acknowledge'}
                </button>
              )}
              <button onClick={() => doAction('escalate')} disabled={!!actioning}
                className="btn-secondary text-xs flex items-center gap-1.5 py-1.5 text-amber disabled:opacity-50">
                <ArrowUpCircle className="w-3.5 h-3.5" />
                {actioning === 'escalate' ? 'Working…' : 'Escalate'}
              </button>
              <button onClick={() => doAction('dismiss')} disabled={!!actioning}
                className="btn-secondary text-xs flex items-center gap-1.5 py-1.5 disabled:opacity-50">
                <XCircle className="w-3.5 h-3.5" />
                {actioning === 'dismiss' ? 'Working…' : 'Dismiss'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
