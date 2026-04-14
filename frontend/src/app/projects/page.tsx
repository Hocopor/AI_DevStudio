'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { ChevronRight, FolderOpen, Pause, Play, Plus, Trash2 } from 'lucide-react'
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
  const [busyProjectId, setBusyProjectId] = useState<string | null>(null)
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

  const runAction = async (projectId: string, action: 'start' | 'pause' | 'delete') => {
    setBusyProjectId(projectId)
    try {
      if (action === 'start') await projectsApi.start(projectId)
      if (action === 'pause') await projectsApi.pause(projectId)
      if (action === 'delete') await projectsApi.delete(projectId)
      await load()
    } finally {
      setBusyProjectId(null)
    }
  }

  return (
    <div className="space-y-6">
      <header className="page-header">
        <div>
          <div className="page-kicker">Project Ledger</div>
          <h1 className="page-title">Проекты в спокойной, плотной операционной сетке.</h1>
          <p className="page-subtitle">
            Каждая карточка показывает полезный минимум: статус, режим автономности, свежесть обновлений и быстрые действия по управлению.
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
            <div key={i} className="panel h-44 animate-pulse" />
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
          {projects.map((project) => (
            <ProjectCard
              key={project.id}
              project={project}
              busy={busyProjectId === project.id}
              onAction={runAction}
            />
          ))}
        </div>
      )}

      {showCreate && <CreateProjectModal onClose={() => setShowCreate(false)} onCreated={load} />}
    </div>
  )
}

function ProjectCard({ project, busy, onAction }: any) {
  return (
    <div className="panel p-5 transition hover:border-[rgba(226,182,132,0.18)] hover:-translate-y-[1px]">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-lg font-medium text-stone-100">{project.title}</span>
            <span className={`rounded-full px-2.5 py-1 text-[0.68rem] uppercase tracking-[0.14em] ${STATUS_BADGE[project.status] ?? 'bg-[rgba(255,255,255,0.05)] text-stone-400'}`}>
              {STATUS_LABEL[project.status] ?? project.status}
            </span>
          </div>
          {project.description && <p className="mt-3 line-clamp-2 text-sm leading-6 text-stone-400">{project.description}</p>}
          <div className="mt-4 flex flex-wrap gap-3 text-xs text-stone-500">
            <span className="pill pill-neutral">{AUTONOMY_LABEL[project.autonomy_mode] ?? project.autonomy_mode}</span>
            <span>{formatDistanceToNow(new Date(project.updated_at), { addSuffix: true, locale: ru })}</span>
          </div>
        </div>

        <Link href={`/projects/${project.id}`} className="mt-1 shrink-0 text-stone-600 hover:text-stone-300 transition">
          <ChevronRight size={18} />
        </Link>
      </div>

      <div className="mt-5 flex flex-wrap gap-2">
        <button
          onClick={() => onAction(project.id, 'start')}
          disabled={busy || project.status === 'active'}
          className="btn-secondary !py-2 !px-3 text-xs disabled:opacity-40"
        >
          <Play size={14} />
          Старт
        </button>
        <button
          onClick={() => onAction(project.id, 'pause')}
          disabled={busy || project.status === 'paused' || project.status === 'archived'}
          className="btn-secondary !py-2 !px-3 text-xs disabled:opacity-40"
        >
          <Pause size={14} />
          Пауза
        </button>
        <button
          onClick={() => onAction(project.id, 'delete')}
          disabled={busy || project.status === 'archived'}
          className="btn-secondary !py-2 !px-3 text-xs text-rose-200 disabled:opacity-40"
        >
          <Trash2 size={14} />
          Удалить
        </button>
      </div>
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
  const [saving, setSaving] = useState(false)

  const submit = async () => {
    if (!form.title.trim()) return
    setSaving(true)
    try {
      await projectsApi.create(form)
      onCreated()
      onClose()
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 bg-[rgba(8,8,8,0.72)] backdrop-blur-sm flex items-center justify-center px-4">
      <div className="panel w-full max-w-2xl p-6 space-y-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="page-kicker">Create Project</div>
            <h2 className="text-xl font-semibold text-white mt-1">Новый проект</h2>
          </div>
          <button onClick={onClose} className="text-stone-500 hover:text-stone-300 transition">Закрыть</button>
        </div>

        <div className="grid gap-4">
          <input value={form.title} onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} placeholder="Название проекта" className="input-base" />
          <textarea value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} placeholder="Описание" className="input-base min-h-28" />
          <input value={form.goal} onChange={(e) => setForm((f) => ({ ...f, goal: e.target.value }))} placeholder="Цель" className="input-base" />
          <input value={form.target_audience} onChange={(e) => setForm((f) => ({ ...f, target_audience: e.target.value }))} placeholder="Целевая аудитория" className="input-base" />
          <input value={form.monetization_model} onChange={(e) => setForm((f) => ({ ...f, monetization_model: e.target.value }))} placeholder="Монетизация" className="input-base" />
          <select value={form.autonomy_mode} onChange={(e) => setForm((f) => ({ ...f, autonomy_mode: e.target.value }))} className="input-base">
            <option value="free">Полная свобода</option>
            <option value="stage_approval">Согласование этапов</option>
            <option value="strict">Жёсткий контроль</option>
          </select>
        </div>

        <div className="flex justify-end gap-3">
          <button onClick={onClose} className="btn-secondary">Отмена</button>
          <button onClick={submit} disabled={saving || !form.title.trim()} className="btn-primary">
            {saving ? 'Создаю...' : 'Создать проект'}
          </button>
        </div>
      </div>
    </div>
  )
}
