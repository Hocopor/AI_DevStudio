'use client'

import { useMemo, useState } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useAuthStore } from '@/store/authStore'
import clsx from 'clsx'
import {
  Activity,
  Bell,
  DollarSign,
  FolderOpen,
  LayoutDashboard,
  LogOut,
  Menu,
  Settings,
  Users,
  X,
} from 'lucide-react'

const NAV = [
  { href: '/dashboard', icon: LayoutDashboard, label: 'Дашборд', note: 'Сводка и сигналы' },
  { href: '/monitoring', icon: Activity, label: 'Мониторинг', note: 'Статусы и активность' },
  { href: '/projects', icon: FolderOpen, label: 'Проекты', note: 'Потоки и прогресс' },
  { href: '/team', icon: Users, label: 'Команда', note: 'Агенты и роли' },
  { href: '/finance', icon: DollarSign, label: 'Финансы', note: 'AI-расходы' },
  { href: '/notifications', icon: Bell, label: 'Уведомления', note: 'Критичные события' },
  { href: '/settings', icon: Settings, label: 'Настройки', note: 'Провайдеры и ключи' },
]

export default function Sidebar() {
  const pathname = usePathname()
  const router = useRouter()
  const { logout } = useAuthStore()
  const [open, setOpen] = useState(false)

  const activeItem = useMemo(
    () => NAV.find((item) => pathname.startsWith(item.href)),
    [pathname]
  )

  const handleLogout = async () => {
    await logout()
    router.push('/login')
  }

  const navContent = (
    <div className="flex h-full flex-col">
      <div className="border-b border-white/10 px-5 py-5">
        <div className="page-kicker">Operational Console</div>
        <div className="mt-2 flex items-end justify-between gap-3">
          <div>
            <div
              className="text-[1.55rem] font-semibold tracking-[0.03em] text-stone-100"
              style={{ fontFamily: '"Iowan Old Style", "Palatino Linotype", "Book Antiqua", serif' }}
            >
              AI DevStudio
            </div>
            <div className="mt-1 text-xs text-stone-400">autonomous operating system</div>
          </div>
          <span className="pill pill-neutral">private</span>
        </div>
      </div>

      <div className="px-5 py-5">
        <div className="rounded-2xl border border-white/10 bg-[rgba(201,155,107,0.08)] px-4 py-3">
          <div className="text-[0.68rem] uppercase tracking-[0.22em] text-[var(--accent)]">Current view</div>
          <div className="mt-2 text-sm font-medium text-stone-100">{activeItem?.label ?? 'Раздел'}</div>
          <div className="mt-1 text-xs leading-5 text-stone-400">{activeItem?.note ?? 'Панель управления системой и рабочими потоками.'}</div>
        </div>
      </div>

      <nav className="flex-1 space-y-1 px-4 pb-6">
        {NAV.map(({ href, icon: Icon, label, note }) => {
          const active = pathname.startsWith(href)
          return (
            <Link
              key={href}
              href={href}
              onClick={() => setOpen(false)}
              className={clsx(
                'group flex items-center gap-3 rounded-2xl px-3 py-3 transition',
                active
                  ? 'bg-[rgba(201,155,107,0.14)] text-stone-50 shadow-[inset_0_0_0_1px_rgba(226,182,132,0.18)]'
                  : 'text-stone-400 hover:bg-white/5 hover:text-stone-100'
              )}
            >
              <span
                className={clsx(
                  'flex h-10 w-10 items-center justify-center rounded-2xl border transition',
                  active
                    ? 'border-[rgba(226,182,132,0.24)] bg-[rgba(226,182,132,0.12)] text-[var(--accent-strong)]'
                    : 'border-white/10 bg-[rgba(255,255,255,0.02)] text-stone-500 group-hover:border-white/20 group-hover:text-stone-200'
                )}
              >
                <Icon size={16} />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-medium">{label}</span>
                <span className="mt-0.5 block truncate text-[0.72rem] text-stone-500 group-hover:text-stone-400">{note}</span>
              </span>
            </Link>
          )
        })}
      </nav>

      <div className="border-t border-white/10 px-4 py-4">
        <button onClick={handleLogout} className="btn-secondary w-full justify-start rounded-2xl px-3 py-3">
          <LogOut size={15} />
          Выйти
        </button>
      </div>
    </div>
  )

  return (
    <>
      <div className="fixed inset-x-0 top-0 z-30 border-b border-white/10 bg-[rgba(18,15,13,0.84)] px-4 py-3 backdrop-blur md:hidden">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-[0.64rem] uppercase tracking-[0.24em] text-[var(--accent)]">AI DevStudio</div>
            <div className="mt-1 text-sm text-stone-200">{activeItem?.label ?? 'Панель'}</div>
          </div>
          <button
            onClick={() => setOpen((value) => !value)}
            className="flex h-11 w-11 items-center justify-center rounded-2xl border border-white/10 bg-white/5 text-stone-100"
          >
            {open ? <X size={18} /> : <Menu size={18} />}
          </button>
        </div>
      </div>

      {open && (
        <button
          className="fixed inset-0 z-30 bg-black/50 backdrop-blur-sm md:hidden"
          onClick={() => setOpen(false)}
          aria-label="Close navigation"
        />
      )}

      <aside
        className={clsx(
          'fixed inset-y-0 left-0 z-40 w-[18.5rem] border-r border-white/10 bg-[linear-gradient(180deg,rgba(27,23,20,0.96),rgba(17,15,13,0.96))] backdrop-blur-2xl transition-transform md:translate-x-0',
          open ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        {navContent}
      </aside>
    </>
  )
}
