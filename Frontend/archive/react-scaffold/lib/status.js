/*
 * The real status vocabulary, taken from two places that disagree:
 *
 *  - the live API writes CREATED / APPROVED_FOR_MANUFACTURING / BLOCKED /
 *    RELEASED (routes/batches.py, routes/lab.py, routes/medicine.py)
 *  - the seeded dataset ships VERIFIED (raw) and COMPLETED (processing)
 *
 * Both are real values a judge can encounter during the demo, so both are
 * mapped. Nothing is invented here — if a status arrives that is not listed,
 * it renders in neutral with its own text rather than being silently recoloured.
 */

export const TONE = {
  VERIFIED: 'verified',
  CHAIN: 'chain',
  ALERT: 'alert',
  CRITICAL: 'critical',
  NEUTRAL: 'neutral',
}

const TONE_BY_STATUS = {
  // ---- batch lifecycle (live API) ----
  CREATED: TONE.NEUTRAL,
  APPROVED_FOR_MANUFACTURING: TONE.VERIFIED,
  BLOCKED: TONE.CRITICAL,
  RELEASED: TONE.VERIFIED,

  // ---- batch lifecycle (seeded dataset) ----
  VERIFIED: TONE.VERIFIED,
  COMPLETED: TONE.VERIFIED,

  // ---- lab ----
  PASS: TONE.VERIFIED,
  FAIL: TONE.CRITICAL,

  // ---- IoT severity + tamper status ----
  NORMAL: TONE.VERIFIED,
  YELLOW: TONE.ALERT,
  WARNING: TONE.ALERT,
  CRITICAL: TONE.CRITICAL,

  // ---- alert / report workflow ----
  OPEN: TONE.ALERT,
  CLOSED: TONE.NEUTRAL,
  RESOLVED: TONE.VERIFIED,

  // ---- ledger ----
  ANCHORED: TONE.CHAIN,

  // ---- transport (seeded dataset) ----
  DELIVERED: TONE.VERIFIED,
  IN_TRANSIT: TONE.NEUTRAL,
  DISPATCHED: TONE.NEUTRAL,
  STORED: TONE.NEUTRAL,
}

export function toneFor(status) {
  if (!status) return TONE.NEUTRAL
  return TONE_BY_STATUS[String(status).toUpperCase()] ?? TONE.NEUTRAL
}

/** Statuses that must dominate a screen rather than sit in a chip. */
export function isBlocking(status) {
  const s = String(status ?? '').toUpperCase()
  return s === 'BLOCKED' || s === 'CRITICAL' || s === 'FAIL'
}

/** BATCH_CREATED -> Batch created */
export function humanize(value) {
  if (!value) return ''
  const s = String(value).replace(/_/g, ' ').toLowerCase()
  return s.charAt(0).toUpperCase() + s.slice(1)
}

/*
 * Ledger event vocabulary. The live routes emit the first four; the migrated
 * seed history additionally contains MEDICINE_LINKAGE, SHIPMENT_MILESTONE and
 * ENVIRONMENTAL_ALERT. The explorer filter offers the union so that filtering
 * never hides real rows.
 */
export const LEDGER_EVENT_TYPES = [
  'BATCH_CREATED',
  'BATCH_LINKED',
  'QUALITY_STATUS',
  'MEDICINE_LINKED',
  'MEDICINE_LINKAGE',
  'TAMPER_EVENT',
  'SHIPMENT_MILESTONE',
  'ENVIRONMENTAL_ALERT',
]

export function ledgerEventTone(eventType) {
  switch (String(eventType ?? '').toUpperCase()) {
    case 'TAMPER_EVENT':
      return TONE.CRITICAL
    case 'ENVIRONMENTAL_ALERT':
      return TONE.ALERT
    case 'QUALITY_STATUS':
    case 'MEDICINE_LINKED':
    case 'MEDICINE_LINKAGE':
      return TONE.VERIFIED
    default:
      return TONE.CHAIN
  }
}
