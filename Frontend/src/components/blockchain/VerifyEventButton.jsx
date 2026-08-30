import { useState } from 'react'
import { blockchainAPI } from '../../api/client'
import { IconShield, IconShieldAlert, IconShieldCheck } from '../ui/Icons'

/*
 * Recomputes ONE event's hash server-side and shows stored vs recomputed side
 * by side. Showing both is the point: "valid: true" is a claim, two matching
 * SHA-256 digests are evidence.
 */
export default function VerifyEventButton({ transactionId, storedHash }) {
  const [state, setState] = useState('idle') // idle | running | done | failed
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const run = async () => {
    setState('running')
    setError(null)
    try {
      const res = await blockchainAPI.verifyEvent(transactionId)
      setResult(res)
      setState('done')
    } catch (e) {
      setError(e.message || 'Verification request failed')
      setState('failed')
    }
  }

  if (state === 'idle') {
    return (
      <button type="button" onClick={run} className="btn btn-chain-soft">
        <IconShield /> Verify this event
      </button>
    )
  }

  if (state === 'running') {
    return (
      <span
        className="inline-flex items-center gap-2 text-small font-medium text-chain-700"
        role="status"
      >
        <span className="spinner" aria-hidden="true" /> Recomputing SHA-256…
      </span>
    )
  }

  if (state === 'failed') {
    return (
      <div
        className="rounded-xl border border-critical-200 bg-critical-50 p-3 text-small text-critical-700"
        role="alert"
      >
        {error}
        <button type="button" onClick={run} className="ml-2 underline underline-offset-2">
          Retry
        </button>
      </div>
    )
  }

  const valid = result?.valid === true
  const stored = result?.stored_hash || storedHash
  const calculated = result?.calculated_hash

  return (
    <div
      className={`rounded-xl border p-3 ${
        valid ? 'border-verified-200 bg-verified-50' : 'border-critical-200 bg-critical-50'
      }`}
      role="status"
    >
      <div
        className={`flex items-center gap-2 text-small font-semibold ${
          valid ? 'text-verified-700' : 'text-critical-700'
        }`}
      >
        {valid ? <IconShieldCheck /> : <IconShieldAlert />}
        {valid ? 'Hash recomputes — event is intact' : 'Hash mismatch — event was modified'}
      </div>

      {result?.message && <p className="mt-2 text-small text-neutral-700">{result.message}</p>}

      {(stored || calculated) && (
        <dl className="mt-3 space-y-2">
          <div>
            <dt className="text-micro font-semibold uppercase tracking-wider text-neutral-500">
              Stored hash
            </dt>
            <dd className="break-all font-mono text-[11px] text-ink">{stored || '—'}</dd>
          </div>
          <div>
            <dt className="text-micro font-semibold uppercase tracking-wider text-neutral-500">
              Recomputed hash
            </dt>
            <dd
              className={`break-all font-mono text-[11px] ${
                valid ? 'text-verified-700' : 'text-critical-700'
              }`}
            >
              {calculated || '—'}
            </dd>
          </div>
        </dl>
      )}

      <button
        type="button"
        onClick={() => setState('idle')}
        className="mt-3 text-micro font-semibold uppercase tracking-wider text-neutral-500 underline underline-offset-2 hover:text-ink"
      >
        Reset
      </button>
    </div>
  )
}
