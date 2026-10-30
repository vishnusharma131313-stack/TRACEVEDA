/*
 * ROLE MODEL — navigation only.
 *
 * The role is issued by the server. It arrives in the POST /api/auth/login
 * response, travels inside the signed token, and the API re-reads it from
 * the database on every request. So what this file decides is which screens
 * a user is SHOWN; what they may actually do is decided by
 * BACKEND/dependencies.require_roles and cannot be changed from here.
 *
 * Editing localStorage now buys nothing: the screens appear and every call
 * they make comes back 401 or 403.
 *
 * Ids must match services/accounts.ROLES on the backend. `consumer` is
 * deliberately absent — the consumer journey is the public /verify page and
 * has no account.
 */

export const ROLES = [
  {
    id: 'farmer',
    label: 'Farmer',
    blurb: 'Register raw material batches at collection',
    home: '/dashboard',
    screens: ['dashboard', 'trace'],
  },
  {
    id: 'processor',
    label: 'Processor',
    blurb: 'Link raw material into processing lots',
    home: '/dashboard',
    screens: ['dashboard', 'trace', 'blockchain'],
  },
  {
    id: 'lab',
    label: 'Laboratory',
    blurb: 'Record quality results and sign them onto the ledger',
    home: '/dashboard',
    screens: ['dashboard', 'blockchain', 'trace'],
  },
  {
    id: 'logistics',
    label: 'Logistics / IoT',
    blurb: 'Monitor transport and storage telemetry',
    home: '/iot',
    screens: ['dashboard', 'iot', 'blockchain'],
  },
  {
    id: 'manufacturer',
    label: 'Manufacturer',
    blurb: 'Formulate medicine batches from approved lots',
    home: '/dashboard',
    screens: ['dashboard', 'trace', 'blockchain', 'iot'],
  },
  {
    id: 'regulator',
    label: 'Regulator / Auditor',
    blurb: 'Full audit access across every screen',
    home: '/dashboard',
    screens: ['dashboard', 'blockchain', 'trace', 'iot'],
  },
  {
    id: 'admin',
    label: 'Administrator',
    blurb: 'Full access, including manual ledger anchoring',
    home: '/dashboard',
    screens: ['dashboard', 'blockchain', 'trace', 'iot'],
  },
]

export const ROLE_BY_ID = Object.fromEntries(ROLES.map((r) => [r.id, r]))

export function getRole(id) {
  return ROLE_BY_ID[id] ?? null
}

export function canSee(roleId, screen) {
  const role = getRole(roleId)
  if (!role) return false
  return role.screens.includes(screen)
}

/** Where to land a user after login. Unknown roles still get a real screen. */
export function homeFor(roleId) {
  return getRole(roleId)?.home ?? '/dashboard'
}
