import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { blockchainAPI } from '../api/client'
import Card, { CardBody } from '../components/ui/Card'
import EmptyState from '../components/ui/EmptyState'
import Skeleton from '../components/ui/Skeleton'
import StatusChip from '../components/ui/StatusChip'
import TxHashChip from '../components/blockchain/TxHashChip'
import VerifyEventButton from '../components/blockchain/VerifyEventButton'
import { formatDateTime, relativeTime, truncateHash } from '../lib/format'
import { LEDGER_EVENT_TYPES, humanize, ledgerEventTone } from '../lib/status'
import {
  IconChevronDown,
  IconDatabase,
  IconRefresh,
  IconSearch,
  IconShield,
  IconShieldAlert,
  IconShieldCheck,
} from '../components/ui/Icons'

/*
 * A block explorer, deliberately shaped like one.
 *
 * Ordering is by `sequence`, never by timestamp — the backend's own contract
 * says timestamps are informational and have no tiebreak at millisecond
 * precision. The API already returns sequence DESC; nothing here re-sorts by
 * time and silently forks the view.
 */

export default function BlockchainExplorer() {
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [query, setQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState('ALL')
  const [expanded, setExpanded] = useState(null)

  const [chain, setChain] = useState({ state: 'idle', result: null, error: null })

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await blockchainAPI.listEvents()
      setEvents(Array.isArray(res?.events) ? res.events : [])
    } catch (e) {
      setError(e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const verifyChain = async () => {
    setChain({ state: 'running', result: null, error: null })
    try {
      const result = await blockchainAPI.verifyChain()
      setChain({ state: 'done', result, error: null })
    } catch (e) {
      setChain({ state: 'failed', result: null, error: e.message })
    }
  }

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return events.filter((e) => {
      if (typeFilter !== 'ALL' && e.event_type !== typeFilter) return false
      if (!q) return true
      return (
        String(e.transaction_id ?? '').toLowerCase().includes(q) ||
        String(e.entity_id ?? '').toLowerCase().includes(q) ||
        String(e.event_hash ?? '').toLowerCase().includes(q)
      )
    })
  }, [events, query, typeFilter])

  const presentTypes = useMemo(() => {
    const seen = new Set(events.map((e) => e.event_type).filter(Boolean))
    return LEDGER_EVENT_TYPES.filter((t) => seen.has(t))
  }, [events])

  const stats = useMemo(() => {
    const highest = events.reduce((max, e) => Math.max(max, Number(e.sequence) || 0), 0)
    const newest = events[0] ?? null // API returns sequence DESC
    const tamper = events.filter((e) => e.event_type === 'TAMPER_EVENT').length
    return { highest, newest, tamper }
  }, [events])

  return (
    <div className="space-y-6">
      {/* ---------------- HEADER ---------------- */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-serif text-h1 text-ink">Blockchain explorer</h1>
          <p className="mt-1 max-w-2xl text-body text-neutral-600">
            Append-only SHA-256 hash chain. Each event carries the fingerprint of the one before it,
            so any edit, deletion or reorder leaves a mark the verifier can find.
          </p>
        </div>

        <button
          type="button"
          onClick={verifyChain}
          disabled={chain.state === 'running'}
          className="btn btn-chain px-6 py-3 text-body"
        >
          {chain.state === 'running' ? (
            <>
              <span className="spinner" aria-hidden="true" /> Walking the chain…
            </>
          ) : (
            <>
              <IconShield /> Verify entire chain
            </>
          )}
        </button>
      </div>

      {/* ---------------- VERDICT ---------------- */}
      <AnimatePresence mode="wait">
        {chain.state !== 'idle' && chain.state !== 'running' && (
          <ChainVerdict
            key={chain.state}
            state={chain.state}
            result={chain.result}
            error={chain.error}
            onDismiss={() => setChain({ state: 'idle', result: null, error: null })}
          />
        )}
      </AnimatePresence>

      {/* ---------------- STATS ---------------- */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat
          label="Events loaded"
          value={loading ? null : events.length.toLocaleString()}
          hint={events.length >= 500 ? 'API caps this list at 500' : 'Newest first'}
        />
        <Stat label="Highest sequence" value={loading ? null : `#${stats.highest}`} hint="Atomic counter" />
        <Stat
          label="Latest transaction"
          value={loading ? null : (stats.newest?.transaction_id ?? '—')}
          hint={loading ? null : relativeTime(stats.newest?.timestamp)}
          mono
        />
        <Stat
          label="Tamper events"
          value={loading ? null : stats.tamper.toLocaleString()}
          hint="CRITICAL alerts only"
          tone={stats.tamper > 0 ? 'critical' : undefined}
        />
      </div>

      {/* ---------------- CONTROLS ---------------- */}
      <Card>
        <CardBody className="flex flex-wrap items-center gap-3">
          <div className="relative min-w-[240px] flex-1">
            <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400">
              <IconSearch />
            </span>
            <label htmlFor="ledger-search" className="sr-only">
              Search by transaction id, entity id or hash
            </label>
            <input
              id="ledger-search"
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Transaction id, entity id or hash…"
              className="input-field pl-9"
            />
          </div>

          <div>
            <label htmlFor="ledger-type" className="sr-only">
              Filter by event type
            </label>
            <select
              id="ledger-type"
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="input-field"
            >
              <option value="ALL">All event types</option>
              {presentTypes.map((t) => (
                <option key={t} value={t}>
                  {humanize(t)}
                </option>
              ))}
            </select>
          </div>

          <button type="button" onClick={load} className="btn btn-outline">
            <IconRefresh /> Reload
          </button>
        </CardBody>
      </Card>

      {/* ---------------- LIST ---------------- */}
      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-[68px] w-full rounded-xl" />
          ))}
        </div>
      ) : error ? (
        <EmptyState
          icon={<IconShieldAlert />}
          title="Could not reach the ledger"
          description={`${error.message}. Start the backend and reload.`}
          action={
            <button type="button" onClick={load} className="btn btn-outline">
              <IconRefresh /> Try again
            </button>
          }
        />
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={<IconDatabase />}
          title={events.length === 0 ? 'No anchored events yet' : 'Nothing matches those filters'}
          description={
            events.length === 0
              ? 'Create a batch, record a lab result or trigger a tamper event and it appears here immediately.'
              : 'Clear the search or pick a different event type.'
          }
          action={
            events.length > 0 && (
              <button
                type="button"
                onClick={() => {
                  setQuery('')
                  setTypeFilter('ALL')
                }}
                className="btn btn-outline"
              >
                Clear filters
              </button>
            )
          }
        />
      ) : (
        <div className="overflow-hidden rounded-2xl border border-neutral-200 bg-surface-raised">
          <div className="hidden border-b border-neutral-200 bg-surface-sunk px-4 py-2.5 text-micro font-semibold uppercase tracking-wider text-neutral-500 lg:grid lg:grid-cols-[64px_170px_1fr_1fr_150px_40px] lg:gap-3">
            <span>Seq</span>
            <span>Transaction</span>
            <span>Event</span>
            <span>Entity</span>
            <span>Timestamp</span>
            <span className="sr-only">Expand</span>
          </div>

          <ul className="divide-y divide-neutral-200">
            {filtered.map((event) => (
              <EventRow
                key={event.transaction_id ?? event.sequence}
                event={event}
                expanded={expanded === event.transaction_id}
                onToggle={() =>
                  setExpanded((cur) =>
                    cur === event.transaction_id ? null : event.transaction_id,
                  )
                }
              />
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ */

function Stat({ label, value, hint, mono, tone }) {
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
        <Skeleton className="mt-2 h-7 w-24" />
      ) : (
        <p
          className={`mt-1.5 truncate text-h3 ${mono ? 'font-mono text-h4' : 'font-serif'} ${
            tone === 'critical' ? 'text-critical-700' : 'text-ink'
          }`}
          title={String(value)}
        >
          {value}
        </p>
      )}
      {hint && <p className="mt-1 text-[11px] text-neutral-500">{hint}</p>}
    </div>
  )
}

function ChainVerdict({ state, result, error, onDismiss }) {
  const failed = state === 'failed'
  const valid = !failed && result?.valid === true

  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.25 }}
      role="status"
      aria-live="polite"
      className={`flex flex-wrap items-start gap-4 rounded-2xl border-2 p-5 ${
        valid
          ? 'border-verified bg-verified-50'
          : 'border-critical bg-critical-50 shadow-critical-glow'
      }`}
    >
      <span className={`text-3xl ${valid ? 'text-verified' : 'text-critical'}`}>
        {valid ? <IconShieldCheck /> : <IconShieldAlert />}
      </span>

      <div className="min-w-0 flex-1">
        <h2
          className={`font-serif text-h2 ${valid ? 'text-verified-700' : 'text-critical-700'}`}
        >
          {failed
            ? 'Verification could not run'
            : valid
              ? 'Chain integrity verified'
              : 'Chain broken'}
        </h2>

        {failed ? (
          <p className="mt-1 text-body text-critical-700">{error}</p>
        ) : valid ? (
          <p className="mt-1 text-body text-verified-700">
            <strong className="font-mono">{Number(result.checked).toLocaleString()}</strong> events
            walked in sequence order. Every hash recomputed from its own contents, and every event
            links to its true predecessor.
          </p>
        ) : (
          <div className="mt-1 space-y-2 text-body text-critical-700">
            <p>
              Walked <strong className="font-mono">{Number(result?.checked ?? 0).toLocaleString()}</strong>{' '}
              events before the break.
            </p>
            {result?.broken_at && (
              <p className="font-mono text-small">Broken at {result.broken_at}</p>
            )}
            {result?.reason && (
              <p className="rounded-lg bg-critical-100 p-2.5 text-small">{result.reason}</p>
            )}
          </div>
        )}
      </div>

      <button type="button" onClick={onDismiss} className="btn btn-ghost">
        Dismiss
      </button>
    </motion.div>
  )
}

function EventRow({ event, expanded, onToggle }) {
  const tone = ledgerEventTone(event.event_type)

  return (
    <li className={expanded ? 'bg-chain-50/40' : ''}>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        className="grid w-full grid-cols-1 items-center gap-2 px-4 py-3 text-left hover:bg-surface-sunk focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-chain-400 lg:grid-cols-[64px_170px_1fr_1fr_150px_40px] lg:gap-3"
      >
        <span className="font-mono text-small text-neutral-500">#{event.sequence}</span>

        <span className="truncate font-mono text-small font-semibold text-chain-700">
          {event.transaction_id}
        </span>

        <span className="min-w-0">
          <StatusChip status={event.event_type} label={humanize(event.event_type)} tone={tone} size="sm" />
        </span>

        <span className="min-w-0 truncate font-mono text-small text-ink" title={event.entity_id}>
          {event.entity_id}
          {event.entity_type && (
            <span className="ml-2 text-[10px] uppercase tracking-wider text-neutral-400">
              {event.entity_type}
            </span>
          )}
        </span>

        <time
          className="text-[11px] text-neutral-500"
          dateTime={event.timestamp || undefined}
          title={formatDateTime(event.timestamp)}
        >
          {relativeTime(event.timestamp)}
        </time>

        <span
          className={`hidden justify-self-end text-neutral-400 transition-transform lg:block ${
            expanded ? 'rotate-180' : ''
          }`}
          aria-hidden="true"
        >
          <IconChevronDown />
        </span>
      </button>

      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22 }}
            className="overflow-hidden"
          >
            <div className="grid gap-5 border-t border-chain-100 px-4 py-4 lg:grid-cols-2">
              <div className="space-y-3">
                <div>
                  <p className="text-micro font-semibold uppercase tracking-wider text-neutral-500">
                    Previous hash
                  </p>
                  <p className="mt-1 break-all font-mono text-[11px] text-neutral-600">
                    {event.previous_hash || 'GENESIS'}
                  </p>
                </div>
                <div>
                  <p className="text-micro font-semibold uppercase tracking-wider text-neutral-500">
                    This event&apos;s hash
                  </p>
                  <p className="mt-1 break-all font-mono text-[11px] text-ink">{event.event_hash}</p>
                </div>

                <div className="flex flex-wrap items-center gap-2 pt-1">
                  <TxHashChip value={event.transaction_id} label="Transaction" truncate={false} />
                  {event.entity_id && (
                    <Link
                      to={`/trace?q=${encodeURIComponent(event.entity_id)}`}
                      className="btn btn-ghost text-small"
                    >
                      Trace {truncateHash(event.entity_id, 12, 4)}
                    </Link>
                  )}
                </div>

                <VerifyEventButton
                  transactionId={event.transaction_id}
                  storedHash={event.event_hash}
                />
              </div>

              <div>
                <p className="mb-1 text-micro font-semibold uppercase tracking-wider text-neutral-500">
                  Event payload
                </p>
                <pre className="max-h-72 overflow-auto rounded-xl bg-ink p-3 font-mono text-[11px] leading-relaxed text-neutral-100">
                  {JSON.stringify(event.event_data ?? {}, null, 2)}
                </pre>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </li>
  )
}
