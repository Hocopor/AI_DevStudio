'use client'
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
        <body className="bg-gray-950 text-gray-100 min-h-screen">{children}</body>
      </html>
    )
  }

  if (!isAuth) return null

  return (
    <html lang="ru">
      <body className="bg-gray-950 text-gray-100 min-h-screen flex">
        <Sidebar />
        <main className="flex-1 ml-56 p-6 overflow-auto">{children}</main>
      </body>
    </html>
  )
}
