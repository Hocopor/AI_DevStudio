'use client'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useAuthStore } from '@/store/authStore'
import clsx from 'clsx'
import {
  LayoutDashboard, Activity, FolderOpen,
  Users, DollarSign, Bell, Settings, LogOut,
} from 'lucide-react'

const NAV = [
  { href: '/dashboard',   icon: LayoutDashboard, label: 'Дашборд' },
  { href: '/monitoring',  icon: Activity,         label: 'Мониторинг' },
  { href: '/projects',    icon: FolderOpen,       label: 'Проекты' },
  { href: '/team',        icon: Users,            label: 'Команда' },
  { href: '/finance',     icon: DollarSign,       label: 'Финансы' },
  { href: '/notifications', icon: Bell,           label: 'Уведомления' },
  { href: '/settings',    icon: Settings,         label: 'Настройки' },
]

export default function Sidebar() {
  const pathname = usePathname()
  const router = useRouter()
  const { logout } = useAuthStore()

  const handleLogout = async () => {
    await logout()
    router.push('/login')
  }

  return (
    <aside className="fixed top-0 left-0 h-screen w-56 bg-gray-900 border-r border-gray-800 flex flex-col z-10">
      {/* Лого */}
      <div className="px-5 py-5 border-b border-gray-800">
        <div className="text-white font-bold text-lg">AI DevStudio</div>
        <div className="text-gray-500 text-xs mt-0.5">Панель управления</div>
      </div>

      {/* Навигация */}
      <nav className="flex-1 py-4 px-3 space-y-1">
        {NAV.map(({ href, icon: Icon, label }) => (
          <Link
            key={href}
            href={href}
            className={clsx(
              'flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition',
              pathname.startsWith(href)
                ? 'bg-indigo-600/20 text-indigo-400 font-medium'
                : 'text-gray-400 hover:text-white hover:bg-gray-800'
            )}
          >
            <Icon size={16} />
            {label}
          </Link>
        ))}
      </nav>

      {/* Выход */}
      <div className="px-3 pb-5 border-t border-gray-800 pt-4">
        <button
          onClick={handleLogout}
          className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-gray-400 hover:text-white hover:bg-gray-800 w-full transition"
        >
          <LogOut size={16} />
          Выйти
        </button>
      </div>
    </aside>
  )
}
