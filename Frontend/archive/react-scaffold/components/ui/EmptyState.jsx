import { IconInfo } from './Icons'

/**
 * Designed empty state. `tone="pending"` is for the case the brief calls out
 * explicitly: the UI is built against a real contract, but that endpoint is
 * not implemented yet. It must read as "pending backend", never as fake data.
 */
export default function EmptyState({
  icon,
  title,
  description,
  action,
  tone = 'neutral',
  className = '',
}) {
  const pending = tone === 'pending'
  return (
    <div
      className={`flex flex-col items-center justify-center rounded-2xl border border-dashed px-6 py-12 text-center ${
        pending ? 'border-alert-200 bg-alert-50/50' : 'border-neutral-300 bg-surface-sunk/60'
      } ${className}`}
    >
      <div className={`mb-3 text-2xl ${pending ? 'text-alert-500' : 'text-neutral-400'}`}>
        {icon ?? <IconInfo />}
      </div>
      <h3 className="font-serif text-h4 text-ink">{title}</h3>
      {description && (
        <p className="mt-2 max-w-md text-small text-neutral-600">{description}</p>
      )}
      {pending && (
        <p className="mt-3 rounded-full bg-alert-100 px-3 py-1 text-micro font-semibold uppercase tracking-wider text-alert-700">
          Pending backend
        </p>
      )}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}
