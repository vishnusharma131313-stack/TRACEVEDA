/* Small formatting helpers. Deliberately tolerant: seeded documents and live
 * documents carry timestamps under different keys and in different precisions. */

export function toDate(value) {
  if (!value) return null
  const d = value instanceof Date ? value : new Date(value)
  return Number.isNaN(d.getTime()) ? null : d
}

export function formatDateTime(value) {
  const d = toDate(value)
  if (!d) return '—'
  return d.toLocaleString(undefined, {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatDate(value) {
  const d = toDate(value)
  if (!d) return '—'
  return d.toLocaleDateString(undefined, {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
}

const UNITS = [
  ['year', 31536000],
  ['month', 2592000],
  ['day', 86400],
  ['hour', 3600],
  ['minute', 60],
]

/** "3 days ago" / "in 2 months". Seed data is dated mid-2026, so future
 *  timestamps are normal and must read correctly, not as "0m ago". */
export function relativeTime(value) {
  const d = toDate(value)
  if (!d) return '—'
  const seconds = (d.getTime() - Date.now()) / 1000
  const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' })
  for (const [unit, secondsInUnit] of UNITS) {
    if (Math.abs(seconds) >= secondsInUnit) {
      return rtf.format(Math.round(seconds / secondsInUnit), unit)
    }
  }
  return rtf.format(Math.round(seconds), 'second')
}

/** 9f2b1c…4d7e — keeps both ends so two hashes stay visually comparable. */
export function truncateHash(hash, head = 10, tail = 6) {
  if (!hash) return '—'
  const s = String(hash)
  if (s.length <= head + tail + 1) return s
  return `${s.slice(0, head)}…${s.slice(-tail)}`
}

export function formatNumber(value, digits = 2) {
  if (value === null || value === undefined || value === '') return '—'
  const n = Number(value)
  if (Number.isNaN(n)) return String(value)
  return n.toLocaleString(undefined, { maximumFractionDigits: digits })
}

export function formatQuantity(value, unit) {
  if (value === null || value === undefined) return '—'
  return `${formatNumber(value)}${unit ? ` ${unit}` : ''}`
}

/**
 * Seeded lab tests store test_parameters as a JSON *string*; live ones store a
 * real object. Callers should not have to care.
 */
export function asObject(value) {
  if (!value) return null
  if (typeof value === 'object') return value
  if (typeof value === 'string') {
    try {
      const parsed = JSON.parse(value)
      return typeof parsed === 'object' ? parsed : null
    } catch {
      return null
    }
  }
  return null
}

export async function copyToClipboard(text) {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch {
    /* falls through to the legacy path below */
  }
  try {
    const el = document.createElement('textarea')
    el.value = text
    el.setAttribute('readonly', '')
    el.style.position = 'fixed'
    el.style.opacity = '0'
    document.body.appendChild(el)
    el.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(el)
    return ok
  } catch {
    return false
  }
}
