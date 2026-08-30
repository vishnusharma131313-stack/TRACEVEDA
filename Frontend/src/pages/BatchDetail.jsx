import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  batchAPI,
  blockchainAPI,
  consumerAPI,
  iotAPI,
  labAPI,
  medicineAPI,
  traceAPI,
  transportAPI,
} from '../api/client'
import Card, { CardBody, CardHeader, Field } from '../components/ui/Card'
import EmptyState from '../components/ui/EmptyState'
import Skeleton, { SkeletonText } from '../components/ui/Skeleton'
import StatusChip from '../components/ui/StatusChip'
import EventTimeline, { buildTimeline } from '../components/timeline/EventTimeline'
import LineageGraph, {
  buildForwardLineage,
  buildProcessingLineage,
  buildReverseLineage,
} from '../components/trace/LineageGraph'
import SensorStrip from '../components/iot/SensorStrip'
import {
  IconAlertTriangle,
  IconArrowLeft,
  IconFlask,
  IconLink,
  IconRoute,
  IconSignal,
} from '../components/ui/Icons'
import { KIND, KIND_LABEL, statusOf, titleOf } from '../lib/batches'
import { asObject, formatDate, formatQuantity } from '../lib/format'
import { isBlocking } from '../lib/status'
import { latestReading } from '../lib/iot'

/*
 * THE screen. Everything a dispute would turn on, on one page, no tabs.
 *
 * Loading strategy: the batch itself is awaited first so the header and the
 * critical banner paint immediately; every satellite request then resolves
 * independently and fills its own card. One missing endpoint degrades one
 * card, never the page.
 */

const VALID_KINDS = new Set([KIND.RAW, KIND.PROCESSING, KIND.MEDICINE])

export default function BatchDetail() {
  const { batchType, batchId } = useParams()
  const kind = VALID_KINDS.has(batchType) ? batchType : null

  const [batch, setBatch] = useState(null)
  const [batchError, setBatchError] = useState(null)
  const [loadingBatch, setLoadingBatch] = useState(true)

  const [ledger, setLedger] = useState({ loading: true, events: [] })
  const [lab, setLab] = useState({ loading: true, tests: [] })
  const [iot, setIot] = useState({ loading: true, readings: [], alerts: [] })
  const [transport, setTransport] = useState({ loading: true, events: [] })
  const [lineage, setLineage] = useState({ loading: true, columns: [], edges: [] })
  const [reports, setReports] = useState({ loading: false, rows: [] })

  const [acknowledged, setAcknowledged] = useState(false)

  /* ---------------- primary record ---------------- */
  useEffect(() => {
    if (!kind) return
    let alive = true
    setLoadingBatch(true)
    setBatchError(null)
    setAcknowledged(false)

    const fetcher =
      kind === KIND.RAW
        ? batchAPI.getRaw
        : kind === KIND.PROCESSING
          ? batchAPI.getProcessing
          : medicineAPI.get

    fetcher(batchId)
      .then((doc) => {
        if (alive) setBatch(doc)
      })
      .catch((e) => {
        if (alive) setBatchError(e)
      })
      .finally(() => {
        if (alive) setLoadingBatch(false)
      })

    return () => {
      alive = false
    }
  }, [kind, batchId])

  /* ---------------- ledger trail ---------------- */
  useEffect(() => {
    let alive = true
    setLedger({ loading: true, events: [] })
    blockchainAPI
      .getTrail(batchId)
      .then((res) => {
        if (alive) setLedger({ loading: false, events: res?.events ?? [] })
      })
      .catch(() => {
        if (alive) setLedger({ loading: false, events: [] })
      })
    return () => {
      alive = false
    }
  }, [batchId])

  /* ---------------- lab / iot / transport ---------------- */
  useEffect(() => {
    let alive = true
    setLab({ loading: true, tests: [] })
    setIot({ loading: true, readings: [], alerts: [] })
    setTransport({ loading: true, events: [] })

    labAPI
      .getTests(batchId)
      .then((r) => alive && setLab({ loading: false, tests: r?.tests ?? [] }))
      .catch(() => alive && setLab({ loading: false, tests: [] }))

    Promise.all([
      iotAPI.getReadings(batchId).catch(() => ({ readings: [] })),
      iotAPI.getAlerts(batchId).catch(() => ({ alerts: [] })),
    ]).then(([r, a]) => {
      if (!alive) return
      setIot({ loading: false, readings: r?.readings ?? [], alerts: a?.alerts ?? [] })
    })

    transportAPI
      .getEvents(batchId)
      .then((r) => alive && setTransport({ loading: false, events: r?.events ?? [] }))
      .catch(() => alive && setTransport({ loading: false, events: [] }))

    return () => {
      alive = false
    }
  }, [batchId])

  /* ---------------- consumer reports (medicine only) ---------------- */
  useEffect(() => {
    if (kind !== KIND.MEDICINE) {
      setReports({ loading: false, rows: [] })
      return undefined
    }
    let alive = true
    setReports({ loading: true, rows: [] })
    consumerAPI
      .getReportsForBatch(batchId)
      .then((r) => alive && setReports({ loading: false, rows: r?.reports ?? [] }))
      .catch(() => alive && setReports({ loading: false, rows: [] }))
    return () => {
      alive = false
    }
  }, [kind, batchId])

  /* ---------------- lineage ---------------- */
  useEffect(() => {
    if (!kind) return undefined
    let alive = true
    setLineage({ loading: true, columns: [], edges: [] })

    const load = async () => {
      try {
        if (kind === KIND.MEDICINE) {
          const trace = await traceAPI.reverse(batchId)
          return buildReverseLineage(trace)
        }
        if (kind === KIND.RAW) {
          const trace = await traceAPI.forward(batchId)
          return buildForwardLineage(trace)
        }
        /* PROCESSING has no single trace endpoint — see buildProcessingLineage. */
        const [rel, meds, processing] = await Promise.all([
          batchAPI.getRelationships(batchId).catch(() => ({ relationships: [] })),
          medicineAPI.list().catch(() => ({ batches: [] })),
          batchAPI.getProcessing(batchId).catch(() => null),
        ])
        return buildProcessingLineage({
          processing,
          relationships: rel?.relationships ?? [],
          medicines: meds?.batches ?? [],
        })
      } catch {
        return { columns: [], edges: [] }
      }
    }

    load().then((graph) => {
      if (alive) setLineage({ loading: false, ...graph })
    })

    return () => {
      alive = false
    }
  }, [kind, batchId])

  const timeline = useMemo(
    () =>
      buildTimeline({
        ledger: ledger.events,
        labTests: lab.tests,
        alerts: iot.alerts,
        transport: transport.events,
      }),
    [ledger.events, lab.tests, iot.alerts, transport.events],
  )

  const criticalAlerts = useMemo(
    () => iot.alerts.filter((a) => String(a.severity).toUpperCase() === 'CRITICAL'),
    [iot.alerts],
  )

  const status = statusOf(batch)
  const blockingStatus = isBlocking(status)
  const showBanner = !acknowledged && (criticalAlerts.length > 0 || blockingStatus)
  const newest = latestReading(iot.readings)

  const anchoredCount = ledger.events.length
  const hasLineage = lineage.columns.some((c) => c.nodes.length > 0)

  if (!kind) {
    return (
      <EmptyState
        title="Unknown batch type"
        description={`"${batchType}" is not one of raw, processing or medicine.`}
        action={
          <Link to="/dashboard" className="btn btn-outline">
            <IconArrowLeft /> Back to command center
          </Link>
        }
      />
    )
  }

  return (
    <div className="space-y-6">
      {/* ---------------- CRITICAL BANNER ---------------- */}
      {showBanner && (
        <div
          role="alert"
          className="flex flex-wrap items-start gap-3 rounded-2xl border-2 border-critical bg-critical-50 p-4 shadow-critical-glow"
        >
          <span className="mt-0.5 shrink-0 text-xl text-critical">
            <IconAlertTriangle />
          </span>
          <div className="min-w-0 flex-1">
            <h2 className="font-serif text-h4 text-critical-700">
              {criticalAlerts.length > 0
                ? `${criticalAlerts.length} critical tamper alert${criticalAlerts.length > 1 ? 's' : ''} on this batch`
                : `Batch status is ${status}`}
            </h2>
            <ul className="mt-1.5 space-y-1 text-small text-critical-700">
              {criticalAlerts.slice(0, 3).map((a) => (
                <li key={a.alert_id}>{a.message ?? a.parameter}</li>
              ))}
              {criticalAlerts.length === 0 && blockingStatus && (
                <li>
                  A failed pre-manufacturing lab test blocks this lot from becoming medicine.
                </li>
              )}
            </ul>
          </div>
          <button
            type="button"
            onClick={() => setAcknowledged(true)}
            className="btn btn-outline border-critical-300 text-critical-700 hover:border-critical hover:text-critical-800"
          >
            Acknowledge
          </button>
        </div>
      )}

      {/* ---------------- HEADER ---------------- */}
      <div>
        <Link
          to="/dashboard"
          className="inline-flex items-center gap-1.5 text-small text-neutral-600 hover:text-ink"
        >
          <IconArrowLeft /> Command center
        </Link>

        <div className="mt-3 flex flex-wrap items-end justify-between gap-4">
          <div className="min-w-0">
            <p className="text-micro font-semibold uppercase tracking-wider text-neutral-500">
              {KIND_LABEL[kind]} batch
            </p>
            <h1 className="mt-1 break-all font-mono text-h1 text-ink">{batchId}</h1>
            {loadingBatch ? (
              <Skeleton className="mt-2 h-4 w-56" />
            ) : (
              <p className="mt-1 text-body text-neutral-600">{titleOf(batch, kind) ?? '—'}</p>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {status && <StatusChip status={status} size="lg" />}
            {anchoredCount > 0 && (
              <span className="inline-flex items-center gap-2 rounded-full border border-chain-200 bg-chain-50 px-3 py-1.5 text-small font-semibold text-chain-700">
                <IconLink /> {anchoredCount} event{anchoredCount === 1 ? '' : 's'} on chain
              </span>
            )}
          </div>
        </div>
      </div>

      {batchError && (
        <EmptyState
          title={batchError.status === 404 ? 'Batch not found' : 'Could not load this batch'}
          description={
            batchError.status === 404
              ? `No ${KIND_LABEL[kind].toLowerCase()} batch with id ${batchId} exists in the database.`
              : batchError.message
          }
          action={
            <Link to="/dashboard" className="btn btn-outline">
              Back to command center
            </Link>
          }
        />
      )}

      {!batchError && (
        <div className="grid gap-6 xl:grid-cols-3">
          {/* ============ LEFT: lineage, record, lab, iot ============ */}
          <div className="space-y-6 xl:col-span-2">
            {/* ---- LINEAGE ---- */}
            <Card>
              <CardHeader
                icon={<IconRoute />}
                title="Provenance lineage"
                subtitle="Farm → raw material → processing → medicine, from batch_relationships. Every node is click-through."
              />
              <CardBody>
                {lineage.loading ? (
                  <Skeleton className="h-48 w-full rounded-xl" />
                ) : hasLineage ? (
                  <LineageGraph
                    columns={lineage.columns}
                    edges={lineage.edges}
                    currentId={batchId}
                  />
                ) : (
                  <EmptyState
                    title="No lineage recorded"
                    description="This batch has no rows in batch_relationships yet, so there is nothing upstream or downstream to draw."
                  />
                )}
              </CardBody>
            </Card>

            {/* ---- RECORD ---- */}
            <Card>
              <CardHeader title="Batch record" />
              <CardBody>
                {loadingBatch ? (
                  <SkeletonText lines={4} />
                ) : (
                  <dl className="grid gap-x-6 gap-y-4 sm:grid-cols-3">
                    <BatchFields kind={kind} batch={batch} />
                  </dl>
                )}
              </CardBody>
            </Card>

            {/* ---- LAB ---- */}
            <Card>
              <CardHeader
                icon={<IconFlask />}
                title="Laboratory verification"
                subtitle="A PASS at PRE_MANUFACTURING is what unlocks manufacturing; a FAIL blocks the lot. Both are anchored."
              />
              <CardBody>
                {lab.loading ? (
                  <SkeletonText lines={3} />
                ) : lab.tests.length === 0 ? (
                  <EmptyState
                    title="No lab tests for this batch"
                    description="Quality results are recorded against processing batches via POST /api/lab/tests."
                  />
                ) : (
                  <ul className="space-y-3">
                    {lab.tests.map((test) => (
                      <LabTestRow key={test.lab_test_id ?? test.certificate_id} test={test} />
                    ))}
                  </ul>
                )}
              </CardBody>
            </Card>

            {/* ---- IOT ---- */}
            <Card>
              <CardHeader
                icon={<IconSignal />}
                title="Live IoT evidence"
                subtitle={
                  iot.readings.length > 0
                    ? `${iot.readings.length.toLocaleString()} readings · ${iot.alerts.length} alert${iot.alerts.length === 1 ? '' : 's'}`
                    : 'Transport and storage telemetry'
                }
                actions={
                  iot.readings.length > 0 && (
                    <Link to={`/iot?batch=${encodeURIComponent(batchId)}`} className="btn btn-ghost">
                      Open monitor
                    </Link>
                  )
                }
              />
              <CardBody>
                {iot.loading ? (
                  <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                    {[0, 1, 2, 3].map((i) => (
                      <Skeleton key={i} className="h-40 rounded-2xl" />
                    ))}
                  </div>
                ) : (
                  <SensorStrip reading={newest} />
                )}
              </CardBody>
            </Card>

            {/* ---- CONSUMER REPORTS ---- */}
            {kind === KIND.MEDICINE && (
              <Card>
                <CardHeader
                  title="Consumer reports"
                  subtitle="Reports filed against this batch from the public QR page."
                />
                <CardBody>
                  {reports.loading ? (
                    <SkeletonText lines={2} />
                  ) : reports.rows.length === 0 ? (
                    <EmptyState
                      title="No consumer reports"
                      description="Nothing has been reported against this batch."
                    />
                  ) : (
                    <ul className="space-y-2">
                      {reports.rows.map((r) => (
                        <li
                          key={r.report_id}
                          className="rounded-xl border border-neutral-200 bg-surface-sunk p-3"
                        >
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <span className="font-mono text-small text-ink">{r.report_id}</span>
                            <StatusChip status={r.report_status} size="sm" />
                          </div>
                          <p className="mt-1.5 text-small text-neutral-700">
                            <span className="font-semibold">{r.issue_type}</span>
                            {r.symptoms ? ` — ${r.symptoms}` : ''}
                          </p>
                          <p className="mt-1 text-[11px] text-neutral-500">
                            {formatDate(r.reported_at)}
                          </p>
                        </li>
                      ))}
                    </ul>
                  )}
                </CardBody>
              </Card>
            )}
          </div>

          {/* ============ RIGHT: timeline ============ */}
          <div className="xl:col-span-1">
            <Card className="xl:sticky xl:top-4">
              <CardHeader
                title="Event timeline"
                subtitle="Every event for this batch, newest first. Indigo entries are anchored on the ledger and can be verified in place."
              />
              <CardBody>
                {ledger.loading || lab.loading || iot.loading || transport.loading ? (
                  <div className="space-y-4">
                    {[0, 1, 2, 3].map((i) => (
                      <div key={i} className="flex gap-3">
                        <Skeleton className="h-8 w-8 shrink-0 rounded-full" />
                        <Skeleton className="h-20 flex-1 rounded-xl" />
                      </div>
                    ))}
                  </div>
                ) : timeline.length === 0 ? (
                  <EmptyState
                    title="No events yet"
                    description="Nothing has been recorded against this batch id in the ledger, lab, IoT or transport collections."
                  />
                ) : (
                  <>
                    <div className="mb-4 flex gap-4 rounded-xl bg-surface-sunk px-3 py-2 text-[11px] text-neutral-600">
                      <span className="inline-flex items-center gap-1.5">
                        <span className="h-2 w-2 rounded-full bg-chain" /> On-chain
                      </span>
                      <span className="inline-flex items-center gap-1.5">
                        <span className="h-2 w-2 rounded-full bg-neutral-400" /> Off-chain
                      </span>
                    </div>
                    <EventTimeline entries={timeline} />
                  </>
                )}
              </CardBody>
            </Card>
          </div>
        </div>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ */

function BatchFields({ kind, batch }) {
  if (!batch) return null

  if (kind === KIND.RAW) {
    return (
      <>
        <Field label="Plant" mono>{batch.plant_id}</Field>
        <Field label="Farm" mono>{batch.farm_id}</Field>
        <Field label="Collected">{formatDate(batch.collection_date)}</Field>
        <Field label="Quantity">{formatQuantity(batch.quantity, batch.unit)}</Field>
        <Field label="Created">{formatDate(batch.created_at)}</Field>
      </>
    )
  }

  if (kind === KIND.PROCESSING) {
    return (
      <>
        <Field label="Processor" mono>{batch.processor_id}</Field>
        <Field label="Process type">{batch.processing_type}</Field>
        <Field label="Processed">{formatDate(batch.processing_date)}</Field>
        <Field label="Output">{formatQuantity(batch.output_quantity, batch.unit)}</Field>
        <Field label="Created">{formatDate(batch.created_at)}</Field>
      </>
    )
  }

  return (
    <>
      <Field label="Product">{batch.product_name}</Field>
      <Field label="Manufacturer" mono>{batch.manufacturer_id}</Field>
      <Field label="Source lot" mono>
        {batch.processing_batch_id ? (
          <Link
            to={`/batch/processing/${encodeURIComponent(batch.processing_batch_id)}`}
            className="text-chain-700 underline underline-offset-2"
          >
            {batch.processing_batch_id}
          </Link>
        ) : (
          '—'
        )}
      </Field>
      <Field label="Manufactured">{formatDate(batch.manufacturing_date)}</Field>
      <Field label="Expires">{formatDate(batch.expiry_date)}</Field>
      <Field label="QR" mono>
        {batch.qr_id ? (
          <Link
            to={`/verify/${encodeURIComponent(batch.qr_id)}`}
            className="text-chain-700 underline underline-offset-2"
          >
            {batch.qr_id}
          </Link>
        ) : (
          '—'
        )}
      </Field>
      {batch.final_lab_status && (
        <Field label="Final lab">
          <StatusChip status={batch.final_lab_status} size="sm" />
        </Field>
      )}
    </>
  )
}

function LabTestRow({ test }) {
  const parameters = asObject(test.test_parameters)
  const failed = String(test.result).toUpperCase() === 'FAIL'

  return (
    <li
      className={`rounded-xl border p-4 ${
        failed ? 'border-critical-200 bg-critical-50' : 'border-neutral-200 bg-surface-sunk'
      }`}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="font-semibold text-ink">
            {String(test.test_stage ?? '').replace(/_/g, ' ')} · {test.test_type ?? 'Quality test'}
          </p>
          <p className="mt-0.5 font-mono text-[11px] text-neutral-500">
            {test.lab_test_id ?? '—'}
            {test.lab_id ? ` · ${test.lab_id}` : ''}
            {test.certificate_id ? ` · ${test.certificate_id}` : ''}
          </p>
        </div>
        <StatusChip status={test.result} />
      </div>

      {parameters && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {Object.entries(parameters).map(([key, value]) => (
            <span
              key={key}
              className="rounded-lg border border-neutral-200 bg-surface-raised px-2 py-1 text-[11px]"
            >
              <span className="text-neutral-500">{key}</span>{' '}
              <span className="font-semibold text-ink">{String(value)}</span>
            </span>
          ))}
        </div>
      )}

      <p className="mt-3 text-[11px] text-neutral-500">
        {formatDate(test.created_at ?? test.test_date)}
        {test.verified_by ? ` · verified by ${test.verified_by}` : ''}
      </p>
    </li>
  )
}
