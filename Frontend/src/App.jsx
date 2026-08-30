import { createContext, useCallback, useMemo, useState } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import AppShell from './components/layout/AppShell'
import BatchCommandCenter from './pages/BatchCommandCenter'
import BatchDetail from './pages/BatchDetail'
import BlockchainExplorer from './pages/BlockchainExplorer'
import ConsumerQR from './pages/ConsumerQR'
import IoTMonitor from './pages/IoTMonitor'
import Login from './pages/Login'
import TraceRecall from './pages/TraceRecall'
import { getRole, readStoredRole, writeStoredRole } from './lib/roles'

export const RoleContext = createContext({ role: null, setRole: () => {}, logout: () => {} })

export default function App() {
  const [role, setRoleState] = useState(readStoredRole)

  const setRole = useCallback((next) => {
    const valid = getRole(next) ? next : null
    setRoleState(valid)
    writeStoredRole(valid)
  }, [])

  const logout = useCallback(() => {
    setRoleState(null)
    writeStoredRole(null)
  }, [])

  const value = useMemo(() => ({ role, setRole, logout }), [role, setRole, logout])

  return (
    <RoleContext.Provider value={value}>
      <Routes>
        {/* ---- public: the consumer QR page needs no role ---- */}
        <Route path="/verify" element={<ConsumerQR />} />
        <Route path="/verify/:qrId" element={<ConsumerQR />} />

        <Route path="/login" element={role ? <Navigate to="/dashboard" replace /> : <Login />} />

        {/* ---- internal ---- */}
        <Route path="/" element={role ? <AppShell /> : <Navigate to="/login" replace />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<BatchCommandCenter />} />
          <Route path="batch/:batchType/:batchId" element={<BatchDetail />} />
          <Route path="blockchain" element={<BlockchainExplorer />} />
          <Route path="trace" element={<TraceRecall />} />
          <Route path="iot" element={<IoTMonitor />} />
        </Route>

        <Route path="*" element={<Navigate to={role ? '/dashboard' : '/login'} replace />} />
      </Routes>
    </RoleContext.Provider>
  )
}
