import axios from 'axios'
import { clearSession, readToken } from '../lib/auth'

/*
 * Every function here returns the response BODY, not the axios envelope.
 * Callers never write `.data` — that mistake is the single easiest way to
 * ship a screen that silently renders nothing.
 *
 * Endpoints below were read off BACKEND/routes/*.py, not the contract doc,
 * which has drifted in a few places (noted inline).
 *
 * Everything except the two public consumer endpoints now requires a bearer
 * token. It is attached by the request interceptor below, so no call site
 * has to remember it.
 */

const API_URL = import.meta.env.VITE_API_URL ?? ''

const http = axios.create({
  baseURL: API_URL,
  timeout: 20000,
  headers: { 'Content-Type': 'application/json' },
})

/** Thrown for every failed call so screens can show one consistent state. */
export class ApiError extends Error {
  constructor(message, { status, url, notImplemented = false, unauthenticated = false, forbidden = false } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.url = url
    this.notImplemented = notImplemented
    this.unauthenticated = unauthenticated
    this.forbidden = forbidden
  }
}

/* Subscribers are notified once when the server rejects our credentials, so
 * App can drop the session and route back to the login screen. */
const unauthorizedHandlers = new Set()

export function onUnauthorized(handler) {
  unauthorizedHandlers.add(handler)
  return () => unauthorizedHandlers.delete(handler)
}

http.interceptors.request.use((config) => {
  const token = readToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

http.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status
    const url = error.config?.url
    const detail = error.response?.data?.detail

    // A 404 on a *collection* route means the route does not exist at all;
    // a 404 on an item route just means "not found". Screens render these
    // very differently, so the distinction is carried on the error.
    const notImplemented = status === 404 && !detail

    // 401 and 403 mean genuinely different things and must not be collapsed:
    // 401 is "log in again", 403 is "this role may not do that". Showing a
    // login prompt for a permissions problem sends the user in a loop.
    if (status === 401) {
      clearSession()
      unauthorizedHandlers.forEach((handler) => {
        try {
          handler()
        } catch {
          /* a listener must not mask the original API error */
        }
      })
    }

    throw new ApiError(
      // FastAPI validation errors put an array of objects in `detail`;
      // rendering that raw prints "[object Object]" into the UI.
      formatDetail(detail) || error.message || 'Request failed',
      {
        status,
        url,
        notImplemented,
        unauthenticated: status === 401,
        forbidden: status === 403,
      },
    )
  },
)

function formatDetail(detail) {
  if (!detail) return null
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === 'string') return item
        const field = Array.isArray(item?.loc) ? item.loc[item.loc.length - 1] : null
        return field ? `${field}: ${item.msg}` : item?.msg
      })
      .filter(Boolean)
      .join(' · ')
  }
  return null
}

const get = (url, config) => http.get(url, config).then((r) => r.data)
const post = (url, body) => http.post(url, body).then((r) => r.data)
const patch = (url, body) => http.patch(url, body).then((r) => r.data)

// ============================================================
// AUTHENTICATION
// ============================================================
export const authAPI = {
  /** -> { access_token, token_type, expires_at, username, role, full_name } */
  login: (username, password) => post('/api/auth/login', { username, password }),
  /** -> { username, role, full_name, organisation_id } */
  me: () => get('/api/auth/me'),
  /** Public — the login screen renders it before anyone has a token. */
  roles: () => get('/api/auth/roles'),
}

// ============================================================
// BATCHES
// ============================================================
export const batchAPI = {
  /** -> { batches: [...], count } */
  listRaw: () => get('/api/batches/raw'),
  listProcessing: () => get('/api/batches/processing'),
  getRaw: (id) => get(`/api/batches/raw/${encodeURIComponent(id)}`),
  getProcessing: (id) => get(`/api/batches/processing/${encodeURIComponent(id)}`),
  createRaw: (body) => post('/api/batches/raw', body),
  createProcessing: (body) => post('/api/batches/processing', body),
  createRelationship: (body) => post('/api/batches/relationships', body),
  /** -> { batch_id, relationships: [...] } — matches parent OR child side */
  getRelationships: (id) => get(`/api/batches/${encodeURIComponent(id)}/relationships`),
}

// ============================================================
// MEDICINE + PUBLIC QR VERIFY
// ============================================================
export const medicineAPI = {
  list: () => get('/api/medicine'),
  get: (id) => get(`/api/medicine/${encodeURIComponent(id)}`),
  create: (body) => post('/api/medicine', body),
  /* NOTE: mounted at /api/verify, not /api/medicine/verify. */
  verifyQr: (qrId) => get(`/api/verify/${encodeURIComponent(qrId)}`),
}

// ============================================================
// PLANTS (botanical reference data)
// ============================================================
export const plantAPI = {
  /** -> { plants: [...], count, total } */
  list: (params) => get('/api/plants', { params }),
  get: (id) => get(`/api/plants/${encodeURIComponent(id)}`),
  /** -> { query, plants, count } — matches common/scientific/vernacular names */
  search: (name) => get('/api/plants/search', { params: { name } }),
}

// ============================================================
// INVESTIGATIONS (regulator only)
// ============================================================
export const investigationAPI = {
  list: (status) => get('/api/investigations', { params: status ? { status } : undefined }),
  get: (id) => get(`/api/investigations/${encodeURIComponent(id)}`),
  open: (body) => post('/api/investigations', body),
  close: (id, body) => patch(`/api/investigations/${encodeURIComponent(id)}/close`, body),
}

// ============================================================
// LABORATORY
// ============================================================
export const labAPI = {
  /** -> { batch_id, tests: [...] } */
  getTests: (batchId) => get(`/api/lab/tests/${encodeURIComponent(batchId)}`),
  createTest: (body) => post('/api/lab/tests', body),
}

// ============================================================
// IOT
// ============================================================
export const iotAPI = {
  /** -> { batch_id, readings: [...] } sorted OLDEST first */
  getReadings: (batchId) => get(`/api/iot/readings/${encodeURIComponent(batchId)}`),
  /** -> { batch_id, alerts: [...] } sorted NEWEST first */
  getAlerts: (batchId) => get(`/api/iot/alerts/${encodeURIComponent(batchId)}`),
  /** -> { reading_id, tamper_status, gate_open, weight_changed, red_led,
   *       alerts_generated, blockchain_tx } */
  postReading: (body) => post('/api/iot/readings', body),
}

// ============================================================
// TRANSPORT / STORAGE
// ============================================================
export const transportAPI = {
  getEvents: (batchId) => get(`/api/transport/${encodeURIComponent(batchId)}`),
  createEvent: (body) => post('/api/transport/events', body),
}

export const storageAPI = {
  /* Storage is keyed on the RAW batch id in this backend, not the medicine
   * batch id the contract doc claims. */
  getEvents: (rawBatchId) => get(`/api/storage/${encodeURIComponent(rawBatchId)}`),
  createEvent: (body) => post('/api/storage/events', body),
}

// ============================================================
// TRACEABILITY
// ============================================================
export const traceAPI = {
  /** -> { medicine_batch, processing_batch, raw_batches: [{raw_batch, farm}] } */
  reverse: (medicineBatchId) => get(`/api/trace/reverse/${encodeURIComponent(medicineBatchId)}`),
  /** -> { raw_batch, downstream: [{processing_batch, medicine_batches}] } */
  forward: (rawBatchId) => get(`/api/trace/forward/${encodeURIComponent(rawBatchId)}`),
  /** -> { raw_batch_id, affected_medicine_batches, affected_count } */
  impact: (rawBatchId) => get(`/api/trace/impact/${encodeURIComponent(rawBatchId)}`),
}

// ============================================================
// BLOCKCHAIN
// ============================================================
export const blockchainAPI = {
  /** -> { events: [...], count } — sequence DESC, capped at 500 by the API */
  listEvents: () => get('/api/blockchain/events'),
  getEvent: (txId) => get(`/api/blockchain/events/${encodeURIComponent(txId)}`),
  /** -> { entity_id, event_count, events } — sequence ASC */
  getTrail: (entityId) => get(`/api/blockchain/batch/${encodeURIComponent(entityId)}`),
  /** -> { transaction_id, valid, stored_hash, calculated_hash } */
  verifyEvent: (txId) => get(`/api/blockchain/verify/${encodeURIComponent(txId)}`),
  /** -> { valid, checked, broken_at, reason } */
  verifyChain: () => get('/api/blockchain/verify-chain'),
  anchorEvent: (body) => post('/api/blockchain/events', body),
}

// ============================================================
// CONSUMER
// ============================================================
export const consumerAPI = {
  /* Public: someone reporting a bad reaction has no account. */
  createReport: (body) => post('/api/consumer/reports', body),
  getReportsForBatch: (medicineBatchId) =>
    get(`/api/consumer/reports/batch/${encodeURIComponent(medicineBatchId)}`),
  getReport: (reportId) => get(`/api/consumer/reports/${encodeURIComponent(reportId)}`),
  /* Regulator only. Status must be one of the values in routes/consumer.py. */
  updateStatus: (reportId, status) =>
    patch(`/api/consumer/reports/${encodeURIComponent(reportId)}/status`, { status }),
}

// ============================================================
// HEALTH
// ============================================================
export const healthAPI = {
  check: () => get('/api/health'),
}

export default http
