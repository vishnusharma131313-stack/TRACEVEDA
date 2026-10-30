import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { batchAPI, iotAPI, medicineAPI } from '../api/client'
import Card, { CardBody, CardHeader } from '../components/ui/Card'
import EmptyState from '../components/ui/EmptyState'
import Skeleton from '../components/ui/Skeleton'
import StatusChip from '../components/ui/StatusChip'
import SensorStrip from '../components/iot/SensorStrip'
import AnchorResult from '../components/blockchain/AnchorResult'
import { KIND, batchPath, normalizeList } from '../lib/batches'
import { formatDateTime, relativeTime } from '../lib/format'
import { IOT_RULES, latestReading, nominalDemoPayload, tamperDemoPayload, toSeries } from '../lib/iot'
import {
  IconAlertTriangle,
  IconArrowRight,
  IconRefresh,
  IconSensorOff,
  IconSignal,
} from '../components/ui/Icons'

/*
 * The live transport / storage screen, and the stage control that drives the
 * demo's cascade beat:
 *
 *   trigger -> POST /api/iot/readings (gate OPEN + weight change past the
 *   0.1 kg tolerance) -> backend 2FA rule raises a CRITICAL tamper_2fa alert
 *   -> that alert anchors as a TAMPER_EVENT -> the response carries
 *   blockchain_tx -> the block animation plays here, in this view.
 *
 * The button exists because hardware cannot be relied on to misbehave on cue
 * on a stage. It is labelled as a demo control, loudly, so nobody mistakes it
 * for production behaviour.
 */

const POLL_MS = 5000

export default function IoTMonitor() {
  const [params, setParams] = useSearchParams()
  const [batches, setBatches] = useState({ loading: true, rows: [] })
  const [selected, setSelected] = useState(params.get('batch') ?? '')

  const [data, setData] = useState({ loading: false, readings: [], alerts: [] })
  const [live, setLive] = useState(true)

  const [trigger, setTrigger] = useState({ state: 'idle', response: null, error: null })
  const previousAlertIds = useRef(new Set())
  const [flash, setFlash] = useState(false)

  /* ---- batch picker: IoT readings can hang off any batch kind ---- */
  useEffect(() => {
    let alive = true
    Promise.allSettled([medicineAPI.list(), batchAPI.listRaw(), batchAPI.listProcessing()]).then(
      ([med, raw, proc]) => {
        if (!alive) return
        const rows = [
          ...(med.status === 'fulfilled' ? normalizeList(med.value, KIND.MEDICINE) : []),
          ...(raw.status === 'fulfilled' ? normalizeList(raw.value, KIND.RAW) : []),
          ...(proc.status === 'fulfilled' ? normalizeList(proc.value, KIND.PROCESSING) : []),
        ]
        setBatches({ loading: false, rows })
      },
    )
    return () => {
      alive = false
    }
  }, [])

  const fetchData = useCallback(async (batchId, { quiet = false } = {}) => {
    if (!batchId) return
    if (!quiet) setData((d) => ({ ...d, loading: true }))
    const [r, a] = await Promise.allSettled([
      iotAPI.getReadings(batchId),
      iotAPI.getAlerts(batchId),
    ])
    setData({
      loading: false,
      readings: r.status === 'fulfilled' ? (r.value?.readings ?? []) : [],
      alerts: a.status === 'fulfilled' ? (a.value?.alerts ?? []) : [],
    })
  }, [])

  useEffect(() => {
    if (!selected) {
      setData({ loading: false, readings: [], alerts: [] })
      return undefined
    }
    previousAlertIds.current = new Set()
    setTrigger({ state: 'idle', response: null, error: null })
    fetchData(selected)
    if (!live) return undefined
    const id = window.setInterval(() => fetchData(selected, { quiet: true }), POLL_MS)
    return () => window.clearInterval(id)
  }, [selected, live, fetchData])

  /* Flash the alert list when a genuinely new alert arrives. */
  useEffect(() => {
    const ids = new Set(data.alerts.map((a) => a.alert_id))
    const isFirstLoad = previousAlertIds.current.size === 0
    const hasNew = [...ids].some((id) => !previousAlertIds.current.has(id))
    previousAlertIds.current = ids
    if (!isFirstLoad && hasNew) {
      setFlash(true)
      const t = window.setTimeout(() => setFlash(false), 1400)
      return () => window.clearTimeout(t)
    }
    return undefined
  }, [data.alerts])

  const newest = latestReading(data.readings)
  const series = useMemo(() => toSeries(data.readings, 80), [data.readings])
  const criticalAlerts = data.alerts.filter(
    (a) => String(a.severity).toUpperCase() === 'CRITICAL',
  )

  const selectBatch = (id) => {
    setSelected(id)
    if (id) setParams({ batch: id }, { replace: true })
    else setParams({}, { replace: true })
  }

  const send = async (payloadFactory, label) => {
    if (!selected) return
    setTrigger({ state: 'running', response: null, error: null, label })
    try {
      const response = await iotAPI.postReading(payloadFactory(selected))
      setTrigger({ state: 'done', response, error: null, label })
      await fetchData(selected, { quiet: true })
    } catch (e) {
      setTrigger({ state: 'failed', response: null, error: e.message, label })
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-serif text-h1 text-ink">IoT live monitor</h1>
          <p className="mt-1 max-w-2xl text-body text-neutral-600">
            Transport and storage telemetry, with the backend&apos;s own thresholds drawn on every
            gauge.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <label className="inline-flex items-center gap-2 text-small text-neutral-600">
            <input
              type="checkbox"
              checked={live}
              onChange={(e) => setLive(e.target.checked)}
              className="h-4 w-4 rounded border-neutral-300 text-verified focus:ring-verified"
            />
            Live ({POLL_MS / 1000}s)
          </label>
          <button
            type="button"
            onClick={() => fetchData(selected, { quiet: false })}
            disabled={!selected}
            className="btn btn-outline"
          >
            <IconRefresh /> Refresh
          </button>
        </div>
      </div>

      {/* ---- batch picker ---- */}
      <Card>
        <CardBody className="flex flex-wrap items-center gap-3">
          <label htmlFor="iot-batch" className="text-small font-semibold text-ink">
            Monitoring
          </label>
          <select
            id="iot-batch"
            value={selected}
            onChange={(e) => selectBatch(e.target.value)}
            className="input-field max-w-md flex-1 font-mono"
            disabled={batches.loading}
          >
            <option value="">
              {batches.loading ? 'Loading batches…' : 'Select a batch to monitor…'}
            </option>
            {batches.rows.map((b) => (
              <option key={`${b.kind}-${b.id}`} value={b.id}>
                {b.id} — {b.kindLabel}
                {b.title ? ` · ${b.title}` : ''}
              </option>
            ))}
          </select>
          {selected && (
            <Link
              to={batchPath(
                batches.rows.find((b) => b.id === selected)?.kind ?? KIND.MEDICINE,
                selected,
              )}
              className="btn btn-ghost"
            >
              Batch detail <IconArrowRight />
            </Link>
          )}
        </CardBody>
      </Card>

      {!selected ? (
        <EmptyState
          icon={<IconSignal />}
          title="Pick a batch to monitor"
          description="The seeded dataset attaches its 11,000 sensor readings to medicine batches, so MED-2026-001 is a good place to start."
        />
      ) : (
        <>
          {/* ---- critical banner ---- */}
          {criticalAlerts.length > 0 && (
            <div
              role="alert"
              className="flex flex-wrap items-start gap-3 rounded-2xl border-2 border-critical bg-critical-50 p-4 shadow-critical-glow"
            >
              <span className="mt-0.5 text-xl text-critical">
                <IconAlertTriangle />
              </span>
              <div className="min-w-0 flex-1">
                <h2 className="font-serif text-h4 text-critical-700">
                  {criticalAlerts.length} critical alert
                  {criticalAlerts.length === 1 ? '' : 's'} on {selected}
                </h2>
                <p className="mt-1 text-small text-critical-700">
                  {criticalAlerts[0].message ?? criticalAlerts[0].parameter}
                </p>
              </div>
              <Link to={`/blockchain?q=${encodeURIComponent(selected)}`} className="btn btn-chain">
                See ledger anchor
              </Link>
            </div>
          )}

          {/* ---- gauges ---- */}
          <Card>
            <CardHeader
              title="Current telemetry"
              subtitle={
                newest
                  ? `Reading ${newest.reading_id ?? ''} · ${formatDateTime(newest.timestamp)}`
                  : 'No readings for this batch'
              }
              actions={
                data.readings.length > 0 && (
                  <span className="text-small text-neutral-500">
                    {data.readings.length.toLocaleString()} readings
                  </span>
                )
              }
            />
            <CardBody>
              {data.loading && !newest ? (
                <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <Skeleton key={i} className="h-44 rounded-2xl" />
                  ))}
                </div>
              ) : (
                <SensorStrip
                  reading={newest}
                  emptyHint={`No rows in iot_readings for ${selected}. Use the demo control below to publish one.`}
                />
              )}
            </CardBody>
          </Card>

          {/* ---- history ---- */}
          {series.length > 1 && (
            <Card>
              <CardHeader
                title="Recent history"
                subtitle="Last 80 readings. The shaded band is the backend's allowed temperature range."
              />
              <CardBody>
                <div className="h-64 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={series} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
                      <CartesianGrid stroke="#E8E6DD" vertical={false} />
                      <ReferenceArea
                        y1={IOT_RULES.temperature_c.min}
                        y2={IOT_RULES.temperature_c.max}
                        fill="#2F6844"
                        fillOpacity={0.07}
                      />
                      <XAxis
                        dataKey="t"
                        tickFormatter={(v) => relativeTime(v)}
                        tick={{ fontSize: 10, fill: '#8A857A' }}
                        stroke="#D4D1C6"
                        minTickGap={48}
                      />
                      <YAxis tick={{ fontSize: 10, fill: '#8A857A' }} stroke="#D4D1C6" />
                      <Tooltip
                        labelFormatter={(v) => formatDateTime(v)}
                        contentStyle={{
                          borderRadius: 12,
                          border: '1px solid #E8E6DD',
                          fontSize: 12,
                          fontFamily: 'Inter, system-ui, sans-serif',
                        }}
                      />
                      <Line
                        type="monotone"
                        dataKey="temperature_c"
                        name="Temperature (°C)"
                        stroke="#2F6844"
                        strokeWidth={2}
                        dot={false}
                        connectNulls
                      />
                      <Line
                        type="monotone"
                        dataKey="humidity_percent"
                        name="Humidity (%)"
                        stroke="#C4622D"
                        strokeWidth={1.5}
                        dot={false}
                        connectNulls
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </CardBody>
            </Card>
          )}

          <div className="grid gap-6 lg:grid-cols-3">
            {/* ---- alerts ---- */}
            <Card className="lg:col-span-2">
              <CardHeader
                title="Alerts"
                subtitle="CRITICAL alerts anchor to the ledger. WARNING and YELLOW stay in MongoDB by design."
              />
              <CardBody>
                {data.loading && data.alerts.length === 0 ? (
                  <Skeleton className="h-24 w-full rounded-xl" />
                ) : data.alerts.length === 0 ? (
                  <EmptyState
                    icon={<IconSensorOff />}
                    title="No alerts raised"
                    description={`Nothing in iot_alerts for ${selected}. Note the seeded dataset loads its historical alerts into a separate "alerts" collection that this endpoint does not read.`}
                  />
                ) : (
                  <motion.ul
                    animate={flash ? { backgroundColor: ['#FDF3F2', '#FFFFFF'] } : {}}
                    transition={{ duration: 1.2 }}
                    className="space-y-2 rounded-xl"
                  >
                    <AnimatePresence initial={false}>
                      {data.alerts.map((alert) => {
                        const critical = String(alert.severity).toUpperCase() === 'CRITICAL'
                        return (
                          <motion.li
                            key={alert.alert_id}
                            layout
                            initial={{ opacity: 0, x: -10 }}
                            animate={{ opacity: 1, x: 0 }}
                            className={`rounded-xl border-l-[3px] p-3 ${
                              critical
                                ? 'border-l-critical bg-critical-50'
                                : 'border-l-alert bg-alert-50'
                            }`}
                          >
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <StatusChip status={alert.severity} size="sm" />
                              <time className="text-[11px] text-neutral-500">
                                {relativeTime(alert.created_at ?? alert.timestamp)}
                              </time>
                            </div>
                            <p className="mt-1.5 text-small font-medium text-ink">
                              {alert.message ?? alert.parameter}
                            </p>
                            <p className="mt-0.5 font-mono text-[11px] text-neutral-500">
                              {alert.alert_id}
                              {alert.parameter ? ` · ${alert.parameter}` : ''}
                              {alert.sensor_id ? ` · ${alert.sensor_id}` : ''}
                            </p>
                          </motion.li>
                        )
                      })}
                    </AnimatePresence>
                  </motion.ul>
                )}
              </CardBody>
            </Card>

            {/* ---- demo controls ---- */}
            <Card className="border-2 border-dashed border-alert-300 bg-alert-50/40">
              <CardHeader
                icon={<IconAlertTriangle />}
                title="Demo controls"
                subtitle="Stage controls only — these publish a real reading to POST /api/iot/readings."
                className="border-alert-200"
              />
              <CardBody className="space-y-3">
                <button
                  type="button"
                  onClick={() => send(tamperDemoPayload, 'tamper')}
                  disabled={trigger.state === 'running'}
                  className="btn btn-danger w-full py-3"
                >
                  {trigger.state === 'running' && trigger.label === 'tamper' ? (
                    <>
                      <span className="spinner" aria-hidden="true" /> Publishing…
                    </>
                  ) : (
                    'Trigger tamper event'
                  )}
                </button>
                <p className="text-[11px] leading-relaxed text-neutral-600">
                  Sends gate <span className="font-mono">OPEN</span> plus a{' '}
                  <span className="font-mono">-0.82 kg</span> weight change. Both factors together
                  are what the backend&apos;s 2FA rule treats as CRITICAL, which is what makes it
                  anchor.
                </p>

                <button
                  type="button"
                  onClick={() => send(nominalDemoPayload, 'nominal')}
                  disabled={trigger.state === 'running'}
                  className="btn btn-outline w-full"
                >
                  {trigger.state === 'running' && trigger.label === 'nominal' ? (
                    <>
                      <span className="spinner" aria-hidden="true" /> Publishing…
                    </>
                  ) : (
                    'Publish nominal reading'
                  )}
                </button>

                {trigger.state === 'failed' && (
                  <div
                    role="alert"
                    className="rounded-xl border border-critical-200 bg-critical-50 p-3 text-small text-critical-700"
                  >
                    {trigger.error}
                  </div>
                )}

                {trigger.state === 'done' && trigger.response && (
                  <div className="space-y-3 pt-1">
                    <dl className="grid grid-cols-2 gap-2 text-[11px]">
                      <Readout label="Reading" value={trigger.response.reading_id} mono />
                      <Readout label="Tamper" value={trigger.response.tamper_status} />
                      <Readout
                        label="Gate"
                        value={trigger.response.gate_open ? 'OPEN' : 'CLOSED'}
                      />
                      <Readout
                        label="Alerts"
                        value={String(trigger.response.alerts_generated ?? 0)}
                      />
                    </dl>

                    <AnchorResult
                      txId={trigger.response.blockchain_tx}
                      eventType="TAMPER_EVENT"
                      offChainReason={
                        !trigger.response.blockchain_tx && trigger.response.alerts_generated === 0
                          ? 'Every value was inside the allowed range, so no alert was raised and nothing needed anchoring.'
                          : !trigger.response.blockchain_tx
                            ? 'Alerts were raised but none reached CRITICAL severity, so they stay in MongoDB — that is the on-chain / off-chain split working as designed.'
                            : null
                      }
                    />
                  </div>
                )}
              </CardBody>
            </Card>
          </div>
        </>
      )}
    </div>
  )
}

function Readout({ label, value, mono }) {
  return (
    <div className="rounded-lg border border-neutral-200 bg-surface-raised px-2.5 py-1.5">
      <dt className="text-[10px] font-semibold uppercase tracking-wider text-neutral-500">
        {label}
      </dt>
      <dd className={`mt-0.5 truncate font-semibold text-ink ${mono ? 'font-mono' : ''}`}>
        {value ?? '—'}
      </dd>
    </div>
  )
}
