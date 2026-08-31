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


const SIGNUP_ROLES = [
  {
    value: 'farmer',
    label: 'Farmer',
  },
  {
    value: 'processor',
    label: 'Processor',
  },
  {
    value: 'lab',
    label: 'Laboratory',
  },
  {
    value: 'logistics',
    label: 'Logistics / IoT',
  },
  {
    value: 'manufacturer',
    label: 'Manufacturer',
  },
]


export default function Login() {

  const { signIn } = useContext(SessionContext)

  const navigate = useNavigate()


  // ============================================================
  // MODE
  // ============================================================

  const [mode, setMode] = useState('signin')


  // ============================================================
  // SIGN IN
  // ============================================================

  const [username, setUsername] = useState('')

  const [password, setPassword] = useState('')


  // ============================================================
  // SIGN UP
  // ============================================================

  const [fullName, setFullName] = useState('')

  const [signupPassword, setSignupPassword] = useState('')

  const [confirmPassword, setConfirmPassword] = useState('')

  const [role, setRole] = useState('')


  // ============================================================
  // STATUS
  // ============================================================

  const [error, setError] = useState(null)

  const [success, setSuccess] = useState(null)

  const [busy, setBusy] = useState(false)


  // ============================================================
  // SWITCH MODE
  // ============================================================

  const switchMode = (newMode) => {

    setMode(newMode)

    setError(null)

    setSuccess(null)

  }


  // ============================================================
  // SIGN IN
  // ============================================================

  const submitLogin = async (event) => {

    event.preventDefault()


    if (!username.trim() || !password) {

      setError('Enter your username and password.')

      return

    }


    setBusy(true)

    setError(null)

    setSuccess(null)


    try {

      const session = await authAPI.login(
        username.trim(),
        password,
      )


      // Save JWT + user session

      signIn(session)


      // Navigate according to SERVER role

      navigate(
        homeFor(session.role),
        {
          replace: true,
        },
      )


    }

    catch (err) {

      setError(

        err?.status === 401
          ? 'Incorrect username or password.'
          : err?.message || 'Could not reach the server.',

      )

    }

    finally {

      setBusy(false)

    }

  }


  // ============================================================
  // SIGN UP
  // ============================================================

  const submitSignup = async (event) => {

    event.preventDefault()


    if (!fullName.trim()) {

      setError('Enter your full name.')

      return

    }


    if (!role) {

      setError('Please select your role.')

      return

    }


    if (!signupPassword) {

      setError('Enter a password.')

      return

    }


    if (signupPassword.length < 8) {

      setError('Password must be at least 8 characters.')

      return

    }


    if (signupPassword !== confirmPassword) {

      setError('Passwords do not match.')

      return

    }


    setBusy(true)

    setError(null)

    setSuccess(null)


    try {

      /*
       * Backend automatically generates the username.
       *
       * Examples:
       *
       * lab-001
       * lab-002
       *
       * man-001
       * man-002
       *
       * aud-001
       *
       * etc.
       */

      const result = await authAPI.signup(

        signupPassword,

        role,

        fullName.trim(),

      )


      const generatedUsername =
        result?.user?.username


      setSuccess(

        generatedUsername
          ? `Account created successfully! Your username is ${generatedUsername}`
          : 'Account created successfully!',

      )


      // Clear signup form

      setFullName('')

      setSignupPassword('')

      setConfirmPassword('')

      setRole('')


      /*
       * Switch to login after account creation.
       *
       * Pre-fill generated username so the user
       * can immediately log in.
       */

      if (generatedUsername) {

        setUsername(generatedUsername)

      }


      setTimeout(() => {

        setMode('signin')

      }, 1500)


    }

    catch (err) {

      setError(

        err?.message ||
        'Could not create the account.',

      )

    }

    finally {

      setBusy(false)

    }

  }


  return (

    <div className="min-h-screen bg-surface">

      <div className="mx-auto flex min-h-screen max-w-5xl flex-col justify-center px-6 py-12">


        {/* ====================================================
            HEADER
        ==================================================== */}

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

            Sign in or create an account to access the TraceVeda supply-chain system.

          </p>

        </header>



        <div className="grid gap-8 lg:grid-cols-[minmax(0,380px)_minmax(0,1fr)]">


          {/* ====================================================
              AUTH CARD
          ==================================================== */}

          <div className="rounded-2xl border border-neutral-200 bg-surface-raised p-6 shadow-card">


            {/* MODE BUTTONS */}

            <div className="mb-6 flex rounded-xl bg-surface-sunk p-1">


              <button

                type="button"

                onClick={() => switchMode('signin')}

                className={`flex-1 rounded-lg px-4 py-2 text-small font-semibold transition ${
                  mode === 'signin'
                    ? 'bg-white text-ink shadow'
                    : 'text-neutral-500'
                }`}

              >

                Sign in

              </button>


              <button

                type="button"

                onClick={() => switchMode('signup')}

                className={`flex-1 rounded-lg px-4 py-2 text-small font-semibold transition ${
                  mode === 'signup'
                    ? 'bg-white text-ink shadow'
                    : 'text-neutral-500'
                }`}

              >

                Create account

              </button>


            </div>



            {/* ====================================================
                SIGN IN FORM
            ==================================================== */}

            {mode === 'signin' && (

              <form onSubmit={submitLogin}>


                <h2 className="font-serif text-h3 text-ink">

                  Sign in

                </h2>


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

                  onChange={(e) =>
                    setUsername(e.target.value)
                  }

                  disabled={busy}

                  placeholder="Example: lab-001"

                  className="mt-1.5 w-full rounded-xl border-2 border-neutral-200 bg-surface px-3.5 py-2.5 text-body text-ink outline-none transition-colors focus:border-verified disabled:opacity-60"

                />


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

                  onChange={(e) =>
                    setPassword(e.target.value)
                  }

                  disabled={busy}

                  className="mt-1.5 w-full rounded-xl border-2 border-neutral-200 bg-surface px-3.5 py-2.5 text-body text-ink outline-none transition-colors focus:border-verified disabled:opacity-60"

                />


                {error && (

                  <p
                    role="alert"
                    className="mt-4 rounded-xl bg-critical-50 px-3.5 py-2.5 text-small text-critical-700"
                  >

                    {error}

                  </p>

                )}


                {success && (

                  <p
                    className="mt-4 rounded-xl bg-verified-50 px-3.5 py-2.5 text-small text-verified"
                  >

                    {success}

                  </p>

                )}


                <button

                  type="submit"

                  disabled={busy}

                  className="btn btn-primary mt-5 w-full justify-center px-6 py-3 text-body disabled:opacity-60"

                >

                  {busy
                    ? 'Signing in…'
                    : <>
                        Sign in
                        <IconArrowRight />
                      </>
                  }

                </button>


                <button

                  type="button"

                  onClick={() => navigate('/verify')}

                  className="btn btn-ghost mt-2 w-full justify-center"

                >

                  Skip — Verify a medicine

                </button>


              </form>

            )}



            {/* ====================================================
                SIGN UP FORM
            ==================================================== */}

            {mode === 'signup' && (

              <form onSubmit={submitSignup}>


                <h2 className="font-serif text-h3 text-ink">

                  Create account

                </h2>


                <p className="mt-1 text-small text-neutral-600">

                  Your TraceVeda username will be generated automatically.

                </p>



                {/* FULL NAME */}

                <label
                  htmlFor="fullName"
                  className="mt-5 block text-small font-semibold text-ink"
                >

                  Full name

                </label>


                <input

                  id="fullName"

                  type="text"

                  value={fullName}

                  onChange={(e) =>
                    setFullName(e.target.value)
                  }

                  disabled={busy}

                  placeholder="Enter your full name"

                  className="mt-1.5 w-full rounded-xl border-2 border-neutral-200 bg-surface px-3.5 py-2.5 text-body text-ink outline-none transition-colors focus:border-verified disabled:opacity-60"

                />



                {/* ROLE */}

                <label
                  htmlFor="role"
                  className="mt-4 block text-small font-semibold text-ink"
                >

                  Role

                </label>


                <select

                  id="role"

                  value={role}

                  onChange={(e) =>
                    setRole(e.target.value)
                  }

                  disabled={busy}

                  className="mt-1.5 w-full rounded-xl border-2 border-neutral-200 bg-surface px-3.5 py-2.5 text-body text-ink outline-none transition-colors focus:border-verified disabled:opacity-60"

                >

                  <option value="">

                    Select your role

                  </option>


                  {SIGNUP_ROLES.map((item) => (

                    <option
                      key={item.value}
                      value={item.value}
                    >

                      {item.label}

                    </option>

                  ))}

                </select>



                {/* PASSWORD */}

                <label
                  htmlFor="signupPassword"
                  className="mt-4 block text-small font-semibold text-ink"
                >

                  Password

                </label>


                <input

                  id="signupPassword"

                  type="password"

                  value={signupPassword}

                  onChange={(e) =>
                    setSignupPassword(e.target.value)
                  }

                  disabled={busy}

                  placeholder="Minimum 8 characters"

                  className="mt-1.5 w-full rounded-xl border-2 border-neutral-200 bg-surface px-3.5 py-2.5 text-body text-ink outline-none transition-colors focus:border-verified disabled:opacity-60"

                />



                {/* CONFIRM PASSWORD */}

                <label
                  htmlFor="confirmPassword"
                  className="mt-4 block text-small font-semibold text-ink"
                >

                  Confirm password

                </label>


                <input

                  id="confirmPassword"

                  type="password"

                  value={confirmPassword}

                  onChange={(e) =>
                    setConfirmPassword(e.target.value)
                  }

                  disabled={busy}

                  className="mt-1.5 w-full rounded-xl border-2 border-neutral-200 bg-surface px-3.5 py-2.5 text-body text-ink outline-none transition-colors focus:border-verified disabled:opacity-60"

                />


                {error && (

                  <p
                    role="alert"
                    className="mt-4 rounded-xl bg-critical-50 px-3.5 py-2.5 text-small text-critical-700"
                  >

                    {error}

                  </p>

                )}


                {success && (

                  <p
                    className="mt-4 rounded-xl bg-verified-50 px-3.5 py-2.5 text-small text-verified"
                  >

                    {success}

                  </p>

                )}


                <button

                  type="submit"

                  disabled={busy}

                  className="btn btn-primary mt-5 w-full justify-center px-6 py-3 text-body disabled:opacity-60"

                >

                  {busy
                    ? 'Creating account…'
                    : <>
                        Create account
                        <IconArrowRight />
                      </>
                  }

                </button>


              </form>

            )}


          </div>



          {/* ====================================================
              INFORMATION
          ==================================================== */}

          <div className="space-y-4">


            <div className="rounded-2xl border border-neutral-200 bg-surface-raised p-6">


              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-verified-50 text-verified">

                <IconShield />

              </span>


              <h2 className="mt-3 font-serif text-h4 text-ink">

                Secure role-based access

              </h2>


              <p className="mt-1.5 text-small text-neutral-600">

                Your role is controlled by the backend. After signing in,
                the server issues an authentication token and the frontend
                opens the appropriate workspace.

              </p>


            </div>



            <div className="rounded-2xl border border-neutral-200 bg-surface-raised p-6">


              <h2 className="font-serif text-h4 text-ink">

                Automatic account IDs

              </h2>


              <p className="mt-2 text-small text-neutral-600">

                TraceVeda automatically generates role-based usernames.

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

                Anyone scanning a medicine QR code can verify its traceability
                without creating an account.

              </span>


            </p>


          </div>


        </div>


      </div>


    </div>

  )

}