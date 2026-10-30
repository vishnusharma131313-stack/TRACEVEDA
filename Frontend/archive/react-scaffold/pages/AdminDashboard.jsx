
import { useContext, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { SessionContext } from '../App'
import { authAPI } from '../api/client'

export default function AdminDashboard() {
  const { user, logout } = useContext(SessionContext)
  const navigate = useNavigate()

  const [users, setUsers] = useState([])
  const [roles, setRoles] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [creating, setCreating] = useState(false)

  const [form, setForm] = useState({
    username: '',
    full_name: '',
    password: '',
    role: '',
    organisation_id: '',
  })

  const loadDashboard = async () => {
    setLoading(true)
    setError('')

    try {
      const [userData, roleData] = await Promise.all([
        authAPI.listUsers(),
        authAPI.roles(),
      ])

      setUsers(userData.users || [])
      setRoles(roleData.roles || [])
    } catch (err) {
      setError(err.message || 'Failed to load dashboard.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadDashboard()
  }, [])

  const handleChange = (event) => {
    setForm({
      ...form,
      [event.target.name]: event.target.value,
    })
  }

  const createUser = async (event) => {
    event.preventDefault()

    setError('')
    setSuccess('')

    if (!form.password || !form.role) {
      setError('Password and role are required.')
      return
    }

    if (form.password.length < 8) {
      setError('Password must contain at least 8 characters.')
      return
    }

    setCreating(true)

    try {
      const payload = {
        password: form.password,
        role: form.role,
        full_name: form.full_name.trim() || null,
        username: form.username.trim() || null,
        organisation_id: form.organisation_id.trim() || null,
      }

      await authAPI.createUser(payload)

      setSuccess('User account created successfully.')

      setForm({
        username: '',
        full_name: '',
        password: '',
        role: '',
        organisation_id: '',
      })

      await loadDashboard()
    } catch (err) {
      setError(err.message || 'Could not create user.')
    } finally {
      setCreating(false)
    }
  }

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  const totalUsers = users.length
  const totalRoles = new Set(users.map((u) => u.role)).size
  const adminUsers = users.filter((u) => u.role === 'admin').length

  return (
    <div className="min-h-screen bg-surface px-6 py-8">

      {/* HEADER */}
      <header className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-serif text-h1 text-ink">
            TraceVeda Admin
          </h1>
          <p className="mt-1 text-small text-neutral-600">
            Administrator control panel
          </p>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-small text-neutral-600">
            {user?.full_name || user?.username || 'Administrator'}
          </span>

          <button
            onClick={handleLogout}
            className="btn btn-ghost"
          >
            Logout
          </button>
        </div>
      </header>

      <main className="mx-auto mt-8 max-w-7xl space-y-8">

        {/* ERROR / SUCCESS */}
        {error && (
          <div className="rounded-xl bg-critical-50 p-4 text-small text-critical-700">
            {error}
          </div>
        )}

        {success && (
          <div className="rounded-xl bg-verified-50 p-4 text-small text-verified">
            {success}
          </div>
        )}

        {/* STATISTICS */}
        <section className="grid gap-4 sm:grid-cols-3">

          <StatCard
            title="Total Users"
            value={loading ? '...' : totalUsers}
          />

          <StatCard
            title="Active Roles"
            value={loading ? '...' : totalRoles}
          />

          <StatCard
            title="Administrators"
            value={loading ? '...' : adminUsers}
          />

        </section>

        {/* CREATE USER */}
        <section className="rounded-2xl border border-neutral-200 bg-surface-raised p-6 shadow-card">

          <h2 className="font-serif text-h3 text-ink">
            Create New User
          </h2>

          <p className="mt-1 text-small text-neutral-600">
            Create an account and assign its role.
          </p>

          <form
            onSubmit={createUser}
            className="mt-6 grid gap-4 md:grid-cols-2"
          >

            <FormField
              label="Full Name"
              name="full_name"
              value={form.full_name}
              onChange={handleChange}
              placeholder="Enter full name"
            />

            <FormField
              label="Username (optional)"
              name="username"
              value={form.username}
              onChange={handleChange}
              placeholder="Auto-generated if empty"
            />

            <FormField
              label="Password"
              name="password"
              type="password"
              value={form.password}
              onChange={handleChange}
              placeholder="Minimum 8 characters"
            />

            <div>
              <label className="block text-small font-semibold text-ink">
                Role
              </label>

              <select
                name="role"
                value={form.role}
                onChange={handleChange}
                required
                className="mt-1.5 w-full rounded-xl border-2 border-neutral-200 bg-surface px-3.5 py-2.5 text-body text-ink"
              >
                <option value="">Select role</option>

                {roles.map((role) => (
                  <option key={role.id} value={role.id}>
                    {role.label}
                  </option>
                ))}
              </select>
            </div>

            <FormField
              label="Organisation ID (optional)"
              name="organisation_id"
              value={form.organisation_id}
              onChange={handleChange}
              placeholder="Enter organisation ID"
            />

            <div className="flex items-end">
              <button
                type="submit"
                disabled={creating}
                className="btn btn-primary w-full justify-center px-6 py-3 disabled:opacity-60"
              >
                {creating ? 'Creating...' : 'Create User'}
              </button>
            </div>

          </form>
        </section>

        {/* USER TABLE */}
        <section className="rounded-2xl border border-neutral-200 bg-surface-raised p-6 shadow-card">

          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="font-serif text-h3 text-ink">
                User Management
              </h2>

              <p className="mt-1 text-small text-neutral-600">
                All registered TraceVeda accounts.
              </p>
            </div>

            <button
              onClick={loadDashboard}
              disabled={loading}
              className="btn btn-ghost"
            >
              {loading ? 'Loading...' : 'Refresh'}
            </button>
          </div>

          {loading ? (
            <p className="py-8 text-center text-neutral-500">
              Loading users...
            </p>
          ) : users.length === 0 ? (
            <p className="py-8 text-center text-neutral-500">
              No users found.
            </p>
          ) : (
            <div className="mt-5 overflow-x-auto">
              <table className="w-full text-left text-small">
                <thead>
                  <tr className="border-b border-neutral-200 text-neutral-500">
                    <th className="p-3">Username</th>
                    <th className="p-3">Full Name</th>
                    <th className="p-3">Role</th>
                    <th className="p-3">Organisation</th>
                  </tr>
                </thead>

                <tbody>
                  {users.map((item, index) => (
                    <tr
                      key={item.username || index}
                      className="border-b border-neutral-100"
                    >
                      <td className="p-3 font-medium text-ink">
                        {item.username || '—'}
                      </td>

                      <td className="p-3">
                        {item.full_name || '—'}
                      </td>

                      <td className="p-3 capitalize">
                        {item.role || '—'}
                      </td>

                      <td className="p-3">
                        {item.organisation_id || '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

        </section>

      </main>
    </div>
  )
}

function StatCard({ title, value }) {
  return (
    <div className="rounded-2xl border border-neutral-200 bg-surface-raised p-6 shadow-card">
      <p className="text-small text-neutral-500">{title}</p>
      <p className="mt-2 font-serif text-h1 text-ink">{value}</p>
    </div>
  )
}

function FormField({
  label,
  name,
  value,
  onChange,
  placeholder,
  type = 'text',
}) {
  return (
    <div>
      <label
        htmlFor={name}
        className="block text-small font-semibold text-ink"
      >
        {label}
      </label>

      <input
        id={name}
        name={name}
        type={type}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        required={name === 'password'}
        className="mt-1.5 w-full rounded-xl border-2 border-neutral-200 bg-surface px-3.5 py-2.5 text-body text-ink outline-none focus:border-verified"
      />
    </div>
  )
}
