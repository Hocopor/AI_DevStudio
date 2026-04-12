'use client'
import { useState } from 'react'
import { tasksApi } from '@/lib/api'

const ALL_AGENTS = [
  { id: 'director',     label: '🎩 Директор',             group: 'Управление' },
  { id: 'analyst',      label: '📊 Аналитик рынка',        group: 'Стратегия' },
  { id: 'pm',           label: '📋 Продуктовый менеджер',  group: 'Стратегия' },
  { id: 'backend_dev',  label: '⚙️ Backend Dev',            group: 'Разработка' },
  { id: 'frontend_dev', label: '🖥️ Frontend Dev',           group: 'Разработка' },
  { id: 'ux_ui',        label: '🎨 UX/UI Дизайнер',         group: 'Разработка' },
  { id: 'qa',           label: '🧪 QA-инженер',             group: 'Разработка' },
  { id: 'devops',       label: '🔧 DevOps',                 group: 'Разработка' },
  { id: 'marketer',     label: '📣 Маркетолог',             group: 'Маркетинг' },
  { id: 'copywriter',   label: '✍️ Копирайтер',             group: 'Маркетинг' },
  { id: 'smm',          label: '📱 SMM-менеджер',           group: 'Маркетинг' },
  { id: 'seo',          label: '🔍 SEO-специалист',         group: 'Маркетинг' },
  { id: 'finance',      label: '💰 Финансовый аналитик',    group: 'Аналитика' },
]

const PRIORITIES = [
  { id: 'low',      label: '↓ Низкий' },
  { id: 'medium',   label: '→ Средний' },
  { id: 'high',     label: '↑ Высокий' },
  { id: 'critical', label: '🔴 Критический' },
]

const GROUPS = ['Управление', 'Стратегия', 'Разработка', 'Маркетинг', 'Аналитика']

export default function CreateTaskModal({ projectId, onClose, onCreated }: {
  projectId?: string
  onClose: () => void
  onCreated: () => void
}) {
  const [form, setForm] = useState({
    title: '',
    description: '',
    assigned_to: 'director',
    priority: 'medium',
    tags: '',
    requires_approval: false,
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const set = (k: string, v: any) => setForm(f => ({ ...f, [k]: v }))

  const submit = async () => {
    if (!form.title.trim()) { setError('Введите название задачи'); return }
    setLoading(true)
    setError('')
    try {
      await tasksApi.create({
        project_id: projectId || null,
        title: form.title.trim(),
        description: form.description.trim() || null,
        assigned_to: form.assigned_to,
        priority: form.priority,
        requires_approval: form.requires_approval,
        tags: form.tags.split(',').map(t => t.trim()).filter(Boolean),
        status: 'todo',
        created_by: 'owner',
      })
      onCreated()
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Ошибка при создании')
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4"
      onClick={onClose}>
      <div className="bg-gray-900 border border-gray-800 rounded-xl w-full max-w-lg p-6"
        onClick={e => e.stopPropagation()}>
        <h2 className="text-lg font-bold text-white mb-5">Новая задача</h2>

        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Название *</label>
            <input type="text" value={form.title} autoFocus
              onChange={e => set('title', e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !e.shiftKey && submit()}
              placeholder="Что нужно сделать?"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500 transition" />
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1">Описание</label>
            <textarea rows={3} value={form.description}
              onChange={e => set('description', e.target.value)}
              placeholder="Подробное описание для агента. Чем конкретнее — тем лучше результат."
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500 resize-none transition" />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Исполнитель</label>
              <select value={form.assigned_to} onChange={e => set('assigned_to', e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500">
                {GROUPS.map(group => (
                  <optgroup key={group} label={group}>
                    {ALL_AGENTS.filter(a => a.group === group).map(a => (
                      <option key={a.id} value={a.id}>{a.label}</option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm text-gray-400 mb-1">Приоритет</label>
              <select value={form.priority} onChange={e => set('priority', e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500">
                {PRIORITIES.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1">
              Теги <span className="text-gray-600">(через запятую)</span>
            </label>
            <input type="text" value={form.tags} onChange={e => set('tags', e.target.value)}
              placeholder="backend, landing, seo..."
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500 transition" />
          </div>

          <label className="flex items-center gap-3 cursor-pointer group">
            <input type="checkbox" checked={form.requires_approval}
              onChange={e => set('requires_approval', e.target.checked)}
              className="w-4 h-4 accent-indigo-500 cursor-pointer" />
            <span className="text-sm text-gray-400 group-hover:text-gray-300 transition">
              Требует моего согласования
            </span>
          </label>
        </div>

        {error && (
          <div className="mt-3 text-red-400 text-sm bg-red-900/10 border border-red-800/40 rounded-lg px-3 py-2">
            {error}
          </div>
        )}

        <div className="flex gap-3 mt-6">
          <button onClick={onClose}
            className="flex-1 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg py-2.5 text-sm transition">
            Отмена
          </button>
          <button onClick={submit} disabled={loading || !form.title.trim()}
            className="flex-1 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg py-2.5 text-sm font-medium transition">
            {loading ? 'Создаём...' : 'Создать задачу'}
          </button>
        </div>
      </div>
    </div>
  )
}
