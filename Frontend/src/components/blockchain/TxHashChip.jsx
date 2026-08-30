import { useState } from 'react'
import { copyToClipboard, truncateHash } from '../../lib/format'
import { IconCheck, IconCopy } from '../ui/Icons'

/** Indigo is reserved for the ledger everywhere in this app, so a hash always
 *  reads as a hash no matter which screen it turns up on. */
export default function TxHashChip({ value, label, truncate = true, className = '' }) {
  const [copied, setCopied] = useState(false)
  if (!value) return null

  const onCopy = async () => {
    const ok = await copyToClipboard(String(value))
    if (!ok) return
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1600)
  }

  return (
    <button
      type="button"
      onClick={onCopy}
      title={String(value)}
      aria-label={`${label ? `${label}: ` : ''}${value}. Copy to clipboard`}
      className={`group inline-flex max-w-full items-center gap-1.5 rounded-full border border-chain-200 bg-chain-50 px-2.5 py-1 font-mono text-[11px] text-chain-700 transition-colors hover:bg-chain-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-chain-400 ${className}`}
    >
      <span className="truncate">{truncate ? truncateHash(value) : value}</span>
      <span className="shrink-0 text-chain-500" aria-hidden="true">
        {copied ? <IconCheck /> : <IconCopy />}
      </span>
      <span className="sr-only" role="status">
        {copied ? 'Copied' : ''}
      </span>
    </button>
  )
}
