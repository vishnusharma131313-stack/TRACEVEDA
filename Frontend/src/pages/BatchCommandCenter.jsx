import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { batchAPI, medicineAPI } from '../api/client'
import Card, { CardBody } from '../components/ui/Card'
import EmptyState from '../components/ui/EmptyState'
import Skeleton from '../components/ui/Skeleton'
import StatusChip from '../components/ui/StatusChip'
import { KIND, KIND_LABEL, batchPath, normalizeList } from '../lib/batches'
import { formatDate, formatQuantity } from '../lib/format'
import {
  IconAlertTriangle,
  IconChevronRight,
  IconFlask,
  IconLeaf,
  IconPill,
  IconRefresh,
  IconSearch,
} from '../components/ui/Icons'

/*
 * The list view. Its only job is to get a judge into Batch Detail fast, so
 * filtering is instant and every card is a link.
 *
 * Status options are derived from the data that actually loaded rather than
 * hardcoded — the live API writes CREATED / APPROVED_FOR_MANUFACTURING /
 * BLOCKED / RELEASED while the seeded dataset ships VERIFIED / COMPLETED, and
 * a hardcoded list would silently hide half the rows.
 */

const KIND_ICON = {
  [KIND.RAW]: <IconLeaf />,
  [KIND.PROCESSING]: <IconFlask />,
  [KIND.MEDICINE]: <IconPill />,
}

const KIND_ACCENT = {
  [KIND.RAW]: 'border-l-verified',
  [KIND.PROCESSING]: 'border-l-chain',
  [KIND.MEDICINE]: 'border-l-alert',
}

export default function BatchCommandCenter() {
  const [state, setState] = useState({ loading: true, batches: [], failures: [] })
  const [kindFilter, setKindFilter] = useState('ALL')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [query, setQuery] = useState('')

  const load = useCallback(async () => {
    setState((s) => ({ ...s, loading: true }))

    const [raw, processing, medicine] = await Promise.allSettled([
      batchAPI.listRaw(),
      batchAPI.listProcessing(),
      medicineAPI.list(),
    ])

    const batches = []
    const failures = []

    const collect = (result, kind) => {
      if (result.status === 'fulfilled') {
        batches.push(...normalizeList(result.value, kind))
      } else {
        failures.push({ kind, message: result.reason?.message ?? 'Request failed' })
      }
    }

    collect(raw, KIND.RAW)
    collect(processing, KIND.PROCESSING)
    collect(medicine, KIND.MEDICINE)

    batches.sort((a, b) => {
      const ta = a.createdAt ? new Date(a.createdAt).getTime() : 0
      const tb = b.createdAt ? new Date(b.createdAt).getTime() : 0
      return tb - ta
    })

    setState({ loading: false, batches, failures })
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const statuses = useMemo(() => {
    const set = new Set(state.batches.map((b) => b.status).filter(Boolean))
    return Array.from(set).sort()
  }, [state.batches])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return state.batches.filter((b) => {
      if (kindFilter !== 'ALL' && b.kind !== kindFilter) return false
      if (statusFilter !== 'ALL' && b.status !== statusFilter) return false
      if (!q) return true
      return (
        b.id.toLowerCase().includes(q) || String(b.title ?? '').toLowerCase().includes(q)
      )
    })
  }, [state.batches, kindFilter, statusFilter, query])

  const counts = useMemo(() => {
    const by = (kind) => state.batches.filter((b) => b.kind === kind).length
    const blocked = state.batches.filter((b) =>
      ['BLOCKED', 'FAIL', 'CRITICAL'].includes(String(b.status ?? '').toUpperCase()),
    ).length
    return {
      total: state.batches.length,
      raw: by(KIND.RAW),
      processing: by(KIND.PROCESSING),
      medicine: by(KIND.MEDICINE),
      blocked,
    }
  }, [state.batches])

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-serif text-h1 text-ink">Batch command center</h1>
          <p className="mt-1 text-body text-neutral-600">
            Every raw material, processing and medicine batch in the system.
          </p>
        </div>
        <button type="button" onClick={load} className="btn btn-outline">
          <IconRefresh /> Refresh
        </button>
      </div>

      {/* ---- partial-failure notice: never silently show a short list ---- */}
      {state.failures.length > 0 && (
        <div
          role="alert"
          className="flex items-start gap-2.5 rounded-2xl border border-alert-200 bg-alert-50 p-4 text-small text-alert-700"
        >
          <span className="mt-0.5 shrink-0">
            <IconAlertTriangle />
          </span>
          <p>
            <strong>This list is incomplete.</strong>{' '}
            {state.failures
              .map((f) => `${KIND_LABEL[f.kind]} batches failed to load (${f.message})`)
              .join('; ')}
            .
          </p>
        </div>
      )}

      {/* ---- stats ---- */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Total batches" value={state.loading ? null : counts.total} />
        <Stat
          label="Raw · processing · medicine"
          value={
            state.loading ? null : `${counts.raw} · ${counts.processing} · ${counts.medicine}`
          }
        />
        <Stat
          label="Blocked"
          value={state.loading ? null : counts.blocked}
          tone={counts.blocked > 0 ? 'critical' : undefined}
          hint="Failed pre-manufacturing lab test"
        />
        <Stat label="Showing" value={state.loading ? null : filtered.length} hint="After filters" />
      </div>

      {/* ---- controls ---- */}
      <Card>
        <CardBody className="flex flex-wrap items-center gap-3">
          <div
            className="flex flex-wrap gap-1 rounded-xl bg-surface-sunk p-1"
            role="group"
            aria-label="Filter by batch type"
          >
            {[
              ['ALL', 'All'],
              [KIND.RAW, 'Raw material'],
              [KIND.PROCESSING, 'Processing'],
              [KIND.MEDICINE, 'Medicine'],
            ].map(([value, label]) => (
              <button
                key={value}
                type="button"
                onClick={() => setKindFilter(value)}
                aria-pressed={kindFilter === value}
                className={`rounded-lg px-3 py-1.5 text-small font-semibold transition-colors ${
                  kindFilter === value
                    ? 'bg-surface-raised text-ink shadow-card'
                    : 'text-neutral-600 hover:text-ink'
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          <div className="relative min-w-[220px] flex-1">
            <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400">
              <IconSearch />
            </span>
            <label htmlFor="batch-search" className="sr-only">
              Search batches
            </label>
            <input
              id="batch-search"
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Batch id or product…"
              className="input-field pl-9"
            />
          </div>

          <div>
            <label htmlFor="batch-status" className="sr-only">
              Filter by status
            </label>
            <select
              id="batch-status"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="input-field"
            >
              <option value="ALL">All statuses</option>
              {statuses.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
        </CardBody>
      </Card>

      {/* ---- grid ---- */}
      {state.loading ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-[152px] rounded-2xl" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          title={state.batches.length === 0 ? 'No batches in the database' : 'Nothing matches'}
          description={
            state.batches.length === 0
              ? 'Load the master dataset with `python import_csv.py`, or create a batch through the API.'
              : 'Try a different type, status or search term.'
          }
          action={
            state.batches.length > 0 && (
              <button
                type="button"
                onClick={() => {
                  setQuery('')
                  setKindFilter('ALL')
                  setStatusFilter('ALL')
                }}
                className="btn btn-outline"
              >
                Clear filters
              </button>
            )
          }
        />
      ) : (
        <motion.ul
          className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3"
          initial="hidden"
          animate="show"
          variants={{ show: { transition: { staggerChildren: 0.03 } } }}
        >
          {filtered.map((batch) => (
            <motion.li
              key={`${batch.kind}-${batch.id}`}
              variants={{ hidden: { opacity: 0, y: 10 }, show: { opacity: 1, y: 0 } }}
            >
              <Link
                to={batchPath(batch.kind, batch.id)}
                className={`group flex h-full flex-col rounded-2xl border border-neutral-200 border-l-[3px] bg-surface-raised p-4 shadow-card transition-all hover:-translate-y-0.5 hover:shadow-card-hover focus:outline-none focus-visible:ring-2 focus-visible:ring-chain-400 ${KIND_ACCENT[batch.kind]}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="inline-flex items-center gap-1.5 text-micro font-semibold uppercase tracking-wider text-neutral-500">
                    {KIND_ICON[batch.kind]} {batch.kindLabel}
                  </span>
                  {batch.status && <StatusChip status={batch.status} size="sm" />}
                </div>

                <p className="mt-2.5 break-all font-mono text-h4 text-ink">{batch.id}</p>
                <p className="mt-1 line-clamp-2 text-small text-neutral-600">
                  {batch.title ?? '—'}
                </p>

                <div className="mt-auto flex items-end justify-between gap-2 pt-4">
                  <div className="text-[11px] text-neutral-500">
                    {batch.quantity !== null && (
                      <div>{formatQuantity(batch.quantity, batch.unit)}</div>
                    )}
                    <div>{formatDate(batch.createdAt)}</div>
                  </div>
                  <span className="inline-flex items-center gap-1 text-small font-semibold text-neutral-400 transition-colors group-hover:text-chain-700">
                    Open <IconChevronRight />
                  </span>
                </div>
              </Link>
            </motion.li>
          ))}
        </motion.ul>
      )}
    </div>
  )
}

function Stat({ label, value, hint, tone }) {
  return (
    <div
      className={`rounded-2xl border p-4 ${
        tone === 'critical'
          ? 'border-critical-200 bg-critical-50'
          : 'border-neutral-200 bg-surface-raised'
      }`}
    >
      <p className="text-micro font-semibold uppercase tracking-wider text-neutral-500">{label}</p>
      {value === null ? (
        <Skeleton className="mt-2 h-7 w-20" />
      ) : (
        <p
          className={`mt-1.5 font-serif text-h2 ${
            tone === 'critical' ? 'text-critical-700' : 'text-ink'
          }`}
        >
          {value}
        </p>
      )}
      {hint && <p className="mt-1 text-[11px] text-neutral-500">{hint}</p>}
    </div>
  )
}
