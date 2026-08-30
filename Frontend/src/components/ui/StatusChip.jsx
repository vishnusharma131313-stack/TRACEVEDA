import { toneFor, TONE } from '../../lib/status'

const TONE_CLASS = {
  [TONE.VERIFIED]: 'bg-verified-50 text-verified-700 ring-verified-200',
  [TONE.CHAIN]: 'bg-chain-50 text-chain-700 ring-chain-200',
  [TONE.ALERT]: 'bg-alert-50 text-alert-700 ring-alert-200',
  [TONE.CRITICAL]: 'bg-critical-50 text-critical-700 ring-critical-200',
  [TONE.NEUTRAL]: 'bg-neutral-100 text-neutral-700 ring-neutral-300',
}

const DOT_CLASS = {
  [TONE.VERIFIED]: 'bg-verified',
  [TONE.CHAIN]: 'bg-chain',
  [TONE.ALERT]: 'bg-alert',
  [TONE.CRITICAL]: 'bg-critical',
  [TONE.NEUTRAL]: 'bg-neutral-400',
}

const SIZE_CLASS = {
  sm: 'text-[10px] px-2 py-0.5 gap-1',
  md: 'text-micro px-2.5 py-1 gap-1.5',
  lg: 'text-small px-3.5 py-1.5 gap-2',
}

/**
 * `status` is the raw backend value and is always what gets rendered — the
 * chip never relabels a status into vocabulary the backend does not use.
 * Pass `label` only to display a different string for the same tone.
 */
export default function StatusChip({ status, label, tone, size = 'md', dot = true, className = '' }) {
  if (!status && !label) return null
  const resolved = tone ?? toneFor(status)
  const text = label ?? String(status)

  return (
    <span
      className={`inline-flex items-center rounded-full font-semibold uppercase tracking-wide ring-1 ring-inset whitespace-nowrap ${TONE_CLASS[resolved]} ${SIZE_CLASS[size]} ${className}`}
    >
      {dot && <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${DOT_CLASS[resolved]}`} />}
      {text}
    </span>
  )
}
