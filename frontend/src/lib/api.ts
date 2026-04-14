import axios from 'axios'

const API_URL = process.env.NEXT_PUBLIC_API_URL || ''

export const api = axios.create({
  baseURL: `${API_URL}/api`,
  withCredentials: true,
})

api.interceptors.request.use((config) => {
  const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

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

export const authApi = {
  login:   (login: string, password: string) => api.post('/auth/login', { login, password }),
  logout:  () => api.post('/auth/logout'),
  me:      () => api.get('/auth/me'),
}

export const dashboardApi = {
  get: () => api.get('/dashboard'),
}

export const projectsApi = {
  list:   (status?: string)       => api.get('/projects', { params: { status_filter: status } }),
  get:    (id: string)            => api.get(`/projects/${id}`),
  create: (data: any)             => api.post('/projects', data),
  update: (id: string, data: any) => api.put(`/projects/${id}`, data),
  delete: (id: string)            => api.delete(`/projects/${id}`),
  start:  (id: string)            => api.post(`/projects/${id}/start`),
  pause:  (id: string)            => api.post(`/projects/${id}/pause`),
  stats:  (id: string)            => api.get(`/projects/${id}/stats`),
  artifacts: (id: string)         => api.get(`/projects/${id}/artifacts`),
  previewArtifact: (id: string, path: string) =>
    api.get(`/projects/${id}/artifacts/preview`, { params: { path } }),
  downloadArtifactUrl: (id: string, path: string) =>
    `${API_URL}/api/projects/${id}/artifacts/download?path=${encodeURIComponent(path)}`,
  getGithub: (id: string)         => api.get(`/projects/${id}/github`),
  saveGithub: (id: string, data: any) => api.put(`/projects/${id}/github`, data),
  publishArtifact: (id: string, data: any) => api.post(`/projects/${id}/github/publish-artifact`, data),
}

export const tasksApi = {
  list:        (params?: any)          => api.get('/tasks', { params }),
  get:         (id: string)            => api.get(`/tasks/${id}`),
  create:      (data: any)             => api.post('/tasks', data),
  update:      (id: string, data: any) => api.put(`/tasks/${id}`, data),
  getComments: (id: string)            => api.get(`/tasks/${id}/comments`),
  addComment:  (id: string, content: string, author = 'owner') =>
    api.post(`/tasks/${id}/comments`, { content, author }),
}

export const agentsApi = {
  list:    ()                         => api.get('/agents'),
  get:     (id: string)               => api.get(`/agents/${id}`),
  update:  (id: string, data: any)    => api.put(`/agents/${id}`, data),
  trigger: (id: string)               => api.post(`/agents/${id}/trigger`),
}

export const notificationsApi = {
  list:        (is_read?: boolean) => api.get('/notifications', { params: { is_read } }),
  unreadCount: ()                  => api.get('/notifications/unread-count'),
  markRead:    (id: string)        => api.put(`/notifications/${id}/read`),
  markAllRead: ()                  => api.put('/notifications/read-all'),
}

export const skillsApi = {
  list:       (agent_id?: string)     => api.get('/skills', { params: { agent_id } }),
  create:     (data: any)             => api.post('/skills', data),
  update:     (id: string, data: any) => api.put(`/skills/${id}`, data),
  delete:     (id: string)            => api.delete(`/skills/${id}`),
  distribute: (id: string, target_agent_ids: string[]) =>
    api.post(`/skills/${id}/distribute`, { target_agent_ids }),
}

export const codexApi = {
  list:       ()                      => api.get('/codex-accounts'),
  add:        (data: any)             => api.post('/codex-accounts', data),
  update:     (id: string, data: any) => api.put(`/codex-accounts/${id}`, data),
  delete:     (id: string)            => api.delete(`/codex-accounts/${id}`),
  setCurrent: (id: string)            => api.post(`/codex-accounts/${id}/set-current`),
}

export const financeApi = {
  summary:  (period: 'day' | 'week' | 'month' | 'all' = 'month') =>
    api.get('/finance/summary', { params: { period } }),
  usageLog: (params?: { provider?: string; agent_id?: string; limit?: number }) =>
    api.get('/finance/usage-log', { params }),
}
