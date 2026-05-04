'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Shield } from 'lucide-react'
import { createClient } from '@/lib/supabase'
import toast from 'react-hot-toast'

export default function LoginPage() {
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      const supabase = createClient()
      const { data, error } = await supabase.auth.signInWithPassword({ email, password })
      if (error) throw new Error(error.message)

      // Store the access token for API calls to FastAPI
      localStorage.setItem('raven_token', data.session.access_token)
      router.push('/dashboard')
    } catch (err: any) {
      toast.error(err.message || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-ink flex items-center justify-center p-6">
      <div className="w-full max-w-sm">
        <div className="flex items-center gap-3 mb-10">
          <Shield className="w-6 h-6 text-gold" />
          <div>
            <div className="font-mono text-sm tracking-widest uppercase text-surface">Raven</div>
            <div className="text-xs text-surface/40 mt-0.5">Risk & Portfolio Intelligence</div>
          </div>
        </div>

        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label className="block text-xs text-surface/50 mb-1.5 font-mono uppercase tracking-widest">
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              className="w-full bg-white/5 border border-white/10 text-surface rounded px-3 py-2.5 text-sm focus:outline-none focus:border-gold/50 transition-colors"
              placeholder="you@raven.internal"
              required
            />
          </div>
          <div>
            <label className="block text-xs text-surface/50 mb-1.5 font-mono uppercase tracking-widest">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              className="w-full bg-white/5 border border-white/10 text-surface rounded px-3 py-2.5 text-sm focus:outline-none focus:border-gold/50 transition-colors"
              required
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-gold text-ink font-medium py-2.5 rounded text-sm hover:bg-gold-light transition-colors disabled:opacity-50 mt-2"
          >
            {loading ? 'Signing in…' : 'Sign In'}
          </button>
        </form>

        <p className="text-xs text-surface/25 text-center mt-8">
          Raven · Swiss Digital Asset Risk Intelligence · Confidential
        </p>
      </div>
    </div>
  )
}
