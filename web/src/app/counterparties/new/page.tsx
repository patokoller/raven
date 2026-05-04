'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import AppLayout from '@/components/layout/AppLayout'
import PageHeader from '@/components/layout/PageHeader'
import { Plus } from 'lucide-react'
import toast from 'react-hot-toast'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const H = () => ({ Authorization: `Bearer ${localStorage.getItem('raven_token')}`, 'Content-Type': 'application/json' })

const ENTITY_TYPES = ['exchange','custodian','otc_desk','defi_protocol','prime_broker','market_maker','lender']
const JURISDICTIONS = [
  {code:'US',label:'United States'},{code:'GB',label:'United Kingdom'},
  {code:'CH',label:'Switzerland'},{code:'DE',label:'Germany'},
  {code:'FR',label:'France'},{code:'LU',label:'Luxembourg'},
  {code:'NL',label:'Netherlands'},{code:'SG',label:'Singapore'},
  {code:'JP',label:'Japan'},{code:'AU',label:'Australia'},
  {code:'CA',label:'Canada'},{code:'KY',label:'Cayman Islands'},
  {code:'AE',label:'United Arab Emirates'},{code:'MT',label:'Malta'},
  {code:'ES',label:'Spain'},{code:'AT',label:'Austria'},
]

export default function AddCounterpartyPage() {
  const router = useRouter()
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({
    display_name: '',
    legal_name:   '',
    slug:         '',
    entity_type:  'exchange',
    jurisdiction: '',
    regulator:    '',
    license_number: '',
    website:      '',
    notes:        '',
    ticker:       '',
  })

  const set = (k: string, v: string) => {
    setForm(prev => {
      const next = { ...prev, [k]: v }
      // Auto-generate slug from display_name
      if (k === 'display_name') {
        next.slug = v.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
      }
      return next
    })
  }

  const submit = async () => {
    if (!form.display_name || !form.entity_type || !form.slug) {
      return toast.error('Display name, type, and slug are required')
    }
    setSaving(true)
    try {
      const body: any = { ...form }
      if (form.ticker) body.external_ids = { ticker: form.ticker }
      delete body.ticker

      const r = await fetch(`${API}/api/v1/admin/counterparties`, {
        method: 'POST', headers: H(),
        body: JSON.stringify(body),
      })
      const d = await r.json()
      if (!r.ok) throw new Error(d.detail)
      toast.success(`${form.display_name} added to registry`)
      router.push(`/counterparties/${d.counterparty.counterparty_id}`)
    } catch (e: any) { toast.error(e.message) }
    finally { setSaving(false) }
  }

  const Field = ({ label, field, placeholder, hint }: any) => (
    <div>
      <label className="label mb-1.5 block">{label}</label>
      <input value={(form as any)[field]} onChange={e => set(field, e.target.value)}
        placeholder={placeholder}
        className="w-full border border-border rounded px-3 py-2 text-sm focus:outline-none focus:border-ink" />
      {hint && <div className="text-xs text-ink-mid mt-1">{hint}</div>}
    </div>
  )

  return (
    <AppLayout>
      <PageHeader title="Add Counterparty" subtitle="Add a new entity to the risk monitoring registry"
        action={
          <button onClick={submit} disabled={saving}
            className="btn-primary text-xs flex items-center gap-1.5 disabled:opacity-50">
            <Plus className="w-3.5 h-3.5" />
            {saving ? 'Adding…' : 'Add to Registry'}
          </button>
        }
      />

      <div className="p-8 max-w-2xl">
        <div className="card p-6 space-y-5">
          <div className="label mb-2">Entity Details</div>

          <Field label="Display Name *" field="display_name" placeholder="e.g. Coinbase" />
          <Field label="Legal Name" field="legal_name" placeholder="e.g. Coinbase Global, Inc." />

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label mb-1.5 block">Slug * (auto-generated)</label>
              <input value={form.slug} onChange={e => set('slug', e.target.value)}
                placeholder="e.g. coinbase"
                className="w-full border border-border rounded px-3 py-2 text-sm font-mono focus:outline-none focus:border-ink" />
              <div className="text-xs text-ink-mid mt-1">Unique identifier — lowercase, hyphens only</div>
            </div>
            <div>
              <label className="label mb-1.5 block">Entity Type *</label>
              <select value={form.entity_type} onChange={e => set('entity_type', e.target.value)}
                className="w-full border border-border rounded px-3 py-2 text-sm bg-white focus:outline-none focus:border-ink">
                {ENTITY_TYPES.map(t => <option key={t} value={t}>{t.replace('_',' ')}</option>)}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label mb-1.5 block">Jurisdiction</label>
              <select value={form.jurisdiction} onChange={e => set('jurisdiction', e.target.value)}
                className="w-full border border-border rounded px-3 py-2 text-sm bg-white focus:outline-none focus:border-ink">
                <option value="">Unknown</option>
                {JURISDICTIONS.map(j => <option key={j.code} value={j.code}>{j.code} — {j.label}</option>)}
              </select>
            </div>
            <Field label="Regulator" field="regulator" placeholder="e.g. FCA, FINMA, SEC" />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <Field label="License Number" field="license_number" placeholder="Optional" />
            <Field label="Stock Ticker" field="ticker" placeholder="e.g. COIN (if listed)" />
          </div>

          <Field label="Website" field="website" placeholder="https://..." />

          <div>
            <label className="label mb-1.5 block">Notes</label>
            <textarea value={form.notes} onChange={e => set('notes', e.target.value)}
              rows={3} placeholder="Brief description, key facts, risk context…"
              className="w-full border border-border rounded px-3 py-2 text-sm resize-none focus:outline-none focus:border-ink" />
          </div>

          <div className="pt-2 flex items-center justify-between border-t border-border">
            <div className="text-xs text-ink-mid">
              After adding, you'll be taken to the detail page where you can run AI research to populate scoring data.
            </div>
            <button onClick={submit} disabled={saving}
              className="btn-primary text-sm flex items-center gap-1.5 disabled:opacity-50">
              <Plus className="w-4 h-4" />
              {saving ? 'Adding…' : 'Add to Registry'}
            </button>
          </div>
        </div>
      </div>
    </AppLayout>
  )
}
