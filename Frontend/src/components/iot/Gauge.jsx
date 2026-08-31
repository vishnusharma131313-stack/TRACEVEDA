import { motion, useReducedMotion } from 'framer-motion'
import { formatNumber } from '../../lib/format'

/*
 * A gauge, not a number in a table.
 *
 * `low`/`high` are the server's own thresholds (lib/iot.js mirrors
 * routes/iot.py), so the arc turns amber at exactly the value that makes the
 * backend raise an alert. The safe band is drawn on the track itself, which
 * is what makes a reading legible at a glance from across a room.
 */

const SIZE = 116
const STROKE = 9
const RADIUS = (SIZE - STROKE) / 2
const CIRC = 2 * Math.PI * RADIUS
const SWEEP = 0.75 // three-quarter dial
const ARC = CIRC * SWEEP

function clamp01(n) {
  return Math.max(0, Math.min(1, n))
}

export default function Gauge({ label, value, unit, min = 0, max = 100, low, high, state = 'ok' }) {
  const reduce = useReducedMotion()
  const hasValue = value !== null && value !== undefined && value !== '' && !Number.isNaN(Number(value))
  const numeric = hasValue ? Number(value) : null
  const fraction = hasValue ? clamp01((numeric - min) / (max - min)) : 0

  const stroke =
    state === 'breach' ? '#B3261E' : state === 'warn' ? '#C4622D' : hasValue ? '#2F6844' : '#D4D1C6'

  // Safe-band overlay on the track.
  const bandStart = low !== undefined ? clamp01((low - min) / (max - min)) : 0
  const bandEnd = high !== undefined ? clamp01((high - min) / (max - min)) : 1
  const bandLength = Math.max(0, bandEnd - bandStart) * ARC

  return (
    <div className="flex flex-col items-center rounded-2xl border border-neutral-200 bg-surface-raised p-4">
      <div className="relative" style={{ width: SIZE, height: SIZE }}>
        <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`} role="img" aria-label={`${label}: ${hasValue ? `${formatNumber(numeric)} ${unit ?? ''}` : 'no reading'}`}>
          <g transform={`rotate(135 ${SIZE / 2} ${SIZE / 2})`}>
            {/* track */}
            <circle
              cx={SIZE / 2}
              cy={SIZE / 2}
              r={RADIUS}
              fill="none"
              stroke="#E8E6DD"
              strokeWidth={STROKE}
              strokeDasharray={`${ARC} ${CIRC}`}
              strokeLinecap="round"
            />
            {/* safe band */}
            {(low !== undefined || high !== undefined) && bandLength > 0 && (
              <circle
                cx={SIZE / 2}
                cy={SIZE / 2}
                r={RADIUS}
                fill="none"
                stroke="#DCF0E2"
                strokeWidth={STROKE}
                strokeDasharray={`${bandLength} ${CIRC}`}
                strokeDashoffset={-bandStart * ARC}
                strokeLinecap="butt"
              />
            )}
            {/* value */}
            {hasValue && (
              <motion.circle
                cx={SIZE / 2}
                cy={SIZE / 2}
                r={RADIUS}
                fill="none"
                stroke={stroke}
                strokeWidth={STROKE}
                strokeLinecap="round"
                strokeDasharray={`${ARC} ${CIRC}`}
                initial={reduce ? false : { strokeDashoffset: ARC }}
                animate={{ strokeDashoffset: ARC - fraction * ARC }}
                transition={{ duration: reduce ? 0 : 0.7, ease: [0.22, 1, 0.36, 1] }}
              />
            )}
          </g>
        </svg>

        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span
            className="font-mono text-[19px] font-semibold leading-none"
            style={{ color: hasValue ? stroke : '#B0ACA0' }}
          >
            {hasValue ? formatNumber(numeric, 1) : '—'}
          </span>
          {unit && <span className="mt-1 text-[10px] text-neutral-500">{unit}</span>}
        </div>
      </div>

      <span className="mt-2 text-center text-micro font-semibold uppercase tracking-wider text-neutral-600">
        {label}
      </span>
      {(low !== undefined || high !== undefined) && (
        <span className="mt-0.5 text-[10px] text-neutral-400">
          safe {low ?? '−∞'}–{high ?? '∞'}
          {unit ? ` ${unit}` : ''}
        </span>
      )}
    </div>
  )
}

/** Binary sensors (gate, shock) read better as a state block than a dial. */
export function StateTile({ label, value, danger, hint }) {
  return (
    <div
      className={`flex flex-col items-center justify-center rounded-2xl border p-4 text-center transition-colors ${
        danger ? 'border-critical-200 bg-critical-50' : 'border-neutral-200 bg-surface-raised'
      }`}
    >
      <span className="text-micro font-semibold uppercase tracking-wider text-neutral-600">
        {label}
      </span>
      <span
        className={`mt-3 rounded-full px-4 py-1.5 text-small font-bold uppercase tracking-wide ${
          danger ? 'bg-critical text-white' : 'bg-verified-50 text-verified-700 ring-1 ring-inset ring-verified-200'
        }`}
      >
        {value}
      </span>
      {hint && <span className="mt-2 text-[10px] leading-tight text-neutral-500">{hint}</span>}
    </div>
  )
}
