import axios from 'axios'

/*
 * Every function here returns the response BODY, not the axios envelope.
 * Callers never write `.data` — that mistake is the single easiest way to
 * ship a screen that silently renders nothing.
 *
 * Endpoints below were read off BACKEND/routes/*.py, not the contract doc,
 * which has drifted in a few places (noted inline).
 */

const API_URL = import.meta.env.VITE_API_URL ?? ''

const http = axios.create({
  baseURL: API_URL,
  timeout: 20000,
  headers: { 'Content-Type': 'application/json' },
})

/** Thrown for every failed call so screens can show one consistent state. */
export class ApiError extends Error {
  constructor(message, { status, url, notImplemented = false } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.url = url
    this.notImplemented = notImplemented
  }
}

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

    throw new ApiError(
      detail || error.message || 'Request failed',
      { status, url, notImplemented },
    )
  },
)

const get = (url, config) => http.get(url, config).then((r) => r.data)
const post = (url, body) => http.post(url, body).then((r) => r.data)

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
  createReport: (body) => post('/api/consumer/reports', body),
  getReportsForBatch: (medicineBatchId) =>
    get(`/api/consumer/reports/batch/${encodeURIComponent(medicineBatchId)}`),
  getReport: (reportId) => get(`/api/consumer/reports/${encodeURIComponent(reportId)}`),
}

// ============================================================
// HEALTH
// ============================================================
export const healthAPI = {
  check: () => get('/api/health'),
}

export default http
