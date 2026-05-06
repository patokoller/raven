'use client'
import { useEffect, useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, FolderOpen, Trash2 } from 'lucide-react'
import AppLayout from '@/components/layout/AppLayout'
import PageHeader from '@/components/layout/PageHeader'
import Link from 'next/link'
import toast from 'react-hot-toast'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const H = () => ({ Authorization: `Bearer ${localStorage.getItem('raven_token')}` })

export default function PortfoliosPage() {
  const [portfolios, setPortfolios] = useState<any[]>([])
  const [loading, setLoading]       = useState(true)
  const [uploading, setUploading]   = useState(false)
  const [showUpload, setShowUpload] = useState(false)
  const [file, setFile]             = useState<File | null>(null)
  const [form, setForm] = useState({
    client_id: '',
    portfolio_name: '',
    valuation_date: new Date().toISOString().split('T')[0],
  })

  const load = async () => {
    setLoading(true)
    try {
      const r = await fetch(`${API}/api/v1/portfolios`, { headers: H() })
      if (r.ok) setPortfolios(await r.json())
    } catch {} finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const onDrop = useCallback((files: File[]) => { if (files[0]) setFile(files[0]) }, [])
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'text/csv': ['.csv'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'] },
    maxFiles: 1,
  })

  const upload = async () => {
    if (!file) return toast.error('Select a file first')
    if (!form.client_id) return toast.error('Enter a client ID')
    if (!form.portfolio_name) return toast.error('Enter a portfolio name')
    setUploading(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('client_id', form.client_id)
      fd.append('portfolio_name', form.portfolio_name)
      fd.append('valuation_date', form.valuation_date)
      const r = await fetch(`${API}/api/v1/portfolios/upload`, { method: 'POST', headers: H(), body: fd })
      const d = await r.json()
      if (!r.ok) throw new Error(d.detail)
      toast.success(`Uploaded ${d.position_count} positions — metrics computing`)
      setShowUpload(false); setFile(null)
      setTimeout(load, 3000)
    } catch (e: any) { toast.error(e.message) } finally { setUploading(false) }
  }

  return (
    <AppLayout>
      <PageHeader title="Portfolios" subtitle="Client portfolio management and risk analytics"
        action={<button onClick={() => setShowUpload(s => !s)} className="btn-primary text-xs flex items-center gap-1.5"><Upload className="w-3.5 h-3.5" /> Upload Portfolio</button>}
      />
      <div className="p-8 space-y-6">

        {showUpload && (
          <div className="card p-6 space-y-5">
            <div className="label">Upload Portfolio — CSV or XLSX</div>
            <div className="grid grid-cols-2 gap-6">
              <div {...getRootProps()} className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${isDragActive ? 'border-gold bg-gold/5' : 'border-border hover:border-ink-mid'}`}>
                <input {...getInputProps()} />
                <Upload className="w-6 h-6 text-ink-mid mx-auto mb-3" />
                {file ? (
                  <div><div className="text-sm font-medium">{file.name}</div><div className="text-xs text-ink-mid mt-1">{(file.size/1024).toFixed(1)} KB — ready to upload</div></div>
                ) : (
                  <div><div className="text-sm text-ink-mid">Drop CSV or XLSX here</div><div className="text-xs text-ink-mid mt-2">Required columns: symbol, quantity<br/>Optional: value_chf, custodian</div></div>
                )}
              </div>
              <div className="space-y-4">
                <div>
                  <label className="label mb-1.5 block">Client ID</label>
                  <input value={form.client_id} onChange={e => setForm(f => ({...f, client_id: e.target.value}))}
                    placeholder="From Supabase → clients table"
                    className="w-full border border-border rounded px-3 py-2 text-sm focus:outline-none focus:border-ink" />
                  <div className="text-xs text-ink-mid mt-1">Go to Supabase → Table Editor → clients → copy the client_id UUID</div>
                </div>
                <div>
                  <label className="label mb-1.5 block">Portfolio Name</label>
                  <input value={form.portfolio_name} onChange={e => setForm(f => ({...f, portfolio_name: e.target.value}))}
                    placeholder="e.g. Helvetic Capital — Main"
                    className="w-full border border-border rounded px-3 py-2 text-sm focus:outline-none focus:border-ink" />
                </div>
                <div>
                  <label className="label mb-1.5 block">Valuation Date</label>
                  <input type="date" value={form.valuation_date} onChange={e => setForm(f => ({...f, valuation_date: e.target.value}))}
                    className="w-full border border-border rounded px-3 py-2 text-sm focus:outline-none focus:border-ink" />
                </div>
                <button onClick={upload} disabled={uploading} className="w-full btn-primary text-sm disabled:opacity-50">
                  {uploading ? 'Uploading…' : 'Upload & Compute Metrics'}
                </button>
              </div>
            </div>
            <div className="bg-surface-2 rounded p-3 text-xs text-ink-mid">
              <strong className="text-ink">Sample CSV row:</strong> BTC, 2.5, 162500, Coinbase<br/>
              <strong className="text-ink">Headers:</strong> symbol, quantity, value_chf, custodian
            </div>
          </div>
        )}

        {loading ? (
          <div className="card p-8 text-center text-sm text-ink-mid">Loading…</div>
        ) : portfolios.length === 0 ? (
          <div className="card p-12 text-center">
            <FolderOpen className="w-8 h-8 text-ink-mid mx-auto mb-3" />
            <div className="text-sm font-medium mb-1">No portfolios yet</div>
            <div className="text-xs text-ink-mid mb-4">Upload a client portfolio CSV to get started</div>
            <button onClick={() => setShowUpload(true)} className="btn-primary text-xs">Upload First Portfolio</button>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-4">
            {portfolios.map((pf: any) => (
              <div key={pf.portfolio_id} className="relative group">
                <Link href={`/portfolios/${pf.portfolio_id}`}>
                  <div className="card p-5 hover:shadow-md transition-shadow cursor-pointer">
                    <div className="flex items-start justify-between mb-3">
                      <div>
                        <div className="font-medium text-sm">{pf.display_name}</div>
                        <div className="text-xs text-ink-mid mt-0.5">{pf.clients?.display_name ?? '—'}</div>
                      </div>
                      <span className="font-mono text-[10px] text-ink-mid">{pf.portfolio_ref}</span>
                    </div>
                    <div className="grid grid-cols-3 gap-3 mt-3">
                      <div><div className="label text-[10px] mb-1">NAV</div><div className="text-sm font-medium">{pf.total_nav_chf ? `CHF ${(pf.total_nav_chf/1e6).toFixed(2)}M` : '—'}</div></div>
                      <div><div className="label text-[10px] mb-1">Currency</div><div className="text-sm">{pf.base_currency}</div></div>
                      <div><div className="label text-[10px] mb-1">Uploaded</div><div className="text-xs text-ink-mid">{pf.last_uploaded_at ? new Date(pf.last_uploaded_at).toLocaleDateString('en-CH') : '—'}</div></div>
                    </div>
                  </div>
                </Link>
                <button
                  onClick={async e => {
                    e.preventDefault()
                    if (!confirm(`Delete "${pf.display_name}"? This cannot be undone.`)) return
                    setDeleting(pf.portfolio_id)
                    try {
                      const r = await fetch(`${API}/api/v1/portfolios/${pf.portfolio_id}`, {
                        method: 'DELETE',
                        headers: { Authorization: `Bearer ${localStorage.getItem('raven_token')}` }
                      })
                      if (r.ok) {
                        setPortfolios(prev => prev.filter(p => p.portfolio_id !== pf.portfolio_id))
                        toast.success(`"${pf.display_name}" deleted`)
                      } else {
                        toast.error('Delete failed')
                      }
                    } catch { toast.error('Delete failed') }
                    finally { setDeleting(null) }
                  }}
                  disabled={deleting === pf.portfolio_id}
                  className="absolute top-3 right-3 p-1.5 rounded bg-white border border-border
                    text-ink-mid hover:text-red hover:border-red/30 disabled:opacity-50 transition-colors"
                  title="Delete portfolio"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </AppLayout>
  )
}
