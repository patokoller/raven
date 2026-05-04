import type { Metadata } from 'next'
import { Inter, JetBrains_Mono } from 'next/font/google'
import './globals.css'
import { Toaster } from 'react-hot-toast'

const inter = Inter({ subsets: ['latin'], variable: '--font-sans' })
const mono = JetBrains_Mono({ subsets: ['latin'], variable: '--font-mono' })

export const metadata: Metadata = {
  title: 'Raven — Risk & Portfolio Intelligence',
  description: 'Swiss-grade counterparty risk monitoring for digital asset wealth managers',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${mono.variable}`}>
      <body className="bg-surface text-ink antialiased">
        <Toaster
          position="top-right"
          toastOptions={{
            style: { background: '#0D0F0E', color: '#F5F0E8', border: '1px solid #2A2E2C' },
          }}
        />
        {children}
      </body>
    </html>
  )
}
