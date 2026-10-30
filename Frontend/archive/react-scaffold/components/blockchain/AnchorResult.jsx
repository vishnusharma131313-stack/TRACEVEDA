import { motion } from 'framer-motion'
import BlockAnchor from './BlockAnchor'
import TxHashChip from './TxHashChip'
import VerifyEventButton from './VerifyEventButton'
import { IconInfo } from '../ui/Icons'

/*
 * Shown immediately after any state-changing action, in the same view.
 *
 * Three cases, all of which happen for real against this backend:
 *   anchored     — blockchain_tx came back, play the block animation
 *   off-chain    — the write succeeded but was deliberately NOT anchored
 *                  (WARNING / YELLOW alerts, routine readings). Saying so
 *                  teaches the on-chain/off-chain split instead of hiding it.
 *   ledger-down  — the write succeeded, anchoring failed. safe_anchor()
 *                  returns null rather than failing the request, so this is a
 *                  real state and must not be dressed up as success.
 */
export default function AnchorResult({ txId, eventType, previousHash, offChainReason, className = '' }) {
  if (txId) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25 }}
        className={`rounded-2xl border border-chain-200 bg-chain-50/60 p-4 ${className}`}
        role="status"
      >
        <div className="mb-3 flex items-center justify-between gap-3">
          <span className="text-micro font-semibold uppercase tracking-wider text-chain-700">
            Anchored to ledger
          </span>
          <TxHashChip value={txId} label="Transaction" truncate={false} />
        </div>

        <BlockAnchor txId={txId} eventType={eventType} previousHash={previousHash} />

        <div className="mt-3">
          <VerifyEventButton transactionId={txId} />
        </div>
      </motion.div>
    )
  }

  if (offChainReason) {
    return (
      <div
        className={`flex items-start gap-2.5 rounded-2xl border border-neutral-200 bg-neutral-50 p-4 text-small text-neutral-700 ${className}`}
        role="status"
      >
        <span className="mt-0.5 shrink-0 text-neutral-500">
          <IconInfo />
        </span>
        <div>
          <p className="font-semibold text-ink">Recorded off-chain</p>
          <p className="mt-1">{offChainReason}</p>
        </div>
      </div>
    )
  }

  return (
    <div
      className={`flex items-start gap-2.5 rounded-2xl border border-alert-200 bg-alert-50 p-4 text-small text-alert-700 ${className}`}
      role="status"
    >
      <span className="mt-0.5 shrink-0">
        <IconInfo />
      </span>
      <div>
        <p className="font-semibold">Saved, but not anchored</p>
        <p className="mt-1">
          The record was written successfully; the ledger did not return a transaction id. The
          backend never fails a write on a ledger outage, so the supply-chain record is safe — but
          this event is not yet tamper-evident.
        </p>
      </div>
    </div>
  )
}
