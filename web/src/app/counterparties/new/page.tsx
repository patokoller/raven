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
  {code:'IT',label:'Italy'},{code:'IE',label:'Ireland'},
  {code:'HK',label:'Hong Kong'},{code:'BM',label:'Bermuda'},
]

// Field MUST be defined outside the page component to prevent remount on every keystroke
function Field({ label, value, onChange, placeholder, hint, mono }: {
  label: string
  value: string
  onChange: (v: string) => void
  placeholder?: string
  hint?: string
  mono?: boolean
}) {
  return (
    <div>
      <label className="label mb-1.5 block">{label}</label>
      <input
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className={`w-full border border-border rounded px-3 py-2 text-sm focus:outline-none focus:border-ink ${mono ? 'font-mono' : ''}`}
      />
      {hint && <div className="text-xs text-ink-mid mt-1">{hint}</div>}
    </div>
  )
}

export default function AddCounterpartyPage() {
  const router = useRouter()
  const [saving, setSaving] = useState(false)
  const [displayName, setDisplayName] = useState('')
  const [legalName, setLegalName]     = useState('')
  const [slug, setSlug]               = useState('')
  const [entityType, setEntityType]   = useState('exchange')
  const [jurisdiction, setJurisdiction] = useState('')
  const [regulator, setRegulator]     = useState('')
  const [licenseNum, setLicenseNum]   = useState('')
  const [website, setWebsite]         = useState('')
  const [notes, setNotes]             = useState('')
  const [ticker, setTicker]           = useState('')

  function handleDisplayName(v: string) {
    setDisplayName(v)
    setSlug(v.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, ''))
  }

  async function submit() {
    if (!displayName || !entityType || !slug) {
      return toast.error('Display name, type, and slug are required')
    }
    setSaving(true)
    try {
      const body: any = {
        display_name: displayName,
        legal_name:   legalName,
        slug,
        entity_type:  entityType,
        jurisdiction,
        regulator,
        license_number: licenseNum,
        website,
        notes,
      }
      if (ticker) body.external_ids = { ticker }

      const r = await fetch(`${API}/api/v1/admin/counterparties`, {
        method: 'POST', headers: H(),
        body: JSON.stringify(body),
      })
      const d = await r.json()
      if (!r.ok) throw new Error(d.detail)
      toast.success(`${displayName} added to registry`)
      router.push(`/counterparties/${d.counterparty.counterparty_id}`)
    } catch (e: any) { toast.error(e.message) }
    finally { setSaving(false) }
  }

  return (
    <AppLayout>
      <PageHeader title="Add Counterparty" subtitle="Add a new entity to the risk monitoring registry"
        action={
          <button onClick={submit} disabled={saving}
            className="btn-primary text-xs flex items-center gap-1.5 disabled:opacity-50">
            <Plus className="w-3.5 h-3.5" />
            {saving ? 'Adding...' : 'Add to Registry'}
          </button>
        }
      />

      <div className="p-8 max-w-2xl">
        <div className="card p-6 space-y-5">
          <div className="label mb-2">Entity Details</div>

          <Field label="Display Name *" value={displayName} onChange={handleDisplayName} placeholder="e.g. Coinbase" />
          <Field label="Legal Name" value={legalName} onChange={setLegalName} placeholder="e.g. Coinbase Global, Inc." />

          <div className="grid grid-cols-2 gap-4">
            <Field
              label="Slug * (auto-generated)"
              value={slug}
              onChange={setSlug}
              placeholder="e.g. coinbase"
              hint="Unique identifier — lowercase, hyphens only"
              mono
            />
            <div>
              <label className="label mb-1.5 block">Entity Type *</label>
              <select value={entityType} onChange={e => setEntityType(e.target.value)}
                className="w-full border border-border rounded px-3 py-2 text-sm bg-white focus:outline-none focus:border-ink">
                {ENTITY_TYPES.map(t => <option key={t} value={t}>{t.replace(/_/g,' ')}</option>)}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label mb-1.5 block">Jurisdiction</label>
              <select value={jurisdiction} onChange={e => setJurisdiction(e.target.value)}
                className="w-full border border-border rounded px-3 py-2 text-sm bg-white focus:outline-none focus:border-ink">
                <option value="">Unknown</option>
                {JURISDICTIONS.map(j => <option key={j.code} value={j.code}>{j.code} — {j.label}</option>)}
              </select>
            </div>
            <Field label="Regulator" value={regulator} onChange={setRegulator} placeholder="e.g. FCA, FINMA, SEC" />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <Field label="License Number" value={licenseNum} onChange={setLicenseNum} placeholder="Optional" />
            <Field label="Stock Ticker" value={ticker} onChange={setTicker} placeholder="e.g. COIN (if listed)" />
          </div>

          <Field label="Website" value={website} onChange={setWebsite} placeholder="https://..." />

          <div>
            <label className="label mb-1.5 block">Notes</label>
            <textarea value={notes} onChange={e => setNotes(e.target.value)}
              rows={3} placeholder="Brief description, key facts, risk context..."
              className="w-full border border-border rounded px-3 py-2 text-sm resize-none focus:outline-none focus:border-ink" />
          </div>

          <div className="pt-2 flex items-center justify-between border-t border-border">
            <div className="text-xs text-ink-mid">
              After adding you'll be taken to the detail page where you can run AI research to populate scoring data.
            </div>
            <button onClick={submit} disabled={saving}
              className="btn-primary text-sm flex items-center gap-1.5 disabled:opacity-50">
              <Plus className="w-4 h-4" />
              {saving ? 'Adding...' : 'Add to Registry'}
            </button>
          </div>
        </div>
      </div>
    </AppLayout>
  )
}
