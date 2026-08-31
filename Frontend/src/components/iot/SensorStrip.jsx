import Gauge, { StateTile } from './Gauge'
import EmptyState from '../ui/EmptyState'
import { IconSensorOff } from '../ui/Icons'
import { formatDateTime } from '../../lib/format'
import { IOT_RULES, breachState, isGateOpen, weightChanged } from '../../lib/iot'

/*
 * Compact live telemetry for one batch. Used on Batch Detail (narrow) and on
 * the IoT Monitor (wide). Every threshold shown here comes from lib/iot.js,
 * which mirrors the backend rule engine.
 */
export default function SensorStrip({ reading, compact = false, emptyHint }) {
  if (!reading) {
    return (
      <EmptyState
        icon={<IconSensorOff />}
        title="No sensor attached"
        description={
          emptyHint ??
          'This batch has no IoT readings yet. Transport and storage nodes publish to POST /api/iot/readings.'
        }
      />
    )
  }

  const gateOpen = isGateOpen(reading.switch_status)
  const weightMoved = weightChanged(reading.weight_change_kg)
  const shock = reading.shock_detected === true

  const gridClass = compact
    ? 'grid grid-cols-2 gap-3'
    : 'grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-5'

  return (
    <div>
      <div className={gridClass}>
        <Gauge
          label="Temperature"
          value={reading.temperature_c}
          unit="°C"
          min={0}
          max={50}
          low={IOT_RULES.temperature_c.min}
          high={IOT_RULES.temperature_c.max}
          state={breachState('temperature_c', reading.temperature_c) === 'breach' ? 'breach' : 'ok'}
        />
        <Gauge
          label="Humidity"
          value={reading.humidity_percent}
          unit="%"
          min={0}
          max={100}
          low={IOT_RULES.humidity_percent.min}
          high={IOT_RULES.humidity_percent.max}
          state={breachState('humidity_percent', reading.humidity_percent) === 'breach' ? 'warn' : 'ok'}
        />
        <Gauge
          label="Light"
          value={reading.light_intensity_lux}
          unit="lux"
          min={0}
          max={2000}
          high={IOT_RULES.light_intensity_lux.max}
          state={
            breachState('light_intensity_lux', reading.light_intensity_lux) === 'breach' ? 'warn' : 'ok'
          }
        />
        {!compact && (
          <Gauge
            label="Tilt"
            value={reading.tilt_angle_deg}
            unit="°"
            min={0}
            max={90}
            high={IOT_RULES.tilt_angle_deg.max}
            state={breachState('tilt_angle_deg', reading.tilt_angle_deg) === 'breach' ? 'warn' : 'ok'}
          />
        )}
        <StateTile
          label="Gate"
          value={gateOpen ? 'Open' : 'Sealed'}
          danger={gateOpen}
          hint={gateOpen ? 'Limit switch triggered' : 'Limit switch closed'}
        />
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Metric label="Weight" value={fmt(reading.weight_kg, 'kg')} />
        <Metric
          label="Weight change"
          value={fmt(reading.weight_change_kg, 'kg')}
          danger={weightMoved}
        />
        <Metric label="Shock" value={shock ? 'Detected' : 'None'} danger={shock} />
        <Metric label="Sensor" value={reading.sensor_id ?? '—'} mono />
      </dl>

      <p className="mt-3 text-[11px] text-neutral-500">
        Latest reading {formatDateTime(reading.timestamp)}
        {reading.reading_id ? ` · ${reading.reading_id}` : ''}
      </p>
    </div>
  )
}

function fmt(value, unit) {
  if (value === null || value === undefined || value === '') return '—'
  return `${Number(value).toFixed(2)} ${unit}`
}

function Metric({ label, value, danger, mono }) {
  return (
    <div className="rounded-xl border border-neutral-200 bg-surface-sunk px-3 py-2">
      <dt className="text-[10px] font-semibold uppercase tracking-wider text-neutral-500">{label}</dt>
      <dd
        className={`mt-0.5 text-small font-semibold ${mono ? 'font-mono' : ''} ${
          danger ? 'text-critical-700' : 'text-ink'
        }`}
      >
        {value}
      </dd>
    </div>
  )
}
