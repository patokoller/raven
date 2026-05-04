export default function PageHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: React.ReactNode }) {
  return (
    <div className="border-b border-border bg-white px-8 py-5 flex items-center justify-between sticky top-0 z-10">
      <div>
        <h1 className="text-base font-medium text-ink">{title}</h1>
        {subtitle && <p className="text-xs text-ink-mid mt-0.5">{subtitle}</p>}
      </div>
      {action && <div>{action}</div>}
    </div>
  )
}
