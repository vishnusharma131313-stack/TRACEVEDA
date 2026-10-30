export default function Card({ children, className = '', as: Tag = 'section', ...rest }) {
  return (
    <Tag
      className={`rounded-2xl border border-neutral-200 bg-surface-raised shadow-card ${className}`}
      {...rest}
    >
      {children}
    </Tag>
  )
}

export function CardHeader({ title, subtitle, actions, icon, className = '' }) {
  return (
    <div className={`flex flex-wrap items-start justify-between gap-3 border-b border-neutral-200 px-5 py-4 ${className}`}>
      <div className="min-w-0">
        <h2 className="flex items-center gap-2 font-serif text-h4 text-ink">
          {icon && <span className="text-neutral-500">{icon}</span>}
          {title}
        </h2>
        {subtitle && <p className="mt-1 text-small text-neutral-600">{subtitle}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  )
}

export function CardBody({ children, className = '' }) {
  return <div className={`p-5 ${className}`}>{children}</div>
}

/** Label/value row used across batch headers and detail panels. */
export function Field({ label, children, mono = false, className = '' }) {
  return (
    <div className={className}>
      <dt className="text-micro font-semibold uppercase tracking-wider text-neutral-500">{label}</dt>
      <dd className={`mt-1 text-body text-ink ${mono ? 'font-mono text-small' : ''}`}>{children ?? '—'}</dd>
    </div>
  )
}
