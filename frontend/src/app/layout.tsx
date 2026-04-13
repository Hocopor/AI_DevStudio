'use client'

import './globals.css'
import { useEffect } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import { useAuthStore } from '@/store/authStore'
import Sidebar from '@/components/ui/Sidebar'

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const { isAuth, check } = useAuthStore()
  const router = useRouter()
  const pathname = usePathname()

  useEffect(() => {
    check().then(() => {
      if (!useAuthStore.getState().isAuth && pathname !== '/login') {
        router.push('/login')
      }
    })
  }, [])

  if (pathname === '/login') {
    return (
      <html lang="ru">
        <body>{children}</body>
      </html>
    )
  }

  if (!isAuth) return null

  return (
    <html lang="ru">
      <body>
        <div className="app-shell md:flex">
          <Sidebar />
          <main className="app-main md:ml-[18.5rem]">
            <div className="page-shell">{children}</div>
          </main>
        </div>
      </body>
    </html>
  )
}
