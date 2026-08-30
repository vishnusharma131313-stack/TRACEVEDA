import { useCallback, useEffect, useRef, useState } from 'react'
import { blockchainAPI } from '../../api/client'
import { IconRefresh, IconShieldAlert, IconShieldCheck } from '../ui/Icons'

/*
 * Live chain integrity, in the header of every internal screen.
 *
 * GET /api/blockchain/verify-chain returns:
 *   { valid, checked, broken_at, reason }
 *
 * Those are the exact field names. Reading `verifiedCount` / `brokenAt` here
 * is why the badge previously always claimed "0 verified".
 */

const POLL_MS = 30000

export default function ChainIntegrityBadge() {
  const [state, setState] = useState('loading') // loading | valid | broken | offline
  const [result, setResult] = useState(null)
  const [open, setOpen] = useState(false)
  const mounted = useRef(true)
  const popover = useRef(null)

  const check = useCallback(async () => {
    try {
      const res = await blockchainAPI.verifyChain()
      if (!mounted.current) return
      setResult(res)
      setState(res?.valid ? 'valid' : 'broken')
    } catch {
      if (!mounted.current) return
      setResult(null)
      setState('offline')
    }
  }, [])

  useEffect(() => {
    mounted.current = true
    check()
    const id = window.setInterval(check, POLL_MS)
    return () => {
      mounted.current = false
      window.clearInterval(id)
    }
  }, [check])

  // Dismiss the detail popover on outside click / Escape.
  useEffect(() => {
    if (!open) return undefined
    const onDown = (e) => {
      if (popover.current && !popover.current.contains(e.target)) setOpen(false)
    }
    const onKey = (e) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  if (state === 'loading') {
    return <div className="skeleton h-8 w-44 rounded-full" aria-label="Checking chain integrity" />
  }

  const tone =
    state === 'valid'
      ? 'border-verified-200 bg-verified-50 text-verified-700'
      : state === 'broken'
        ? 'border-critical-200 bg-critical-50 text-critical-700'
        : 'border-neutral-300 bg-neutral-100 text-neutral-600'

  const label =
    state === 'valid'
      ? `Chain intact · ${Number(result?.checked ?? 0).toLocaleString()} events`
      : state === 'broken'
        ? 'Chain broken'
        : 'Ledger unreachable'

  return (
    <div className="relative" ref={popover}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="dialog"
        className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-small font-semibold transition-colors hover:brightness-[.98] focus:outline-none focus-visible:ring-2 focus-visible:ring-chain-400 ${tone}`}
      >
        {state === 'valid' ? <IconShieldCheck /> : <IconShieldAlert />}
        <span className="hidden sm:inline">{label}</span>
        <span className="sm:hidden">{state === 'valid' ? 'Intact' : 'Chain'}</span>
      </button>

      {open && (
        <div
          role="dialog"
          aria-label="Chain integrity details"
          className="absolute right-0 z-40 mt-2 w-80 rounded-2xl border border-neutral-200 bg-surface-raised p-4 shadow-elevated"
        >
          <div className="mb-3 flex items-center justify-between">
            <h3 className="font-serif text-h5 text-ink">Chain integrity</h3>
            <button
              type="button"
              onClick={check}
              className="inline-flex items-center gap-1 text-micro font-semibold uppercase tracking-wider text-neutral-500 hover:text-ink"
            >
              <IconRefresh /> Recheck
            </button>
          </div>

          {state === 'offline' ? (
            <p className="text-small text-neutral-600">
              The backend did not answer <code className="font-mono">/api/blockchain/verify-chain</code>.
              Start the API and this badge goes live again.
            </p>
          ) : (
            <dl className="space-y-2 text-small">
              <div className="flex justify-between gap-3">
                <dt className="text-neutral-600">Events walked</dt>
                <dd className="font-mono text-ink">{Number(result?.checked ?? 0).toLocaleString()}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-neutral-600">Verdict</dt>
                <dd className={state === 'valid' ? 'font-semibold text-verified-700' : 'font-semibold text-critical-700'}>
                  {state === 'valid' ? 'Every hash recomputes' : 'Tampering detected'}
                </dd>
              </div>
              {result?.broken_at && (
                <div className="border-t border-neutral-200 pt-2">
                  <dt className="text-micro font-semibold uppercase tracking-wider text-critical-700">
                    Broken at
                  </dt>
                  <dd className="mt-1 break-all font-mono text-[11px] text-ink">{result.broken_at}</dd>
                </div>
              )}
              {result?.reason && (
                <p className="rounded-lg bg-critical-50 p-2 text-[12px] leading-relaxed text-critical-700">
                  {result.reason}
                </p>
              )}
            </dl>
          )}

          <p className="mt-3 border-t border-neutral-200 pt-2 text-[11px] leading-relaxed text-neutral-500">
            Re-walked every {POLL_MS / 1000}s. The verifier checks each event&apos;s own hash and its
            link to the preceding event, in sequence order.
          </p>
        </div>
      )}
    </div>
  )
}
