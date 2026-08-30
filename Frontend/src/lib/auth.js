/*
 * SESSION STORAGE — the token, and who it belongs to.
 *
 * The role is no longer a client-side choice. It arrives inside the token
 * from POST /api/auth/login and the server re-reads it from the database on
 * every single request, so editing anything here changes what the UI shows
 * and nothing about what the API will accept. That is the whole point: the
 * screens a user sees are a convenience, not the security boundary.
 *
 * localStorage rather than a cookie because the API authenticates with an
 * Authorization header and sets no cookie, so there is nothing for a
 * cross-site request to send on the user's behalf.
 */

const TOKEN_KEY = 'traceveda.token'
const USER_KEY = 'traceveda.user'

/* localStorage throws outright in some privacy modes, so every access is
 * guarded. A blocked store means the session does not persist across a
 * reload — it must never mean a blank screen. */
function safeGet(key) {
  try {
    const raw = window.localStorage.getItem(key)
    if (!raw || raw === 'null' || raw === 'undefined') return null
    return raw
  } catch {
    return null
  }
}

function safeSet(key, value) {
  try {
    if (value === null || value === undefined) window.localStorage.removeItem(key)
    else window.localStorage.setItem(key, value)
  } catch {
    /* private mode / blocked site data — the session just does not persist */
  }
}

export function readToken() {
  return safeGet(TOKEN_KEY)
}

export function readUser() {
  const raw = safeGet(USER_KEY)
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw)
    return parsed && parsed.username ? parsed : null
  } catch {
    /* A corrupt entry must not wedge the app on every load. */
    safeSet(USER_KEY, null)
    return null
  }
}

/** Persist a successful login. `session` is the POST /api/auth/login body. */
export function writeSession(session) {
  if (!session?.access_token) return null

  const user = {
    username: session.username,
    role: session.role,
    fullName: session.full_name ?? null,
    expiresAt: session.expires_at ?? null,
  }

  safeSet(TOKEN_KEY, session.access_token)
  safeSet(USER_KEY, JSON.stringify(user))

  return user
}

export function clearSession() {
  safeSet(TOKEN_KEY, null)
  safeSet(USER_KEY, null)
}

/**
 * True when the stored token is past its expiry.
 *
 * A courtesy check only — it saves a round trip that would come back 401
 * anyway. The server is the authority, and a client whose clock is wrong
 * simply gets the 401 instead.
 */
export function isExpired(user) {
  if (!user?.expiresAt) return false
  return Date.now() >= user.expiresAt * 1000
}

/** A restored session, or null. Expired tokens are cleared on the way out. */
export function restoreSession() {
  const token = readToken()
  const user = readUser()

  if (!token || !user) {
    if (token || user) clearSession()
    return null
  }

  if (isExpired(user)) {
    clearSession()
    return null
  }

  return user
}
