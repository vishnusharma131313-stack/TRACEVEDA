/** A skeleton must match the shape of what replaces it, so callers pass the
 *  real layout classes rather than choosing from a fixed set of variants. */
export default function Skeleton({ className = 'h-4 w-full' }) {
  return <div className={`skeleton ${className}`} aria-hidden="true" />
}

export function SkeletonText({ lines = 3, className = '' }) {
  const widths = ['w-full', 'w-[88%]', 'w-[72%]', 'w-[80%]']
  return (
    <div className={`space-y-2 ${className}`} aria-hidden="true">
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className={`skeleton h-3.5 rounded ${widths[i % widths.length]}`} />
      ))}
    </div>
  )
}

/** Screen-reader announcement to pair with any visual skeleton. */
export function LoadingAnnounce({ label = 'Loading' }) {
  return (
    <span role="status" aria-live="polite" className="sr-only">
      {label}
    </span>
  )
}
