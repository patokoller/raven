'use client'
import { usePathname, useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import { Shield, LayoutDashboard, Building2, FolderOpen, FileText, Bell, LogOut, ChevronRight, Settings, Scale, Users } from 'lucide-react'
import { createClient } from '@/lib/supabase'
import Link from 'next/link'

const NAV = [
  { href: '/dashboard',      label: 'Dashboard',     icon: LayoutDashboard },
  { href: '/counterparties', label: 'Counterparties', icon: Building2 },
  { href: '/portfolios',     label: 'Portfolios',     icon: FolderOpen },
  { href: '/reports',        label: 'Reports',        icon: FileText },
  { href: '/alerts',         label: 'Alerts',         icon: Bell },
  { href: '/admin',          label: 'Calibration',    icon: Settings },
  { href: '/regulations',    label: 'Regulations',    icon: Scale },
  { href: '/clients',         label: 'Clients',         icon: Users },
]

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const router   = useRouter()
  const [user, setUser] = useState('')

  useEffect(() => {
    createClient().auth.getUser().then(({ data }) => {
      if (!data.user) { router.replace('/login'); return }
      setUser(data.user.email ?? '')
    })
  }, [])

  const logout = async () => {
    await createClient().auth.signOut()
    localStorage.removeItem('raven_token')
    router.push('/login')
  }

  return (
    <div className="flex min-h-screen bg-surface">
      <aside className="w-52 bg-ink flex flex-col flex-shrink-0 fixed h-full z-20">
        <div className="px-5 py-5 border-b border-white/5">
          <div className="flex items-center gap-2.5">
            <Shield className="w-4 h-4 text-gold flex-shrink-0" />
            <div>
              <div className="font-mono text-xs tracking-widest uppercase text-surface">Raven</div>
              <div className="text-[10px] text-surface/30 mt-0.5">Risk Intelligence</div>
            </div>
          </div>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-0.5">
          {NAV.map(({ href, label, icon: Icon }) => {
            const active = pathname === href || pathname.startsWith(href + '/')
            return (
              <Link key={href} href={href} className={`flex items-center gap-2.5 px-3 py-2 rounded text-sm transition-colors ${active ? 'bg-white/10 text-surface' : 'text-surface/40 hover:text-surface/70 hover:bg-white/5'}`}>
                <Icon className="w-3.5 h-3.5 flex-shrink-0" />
                {label}
                {active && <ChevronRight className="w-3 h-3 ml-auto opacity-40" />}
              </Link>
            )
          })}
        </nav>
        <div className="px-3 py-4 border-t border-white/5">
          <div className="px-3 py-2 mb-1">
            <div className="text-[10px] text-surface/30 font-mono uppercase tracking-widest mb-0.5">Signed in as</div>
            <div className="text-xs text-surface/50 truncate">{user}</div>
          </div>
          <button onClick={logout} className="flex items-center gap-2 px-3 py-2 w-full text-left text-surface/40 hover:text-surface/70 text-xs rounded hover:bg-white/5 transition-colors">
            <LogOut className="w-3.5 h-3.5" /> Sign out
          </button>
        </div>
      </aside>
      <main className="flex-1 ml-52 min-h-screen">{children}</main>
    </div>
  )
}
