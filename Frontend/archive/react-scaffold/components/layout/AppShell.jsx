import { useContext, useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { SessionContext } from '../../App'
import ChainIntegrityBadge from './ChainIntegrityBadge'
import { getRole } from '../../lib/roles'
import { IconBlocks, IconGrid, IconLeaf, IconLogout, IconMenu, IconRoute, IconSignal, IconX } from '../ui/Icons'

const NAV = [
  { screen: 'dashboard', to: '/dashboard', label: 'Command center', icon: <IconGrid /> },
  { screen: 'blockchain', to: '/blockchain', label: 'Blockchain explorer', icon: <IconBlocks /> },
  { screen: 'trace', to: '/trace', label: 'Trace & recall', icon: <IconRoute /> },
  { screen: 'iot', to: '/iot', label: 'IoT monitor', icon: <IconSignal /> },
]

export default function AppShell() {
  const { user, role, logout } = useContext(SessionContext)
  const location = useLocation()
  const [open, setOpen] = useState(false)

  const roleMeta = getRole(role)
  /* An unknown role would otherwise render an empty sidebar with no way out. */
  const links = NAV.filter((n) => !roleMeta || roleMeta.screens.includes(n.screen))
  const visible = links.length > 0 ? links : NAV

  useEffect(() => {
    setOpen(false)
  }, [location.pathname])

  return (
    <div className="flex min-h-screen bg-surface">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-ink focus:px-4 focus:py-2 focus:text-white"
      >
        Skip to content
      </a>

      {open && (
        <button
          type="button"
          aria-label="Close navigation"
          onClick={() => setOpen(false)}
          className="fixed inset-0 z-30 bg-ink/40 lg:hidden"
        />
      )}

      {/* ---------------- SIDEBAR ---------------- */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-[262px] flex-col border-r border-neutral-200 bg-surface-raised transition-transform duration-200 lg:static lg:translate-x-0 ${
          open ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex items-center justify-between px-5 py-5">
          <span className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-verified text-lg text-white">
              <IconLeaf />
            </span>
            <span>
              <span className="block font-serif text-h4 leading-none text-ink">TraceVeda</span>
              <span className="mt-0.5 block text-[10px] uppercase tracking-[0.12em] text-neutral-500">
                Traceability
              </span>
            </span>
          </span>
          <button
            type="button"
            onClick={() => setOpen(false)}
            aria-label="Close navigation"
            className="rounded-lg p-1.5 text-neutral-500 hover:bg-neutral-100 lg:hidden"
          >
            <IconX />
          </button>
        </div>

        <nav className="flex-1 space-y-1 px-3" aria-label="Main">
          {visible.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-xl px-3 py-2.5 text-small font-medium transition-colors ${
                  isActive
                    ? 'bg-verified-50 text-verified-700 ring-1 ring-inset ring-verified-200'
                    : 'text-neutral-600 hover:bg-neutral-100 hover:text-ink'
                }`
              }
            >
              <span className="text-base">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-neutral-200 p-3">
          <div className="flex items-center justify-between gap-2 rounded-xl bg-surface-sunk px-3 py-2.5">
            <div className="min-w-0">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-neutral-500">
                Signed in as
              </p>
              <p className="truncate text-small font-semibold text-ink">
                {user?.fullName || user?.username || 'Unknown user'}
              </p>
              <p className="truncate text-[11px] text-neutral-500">
                {roleMeta?.label ?? role ?? 'Unknown role'}
              </p>
            </div>
            <button
              type="button"
              onClick={logout}
              title="Sign out"
              aria-label="Sign out"
              className="rounded-lg p-2 text-neutral-500 transition-colors hover:bg-critical-50 hover:text-critical-700"
            >
              <IconLogout />
            </button>
          </div>
        </div>
      </aside>

      {/* ---------------- CONTENT ---------------- */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between gap-3 border-b border-neutral-200 bg-surface-raised/90 px-4 backdrop-blur lg:px-8">
          <button
            type="button"
            onClick={() => setOpen(true)}
            aria-label="Open navigation"
            className="rounded-lg p-2 text-neutral-600 hover:bg-neutral-100 lg:hidden"
          >
            <IconMenu />
          </button>

          <span className="hidden text-small text-neutral-500 lg:block">
            Chain integrity is re-verified live on every screen
          </span>

          <ChainIntegrityBadge />
        </header>

        <main id="main" className="flex-1 px-4 py-6 lg:px-8 lg:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
