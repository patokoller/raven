'use client'
import { useState } from 'react'
import { Download } from 'lucide-react'
import toast from 'react-hot-toast'

interface DownloadButtonProps {
  report: any
  clientName?: string
}

export default function DownloadButton({ report, clientName }: DownloadButtonProps) {
  const [loading, setLoading] = useState(false)

  const handleDownload = async () => {
    setLoading(true)
    try {
      // Dynamic import to avoid SSR issues
      const { pdf } = await import('@react-pdf/renderer')
      const { ReportPDF } = await import('./ReportPDF')
      const React = await import('react')

      const blob = await pdf(
        React.createElement(ReportPDF, { report, clientName })
      ).toBlob()

      const url  = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href     = url
      link.download = `${report.report_ref}_${report.report_period.replace(/\s/g, '_')}.pdf`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)

      toast.success('PDF downloaded')
    } catch (e: any) {
      console.error(e)
      toast.error('PDF generation failed — ' + e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <button
      onClick={handleDownload}
      disabled={loading}
      className="btn-secondary text-xs flex items-center gap-1.5 disabled:opacity-50"
    >
      <Download className="w-3.5 h-3.5" />
      {loading ? 'Generating PDF…' : 'Download PDF'}
    </button>
  )
}
