import axios from 'axios'

const API_URL = process.env.NEXT_PUBLIC_API_URL || ''

export const api = axios.create({
  baseURL: `${API_URL}/api`,
  withCredentials: true,
})

// Токен из localStorage
api.interceptors.request.use((config) => {
  const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Авто-рефреш при 401
api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const original = error.config
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true
      try {
        const res = await axios.post(`${API_URL}/api/auth/refresh`, {}, { withCredentials: true })
        const token = res.data.access_token
        localStorage.setItem('access_token', token)
        original.headers.Authorization = `Bearer ${token}`
        return api(original)
      } catch {
        localStorage.removeItem('access_token')
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

// ── API методы ──────────────────────────────────────

export const authApi = {
  login: (login: string, password: string) =>
    api.post('/auth/login', { login, password }),
  logout: () => api.post('/auth/logout'),
  me: () => api.get('/auth/me'),
}

export const dashboardApi = {
  get: () => api.get('/dashboard'),
}

export const projectsApi = {
  list: (status?: string) => api.get('/projects', { params: { status_filter: status } }),
  get: (id: string) => api.get(`/projects/${id}`),
  create: (data: any) => api.post('/projects', data),
  update: (id: string, data: any) => api.put(`/projects/${id}`, data),
  delete: (id: string) => api.delete(`/projects/${id}`),
  stats: (id: string) => api.get(`/projects/${id}/stats`),
}

export const tasksApi = {
  list: (params?: any) => api.get('/tasks', { params }),
  get: (id: string) => api.get(`/tasks/${id}`),
  create: (data: any) => api.post('/tasks', data),
  update: (id: string, data: any) => api.put(`/tasks/${id}`, data),
  getComments: (id: string) => api.get(`/tasks/${id}/comments`),
  addComment: (id: string, content: string, author = 'owner') =>
    api.post(`/tasks/${id}/comments`, { content, author }),
}

export const agentsApi = {
  list: () => api.get('/agents'),
  get: (id: string) => api.get(`/agents/${id}`),
  update: (id: string, data: any) => api.put(`/agents/${id}`, data),
  trigger: (id: string) => api.post(`/agents/${id}/trigger`),
}

export const notificationsApi = {
  list: (is_read?: boolean) => api.get('/notifications', { params: { is_read } }),
  unreadCount: () => api.get('/notifications/unread-count'),
  markRead: (id: string) => api.put(`/notifications/${id}/read`),
  markAllRead: () => api.put('/notifications/read-all'),
}
