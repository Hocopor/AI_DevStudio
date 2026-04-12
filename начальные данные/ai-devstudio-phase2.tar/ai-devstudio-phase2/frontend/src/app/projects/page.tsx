'use client'
import { useEffect, useState } from 'react'
import { projectsApi } from '@/lib/api'
import Link from 'next/link'
import { Plus, FolderOpen, ChevronRight } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { ru } from 'date-fns/locale'

const STATUS_TABS = [
  { key: undefined, label: 'Все' },
  { key: 'active',   label: 'Активные' },
  { key: 'paused',   label: 'На паузе' },
  { key: 'done',     label: 'Завершённые' },
  { key: 'archived', label: 'Архив' },
]

const STATUS_BADGE: Record<string, string> = {
  active:   'bg-emerald-900/40 text-emerald-400',
  paused:   'bg-amber-900/40 text-amber-400',
  done:     'bg-indigo-900/40 text-indigo-400',
  archived: 'bg-gray-800 text-gray-500',
}

const STATUS_LABEL: Record<string, string> = {
  active: 'Активен', paused: 'Пауза', done: 'Завершён', archived: 'Архив',
}

const AUTONOMY_LABEL: Record<string, string> = {
  free:            '🟢 Полная свобода',
  stage_approval:  '🟡 Согласование этапов',
  strict:          '🔴 Жёсткий контроль',
}

export default function ProjectsPage() {
  const [projects, setProjects] = useState<any[]>([])
  const [tab, setTab] = useState<string | undefined>('active')
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const res = await projectsApi.list(tab)
      setProjects(res.data)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [tab])

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Проекты</h1>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition"
        >
          <Plus size={16} /> Новый проект
        </button>
      </div>

      {/* Вкладки */}
      <div className="flex gap-1 bg-gray-900 p-1 rounded-lg border border-gray-800 w-fit">
        {STATUS_TABS.map(({ key, label }) => (
          <button
            key={String(key)}
            onClick={() => setTab(key)}
            className={`px-4 py-1.5 rounded-md text-sm transition ${
              tab === key ? 'bg-indigo-600 text-white' : 'text-gray-400 hover:text-white'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Список */}
      {loading ? (
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-24 bg-gray-900 rounded-xl border border-gray-800 animate-pulse" />
          ))}
        </div>
      ) : projects.length === 0 ? (
        <div className="text-center py-20 text-gray-600">
          <FolderOpen size={40} className="mx-auto mb-3 opacity-30" />
          <div>Проектов нет</div>
        </div>
      ) : (
        <div className="space-y-3">
          {projects.map((p) => (
            <Link
              key={p.id}
              href={`/projects/${p.id}`}
              className="block bg-gray-900 border border-gray-800 rounded-xl p-5 hover:border-gray-700 transition group"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 mb-1">
                    <span className="text-white font-medium text-base">{p.title}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_BADGE[p.status] ?? 'bg-gray-800 text-gray-400'}`}>
                      {STATUS_LABEL[p.status] ?? p.status}
                    </span>
                  </div>
                  {p.description && (
                    <p className="text-sm text-gray-500 line-clamp-1">{p.description}</p>
                  )}
                  <div className="flex items-center gap-4 mt-2 text-xs text-gray-600">
                    <span>{AUTONOMY_LABEL[p.autonomy_mode] ?? p.autonomy_mode}</span>
                    <span>·</span>
                    <span>
                      {formatDistanceToNow(new Date(p.updated_at), { addSuffix: true, locale: ru })}
                    </span>
                  </div>
                </div>
                <ChevronRight size={18} className="text-gray-700 group-hover:text-gray-400 transition mt-1 shrink-0" />
              </div>
            </Link>
          ))}
        </div>
      )}

      {/* Модалка создания */}
      {showCreate && <CreateProjectModal onClose={() => setShowCreate(false)} onCreated={load} />}
    </div>
  )
}

function CreateProjectModal({ onClose, onCreated }: any) {
  const [form, setForm] = useState({
    title: '',
    description: '',
    goal: '',
    target_audience: '',
    monetization_model: '',
    autonomy_mode: 'stage_approval',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }))

  const submit = async () => {
    if (!form.title.trim()) { setError('Введите название'); return }
    setLoading(true)
    try {
      await projectsApi.create(form)
      onCreated()
      onClose()
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Ошибка создания')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-900 border border-gray-800 rounded-xl w-full max-w-lg p-6">
        <h2 className="text-lg font-bold text-white mb-5">Новый проект</h2>

        <div className="space-y-4">
          <Field label="Название *" value={form.title} onChange={(v: string) => set('title', v)} />
          <Field label="Описание" value={form.description} onChange={(v: string) => set('description', v)} textarea />
          <Field label="Цель проекта" value={form.goal} onChange={(v: string) => set('goal', v)} />
          <Field label="Целевая аудитория" value={form.target_audience} onChange={(v: string) => set('target_audience', v)} />
          <Field label="Модель монетизации" value={form.monetization_model} onChange={(v: string) => set('monetization_model', v)} />

          <div>
            <label className="block text-sm text-gray-400 mb-1">Режим автономности</label>
            <select
              value={form.autonomy_mode}
              onChange={(e) => set('autonomy_mode', e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500"
            >
              <option value="free">🟢 Полная свобода</option>
              <option value="stage_approval">🟡 Согласование этапов</option>
              <option value="strict">🔴 Жёсткий контроль</option>
            </select>
          </div>
        </div>

        {error && <div className="mt-3 text-red-400 text-sm">{error}</div>}

        <div className="flex gap-3 mt-6">
          <button onClick={onClose} className="flex-1 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg py-2 text-sm transition">
            Отмена
          </button>
          <button onClick={submit} disabled={loading} className="flex-1 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg py-2 text-sm font-medium transition">
            {loading ? 'Создаём...' : 'Создать'}
          </button>
        </div>
      </div>
    </div>
  )
}

function Field({ label, value, onChange, textarea }: any) {
  const cls = "w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500 transition"
  return (
    <div>
      <label className="block text-sm text-gray-400 mb-1">{label}</label>
      {textarea
        ? <textarea rows={2} value={value} onChange={(e) => onChange(e.target.value)} className={cls} />
        : <input type="text" value={value} onChange={(e) => onChange(e.target.value)} className={cls} />
      }
    </div>
  )
}
