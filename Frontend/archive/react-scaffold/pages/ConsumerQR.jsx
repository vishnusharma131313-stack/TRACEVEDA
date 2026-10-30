import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import { consumerAPI, medicineAPI, traceAPI } from '../api/client'
import {
  IconAlertTriangle,
  IconCheck,
  IconFactory,
  IconFlask,
  IconLeaf,
  IconPill,
  IconQr,
  IconSearch,
  IconShieldCheck,
  IconX,
} from '../components/ui/Icons'
import { formatDate } from '../lib/format'

/*
 * PUBLIC CONSUMER VIEW — no login, mobile first.
 *
 * A deliberately different visual register from the internal tools: bigger
 * type, far more whitespace, no internal ids, no logistics detail, no ledger
 * jargon. The dossier's privacy rule is enforced here in what is NOT shown —
 * the consumer sees the farm's region, never the farm id, batch relationships
 * or transport records.
 *
 * Accessibility is treated as a requirement on this screen specifically: it is
 * the one page the public reaches, and it is an easy, visible point to lose.
 */

export default function ConsumerQR() {
  const { qrId } = useParams()
  const navigate = useNavigate()

  const [state, setState] = useState({ status: 'idle', data: null, error: null })
  const [journey, setJourney] = useState(null)
  const [input, setInput] = useState('')
  const headingRef = useRef(null)

  const lookup = useCallback(async (id) => {
    setState({ status: 'loading', data: null, error: null })
    setJourney(null)
    try {
      const result = await medicineAPI.verifyQr(id)
      setState({ status: 'done', data: result, error: null })

      /* The journey is a second, optional call — a failure here must not
       * turn a successful verification into an error screen. */
      if (result?.verified && result?.medicine_batch_id) {
        traceAPI
          .reverse(result.medicine_batch_id)
          .then(setJourney)
          .catch(() => setJourney(null))
      }
    } catch (e) {
      setState({ status: 'error', data: null, error: e })
    }
  }, [])

  useEffect(() => {
    if (qrId) lookup(qrId)
    else setState({ status: 'idle', data: null, error: null })
  }, [qrId, lookup])

  /* Move focus to the verdict so a screen-reader user is told the outcome. */
  useEffect(() => {
    if (state.status === 'done' && headingRef.current) headingRef.current.focus()
  }, [state.status])

  return (
    <div className="min-h-screen bg-surface">
      <header className="border-b border-neutral-200 bg-surface-raised">
        <div className="mx-auto flex max-w-2xl items-center gap-3 px-5 py-4">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-verified text-lg text-white">
            <IconLeaf />
          </span>
          <div>
            <p className="font-serif text-h4 leading-none text-ink">TraceVeda</p>
            <p className="mt-0.5 text-[11px] uppercase tracking-[0.12em] text-neutral-500">
              Verify your medicine
            </p>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-2xl px-5 py-8 pb-20">
        {state.status === 'idle' && <Lookup input={input} setInput={setInput} navigate={navigate} />}

        {state.status === 'loading' && (
          <div className="space-y-4" role="status" aria-live="polite">
            <span className="sr-only">Verifying</span>
            <div className="skeleton h-40 w-full rounded-3xl" />
            <div className="skeleton h-24 w-full rounded-2xl" />
            <div className="skeleton h-48 w-full rounded-2xl" />
          </div>
        )}

        {state.status === 'error' && (
          <Verdict
            ok={false}
            headingRef={headingRef}
            title="We couldn't check this code"
            body={
              state.error?.status === 404
                ? 'This QR code is not in our records.'
                : 'We could not reach the verification service. Please try again in a moment.'
            }
            action={
              <button type="button" onClick={() => lookup(qrId)} className="btn btn-outline">
                Try again
              </button>
            }
          />
        )}

        {state.status === 'done' && state.data?.verified === false && (
          <Verdict
            ok={false}
            headingRef={headingRef}
            title="Not verified"
            body="This code does not match any medicine batch we hold. Do not consume the product, and please report it to your pharmacist."
            action={<ReportLink qrId={qrId} />}
          />
        )}

        {state.status === 'done' && state.data?.verified === true && (
          <VerifiedProduct data={state.data} journey={journey} qrId={qrId} />
        )}
      </main>
    </div>
  )
}

/* ------------------------------------------------------------------ */

function Lookup({ input, setInput, navigate }) {
  return (
    <div className="py-8 text-center">
      <span className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-verified-50 text-3xl text-verified">
        <IconQr />
      </span>
      <h1 className="mt-5 font-serif text-h1 text-ink">Check your medicine</h1>
      <p className="mx-auto mt-2 max-w-md text-body text-neutral-600">
        Enter the code printed on the pack, or scan the QR code with your phone camera.
      </p>

      <form
        onSubmit={(e) => {
          e.preventDefault()
          if (input.trim()) navigate(`/verify/${encodeURIComponent(input.trim())}`)
        }}
        className="mx-auto mt-6 flex max-w-md gap-2"
      >
        <div className="relative flex-1">
          <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400">
            <IconSearch />
          </span>
          <label htmlFor="qr-input" className="sr-only">
            QR code from the pack
          </label>
          <input
            id="qr-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="QR-2026-001"
            autoComplete="off"
            className="input-field pl-9 text-center font-mono text-body"
          />
        </div>
        <button type="submit" disabled={!input.trim()} className="btn btn-primary px-6">
          Verify
        </button>
      </form>
    </div>
  )
}

function Verdict({ ok, title, body, action, headingRef, children }) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className={`rounded-3xl border-2 p-7 text-center ${
        ok ? 'border-verified bg-verified-50' : 'border-critical bg-critical-50'
      }`}
    >
      <span
        className={`mx-auto flex h-16 w-16 items-center justify-center rounded-full text-3xl text-white ${
          ok ? 'bg-verified' : 'bg-critical'
        }`}
        aria-hidden="true"
      >
        {ok ? <IconCheck /> : <IconX />}
      </span>

      <h1
        ref={headingRef}
        tabIndex={-1}
        className={`mt-4 font-serif text-h1 outline-none ${
          ok ? 'text-verified-700' : 'text-critical-700'
        }`}
      >
        {title}
      </h1>

      <p className={`mx-auto mt-2 max-w-md text-body ${ok ? 'text-verified-700' : 'text-critical-700'}`}>
        {body}
      </p>

      {children}
      {action && <div className="mt-5">{action}</div>}
    </motion.section>
  )
}

function VerifiedProduct({ data, journey, qrId }) {
  const headingRef = useRef(null)
  const raws = Array.isArray(journey?.raw_batches) ? journey.raw_batches : []
  const regions = Array.from(
    new Set(
      raws
        .map(({ farm }) => [farm?.district, farm?.state].filter(Boolean).join(', '))
        .filter(Boolean),
    ),
  )
  const medicine = journey?.medicine_batch

  return (
    <div className="space-y-6">
      <Verdict
        ok
        headingRef={headingRef}
        title="Authentic"
        body={`${data.product_name} is a genuine, registered batch.`}
      >
        <p className="mt-4 inline-flex items-center gap-2 rounded-full bg-verified px-4 py-1.5 text-small font-semibold text-white">
          <IconShieldCheck /> Verified against the tamper-evident record
        </p>
      </Verdict>

      {/* ---- product ---- */}
      <section className="rounded-2xl border border-neutral-200 bg-surface-raised p-6">
        <h2 className="font-serif text-h2 text-ink">{data.product_name}</h2>
        <dl className="mt-4 space-y-3 text-body">
          <Row label="Status" value={data.batch_status === 'RELEASED' ? 'Released for sale' : data.batch_status} />
          {medicine?.manufacturing_date && (
            <Row label="Manufactured" value={formatDate(medicine.manufacturing_date)} />
          )}
          {medicine?.expiry_date && <Row label="Use before" value={formatDate(medicine.expiry_date)} />}
        </dl>
      </section>

      {/* ---- journey ---- */}
      <section className="rounded-2xl border border-neutral-200 bg-surface-raised p-6">
        <h2 className="font-serif text-h3 text-ink">How it got to you</h2>
        <p className="mt-1 text-small text-neutral-600">
          Each step below was recorded when it happened and cannot be edited afterwards.
        </p>

        <ol className="mt-5 space-y-5">
          <Step
            icon={<IconLeaf />}
            title="Grown and harvested"
            detail={
              regions.length > 0
                ? `Sourced from ${regions.join(' and ')}`
                : 'Sourced from certified partner farms'
            }
            done
          />
          <Step
            icon={<IconFlask />}
            title="Processed and tested"
            detail="Dried, ground and passed laboratory identity, purity and moisture checks"
            done
          />
          <Step
            icon={<IconFactory />}
            title="Manufactured"
            detail="Produced from a lot cleared for manufacturing"
            done
          />
          <Step
            icon={<IconPill />}
            title="Released for sale"
            detail="Final quality check passed and the batch was released"
            done
            last
          />
        </ol>
      </section>

      <ReportSection qrId={qrId} medicineBatchId={data.medicine_batch_id} />
    </div>
  )
}

function Row({ label, value }) {
  return (
    <div className="flex flex-wrap justify-between gap-2 border-b border-neutral-100 pb-3 last:border-0 last:pb-0">
      <dt className="text-neutral-600">{label}</dt>
      <dd className="font-semibold text-ink">{value ?? '—'}</dd>
    </div>
  )
}

function Step({ icon, title, detail, done, last }) {
  return (
    <li className="relative flex gap-4 pl-1">
      {!last && (
        <span
          className="absolute left-[19px] top-10 h-[calc(100%-8px)] w-0.5 bg-verified-200"
          aria-hidden="true"
        />
      )}
      <span
        className={`relative z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-lg ${
          done ? 'bg-verified-50 text-verified ring-2 ring-verified-200' : 'bg-neutral-100 text-neutral-400'
        }`}
        aria-hidden="true"
      >
        {icon}
      </span>
      <div className="pt-1">
        <p className="text-h4 font-semibold text-ink">{title}</p>
        <p className="mt-0.5 text-body text-neutral-600">{detail}</p>
      </div>
    </li>
  )
}

function ReportLink({ qrId }) {
  return (
    <a href={`#report-${qrId ?? ''}`} className="btn btn-outline">
      Report a problem
    </a>
  )
}

const ISSUE_TYPES = [
  'Packaging looks tampered with',
  'Suspected counterfeit',
  'Unexpected side effect',
  'Product quality problem',
  'Other',
]

function ReportSection({ qrId, medicineBatchId }) {
  const [open, setOpen] = useState(false)
  const [issueType, setIssueType] = useState(ISSUE_TYPES[0])
  const [symptoms, setSymptoms] = useState('')
  const [description, setDescription] = useState('')
  const [state, setState] = useState({ status: 'idle', reportId: null, error: null })

  const submit = async (e) => {
    e.preventDefault()
    if (!description.trim()) return
    setState({ status: 'sending', reportId: null, error: null })
    try {
      const res = await consumerAPI.createReport({
        medicine_batch_id: medicineBatchId,
        qr_id: qrId,
        reported_at: new Date().toISOString(),
        issue_type: issueType,
        symptoms: symptoms.trim() || 'Not specified',
        description: description.trim(),
        report_status: 'OPEN',
        is_synthetic: false,
      })
      setState({ status: 'sent', reportId: res?.report_id ?? null, error: null })
    } catch (err) {
      setState({ status: 'error', reportId: null, error: err.message })
    }
  }

  if (state.status === 'sent') {
    return (
      <section
        className="rounded-2xl border-2 border-verified bg-verified-50 p-6 text-center"
        role="status"
      >
        <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-verified text-2xl text-white">
          <IconCheck />
        </span>
        <h2 className="mt-3 font-serif text-h3 text-verified-700">Report received</h2>
        <p className="mt-2 text-body text-verified-700">
          Thank you. Your report has been logged against this batch and will be reviewed.
        </p>
        {state.reportId && (
          <p className="mt-3 font-mono text-small text-verified-700">
            Reference {state.reportId}
          </p>
        )}
      </section>
    )
  }

  return (
    <section id={`report-${qrId ?? ''}`} className="rounded-2xl border border-neutral-200 bg-surface-raised p-6">
      <h2 className="flex items-center gap-2 font-serif text-h3 text-ink">
        <span className="text-alert">
          <IconAlertTriangle />
        </span>
        Something wrong with this product?
      </h2>
      <p className="mt-1 text-body text-neutral-600">
        Tell us what you noticed. Reports go straight to the auditors who can investigate this
        batch.
      </p>

      {!open ? (
        <button type="button" onClick={() => setOpen(true)} className="btn btn-outline mt-4">
          Report an issue
        </button>
      ) : (
        <form onSubmit={submit} className="mt-5 space-y-4">
          <div>
            <label htmlFor="issue-type" className="mb-1.5 block text-small font-semibold text-ink">
              What is the problem?
            </label>
            <select
              id="issue-type"
              value={issueType}
              onChange={(e) => setIssueType(e.target.value)}
              className="input-field"
            >
              {ISSUE_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="symptoms" className="mb-1.5 block text-small font-semibold text-ink">
              Any symptoms? <span className="font-normal text-neutral-500">(optional)</span>
            </label>
            <input
              id="symptoms"
              value={symptoms}
              onChange={(e) => setSymptoms(e.target.value)}
              className="input-field"
              placeholder="e.g. headache, nausea"
            />
          </div>

          <div>
            <label htmlFor="description" className="mb-1.5 block text-small font-semibold text-ink">
              Tell us more
            </label>
            <textarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={4}
              required
              aria-describedby="description-hint"
              className="input-field resize-y"
              placeholder="Describe what you noticed."
            />
            <p id="description-hint" className="mt-1 text-[11px] text-neutral-500">
              Please do not include personal health details you would rather keep private.
            </p>
          </div>

          {state.status === 'error' && (
            <p role="alert" className="rounded-xl bg-critical-50 p-3 text-small text-critical-700">
              {state.error}
            </p>
          )}

          <div className="flex flex-wrap gap-2">
            <button
              type="submit"
              disabled={!description.trim() || state.status === 'sending'}
              className="btn btn-primary"
            >
              {state.status === 'sending' ? (
                <>
                  <span className="spinner" aria-hidden="true" /> Sending…
                </>
              ) : (
                'Submit report'
              )}
            </button>
            <button type="button" onClick={() => setOpen(false)} className="btn btn-ghost">
              Cancel
            </button>
          </div>
        </form>
      )}
    </section>
  )
}
