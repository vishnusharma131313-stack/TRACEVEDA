import { useCallback, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import { traceAPI } from '../api/client'
import Card, { CardBody, CardHeader } from '../components/ui/Card'
import EmptyState from '../components/ui/EmptyState'
import Skeleton from '../components/ui/Skeleton'
import StatusChip from '../components/ui/StatusChip'
import LineageGraph, {
  buildForwardLineage,
  buildReverseLineage,
} from '../components/trace/LineageGraph'
import { KIND, batchPath } from '../lib/batches'
import { formatDate } from '../lib/format'
import {
  IconAlertTriangle,
  IconArrowLeft,
  IconArrowRight,
  IconPill,
  IconRoute,
  IconSearch,
} from '../components/ui/Icons'

/*
 * Reverse trace and recall simulation, side by side.
 *
 *   REVERSE  medicine -> processing -> raw -> farm     "where did this come from"
 *   RECALL   raw      -> processing -> medicines       "what else is affected"
 *
 * The recall mode is the dossier's Section 8 beat — Incident, Detection,
 * Investigation, Action — so the screen is laid out in that order and the
 * presenter's narration and the screen advance together.
 *
 * Endpoint constraint, enforced in the UI rather than discovered at runtime:
 * /trace/reverse only accepts a MEDICINE id and /trace/forward only accepts a
 * RAW id. Each mode says which id it wants.
 */

const MODES = {
  reverse: {
    label: 'Reverse trace',
    caption: 'Medicine → farm',
    placeholder: 'Medicine batch id, e.g. MED-2026-001',
    cta: 'Trace to origin',
  },
  recall: {
    label: 'Recall simulator',
    caption: 'Raw material → every affected product',
    placeholder: 'Raw batch id, e.g. ASH-2026-001',
    cta: 'Analyse impact',
  },
}

export default function TraceRecall() {
  const [params, setParams] = useSearchParams()
  const [mode, setMode] = useState(params.get('mode') === 'recall' ? 'recall' : 'reverse')
  const [input, setInput] = useState(params.get('q') ?? '')
  const [state, setState] = useState({ status: 'idle', data: null, error: null })

  const run = useCallback(async (nextMode, id) => {
    const trimmed = id.trim()
    if (!trimmed) return
    setState({ status: 'loading', data: null, error: null })
    try {
      if (nextMode === 'reverse') {
        const trace = await traceAPI.reverse(trimmed)
        setState({ status: 'done', data: { trace }, error: null })
      } else {
        const [trace, impact] = await Promise.all([
          traceAPI.forward(trimmed),
          traceAPI.impact(trimmed),
        ])
        setState({ status: 'done', data: { trace, impact }, error: null })
      }
    } catch (e) {
      setState({ status: 'error', data: null, error: e })
    }
  }, [])

  /* Deep links from the explorer and batch detail land here ready to run. */
  useEffect(() => {
    const q = params.get('q')
    if (q) run(params.get('mode') === 'recall' ? 'recall' : 'reverse', q)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const submit = (e) => {
    e.preventDefault()
    setParams({ mode, q: input.trim() }, { replace: true })
    run(mode, input)
  }

  const switchMode = (next) => {
    setMode(next)
    setState({ status: 'idle', data: null, error: null })
    setInput('')
    setParams({ mode: next }, { replace: true })
  }

  const config = MODES[mode]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-serif text-h1 text-ink">Trace &amp; recall</h1>
        <p className="mt-1 max-w-3xl text-body text-neutral-600">
          A contamination report names one product. Traceability turns that into the exact set of
          batches to pull — and nothing more.
        </p>
      </div>

      {/* ---- mode switch ---- */}
      <div className="grid gap-3 sm:grid-cols-2">
        {Object.entries(MODES).map(([key, m]) => {
          const active = mode === key
          const recall = key === 'recall'
          return (
            <button
              key={key}
              type="button"
              onClick={() => switchMode(key)}
              aria-pressed={active}
              className={`rounded-2xl border-2 p-4 text-left transition-all ${
                active
                  ? recall
                    ? 'border-critical bg-critical-50'
                    : 'border-verified bg-verified-50'
                  : 'border-neutral-200 bg-surface-raised hover:border-neutral-300'
              }`}
            >
              <span
                className={`inline-flex items-center gap-2 font-serif text-h4 ${
                  active ? (recall ? 'text-critical-700' : 'text-verified-700') : 'text-ink'
                }`}
              >
                {recall ? <IconAlertTriangle /> : <IconArrowLeft />}
                {m.label}
              </span>
              <p className="mt-1 text-small text-neutral-600">{m.caption}</p>
            </button>
          )
        })}
      </div>

      {/* ---- search ---- */}
      <Card>
        <CardBody>
          <form onSubmit={submit} className="flex flex-wrap items-center gap-3">
            <div className="relative min-w-[260px] flex-1">
              <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400">
                <IconSearch />
              </span>
              <label htmlFor="trace-input" className="sr-only">
                {config.placeholder}
              </label>
              <input
                id="trace-input"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={config.placeholder}
                className="input-field pl-9 font-mono"
                autoComplete="off"
              />
            </div>
            <button
              type="submit"
              disabled={!input.trim() || state.status === 'loading'}
              className={mode === 'recall' ? 'btn btn-danger' : 'btn btn-primary'}
            >
              {state.status === 'loading' ? (
                <>
                  <span className="spinner" aria-hidden="true" /> Tracing…
                </>
              ) : (
                <>
                  {config.cta} <IconArrowRight />
                </>
              )}
            </button>
          </form>
          <p className="mt-2 text-[11px] text-neutral-500">
            {mode === 'reverse'
              ? 'Reverse trace accepts a medicine batch id only.'
              : 'Forward trace and impact analysis accept a raw material batch id only.'}
          </p>
        </CardBody>
      </Card>

      {/* ---- results ---- */}
      {state.status === 'loading' && (
        <Card>
          <CardBody>
            <Skeleton className="h-56 w-full rounded-xl" />
          </CardBody>
        </Card>
      )}

      {state.status === 'error' && (
        <EmptyState
          icon={<IconAlertTriangle />}
          title={state.error?.status === 404 ? 'Not found' : 'Trace failed'}
          description={
            state.error?.status === 404
              ? mode === 'reverse'
                ? `No medicine batch with id "${input.trim()}". Reverse trace only accepts medicine ids.`
                : `No raw material batch with id "${input.trim()}". Forward trace only accepts raw ids.`
              : state.error?.message
          }
        />
      )}

      {state.status === 'idle' && (
        <EmptyState
          icon={<IconRoute />}
          title="Enter a batch id to begin"
          description={
            mode === 'reverse'
              ? 'The reverse trace walks batch_relationships back from a finished medicine to the farms that supplied it.'
              : 'Impact analysis walks forward from one raw batch to every medicine batch it reached.'
          }
        />
      )}

      {state.status === 'done' && mode === 'reverse' && <ReverseResult trace={state.data.trace} />}
      {state.status === 'done' && mode === 'recall' && (
        <RecallResult trace={state.data.trace} impact={state.data.impact} rawId={input.trim()} />
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ */

function ReverseResult({ trace }) {
  const graph = buildReverseLineage(trace)
  const medicine = trace?.medicine_batch
  const raws = Array.isArray(trace?.raw_batches) ? trace.raw_batches : []

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader
          icon={<IconPill />}
          title={medicine?.product_name ?? medicine?.medicine_batch_id ?? 'Medicine batch'}
          subtitle={`${medicine?.medicine_batch_id ?? ''} traced back through processing to origin`}
          actions={medicine?.batch_status && <StatusChip status={medicine.batch_status} size="lg" />}
        />
        <CardBody>
          {graph.columns.some((c) => c.nodes.length > 0) ? (
            <LineageGraph columns={graph.columns} edges={graph.edges} currentId={medicine?.medicine_batch_id} />
          ) : (
            <EmptyState
              title="No upstream lineage"
              description="This medicine batch has no batch_relationships rows linking it to raw material."
            />
          )}
        </CardBody>
      </Card>

      {raws.length > 0 && (
        <Card>
          <CardHeader
            title={`${raws.length} source batch${raws.length === 1 ? '' : 'es'}`}
            subtitle="Origin of the raw material that went into this product"
          />
          <CardBody>
            <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {raws.map(({ raw_batch: raw, farm }) => (
                <li
                  key={raw.raw_batch_id}
                  className="rounded-xl border border-neutral-200 bg-surface-sunk p-3.5"
                >
                  <Link
                    to={batchPath(KIND.RAW, raw.raw_batch_id)}
                    className="font-mono text-small font-semibold text-chain-700 underline underline-offset-2"
                  >
                    {raw.raw_batch_id}
                  </Link>
                  <dl className="mt-2 space-y-1 text-[11px] text-neutral-600">
                    <div>
                      <span className="text-neutral-500">Farm </span>
                      <span className="font-medium text-ink">
                        {farm?.farm_name ?? raw.farm_id ?? '—'}
                      </span>
                    </div>
                    {(farm?.district || farm?.state) && (
                      <div>
                        <span className="text-neutral-500">Region </span>
                        <span className="text-ink">
                          {[farm?.district, farm?.state].filter(Boolean).join(', ')}
                        </span>
                      </div>
                    )}
                    <div>
                      <span className="text-neutral-500">Plant </span>
                      <span className="font-mono text-ink">{raw.plant_id ?? '—'}</span>
                    </div>
                    <div>
                      <span className="text-neutral-500">Collected </span>
                      <span className="text-ink">{formatDate(raw.collection_date)}</span>
                    </div>
                  </dl>
                </li>
              ))}
            </ul>
          </CardBody>
        </Card>
      )}
    </div>
  )
}

function RecallResult({ trace, impact, rawId }) {
  const affected = Array.isArray(impact?.affected_medicine_batches)
    ? impact.affected_medicine_batches
    : []
  const count = impact?.affected_count ?? affected.length
  const graph = buildForwardLineage(trace, { criticalEdges: count > 0 })

  return (
    <div className="space-y-5">
      {/* ---- ACTION: the headline a regulator acts on ---- */}
      <motion.div
        initial={{ opacity: 0, y: -6 }}
        animate={{ opacity: 1, y: 0 }}
        className={`rounded-2xl border-2 p-5 ${
          count > 0
            ? 'border-critical bg-critical-50 shadow-critical-glow'
            : 'border-verified bg-verified-50'
        }`}
        role="status"
      >
        <div className="flex flex-wrap items-start gap-4">
          <span className={`text-3xl ${count > 0 ? 'text-critical' : 'text-verified'}`}>
            <IconAlertTriangle />
          </span>
          <div className="min-w-0 flex-1">
            <h2
              className={`font-serif text-h2 ${count > 0 ? 'text-critical-700' : 'text-verified-700'}`}
            >
              {count > 0
                ? `${count} medicine batch${count === 1 ? '' : 'es'} affected`
                : 'No downstream products affected'}
            </h2>
            <p className={`mt-1 text-body ${count > 0 ? 'text-critical-700' : 'text-verified-700'}`}>
              {count > 0 ? (
                <>
                  Recalling <span className="font-mono">{rawId}</span> means pulling exactly these{' '}
                  {count} batches — not the whole product line.
                </>
              ) : (
                <>
                  <span className="font-mono">{rawId}</span> has not reached any finished medicine
                  batch yet, so there is nothing on shelves to recall.
                </>
              )}
            </p>
          </div>
        </div>
      </motion.div>

      {/* ---- INVESTIGATION: the fan-out, drawn ---- */}
      <Card>
        <CardHeader
          icon={<IconRoute />}
          title="Downstream impact"
          subtitle="Forward trace from the implicated raw batch through every processing lot it fed"
        />
        <CardBody>
          {graph.columns.some((c) => c.nodes.length > 0) ? (
            <LineageGraph columns={graph.columns} edges={graph.edges} currentId={rawId} />
          ) : (
            <EmptyState
              title="No downstream lineage"
              description="This raw batch has no batch_relationships rows, so it has not entered processing yet."
            />
          )}
        </CardBody>
      </Card>

      {/* ---- the actionable list ---- */}
      {affected.length > 0 && (
        <Card>
          <CardHeader
            title="Batches to recall"
            subtitle="Every finished product containing material from this raw batch"
          />
          <CardBody>
            <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {affected.map((medicine) => (
                <li
                  key={medicine.medicine_batch_id}
                  className="rounded-xl border-2 border-critical-200 bg-critical-50 p-3.5"
                >
                  <div className="flex items-start justify-between gap-2">
                    <Link
                      to={batchPath(KIND.MEDICINE, medicine.medicine_batch_id)}
                      className="font-mono text-small font-bold text-critical-700 underline underline-offset-2"
                    >
                      {medicine.medicine_batch_id}
                    </Link>
                    {medicine.batch_status && (
                      <StatusChip status={medicine.batch_status} size="sm" />
                    )}
                  </div>
                  <p className="mt-1.5 text-small font-medium text-ink">{medicine.product_name}</p>
                  <p className="mt-1 text-[11px] text-neutral-600">
                    Mfd {formatDate(medicine.manufacturing_date)} · Exp{' '}
                    {formatDate(medicine.expiry_date)}
                  </p>
                  {medicine.qr_id && (
                    <Link
                      to={`/verify/${encodeURIComponent(medicine.qr_id)}`}
                      className="mt-2 inline-block font-mono text-[11px] text-chain-700 underline underline-offset-2"
                    >
                      {medicine.qr_id}
                    </Link>
                  )}
                </li>
              ))}
            </ul>
          </CardBody>
        </Card>
      )}
    </div>
  )
}
