'use client'
import { useEffect, useState, useCallback } from 'react'
import { tasksApi } from '@/lib/api'
import { projectWS } from '@/lib/websocket'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { Clock, AlertCircle, User } from 'lucide-react'

const COLUMNS = [
  { id: 'backlog',           label: 'Backlog',            color: 'border-gray-700' },
  { id: 'todo',              label: 'To Do',               color: 'border-gray-700' },
  { id: 'in_progress',       label: 'В работе',            color: 'border-indigo-700' },
  { id: 'review',            label: 'Проверка',            color: 'border-amber-700' },
  { id: 'awaiting_approval', label: '⏳ Согласование',     color: 'border-red-700' },
  { id: 'testing',           label: 'Тестирование',        color: 'border-purple-700' },
  { id: 'done',              label: '✅ Готово',            color: 'border-emerald-700' },
]

const PRIORITY_DOT: Record<string, string> = {
  critical: 'bg-red-500',
  high:     'bg-amber-500',
  medium:   'bg-blue-500',
  low:      'bg-gray-600',
}

const AGENT_SHORT: Record<string, string> = {
  director:    'DIR',
  backend_dev: 'BE',
  frontend_dev:'FE',
  ux_ui:       'UX',
  qa:          'QA',
  devops:      'DO',
  marketer:    'MKT',
  copywriter:  'CPW',
  smm:         'SMM',
  seo:         'SEO',
  analyst:     'ANL',
  pm:          'PM',
  finance:     'FIN',
}

interface Task {
  id: string
  title: string
  status: string
  priority: string
  assigned_to?: string
  live_plan?: any
  tags?: string[]
}

export default function KanbanBoard({ projectId }: { projectId: string }) {
  const [tasks, setTasks] = useState<Task[]>([])
  const [loading, setLoading] = useState(true)
  const [dragging, setDragging] = useState<string | null>(null)

  const load = useCallback(async () => {
    const res = await tasksApi.list({ project_id: projectId })
    setTasks(res.data)
    setLoading(false)
  }, [projectId])

  useEffect(() => {
    load()
    projectWS.connect(`/ws/project/${projectId}`)
    const handler = () => load()
    projectWS.on('task_created', handler)
    projectWS.on('task_status_changed', handler)
    projectWS.on('task_comment_added', handler)
    return () => {
      projectWS.off('task_created', handler)
      projectWS.off('task_status_changed', handler)
      projectWS.off('task_comment_added', handler)
    }
  }, [load, projectId])

  const moveTask = async (taskId: string, newStatus: string) => {
    setTasks((prev) => prev.map((t) => t.id === taskId ? { ...t, status: newStatus } : t))
    await tasksApi.update(taskId, { status: newStatus })
  }

  if (loading) return (
    <div className="flex gap-4 overflow-x-auto pb-4">
      {COLUMNS.map((c) => (
        <div key={c.id} className="min-w-[220px] h-64 bg-gray-900 rounded-xl border border-gray-800 animate-pulse" />
      ))}
    </div>
  )

  return (
    <div className="flex gap-4 overflow-x-auto pb-6 -mx-1 px-1">
      {COLUMNS.map((col) => {
        const colTasks = tasks.filter((t) => t.status === col.id)
        return (
          <div
            key={col.id}
            className={`min-w-[230px] max-w-[230px] flex flex-col rounded-xl bg-gray-900 border ${col.color} border-t-2`}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault()
              if (dragging) moveTask(dragging, col.id)
              setDragging(null)
            }}
          >
            {/* Заголовок колонки */}
            <div className="px-3 py-3 flex items-center justify-between">
              <span className="text-xs font-semibold text-gray-300">{col.label}</span>
              <span className="text-xs bg-gray-800 text-gray-500 px-2 py-0.5 rounded-full">{colTasks.length}</span>
            </div>

            {/* Карточки */}
            <div className="flex-1 px-2 pb-3 space-y-2 min-h-[80px]">
              {colTasks.map((task) => (
                <TaskCard
                  key={task.id}
                  task={task}
                  projectId={projectId}
                  onDragStart={() => setDragging(task.id)}
                  onDragEnd={() => setDragging(null)}
                />
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}

function TaskCard({ task, projectId, onDragStart, onDragEnd }: any) {
  const steps = task.live_plan?.steps ?? []
  const doneSteps = steps.filter((s: any) => s.status === 'done').length
  const totalSteps = steps.length

  return (
    <Link
      href={`/projects/${projectId}/tasks/${task.id}`}
      draggable
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      className="block bg-gray-800 hover:bg-gray-750 border border-gray-700 hover:border-gray-600 rounded-lg p-3 cursor-grab active:cursor-grabbing transition group"
    >
      {/* Приоритет + теги */}
      <div className="flex items-center gap-1.5 mb-2">
        <span className={`w-2 h-2 rounded-full shrink-0 ${PRIORITY_DOT[task.priority] ?? 'bg-gray-600'}`} />
        {task.tags?.slice(0, 2).map((tag: string) => (
          <span key={tag} className="text-xs bg-gray-700 text-gray-400 px-1.5 py-0.5 rounded">{tag}</span>
        ))}
      </div>

      {/* Заголовок */}
      <div className="text-sm text-gray-200 group-hover:text-white transition leading-snug line-clamp-3">
        {task.title}
      </div>

      {/* Живой план прогресс */}
      {totalSteps > 0 && (
        <div className="mt-2">
          <div className="flex justify-between text-xs text-gray-600 mb-1">
            <span>План</span>
            <span>{doneSteps}/{totalSteps}</span>
          </div>
          <div className="h-1 bg-gray-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-indigo-500 rounded-full"
              style={{ width: `${totalSteps ? (doneSteps / totalSteps) * 100 : 0}%` }}
            />
          </div>
        </div>
      )}

      {/* Агент */}
      {task.assigned_to && (
        <div className="flex items-center justify-end mt-2">
          <span className="text-xs bg-gray-700 text-gray-400 px-2 py-0.5 rounded-full font-mono">
            {AGENT_SHORT[task.assigned_to] ?? task.assigned_to}
          </span>
        </div>
      )}
    </Link>
  )
}
