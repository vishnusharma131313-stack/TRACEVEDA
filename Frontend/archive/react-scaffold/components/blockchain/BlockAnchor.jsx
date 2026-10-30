import { motion, useReducedMotion } from 'framer-motion'
import { truncateHash } from '../../lib/format'
import { IconLink } from '../ui/Icons'

/*
 * THE SIGNATURE MOMENT.
 *
 * One component, reused everywhere an event anchors: batch creation, lab
 * result, tamper event, medicine linkage. It draws a link line out of the
 * previous block and lands the new block on the end of it in ~560ms.
 *
 * It renders INLINE, in whatever view the action was taken in. There is
 * deliberately no full-screen overlay: the brief is explicit that the
 * presenter must never navigate away to prove the anchor happened.
 */

const LINK_MS = 0.26
const BLOCK_MS = 0.3

function PreviousBlock({ hash }) {
  return (
    <div className="w-[132px] shrink-0 rounded-xl border border-neutral-200 bg-neutral-50 px-3 py-2.5 text-neutral-500">
      <div className="text-[9px] font-semibold uppercase tracking-[0.08em] opacity-70">Previous</div>
      <div className="mt-1 truncate font-mono text-[11px] font-semibold" title={hash || undefined}>
        {hash ? truncateHash(hash, 8, 4) : 'GENESIS'}
      </div>
    </div>
  )
}

export default function BlockAnchor({ txId, eventType = 'ANCHORED', previousHash, className = '' }) {
  const reduce = useReducedMotion()

  // With reduced motion the block still appears, it just does not travel.
  const linkAnim = reduce
    ? { initial: { opacity: 0 }, animate: { opacity: 1 }, transition: { duration: 0.15 } }
    : {
        initial: { scaleX: 0, opacity: 0 },
        animate: { scaleX: 1, opacity: 1 },
        transition: { duration: LINK_MS, ease: 'easeOut' },
      }

  const blockAnim = reduce
    ? { initial: { opacity: 0 }, animate: { opacity: 1 }, transition: { duration: 0.2, delay: 0.1 } }
    : {
        initial: { opacity: 0, x: 18, scale: 0.9 },
        animate: { opacity: 1, x: 0, scale: 1 },
        transition: { duration: BLOCK_MS, delay: LINK_MS, ease: [0.34, 1.4, 0.64, 1] },
      }

  return (
    <div className={`flex items-center overflow-x-auto ${className}`}>
      <PreviousBlock hash={previousHash} />

      <motion.div
        {...linkAnim}
        style={{ originX: 0 }}
        className="relative mx-1.5 h-[2px] w-8 shrink-0 rounded-full bg-chain-300"
      >
        <span className="absolute -top-[7px] left-1/2 -translate-x-1/2 text-[11px] text-chain-400">
          <IconLink />
        </span>
      </motion.div>

      <motion.div {...blockAnim} className="shrink-0">
        <div className="w-[172px] rounded-xl border border-chain bg-chain px-3 py-2.5 text-white shadow-chain-glow">
          <div className="text-[9px] font-semibold uppercase tracking-[0.08em] text-chain-100">
            {String(eventType).replace(/_/g, ' ')}
          </div>
          <div className="mt-1 truncate font-mono text-[11px] font-semibold" title={txId || undefined}>
            {txId || 'anchoring…'}
          </div>
        </div>
      </motion.div>
    </div>
  )
}
