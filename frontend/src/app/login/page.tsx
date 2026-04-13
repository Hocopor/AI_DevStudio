'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { ArrowRight } from 'lucide-react'
import { useAuthStore } from '@/store/authStore'

export default function LoginPage() {
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { login: doLogin } = useAuthStore()
  const router = useRouter()

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    const form = new FormData(e.currentTarget)
    const login = String(form.get('login') ?? '').trim()
    const password = String(form.get('password') ?? '')

    try {
      await doLogin(login, password)
      router.push('/dashboard')
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Неверный логин или пароль')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="relative min-h-screen overflow-hidden px-4 py-8">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(171,125,86,0.14),transparent_28%),linear-gradient(180deg,rgba(14,12,11,1),rgba(10,9,8,1))]" />
      <div className="relative flex min-h-screen items-center justify-center">
        <section className="panel w-full max-w-sm p-5 sm:p-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="login" className="sr-only">
                Логин
              </label>
              <input
                id="login"
                name="login"
                type="text"
                className="input-base"
                placeholder="Login"
                autoComplete="username"
                autoCapitalize="none"
                autoCorrect="off"
                spellCheck={false}
                required
              />
            </div>

            <div>
              <label htmlFor="password" className="sr-only">
                Пароль
              </label>
              <input
                id="password"
                name="password"
                type="password"
                className="input-base"
                placeholder="Password"
                autoComplete="current-password"
                required
              />
            </div>

            {error && (
              <div className="rounded-2xl border border-[rgba(215,122,109,0.22)] bg-[rgba(215,122,109,0.08)] px-4 py-3 text-sm text-[var(--danger)]">
                {error}
              </div>
            )}

            <button type="submit" disabled={loading} className="btn-primary w-full">
              {loading ? 'Entering...' : 'Enter'}
              <ArrowRight size={15} />
            </button>
          </form>
        </section>
      </div>
    </div>
  )
}
