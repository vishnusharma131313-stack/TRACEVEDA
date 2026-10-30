
import { useContext, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { SessionContext } from '../App'
import { authAPI } from '../api/client'
import { homeFor } from '../lib/roles'

import {
  IconArrowRight,
  IconInfo,
  IconLeaf,
  IconShield,
} from '../components/ui/Icons'

export default function Login() {
  const { signIn } = useContext(SessionContext)
  const navigate = useNavigate()

  const [mode, setMode] = useState('signin')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const isAdminLogin = mode === 'admin'

  const submitLogin = async (event) => {
    event.preventDefault()

    if (!username.trim() || !password) {
      setError('Enter your username and password.')
      return
    }

    setBusy(true)
    setError(null)

    try {
      const session = await authAPI.login(
        username.trim(),
        password,
      )

      // Verify the role issued by the backend.
      if (isAdminLogin && session.role !== 'admin') {
        setError(
          'Access denied. Administrator account required.'
        )
        return
      }

      // Save the authenticated session.
      signIn(session)

      // Redirect according to the server-issued role.
      navigate(
        session.role === 'admin'
          ? '/admin'
          : homeFor(session.role),
        { replace: true }
      )
    } catch (err) {
      setError(
        err?.status === 401
          ? 'Incorrect username or password.'
          : err?.message || 'Could not reach the server.'
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen bg-surface">
      <div className="mx-auto flex min-h-screen max-w-5xl flex-col justify-center px-6 py-12">

        {/* HEADER */}
        <header className="mb-10">
          <span className="inline-flex items-center gap-2.5">
            <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-verified text-xl text-white">
              <IconLeaf />
            </span>

            <span>
              <span className="block font-serif text-h2 leading-none text-ink">
                TraceVeda
              </span>

              <span className="mt-1 block text-[11px] uppercase tracking-[0.14em] text-neutral-500">
                Ayurvedic supply-chain traceability
              </span>
            </span>
          </span>

          <h1 className="mt-8 max-w-2xl font-serif text-h1 text-ink">
            Every batch carries its own evidence.
          </h1>

          <p className="mt-2 max-w-2xl text-body text-neutral-600">
            Sign in to access the TraceVeda supply-chain system.
          </p>
        </header>

        <div className="grid gap-8 lg:grid-cols-[minmax(0,380px)_minmax(0,1fr)]">

          {/* LOGIN CARD */}
          <div className="rounded-2xl border border-neutral-200 bg-surface-raised p-6 shadow-card">

            <form onSubmit={submitLogin}>

              <h2 className="font-serif text-h3 text-ink">
                {isAdminLogin
                  ? 'Administrator Login'
                  : 'Sign in'}
              </h2>

              {!isAdminLogin && (
                <button
                  type="button"
                  onClick={() => {
                    setMode('admin')
                    setError(null)
                  }}
                  className="btn btn-ghost mt-3 w-full justify-center"
                >
                  <IconShield />
                  Admin Login
                </button>
              )}

              {isAdminLogin && (
                <p className="mt-2 text-small text-neutral-600">
                  Sign in using your administrator credentials.
                </p>
              )}

              {/* USERNAME */}
              <label
                htmlFor="username"
                className="mt-5 block text-small font-semibold text-ink"
              >
                Username
              </label>

              <input
                id="username"
                name="username"
                type="text"
                autoComplete="username"
                autoFocus
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                disabled={busy}
                placeholder="Example: lab-001"
                className="mt-1.5 w-full rounded-xl border-2 border-neutral-200 bg-surface px-3.5 py-2.5 text-body text-ink outline-none transition-colors focus:border-verified disabled:opacity-60"
              />

              {/* PASSWORD */}
              <label
                htmlFor="password"
                className="mt-4 block text-small font-semibold text-ink"
              >
                Password
              </label>

              <input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={busy}
                className="mt-1.5 w-full rounded-xl border-2 border-neutral-200 bg-surface px-3.5 py-2.5 text-body text-ink outline-none transition-colors focus:border-verified disabled:opacity-60"
              />

              {/* ERROR */}
              {error && (
                <p
                  role="alert"
                  className="mt-4 rounded-xl bg-critical-50 px-3.5 py-2.5 text-small text-critical-700"
                >
                  {error}
                </p>
              )}

              {/* LOGIN BUTTON */}
              <button
                type="submit"
                disabled={busy}
                className="btn btn-primary mt-5 w-full justify-center px-6 py-3 text-body disabled:opacity-60"
              >
                {busy ? (
                  'Signing in…'
                ) : (
                  <>
                    {isAdminLogin
                      ? 'Admin Sign in'
                      : 'Sign in'}
                    <IconArrowRight />
                  </>
                )}
              </button>

              {/* BACK TO USER LOGIN */}
              {isAdminLogin && (
                <button
                  type="button"
                  onClick={() => {
                    setMode('signin')
                    setError(null)
                    setPassword('')
                  }}
                  className="btn btn-ghost mt-2 w-full justify-center"
                >
                  Back to User Login
                </button>
              )}

              {/* PUBLIC VERIFICATION */}
              {!isAdminLogin && (
                <button
                  type="button"
                  onClick={() => navigate('/verify')}
                  className="btn btn-ghost mt-2 w-full justify-center"
                >
                  Skip — Verify a medicine
                </button>
              )}

            </form>
          </div>

          {/* INFORMATION PANEL */}
          <div className="space-y-4">

            <div className="rounded-2xl border border-neutral-200 bg-surface-raised p-6">
              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-verified-50 text-verified">
                <IconShield />
              </span>

              <h2 className="mt-3 font-serif text-h4 text-ink">
                Secure role-based access
              </h2>

              <p className="mt-1.5 text-small text-neutral-600">
                Your role is controlled by the backend.
                After signing in, the server issues an
                authentication token and the frontend opens
                the appropriate workspace.
              </p>
            </div>

            <div className="rounded-2xl border border-neutral-200 bg-surface-raised p-6">
              <h2 className="font-serif text-h4 text-ink">
                Administrator-managed accounts
              </h2>

              <p className="mt-2 text-small text-neutral-600">
                TraceVeda accounts are created and assigned
                roles by an administrator.
              </p>

              <div className="mt-3 grid grid-cols-2 gap-2 text-small">
                <code className="rounded-lg bg-surface-sunk px-3 py-2">
                  lab-001
                </code>

                <code className="rounded-lg bg-surface-sunk px-3 py-2">
                  man-001
                </code>

                <code className="rounded-lg bg-surface-sunk px-3 py-2">
                  aud-001
                </code>

                <code className="rounded-lg bg-surface-sunk px-3 py-2">
                  farmer-001
                </code>
              </div>
            </div>

            <p className="flex items-start gap-2.5 rounded-xl border border-neutral-200 bg-surface-sunk p-3.5 text-small text-neutral-600">
              <span className="mt-0.5 shrink-0 text-neutral-500">
                <IconInfo />
              </span>

              <span>
                <strong className="text-ink">
                  Consumer verification is public.
                </strong>{' '}
                Anyone scanning a medicine QR code can
                verify its traceability without creating
                an account.
              </span>
            </p>

          </div>
        </div>
      </div>
    </div>
  )
}
