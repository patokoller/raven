'use client'
import { ChevronRight, Zap } from 'lucide-react'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const H = () => ({ Authorization: 'Bearer ' + localStorage.getItem('raven_token'), 'Content-Type': 'application/json' })

export function pollForAiResult(portfolioId: string, setter: any, setRunning: any) {
  let remaining = 12
  const pollId = setInterval(function() {
    remaining = remaining - 1
    fetch(API + '/api/v1/portfolios/' + portfolioId + '/ai-analysis', { headers: H() })
      .then(function(r: any) { return r.json() })
      .then(function(data: any) {
        if (data && data.status === 'ready' && data.analysis) {
          setter(data.analysis)
          setRunning(false)
          clearInterval(pollId)
        }
      })
      .catch(function() {})
    if (!remaining) { clearInterval(pollId); setRunning(false) }
  }, 5000)
}

function RiskBadge({ level }: { level: string }) {
  const cls = level === 'LOW' ? 'bg-teal/20 text-teal border-teal/30'
    : level === 'MEDIUM' ? 'bg-amber/20 text-amber border-amber/30'
    : level === 'HIGH' ? 'bg-orange-500/20 text-orange-500 border-orange-500/30'
    : 'bg-red/20 text-red border-red/30'
  return <span className={'text-xs font-mono px-2.5 py-1 rounded border ' + cls}>{level} RISK</span>
}

function PriorityColor({ priority }: { priority: string }) {
  if (priority === 'IMMEDIATE') return 'text-red'
  if (priority === 'SHORT_TERM') return 'text-amber'
  return 'text-ink-mid'
}

function BorderColor({ priority }: { priority: string }) {
  if (priority === 'IMMEDIATE') return 'border-red bg-red/5'
  if (priority === 'SHORT_TERM') return 'border-amber bg-amber/5'
  return 'border-border bg-surface-2/30'
}

export default function AiAnalysisPanel({ aiResult, aiRunning }: { aiResult: any, aiRunning: boolean }) {
  if (!aiRunning && !aiResult) return null

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <div className="px-6 py-4 bg-ink flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Zap className="w-4 h-4 text-gold" />
          <span className="text-sm font-medium text-white">AI Risk Analysis</span>
          {aiResult && aiResult.generated_at && (
            <span className="text-xs text-white/40 font-mono">
              {new Date(aiResult.generated_at).toLocaleString()}
            </span>
          )}
        </div>
        {aiResult && aiResult.overall_assessment && (
          <RiskBadge level={aiResult.overall_assessment} />
        )}
      </div>

      {aiRunning && !aiResult && (
        <div className="px-6 py-10 text-center">
          <Zap className="w-6 h-6 text-ink-mid mx-auto mb-3 animate-pulse" />
          <p className="text-sm text-ink font-medium">Analysing portfolio...</p>
          <p className="text-xs text-ink-mid mt-1">Claude is reviewing your positions, stress tests and counterparty scores. Ready in 20-30s.</p>
        </div>
      )}

      {aiResult && (
        <div className="divide-y divide-border">
          <div className="px-6 py-5">
            <p className="text-sm text-ink leading-relaxed">{aiResult.risk_verdict}</p>
          </div>

          <div className="grid grid-cols-2 divide-x divide-border">
            <div className="px-6 py-5">
              <div className="text-[10px] font-mono text-ink-mid uppercase tracking-widest mb-3">Key Risk Drivers</div>
              <div className="space-y-3">
                {(aiResult.key_risk_drivers || []).map(function(d: any, i: number) {
                  const badgeCls = d.severity === 'HIGH' ? 'bg-red/10 text-red' : 'bg-amber/10 text-amber'
                  return (
                    <div key={i} className="flex gap-3">
                      <div className={'w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 text-[10px] font-bold mt-0.5 ' + badgeCls}>{i + 1}</div>
                      <div>
                        <div className="text-xs font-medium">{d.driver}</div>
                        <div className="text-xs text-ink-mid mt-0.5 leading-relaxed">{d.description}</div>
                        {d.chf_at_risk > 0 && (
                          <div className="text-[10px] font-mono text-red mt-1">
                            CHF {Number(d.chf_at_risk).toLocaleString('de-CH', { maximumFractionDigits: 0 })} at risk
                          </div>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>

            <div className="px-6 py-5">
              <div className="text-[10px] font-mono text-ink-mid uppercase tracking-widest mb-3">Action Items</div>
              <div className="space-y-2">
                {(aiResult.action_items || []).map(function(a: any, i: number) {
                  const borderCls = a.priority === 'IMMEDIATE' ? 'border-red bg-red/5'
                    : a.priority === 'SHORT_TERM' ? 'border-amber bg-amber/5'
                    : 'border-border bg-surface-2/30'
                  const textCls = a.priority === 'IMMEDIATE' ? 'text-red'
                    : a.priority === 'SHORT_TERM' ? 'text-amber'
                    : 'text-ink-mid'
                  return (
                    <div key={i} className={'p-3 rounded border-l-2 ' + borderCls}>
                      <div className={'text-[10px] font-mono mb-0.5 ' + textCls}>{a.priority} - {a.deadline}</div>
                      <div className="text-xs font-medium">{a.action}</div>
                      <div className="text-xs text-ink-mid mt-0.5">{a.rationale}</div>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>

          {(aiResult.rebalancing_suggestions || []).length !== 0 && (
            <div className="px-6 py-5">
              <div className="text-[10px] font-mono text-ink-mid uppercase tracking-widest mb-3">Rebalancing Suggestions</div>
              <div className="space-y-2">
                {(aiResult.rebalancing_suggestions || []).map(function(r: any, i: number) {
                  return (
                    <div key={i} className="flex items-center gap-3 p-2.5 bg-surface-2/50 rounded text-xs">
                      <span className="font-medium">{r.from_counterparty}</span>
                      <ChevronRight className="w-3 h-3 text-ink-mid flex-shrink-0" />
                      <span className="font-medium text-teal">{r.to_counterparty}</span>
                      <span className="font-mono">CHF {Number(r.amount_chf).toLocaleString('de-CH', { maximumFractionDigits: 0 })}</span>
                      <span className="text-ink-mid flex-1 min-w-0 truncate">{r.rationale}</span>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {aiResult.client_communication && (
            <div className="px-6 py-5">
              <div className="text-[10px] font-mono text-ink-mid uppercase tracking-widest mb-3">Client Communication Draft</div>
              <div className="bg-surface-2/50 rounded p-4 border border-border">
                <p className="text-xs text-ink leading-relaxed whitespace-pre-line">{aiResult.client_communication}</p>
              </div>
            </div>
          )}

          {aiResult.analyst_notes && (
            <div className="px-6 py-5 bg-surface-2/20">
              <div className="text-[10px] font-mono text-ink-mid uppercase tracking-widest mb-2">Analyst Notes</div>
              <p className="text-xs text-ink-mid leading-relaxed">{aiResult.analyst_notes}</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
