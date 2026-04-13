'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { ArrowRight, ShieldCheck } from 'lucide-react'
import { useAuthStore } from '@/store/authStore'

export default function LoginPage() {
  const [login, setLogin] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { login: doLogin } = useAuthStore()
  const router = useRouter()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
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
    <div className="relative min-h-screen overflow-hidden px-4 py-10 md:px-8">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(201,155,107,0.14),transparent_25%),radial-gradient(circle_at_80%_15%,rgba(129,100,76,0.18),transparent_20%),linear-gradient(180deg,rgba(19,16,14,0.98),rgba(14,12,11,1))]" />
      <div className="relative mx-auto flex min-h-[calc(100vh-5rem)] max-w-6xl items-center">
        <div className="grid w-full gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <section className="panel hidden min-h-[620px] overflow-hidden lg:block">
            <div className="flex h-full flex-col justify-between p-10">
              <div>
                <div className="page-kicker">Autonomous Studio</div>
                <h1 className="page-title max-w-lg">Строгая операционная среда для AI-команды, проектов и решений владельца.</h1>
                <p className="page-subtitle">
                  Минималистичная контрольная панель для управления агентами, задачами, расходами и рабочими циклами без визуального шума.
                </p>
              </div>

              <div className="grid gap-4 md:grid-cols-3">
                <FeatureCard title="Контроль" text="Ключевые сигналы, блокеры и одобрения в одном спокойном контуре." />
                <FeatureCard title="Темп" text="Проекты, Kanban и агенты организованы в компактные рабочие поверхности." />
                <FeatureCard title="Надёжность" text="Без внешних портов, через туннель и с предсказуемой инфраструктурой." />
              </div>
            </div>
          </section>

          <section className="panel mx-auto w-full max-w-md p-6 sm:p-8">
            <div className="flex items-center gap-3">
              <span className="flex h-11 w-11 items-center justify-center rounded-2xl border border-[rgba(226,182,132,0.18)] bg-[rgba(201,155,107,0.12)] text-[var(--accent-strong)]">
                <ShieldCheck size={18} />
              </span>
              <div>
                <div className="page-kicker">Secure access</div>
                <div className="mt-1 text-xl font-semibold text-stone-100">Вход в AI DevStudio</div>
              </div>
            </div>

            <form onSubmit={handleSubmit} className="mt-8 space-y-4">
              <div>
                <label className="mb-2 block text-sm text-stone-400">Логин</label>
                <input
                  type="text"
                  value={login}
                  onChange={(e) => setLogin(e.target.value)}
                  className="input-base"
                  autoComplete="username"
                  required
                />
              </div>

              <div>
                <label className="mb-2 block text-sm text-stone-400">Пароль</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="input-base"
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
                {loading ? 'Вход...' : 'Войти в панель'}
                <ArrowRight size={15} />
              </button>
            </form>

            <div className="mt-8 rounded-2xl border border-white/10 bg-[rgba(255,255,255,0.02)] px-4 py-4 text-sm text-stone-400">
              Внутренний интерфейс для владельца. Авторизация нужна для управления проектами, агентами и инфраструктурой.
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}

function FeatureCard({ title, text }: { title: string; text: string }) {
  return (
    <div className="rounded-[20px] border border-white/10 bg-[rgba(255,255,255,0.03)] p-4">
      <div className="text-sm font-medium text-stone-100">{title}</div>
      <div className="mt-2 text-sm leading-6 text-stone-400">{text}</div>
    </div>
  )
}
