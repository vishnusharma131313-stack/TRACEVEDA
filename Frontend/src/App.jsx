import { createContext, useCallback, useEffect, useMemo, useState } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import AppShell from './components/layout/AppShell'
import BatchCommandCenter from './pages/BatchCommandCenter'
import BatchDetail from './pages/BatchDetail'
import BlockchainExplorer from './pages/BlockchainExplorer'
import ConsumerQR from './pages/ConsumerQR'
import IoTMonitor from './pages/IoTMonitor'
import Login from './pages/Login'
import TraceRecall from './pages/TraceRecall'
import { onUnauthorized } from './api/client'
import { clearSession, restoreSession, writeSession } from './lib/auth'
import { homeFor } from './lib/roles'

/*
 * SessionContext replaces the old RoleContext. The difference is not
 * cosmetic: `role` used to be whatever the user clicked on the login screen,
 * and now it is whatever the server put in the token. Screens read it to
 * decide what to show; the API decides what to allow.
 */

export const SessionContext = createContext({
  user: null,
  role: null,
  signIn: () => {},
  logout: () => {},
})

export default function App() {
  const [user, setUser] = useState(restoreSession)

  const signIn = useCallback((session) => {
    const stored = writeSession(session)
    setUser(stored)
    return stored
  }, [])

  const logout = useCallback(() => {
    clearSession()
    setUser(null)
  }, [])

  /* The server is the authority on whether a session is still good. When any
   * call comes back 401 — expired token, deactivated account, restarted
   * server with a fresh signing key — drop the session so the router sends
   * the user to the login screen instead of leaving them on a page whose
   * every request fails. */
  useEffect(() => onUnauthorized(() => setUser(null)), [])

  const value = useMemo(
    () => ({ user, role: user?.role ?? null, signIn, logout }),
    [user, signIn, logout],
  )

  const home = homeFor(user?.role)

  return (
    <SessionContext.Provider value={value}>
      <Routes>
        {/* ---- public: the consumer QR page needs no account ---- */}
        <Route path="/verify" element={<ConsumerQR />} />
        <Route path="/verify/:qrId" element={<ConsumerQR />} />

        <Route path="/login" element={user ? <Navigate to={home} replace /> : <Login />} />

        {/* ---- internal ---- */}
        <Route path="/" element={user ? <AppShell /> : <Navigate to="/login" replace />}>
          <Route index element={<Navigate to={home} replace />} />
          <Route path="dashboard" element={<BatchCommandCenter />} />
          <Route path="batch/:batchType/:batchId" element={<BatchDetail />} />
          <Route path="blockchain" element={<BlockchainExplorer />} />
          <Route path="trace" element={<TraceRecall />} />
          <Route path="iot" element={<IoTMonitor />} />
        </Route>

        <Route path="*" element={<Navigate to={user ? home : '/login'} replace />} />
      </Routes>
    </SessionContext.Provider>
  )
}

/* Kept so components importing the old name keep working. */
export const RoleContext = SessionContext
