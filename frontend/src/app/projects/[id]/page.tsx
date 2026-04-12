'use client'
import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import { projectsApi, tasksApi } from '@/lib/api'
import Link from 'next/link'
import { ArrowLeft, LayoutGrid, FileText, BarChart2, MessageSquare } from 'lucide-react'
import KanbanBoard from '@/components/kanban/KanbanBoard'
import CreateTaskModal from '@/components/kanban/CreateTaskModal'

const TABS = [
  { key: 'board',    label: 'Задачи',   icon: LayoutGrid },
  { key: 'overview', label: 'Обзор',    icon: FileText },
  { key: 'analytics',label: 'Аналитика',icon: BarChart2 },
  { key: 'feed',     label: 'Лента',    icon: MessageSquare },
]

const AUTONOMY_LABEL: Record<string, string> = {
  free:           '🟢 Полная свобода',
  stage_approval: '🟡 Согласование этапов',
  strict:         '🔴 Жёсткий контроль',
}

export default function ProjectPage() {
  const { id } = useParams<{ id: string }>()
  const [project, setProject] = useState<any>(null)
  const [stats, setStats] = useState<any>(null)
  const [tab, setTab] = useState('board')
  const [showCreate, setShowCreate] = useState(false)

  useEffect(() => {
    projectsApi.get(id).then((r) => setProject(r.data))
    projectsApi.stats(id).then((r) => setStats(r.data))
  }, [id])

  if (!project) return <div className="animate-pulse h-8 w-60 bg-gray-800 rounded mt-2" />

  return (
    <div className="max-w-6xl mx-auto space-y-5">
      {/* Header */}
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
                <span>·</span>
                <span>{stats.done_tasks} / {stats.total_tasks} задач</span>
                <span>·</span>
                <span className="text-indigo-400">{stats.progress_pct}%</span>
              </>
            )}
          </div>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition shrink-0"
        >
          + Задача
        </button>
      </div>

      {/* Прогресс-бар */}
      {stats && (
        <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
          <div className="h-full bg-indigo-500 rounded-full transition-all" style={{ width: `${stats.progress_pct}%` }} />
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-900 border border-gray-800 p-1 rounded-lg w-fit">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`flex items-center gap-1.5 px-4 py-1.5 rounded-md text-sm transition ${
              tab === key ? 'bg-indigo-600 text-white' : 'text-gray-400 hover:text-white'
            }`}
          >
            <Icon size={14} /> {label}
          </button>
        ))}
      </div>

      {/* Content */}
      {tab === 'board' && <KanbanBoard projectId={id} />}
      {tab === 'overview' && <ProjectOverview project={project} />}
      {tab === 'analytics' && <ProjectAnalytics stats={stats} />}
      {tab === 'feed' && <ProjectFeed projectId={id} />}

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
      {fields.every((f) => !f.value) && (
        <div className="text-gray-600 text-sm">Информация о проекте не заполнена</div>
      )}
    </div>
  )
}

function ProjectAnalytics({ stats }: any) {
  if (!stats) return null
  return (
    <div className="grid grid-cols-3 gap-4">
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

function ProjectFeed({ projectId }: any) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 text-gray-600 text-sm text-center py-12">
      Лента событий появится после первой активности агентов
    </div>
  )
}
