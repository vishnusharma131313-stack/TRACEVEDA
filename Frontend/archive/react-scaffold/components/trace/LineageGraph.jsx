import { motion, useReducedMotion } from 'framer-motion'
import { Link } from 'react-router-dom'
import StatusChip from '../ui/StatusChip'
import { KIND, batchPath } from '../../lib/batches'
import { IconFactory, IconFlask, IconLeaf, IconPill } from '../ui/Icons'

/*
 * The lineage tree, as a tree — not a table.
 *
 * Columns are supply-chain stages, left to right:
 *   farm -> raw batch -> processing batch -> medicine batch
 *
 * A processing lot is fed by SEVERAL raw batches (batch_relationships is
 * many-to-one), and one raw batch can reach SEVERAL medicines. Both fan-outs
 * are drawn, because the fan-out is the whole argument for targeted recall.
 *
 * Shape expected (built by lib callers, never by this component):
 *   columns: [{ stage, title, nodes: [{ id, kind, status, subtitle, href }] }]
 *   edges:   [{ from: nodeId, to: nodeId }]
 */

const STAGE_ICON = {
  farm: <IconLeaf />,
  [KIND.RAW]: <IconLeaf />,
  [KIND.PROCESSING]: <IconFlask />,
  [KIND.MEDICINE]: <IconPill />,
  manufacturer: <IconFactory />,
}

const NODE_W = 168
const NODE_H = 76
const COL_GAP = 72
const ROW_GAP = 18

function layout(columns) {
  const positions = new Map()
  const tallest = Math.max(1, ...columns.map((c) => c.nodes.length))
  const height = tallest * NODE_H + (tallest - 1) * ROW_GAP

  columns.forEach((column, columnIndex) => {
    const count = column.nodes.length
    const blockHeight = count * NODE_H + Math.max(0, count - 1) * ROW_GAP
    const top = (height - blockHeight) / 2
    column.nodes.forEach((node, rowIndex) => {
      positions.set(node.id, {
        x: columnIndex * (NODE_W + COL_GAP),
        y: top + rowIndex * (NODE_H + ROW_GAP),
        node,
      })
    })
  })

  const width = columns.length * NODE_W + Math.max(0, columns.length - 1) * COL_GAP
  return { positions, width, height }
}

function NodeCard({ node, isCurrent }) {
  const body = (
    <div
      className={`flex h-full w-full flex-col justify-center rounded-xl border px-3 py-2 transition-shadow ${
        isCurrent
          ? 'border-chain bg-chain-50 shadow-chain-glow'
          : 'border-neutral-200 bg-surface-raised hover:shadow-card-hover'
      }`}
    >
      <div className="flex items-center gap-1.5 text-micro font-semibold uppercase tracking-wider text-neutral-500">
        <span className="text-[13px]">{STAGE_ICON[node.kind] ?? STAGE_ICON.farm}</span>
        <span className="truncate">{node.stageLabel}</span>
      </div>
      <div className="mt-1 truncate font-mono text-[12px] font-semibold text-ink" title={node.id}>
        {node.id}
      </div>
      <div className="mt-1 flex items-center gap-1.5">
        {node.status ? (
          <StatusChip status={node.status} size="sm" />
        ) : (
          node.subtitle && (
            <span className="truncate text-[11px] text-neutral-600" title={node.subtitle}>
              {node.subtitle}
            </span>
          )
        )}
      </div>
    </div>
  )

  if (!node.href) {
    return <div className="h-full w-full">{body}</div>
  }

  return (
    <Link
      to={node.href}
      aria-current={isCurrent ? 'page' : undefined}
      className="block h-full w-full rounded-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-chain-400"
    >
      {body}
    </Link>
  )
}

export default function LineageGraph({ columns = [], edges = [], currentId, animate = true }) {
  const reduce = useReducedMotion()
  const usable = columns.filter((c) => c.nodes.length > 0)

  if (usable.length === 0) return null

  const { positions, width, height } = layout(usable)
  const shouldAnimate = animate && !reduce

  return (
    <div className="overflow-x-auto pb-2">
      <div className="relative mx-auto" style={{ width, height, minWidth: width }}>
        {/* Edges sit behind the cards. */}
        <svg
          className="pointer-events-none absolute inset-0"
          width={width}
          height={height}
          aria-hidden="true"
        >
          {edges.map((edge, i) => {
            const from = positions.get(edge.from)
            const to = positions.get(edge.to)
            if (!from || !to) return null

            const x1 = from.x + NODE_W
            const y1 = from.y + NODE_H / 2
            const x2 = to.x
            const y2 = to.y + NODE_H / 2
            const mid = x1 + (x2 - x1) / 2
            const d = `M ${x1} ${y1} C ${mid} ${y1}, ${mid} ${y2}, ${x2} ${y2}`

            return (
              <motion.path
                key={`${edge.from}->${edge.to}-${i}`}
                d={d}
                fill="none"
                stroke={edge.tone === 'critical' ? '#B3261E' : '#D4D1C6'}
                strokeWidth={edge.tone === 'critical' ? 2 : 1.5}
                strokeDasharray={edge.dashed ? '5 4' : undefined}
                initial={shouldAnimate ? { pathLength: 0, opacity: 0 } : false}
                animate={shouldAnimate ? { pathLength: 1, opacity: 1 } : false}
                transition={{ duration: 0.45, delay: 0.12 * (edge.depth ?? 0), ease: 'easeOut' }}
              />
            )
          })}
        </svg>

        {usable.map((column, columnIndex) =>
          column.nodes.map((node) => {
            const pos = positions.get(node.id)
            if (!pos) return null
            return (
              <motion.div
                key={node.id}
                className="absolute"
                style={{ left: pos.x, top: pos.y, width: NODE_W, height: NODE_H }}
                initial={shouldAnimate ? { opacity: 0, y: 10 } : false}
                animate={shouldAnimate ? { opacity: 1, y: 0 } : false}
                transition={{ duration: 0.32, delay: 0.12 * columnIndex, ease: 'easeOut' }}
              >
                <NodeCard node={node} isCurrent={node.id === currentId} />
              </motion.div>
            )
          }),
        )}
      </div>

      <div className="mt-3 flex flex-wrap justify-center gap-x-6 gap-y-1">
        {usable.map((column) => (
          <span
            key={column.stage}
            className="text-micro font-semibold uppercase tracking-wider text-neutral-500"
          >
            {column.title}
          </span>
        ))}
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Builders — turn each trace endpoint's response into graph props.    */
/* ------------------------------------------------------------------ */

/** GET /api/trace/reverse/{medicine_batch_id} */
export function buildReverseLineage(trace) {
  if (!trace) return { columns: [], edges: [] }

  const farms = []
  const raws = []
  const edges = []

  const rawEntries = Array.isArray(trace.raw_batches) ? trace.raw_batches : []
  rawEntries.forEach((entry) => {
    const raw = entry?.raw_batch
    if (!raw?.raw_batch_id) return

    const farm = entry?.farm
    const farmId = farm?.farm_id ?? raw.farm_id
    if (farmId && !farms.some((f) => f.id === farmId)) {
      farms.push({
        id: farmId,
        kind: 'farm',
        stageLabel: 'Farm',
        subtitle: farm?.farm_name ?? farm?.district ?? farm?.location ?? null,
        status: farm?.certification_status ?? null,
      })
    }

    raws.push({
      id: raw.raw_batch_id,
      kind: KIND.RAW,
      stageLabel: 'Raw batch',
      status: raw.batch_status ?? null,
      subtitle: raw.plant_id ?? null,
      href: batchPath(KIND.RAW, raw.raw_batch_id),
    })

    if (farmId) edges.push({ from: farmId, to: raw.raw_batch_id, depth: 0 })
  })

  const processing = trace.processing_batch
  const processingNodes = processing?.processing_batch_id
    ? [
        {
          id: processing.processing_batch_id,
          kind: KIND.PROCESSING,
          stageLabel: 'Processing',
          status: processing.status ?? null,
          subtitle: processing.processing_type ?? null,
          href: batchPath(KIND.PROCESSING, processing.processing_batch_id),
        },
      ]
    : []

  if (processing?.processing_batch_id) {
    raws.forEach((raw) => edges.push({ from: raw.id, to: processing.processing_batch_id, depth: 1 }))
  }

  const medicine = trace.medicine_batch
  const medicineNodes = medicine?.medicine_batch_id
    ? [
        {
          id: medicine.medicine_batch_id,
          kind: KIND.MEDICINE,
          stageLabel: 'Medicine',
          status: medicine.batch_status ?? null,
          subtitle: medicine.product_name ?? null,
          href: batchPath(KIND.MEDICINE, medicine.medicine_batch_id),
        },
      ]
    : []

  if (processing?.processing_batch_id && medicine?.medicine_batch_id) {
    edges.push({ from: processing.processing_batch_id, to: medicine.medicine_batch_id, depth: 2 })
  }

  return {
    columns: [
      { stage: 'farm', title: 'Farm', nodes: farms },
      { stage: KIND.RAW, title: 'Raw material', nodes: raws },
      { stage: KIND.PROCESSING, title: 'Processing', nodes: processingNodes },
      { stage: KIND.MEDICINE, title: 'Medicine', nodes: medicineNodes },
    ],
    edges,
  }
}

/** GET /api/trace/forward/{raw_batch_id} */
export function buildForwardLineage(trace, { criticalEdges = false } = {}) {
  if (!trace?.raw_batch?.raw_batch_id) return { columns: [], edges: [] }

  const raw = trace.raw_batch
  const rawNode = {
    id: raw.raw_batch_id,
    kind: KIND.RAW,
    stageLabel: 'Raw batch',
    status: raw.batch_status ?? null,
    subtitle: raw.plant_id ?? null,
    href: batchPath(KIND.RAW, raw.raw_batch_id),
  }

  const processingNodes = []
  const medicineNodes = []
  const edges = []
  const tone = criticalEdges ? 'critical' : undefined

  const downstream = Array.isArray(trace.downstream) ? trace.downstream : []
  downstream.forEach((branch) => {
    const processing = branch?.processing_batch
    if (!processing?.processing_batch_id) return

    processingNodes.push({
      id: processing.processing_batch_id,
      kind: KIND.PROCESSING,
      stageLabel: 'Processing',
      status: processing.status ?? null,
      subtitle: processing.processing_type ?? null,
      href: batchPath(KIND.PROCESSING, processing.processing_batch_id),
    })
    edges.push({ from: raw.raw_batch_id, to: processing.processing_batch_id, depth: 0, tone })

    const medicines = Array.isArray(branch.medicine_batches) ? branch.medicine_batches : []
    medicines.forEach((medicine) => {
      if (!medicine?.medicine_batch_id) return
      if (!medicineNodes.some((n) => n.id === medicine.medicine_batch_id)) {
        medicineNodes.push({
          id: medicine.medicine_batch_id,
          kind: KIND.MEDICINE,
          stageLabel: 'Medicine',
          status: medicine.batch_status ?? null,
          subtitle: medicine.product_name ?? null,
          href: batchPath(KIND.MEDICINE, medicine.medicine_batch_id),
        })
      }
      edges.push({
        from: processing.processing_batch_id,
        to: medicine.medicine_batch_id,
        depth: 1,
        tone,
      })
    })
  })

  return {
    columns: [
      { stage: KIND.RAW, title: 'Raw material', nodes: [rawNode] },
      { stage: KIND.PROCESSING, title: 'Processing', nodes: processingNodes },
      { stage: KIND.MEDICINE, title: 'Medicine', nodes: medicineNodes },
    ],
    edges,
  }
}

/**
 * A processing batch sits in the middle of the chain and no single endpoint
 * returns both of its sides:
 *
 *   - upstream   GET /api/batches/{id}/relationships  (parent raw batches)
 *   - downstream there is no /trace endpoint that accepts a PROCESSING id —
 *                /trace/forward only accepts a raw id — so the child medicines
 *                are filtered out of GET /api/medicine, which carries
 *                processing_batch_id on every row.
 */
export function buildProcessingLineage({ processing, relationships = [], medicines = [] }) {
  if (!processing?.processing_batch_id) return { columns: [], edges: [] }

  const id = processing.processing_batch_id
  const edges = []

  const parents = relationships
    .filter((r) => r?.child_batch_id === id && r?.parent_batch_id)
    .map((r) => ({
      id: r.parent_batch_id,
      kind: KIND.RAW,
      stageLabel: 'Raw batch',
      status: null,
      subtitle: r.quantity_contributed
        ? `${r.quantity_contributed} ${r.unit ?? ''}`.trim()
        : null,
      href: batchPath(KIND.RAW, r.parent_batch_id),
    }))

  parents.forEach((p) => edges.push({ from: p.id, to: id, depth: 0 }))

  const processingNode = {
    id,
    kind: KIND.PROCESSING,
    stageLabel: 'Processing',
    status: processing.status ?? null,
    subtitle: processing.processing_type ?? null,
  }

  const medicineNodes = []
  medicines
    .filter((m) => m?.processing_batch_id === id && m?.medicine_batch_id)
    .forEach((medicine) => {
      medicineNodes.push({
        id: medicine.medicine_batch_id,
        kind: KIND.MEDICINE,
        stageLabel: 'Medicine',
        status: medicine.batch_status ?? null,
        subtitle: medicine.product_name ?? null,
        href: batchPath(KIND.MEDICINE, medicine.medicine_batch_id),
      })
      edges.push({ from: id, to: medicine.medicine_batch_id, depth: 1 })
    })

  return {
    columns: [
      { stage: KIND.RAW, title: 'Raw material', nodes: parents },
      { stage: KIND.PROCESSING, title: 'Processing', nodes: [processingNode] },
      { stage: KIND.MEDICINE, title: 'Medicine', nodes: medicineNodes },
    ],
    edges,
  }
}
