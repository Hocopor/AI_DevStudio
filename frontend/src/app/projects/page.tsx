'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { ChevronRight, FolderOpen, Plus } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { ru } from 'date-fns/locale'
import { projectsApi } from '@/lib/api'

const STATUS_TABS = [
  { key: undefined, label: 'Все' },
  { key: 'active', label: 'Активные' },
  { key: 'paused', label: 'На паузе' },
  { key: 'done', label: 'Завершённые' },
  { key: 'archived', label: 'Архив' },
]

const STATUS_BADGE: Record<string, string> = {
  active: 'bg-[rgba(125,169,138,0.12)] text-[var(--success)]',
  paused: 'bg-[rgba(214,173,114,0.12)] text-[var(--warning)]',
  done: 'bg-[rgba(201,155,107,0.12)] text-[var(--accent-strong)]',
  archived: 'bg-[rgba(255,255,255,0.05)] text-stone-400',
}

const STATUS_LABEL: Record<string, string> = {
  active: 'Активен',
  paused: 'Пауза',
  done: 'Завершён',
  archived: 'Архив',
}

const AUTONOMY_LABEL: Record<string, string> = {
  free: 'Полная свобода',
  stage_approval: 'Согласование этапов',
  strict: 'Жёсткий контроль',
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

  useEffect(() => {
    load()
  }, [tab])

  return (
    <div className="space-y-6">
      <header className="page-header">
        <div>
          <div className="page-kicker">Project Ledger</div>
          <h1 className="page-title">Проекты в спокойной, плотной операционной сетке.</h1>
          <p className="page-subtitle">
            Каждая карточка показывает только полезный минимум: статус, режим автономности и текущий темп обновлений.
          </p>
        </div>
        <button onClick={() => setShowCreate(true)} className="btn-primary">
          <Plus size={15} />
          Новый проект
        </button>
      </header>

      <div className="flex flex-wrap gap-2">
        {STATUS_TABS.map(({ key, label }) => (
          <button
            key={String(key)}
            onClick={() => setTab(key)}
            className={tab === key ? 'btn-primary !py-2 !text-xs !tracking-[0.16em]' : 'btn-secondary !py-2 !text-xs !tracking-[0.16em]'}
          >
            {label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="panel h-40 animate-pulse" />
          ))}
        </div>
      ) : projects.length === 0 ? (
        <div className="panel px-6 py-20 text-center">
          <FolderOpen size={38} className="mx-auto text-stone-600" />
          <div className="mt-4 text-base text-stone-300">Пока нет проектов в этом фильтре.</div>
          <div className="mt-2 text-sm text-stone-500">Создайте новый поток, чтобы запустить работу команды.</div>
        </div>
      ) : (
        <div className="grid gap-4 xl:grid-cols-2">
          {projects.map((p) => (
            <Link key={p.id} href={`/projects/${p.id}`} className="panel block p-5 transition hover:border-[rgba(226,182,132,0.18)] hover:-translate-y-[1px]">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-lg font-medium text-stone-100">{p.title}</span>
                    <span className={`rounded-full px-2.5 py-1 text-[0.68rem] uppercase tracking-[0.14em] ${STATUS_BADGE[p.status] ?? 'bg-[rgba(255,255,255,0.05)] text-stone-400'}`}>
                      {STATUS_LABEL[p.status] ?? p.status}
                    </span>
                  </div>
                  {p.description && <p className="mt-3 line-clamp-2 text-sm leading-6 text-stone-400">{p.description}</p>}
                  <div className="mt-4 flex flex-wrap gap-3 text-xs text-stone-500">
                    <span className="pill pill-neutral">{AUTONOMY_LABEL[p.autonomy_mode] ?? p.autonomy_mode}</span>
                    <span>{formatDistanceToNow(new Date(p.updated_at), { addSuffix: true, locale: ru })}</span>
                  </div>
                </div>
                <ChevronRight size={18} className="mt-1 shrink-0 text-stone-600" />
              </div>
            </Link>
          ))}
        </div>
      )}

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
    if (!form.title.trim()) {
      setError('Введите название')
      return
    }
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/65 px-4 py-6 backdrop-blur-md">
      <div className="panel w-full max-w-2xl p-6">
        <div className="page-kicker">Create Project</div>
        <h2 className="mt-2 text-2xl font-semibold text-stone-100">Новый проект</h2>

        <div className="mt-6 grid gap-4 md:grid-cols-2">
          <Field label="Название *" value={form.title} onChange={(v: string) => set('title', v)} />
          <Field label="Цель проекта" value={form.goal} onChange={(v: string) => set('goal', v)} />
          <Field label="Целевая аудитория" value={form.target_audience} onChange={(v: string) => set('target_audience', v)} />
          <Field label="Модель монетизации" value={form.monetization_model} onChange={(v: string) => set('monetization_model', v)} />
          <div className="md:col-span-2">
            <Field label="Описание" value={form.description} onChange={(v: string) => set('description', v)} textarea />
          </div>
          <div className="md:col-span-2">
            <label className="mb-2 block text-sm text-stone-400">Режим автономности</label>
            <select value={form.autonomy_mode} onChange={(e) => set('autonomy_mode', e.target.value)} className="input-base">
              <option value="free">Полная свобода</option>
              <option value="stage_approval">Согласование этапов</option>
              <option value="strict">Жёсткий контроль</option>
            </select>
          </div>
        </div>

        {error && <div className="mt-4 rounded-2xl border border-[rgba(215,122,109,0.2)] bg-[rgba(215,122,109,0.08)] px-4 py-3 text-sm text-[var(--danger)]">{error}</div>}

        <div className="mt-6 flex flex-col gap-3 sm:flex-row">
          <button onClick={onClose} className="btn-secondary flex-1">Отмена</button>
          <button onClick={submit} disabled={loading} className="btn-primary flex-1">
            {loading ? 'Создаём...' : 'Создать'}
          </button>
        </div>
      </div>
    </div>
  )
}

function Field({ label, value, onChange, textarea }: any) {
  return (
    <div>
      <label className="mb-2 block text-sm text-stone-400">{label}</label>
      {textarea ? (
        <textarea rows={3} value={value} onChange={(e) => onChange(e.target.value)} className="input-base resize-none" />
      ) : (
        <input type="text" value={value} onChange={(e) => onChange(e.target.value)} className="input-base" />
      )}
    </div>
  )
}
