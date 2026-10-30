
import { createContext, useCallback, useEffect, useMemo, useState } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'

import AppShell from './components/layout/AppShell'
import AdminDashboard from './pages/AdminDashboard'
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

  useEffect(() => onUnauthorized(() => setUser(null)), [])

  const value = useMemo(
    () => ({ user, role: user?.role ?? null, signIn, logout }),
    [user, signIn, logout],
  )

  const home = homeFor(user?.role)

  return (
    <SessionContext.Provider value={value}>
      <Routes>
        {/* Public routes */}
        <Route path="/verify" element={<ConsumerQR />} />
        <Route path="/verify/:qrId" element={<ConsumerQR />} />

        <Route
          path="/login"
          element={
            user
              ? <Navigate to={home} replace />
              : <Login />
          }
        />

        {/* Admin-only route */}
        <Route
          path="/admin"
          element={
            user?.role === 'admin'
              ? <AdminDashboard />
              : <Navigate to={user ? home : '/login'} replace />
          }
        />

        {/* Regular authenticated users */}
        <Route
          path="/"
          element={
            user && user.role !== 'admin'
              ? <AppShell />
              : <Navigate to={user ? '/admin' : '/login'} replace />
          }
        >
          <Route index element={<Navigate to={home} replace />} />
          <Route path="dashboard" element={<BatchCommandCenter />} />
          <Route path="batch/:batchType/:batchId" element={<BatchDetail />} />
          <Route path="blockchain" element={<BlockchainExplorer />} />
          <Route path="trace" element={<TraceRecall />} />
          <Route path="iot" element={<IoTMonitor />} />
        </Route>

        <Route
          path="*"
          element={
            <Navigate
              to={user ? (user.role === 'admin' ? '/admin' : home) : '/login'}
              replace
            />
          }
        />
      </Routes>
    </SessionContext.Provider>
  )
}

export const RoleContext = SessionContext
