import { create } from 'zustand'
import { authApi } from '@/lib/api'

interface AuthState {
  isAuth: boolean
  login: (login: string, password: string) => Promise<void>
  logout: () => Promise<void>
  check: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set) => ({
  isAuth: false,

  login: async (login, password) => {
    const res = await authApi.login(login, password)
    localStorage.setItem('access_token', res.data.access_token)
    set({ isAuth: true })
  },

  logout: async () => {
    await authApi.logout()
    localStorage.removeItem('access_token')
    set({ isAuth: false })
  },

  check: async () => {
    try {
      await authApi.me()
      set({ isAuth: true })
    } catch {
      set({ isAuth: false })
    }
  },
}))
