'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import {
  ArrowLeft,
  BarChart2,
  Download,
  Eye,
  FileText,
  Github,
  LayoutGrid,
  MessageSquare,
  Package,
  Upload,
} from 'lucide-react'

import { projectsApi } from '@/lib/api'
import KanbanBoard from '@/components/kanban/KanbanBoard'
import CreateTaskModal from '@/components/kanban/CreateTaskModal'

const TABS = [
  { key: 'board', label: 'Задачи', icon: LayoutGrid },
  { key: 'overview', label: 'Обзор', icon: FileText },
  { key: 'analytics', label: 'Аналитика', icon: BarChart2 },
  { key: 'feed', label: 'Лента', icon: MessageSquare },
  { key: 'delivery', label: 'Результат', icon: Package },
]

const AUTONOMY_LABEL: Record<string, string> = {
  free: 'Полная свобода',
  stage_approval: 'Согласование этапов',
  strict: 'Жёсткий контроль',
}

export default function ProjectPage() {
  const { id } = useParams<{ id: string }>()
  const [project, setProject] = useState<any>(null)
  const [stats, setStats] = useState<any>(null)
  const [artifacts, setArtifacts] = useState<any[]>([])
  const [github, setGithub] = useState<any>(null)
  const [tab, setTab] = useState('board')
  const [showCreate, setShowCreate] = useState(false)

  useEffect(() => {
    projectsApi.get(id).then((r) => setProject(r.data))
    projectsApi.stats(id).then((r) => setStats(r.data))
    projectsApi.artifacts(id).then((r) => setArtifacts(r.data)).catch(() => setArtifacts([]))
    projectsApi.getGithub(id).then((r) => setGithub(r.data)).catch(() => setGithub(null))
  }, [id])

  if (!project) return <div className="animate-pulse h-8 w-60 bg-gray-800 rounded mt-2" />

  return (
    <div className="max-w-6xl mx-auto space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <Link href="/projects" className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-300 mb-2 transition">
            <ArrowLeft size={14} /> Проекты
          </Link>
          <h1 className="text-2xl font-bold text-white">{project.title}</h1>
          <div className="flex items-center gap-3 mt-1 text-sm text-gray-500">
            <span>{AUTONOMY_LABEL[project.autonomy_mode]}</span>
            {stats && (
              <>
                <span>•</span>
                <span>{stats.done_tasks} / {stats.total_tasks} задач</span>
                <span>•</span>
                <span className="text-[var(--accent)]">{stats.progress_pct}%</span>
              </>
            )}
          </div>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="bg-[var(--accent)] hover:opacity-90 text-[var(--accent-contrast)] text-sm font-medium px-4 py-2 rounded-lg transition shrink-0"
        >
          + Задача
        </button>
      </div>

      {stats && (
        <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
          <div className="h-full bg-[var(--accent)] rounded-full transition-all" style={{ width: `${stats.progress_pct}%` }} />
        </div>
      )}

      <div className="flex gap-1 bg-gray-900 border border-gray-800 p-1 rounded-lg w-fit flex-wrap">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`flex items-center gap-1.5 px-4 py-1.5 rounded-md text-sm transition ${
              tab === key ? 'bg-[var(--accent)] text-[var(--accent-contrast)]' : 'text-gray-400 hover:text-white'
            }`}
          >
            <Icon size={14} /> {label}
          </button>
        ))}
      </div>

      {tab === 'board' && <KanbanBoard projectId={id} />}
      {tab === 'overview' && <ProjectOverview project={project} />}
      {tab === 'analytics' && <ProjectAnalytics stats={stats} />}
      {tab === 'feed' && <ProjectFeed />}
      {tab === 'delivery' && (
        <ProjectDelivery
          projectId={id}
          artifacts={artifacts}
          github={github}
          onArtifactsChange={setArtifacts}
          onGithubChange={setGithub}
        />
      )}

      {showCreate && (
        <CreateTaskModal
          projectId={id}
          onClose={() => setShowCreate(false)}
          onCreated={() => {
            setShowCreate(false)
            projectsApi.stats(id).then((r) => setStats(r.data))
          }}
        />
      )}
    </div>
  )
}

function ProjectOverview({ project }: any) {
  const fields = [
    { label: 'Цель', value: project.goal },
    { label: 'Целевая аудитория', value: project.target_audience },
    { label: 'Монетизация', value: project.monetization_model },
    { label: 'Описание', value: project.description },
  ]
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-4">
      {fields.map(({ label, value }) => value ? (
        <div key={label}>
          <div className="text-xs text-gray-500 mb-1">{label}</div>
          <div className="text-sm text-gray-200">{value}</div>
        </div>
      ) : null)}
      {fields.every((field) => !field.value) && (
        <div className="text-gray-600 text-sm">Информация о проекте пока не заполнена.</div>
      )}
    </div>
  )
}

function ProjectAnalytics({ stats }: any) {
  if (!stats) return null
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {[
        { label: 'Всего задач', value: stats.total_tasks },
        { label: 'Завершено', value: stats.done_tasks },
        { label: 'В работе', value: stats.in_progress_tasks },
      ].map(({ label, value }) => (
        <div key={label} className="bg-gray-900 border border-gray-800 rounded-xl p-5 text-center">
          <div className="text-3xl font-bold text-white">{value}</div>
          <div className="text-xs text-gray-500 mt-1">{label}</div>
        </div>
      ))}
    </div>
  )
}

function ProjectFeed() {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 text-gray-600 text-sm text-center py-12">
      Лента событий появится после первой активности агентов.
    </div>
  )
}

function ProjectDelivery({ projectId, artifacts, github, onArtifactsChange, onGithubChange }: any) {
  const [selected, setSelected] = useState<any>(null)
  const [preview, setPreview] = useState<any>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [publishing, setPublishing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [form, setForm] = useState({
    repo_owner: '',
    repo_name: '',
    default_branch: 'main',
    base_path: '',
    oauth_token: '',
  })

  useEffect(() => {
    setForm({
      repo_owner: github?.repo_owner || '',
      repo_name: github?.repo_name || '',
      default_branch: github?.default_branch || 'main',
      base_path: github?.base_path || '',
      oauth_token: '',
    })
  }, [github])

  const refreshArtifacts = async () => {
    const res = await projectsApi.artifacts(projectId)
    onArtifactsChange(res.data)
  }

  const openPreview = async (artifact: any) => {
    setSelected(artifact)
    setPreview(null)
    setPreviewLoading(true)
    setMessage('')
    try {
      const res = await projectsApi.previewArtifact(projectId, artifact.path)
      setPreview(res.data)
    } catch (error: any) {
      setPreview({
        content: error?.response?.data?.detail || 'Preview недоступен для этого файла.',
      })
    } finally {
      setPreviewLoading(false)
    }
  }

  const saveGithub = async () => {
    setSaving(true)
    setMessage('')
    try {
      const res = await projectsApi.saveGithub(projectId, form)
      onGithubChange(res.data)
      setMessage('GitHub интеграция сохранена.')
    } catch (error: any) {
      setMessage(error?.response?.data?.detail || 'Не удалось сохранить GitHub интеграцию.')
    } finally {
      setSaving(false)
    }
  }

  const publishSelected = async () => {
    if (!selected) return
    setPublishing(true)
    setMessage('')
    try {
      const res = await projectsApi.publishArtifact(projectId, {
        artifact_path: selected.path,
        target_path: selected.filename,
        commit_message: `Publish ${selected.filename} from AI DevStudio`,
      })
      setMessage(`Опубликовано: ${res.data.html_url}`)
    } catch (error: any) {
      setMessage(error?.response?.data?.detail || 'Не удалось опубликовать артефакт.')
    } finally {
      setPublishing(false)
    }
  }

  return (
    <div className="grid grid-cols-1 xl:grid-cols-[1.1fr_0.9fr] gap-5">
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-800 flex items-center justify-between gap-3">
          <div>
            <div className="page-kicker">Artifacts</div>
            <div className="text-sm text-white font-semibold mt-1">Сохранённые результаты проекта</div>
          </div>
          <button onClick={refreshArtifacts} className="text-xs text-gray-400 hover:text-white transition">
            Обновить
          </button>
        </div>

        <div className="divide-y divide-gray-800">
          {artifacts.length === 0 && (
            <div className="px-5 py-10 text-sm text-gray-500">
              Пока нет сохранённых артефактов. Они появятся здесь, когда агент сохранит файл через `write_file` или завершит работу с результатом.
            </div>
          )}
          {artifacts.map((artifact: any) => (
            <div key={artifact.path} className="px-5 py-4 flex items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="text-sm text-white font-medium truncate">{artifact.filename}</div>
                <div className="text-xs text-gray-500 mt-1 break-all">{artifact.path}</div>
                <div className="text-xs text-gray-600 mt-1">
                  {artifact.agent_id ? `${artifact.agent_id} • ` : ''}
                  {Math.max(1, Math.round((artifact.size || 0) / 1024))} KB
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <button onClick={() => openPreview(artifact)} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-xs text-gray-200 transition">
                  <Eye size={14} /> Preview
                </button>
                <a
                  href={projectsApi.downloadArtifactUrl(projectId, artifact.path)}
                  className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-xs text-gray-200 transition"
                >
                  <Download size={14} /> Скачать
                </a>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="space-y-5">
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <div className="flex items-center gap-2 text-white font-semibold text-sm">
            <Github size={16} /> GitHub
          </div>
          <p className="text-xs text-gray-500 mt-2 leading-relaxed">
            В GitHub публикуются только явно выбранные артефакты проекта. Это защищает от случайной публикации `.env`, ключей и прочих служебных файлов.
          </p>

          <div className="grid grid-cols-1 gap-3 mt-4">
            <input value={form.repo_owner} onChange={(e) => setForm((f) => ({ ...f, repo_owner: e.target.value }))} placeholder="repo owner" className="input-base" />
            <input value={form.repo_name} onChange={(e) => setForm((f) => ({ ...f, repo_name: e.target.value }))} placeholder="repo name" className="input-base" />
            <div className="grid grid-cols-2 gap-3">
              <input value={form.default_branch} onChange={(e) => setForm((f) => ({ ...f, default_branch: e.target.value }))} placeholder="main" className="input-base" />
              <input value={form.base_path} onChange={(e) => setForm((f) => ({ ...f, base_path: e.target.value }))} placeholder="deliverables/" className="input-base" />
            </div>
            <input
              value={form.oauth_token}
              onChange={(e) => setForm((f) => ({ ...f, oauth_token: e.target.value }))}
              type="password"
              placeholder={github?.has_token ? 'Оставьте пустым, чтобы не менять токен' : 'GitHub token'}
              className="input-base"
            />
          </div>

          <div className="flex items-center gap-3 mt-4 flex-wrap">
            <button onClick={saveGithub} disabled={saving || !form.repo_owner || !form.repo_name} className="btn-primary">
              {saving ? 'Сохраняю...' : 'Сохранить GitHub'}
            </button>
            {github?.repo_url && (
              <a href={github.repo_url} target="_blank" rel="noreferrer" className="text-xs text-[var(--accent)] hover:text-white transition">
                Открыть репозиторий
              </a>
            )}
          </div>
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <div className="text-sm text-white font-semibold">Preview и публикация</div>
          {!selected && <div className="text-sm text-gray-500 mt-3">Выберите артефакт слева, чтобы посмотреть содержимое или отправить его в GitHub.</div>}
          {selected && (
            <div className="mt-4 space-y-3">
              <div className="text-xs text-gray-500 break-all">{selected.path}</div>
              <div className="rounded-xl bg-[#0f0f10] border border-white/5 p-4 max-h-[320px] overflow-auto text-xs text-gray-300 whitespace-pre-wrap">
                {previewLoading ? 'Загружаю preview...' : preview?.content || 'Preview пуст.'}
              </div>
              <button
                onClick={publishSelected}
                disabled={publishing || !github?.has_token}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--accent)] text-[var(--accent-contrast)] text-sm font-medium disabled:opacity-40"
              >
                <Upload size={14} /> {publishing ? 'Публикую...' : 'Опубликовать в GitHub'}
              </button>
              {!github?.has_token && <div className="text-xs text-amber-400">Сначала сохраните настройки GitHub с токеном доступа.</div>}
            </div>
          )}
          {message && <div className="mt-4 text-xs text-gray-400 break-all">{message}</div>}
        </div>
      </div>
    </div>
  )
}
