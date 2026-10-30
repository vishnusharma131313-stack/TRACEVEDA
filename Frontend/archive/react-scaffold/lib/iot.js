/*
 * Sensor thresholds mirrored from BACKEND/routes/iot.py (IOT_RULES).
 *
 * Kept in sync deliberately so a gauge turns amber at exactly the value that
 * makes the server raise an alert. If the backend rules move, move these.
 */

export const IOT_RULES = {
  temperature_c: { min: 10, max: 35, severity: 'CRITICAL' },
  humidity_percent: { min: 20, max: 70, severity: 'WARNING' },
  light_intensity_lux: { max: 1000, severity: 'WARNING' },
  tilt_angle_deg: { max: 45, severity: 'WARNING' },
}

export const WEIGHT_CHANGE_TOLERANCE_KG = 0.1

export const GATE_OPEN_VALUES = ['OPEN', 'TAMPER', 'TRIGGERED']

export function isGateOpen(switchStatus) {
  if (!switchStatus) return false
  return GATE_OPEN_VALUES.includes(String(switchStatus).toUpperCase())
}

export function weightChanged(weightChangeKg) {
  if (weightChangeKg === null || weightChangeKg === undefined) return false
  return Math.abs(Number(weightChangeKg)) >= WEIGHT_CHANGE_TOLERANCE_KG
}

/** The backend's 2FA tamper decision, recomputed client-side for live gauges. */
export function tamperStatusFor(reading) {
  const gate = isGateOpen(reading?.switch_status)
  const weight = weightChanged(reading?.weight_change_kg)
  if (gate && weight) return 'CRITICAL'
  if (gate || weight) return 'YELLOW'
  return 'NORMAL'
}

/** 'ok' | 'breach' for a single parameter, given the server's own rule. */
export function breachState(parameter, value) {
  if (value === null || value === undefined) return 'unknown'
  const rule = IOT_RULES[parameter]
  if (!rule) return 'ok'
  const n = Math.abs(parameter === 'tilt_angle_deg' ? Number(value) : Number(value))
  if (Number.isNaN(n)) return 'unknown'
  if (rule.min !== undefined && Number(value) < rule.min) return 'breach'
  if (rule.max !== undefined && n > rule.max) return 'breach'
  return 'ok'
}

/** Readings arrive OLDEST first; the live strip always wants the newest. */
export function latestReading(readings) {
  if (!Array.isArray(readings) || readings.length === 0) return null
  return readings[readings.length - 1]
}

/** Last N readings shaped for a Recharts time series. */
export function toSeries(readings, limit = 60) {
  if (!Array.isArray(readings)) return []
  return readings.slice(-limit).map((r) => ({
    t: r.timestamp,
    temperature_c: numOrNull(r.temperature_c),
    humidity_percent: numOrNull(r.humidity_percent),
    light_intensity_lux: numOrNull(r.light_intensity_lux),
    weight_kg: numOrNull(r.weight_kg),
  }))
}

function numOrNull(v) {
  if (v === null || v === undefined || v === '') return null
  const n = Number(v)
  return Number.isNaN(n) ? null : n
}

/**
 * The payload the demo trigger posts. Gate open + a weight change past the
 * tolerance is exactly the pair that makes routes/iot.py raise a CRITICAL
 * tamper_2fa alert and anchor it to the chain.
 */
export function tamperDemoPayload(batchId, sensorId = 'IOT-DEMO-001') {
  return {
    batch_id: batchId,
    sensor_id: sensorId,
    timestamp: new Date().toISOString(),
    switch_status: 'OPEN',
    weight_kg: 4.18,
    weight_change_kg: -0.82,
    temperature_c: 24.6,
    humidity_percent: 52.4,
    light_intensity_lux: 1850,
    tilt_angle_deg: 12.4,
    shock_detected: false,
  }
}

/** A benign reading, for resetting the demo between rehearsals. */
export function nominalDemoPayload(batchId, sensorId = 'IOT-DEMO-001') {
  return {
    batch_id: batchId,
    sensor_id: sensorId,
    timestamp: new Date().toISOString(),
    switch_status: 'CLOSED',
    weight_kg: 5.0,
    weight_change_kg: 0.0,
    temperature_c: 22.4,
    humidity_percent: 48.2,
    light_intensity_lux: 120,
    tilt_angle_deg: 1.2,
    shock_detected: false,
  }
}
