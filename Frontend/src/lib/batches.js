/*
 * One batch shape for three collections.
 *
 * The backend is not consistent, and the seeded dataset is not consistent
 * with the backend either. Rather than sprinkle `?? ` chains across every
 * screen, every batch is normalised here exactly once.
 *
 *   collection            id field             status field
 *   raw_material_batches  raw_batch_id         batch_status
 *   processing_batches    processing_batch_id  status          <-- differs
 *   medicine_batches      medicine_batch_id    batch_status
 *
 * Seeded ids are ASH-2026-001 / ASH-P-2026-001 / MED-2026-001; ids minted by
 * the live API are RAW-2026-001 / PROCESS-2026-001 / MED-2026-001. Nothing
 * may assume a prefix.
 */

export const KIND = {
  RAW: 'raw',
  PROCESSING: 'processing',
  MEDICINE: 'medicine',
}

export const KIND_LABEL = {
  [KIND.RAW]: 'Raw material',
  [KIND.PROCESSING]: 'Processing',
  [KIND.MEDICINE]: 'Medicine',
}

/** entity_type as the blockchain layer records it. */
export const KIND_ENTITY_TYPE = {
  [KIND.RAW]: 'RAW',
  [KIND.PROCESSING]: 'PROCESSING',
  [KIND.MEDICINE]: 'MEDICINE',
}

export function idOf(batch, kind) {
  if (!batch) return null
  if (kind === KIND.RAW) return batch.raw_batch_id ?? null
  if (kind === KIND.PROCESSING) return batch.processing_batch_id ?? null
  if (kind === KIND.MEDICINE) return batch.medicine_batch_id ?? null
  return (
    batch.raw_batch_id ??
    batch.processing_batch_id ??
    batch.medicine_batch_id ??
    null
  )
}

/** Processing batches carry `status`; the other two carry `batch_status`. */
export function statusOf(batch) {
  if (!batch) return null
  return batch.batch_status ?? batch.status ?? null
}

/**
 * The human-facing subtitle for a batch card / header.
 * Raw batches have no product name, so the plant id is the most useful thing
 * we can show without a /api/plants endpoint (which does not exist yet).
 */
export function titleOf(batch, kind) {
  if (!batch) return null
  if (kind === KIND.MEDICINE) return batch.product_name ?? null
  if (kind === KIND.PROCESSING) return batch.processing_type ?? null
  if (kind === KIND.RAW) return batch.plant_id ?? null
  return batch.product_name ?? batch.processing_type ?? batch.plant_id ?? null
}

/** Best available creation instant, as an ISO string or null. */
export function createdAtOf(batch) {
  if (!batch) return null
  return (
    batch.created_at ??
    batch.manufacturing_timestamp ??
    batch.manufacturing_date ??
    batch.processing_date ??
    batch.collection_date ??
    null
  )
}

/** Collapse a batch document into the shape every list/card renders. */
export function normalizeBatch(batch, kind) {
  const id = idOf(batch, kind)
  return {
    kind,
    kindLabel: KIND_LABEL[kind],
    id,
    status: statusOf(batch),
    title: titleOf(batch, kind),
    createdAt: createdAtOf(batch),
    quantity: batch.quantity ?? batch.output_quantity ?? null,
    unit: batch.unit ?? null,
    qrId: batch.qr_id ?? null,
    raw: batch,
  }
}

export function normalizeList(payload, kind) {
  const rows = Array.isArray(payload?.batches) ? payload.batches : []
  return rows.map((b) => normalizeBatch(b, kind)).filter((b) => b.id)
}

/** Route for a normalized batch. */
export function batchPath(kind, id) {
  return `/batch/${kind}/${encodeURIComponent(id)}`
}

/**
 * Which trace direction makes sense from here.
 * Reverse trace only accepts a medicine id; forward/impact only accept a raw id.
 */
export function traceModeFor(kind) {
  if (kind === KIND.MEDICINE) return 'reverse'
  if (kind === KIND.RAW) return 'forward'
  return null
}
