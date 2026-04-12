'use client'
import { useEffect, useState } from 'react'
import { agentsApi, tasksApi, notificationsApi } from '@/lib/api'
import { formatDistanceToNow } from 'date-fns'
import { ru } from 'date-fns/locale'

const TABS = ['Агенты', 'Задачи', 'API', 'Логи']

const STATUS_COLOR: Record<string, string> = {
  active:   'bg-emerald-400',
  idle:     'bg-gray-500',
  error:    'bg-red-500',
  disabled: 'bg-gray-700',
}

export default function MonitoringPage() {
  const [tab, setTab] = useState('Агенты')
  const [agents, setAgents] = useState<any[]>([])
  const [tasks, setTasks]   = useState<any[]>([])
  const [notifications, setNotifications] = useState<any[]>([])

  useEffect(() => {
    agentsApi.list().then(r => setAgents(r.data))
    tasksApi.list().then(r => setTasks(r.data))
    notificationsApi.list().then(r => setNotifications(r.data))
    const iv = setInterval(() => {
      agentsApi.list().then(r => setAgents(r.data))
      tasksApi.list().then(r => setTasks(r.data))
    }, 15000)
    return () => clearInterval(iv)
  }, [])

  return (
    <div className="max-w-6xl mx-auto space-y-5">
      <h1 className="text-2xl font-bold text-white">Мониторинг</h1>

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-900 border border-gray-800 p-1 rounded-lg w-fit">
        {TABS.map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-1.5 rounded-md text-sm transition ${tab === t ? 'bg-indigo-600 text-white' : 'text-gray-400 hover:text-white'}`}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === 'Агенты' && <AgentsTab agents={agents} tasks={tasks} />}
      {tab === 'Задачи' && <TasksTab tasks={tasks} />}
      {tab === 'API' && <APITab agents={agents} />}
      {tab === 'Логи' && <LogsTab notifications={notifications} />}
    </div>
  )
}

function AgentsTab({ agents, tasks }: any) {
  return (
    <div className="space-y-3">
      {agents.map((a: any) => {
        const currentTask = tasks.find((t: any) => t.id === a.current_task_id)
        const plan = currentTask?.live_plan?.steps ?? []
        const done = plan.filter((s: any) => s.status === 'done').length
        return (
          <div key={a.id} className="bg-gray-900 border border-gray-800 rounded-xl p-5">
            <div className="flex items-center gap-3 mb-3">
              <span className={`w-2.5 h-2.5 rounded-full ${STATUS_COLOR[a.status] ?? 'bg-gray-500'}`} />
              <span className="text-white font-medium">{a.name}</span>
              <span className="text-gray-500 text-sm">{a.role}</span>
              <span className="ml-auto text-xs text-gray-600">{a.provider} / {a.model}</span>
            </div>

            {currentTask ? (
              <div className="bg-gray-800/50 rounded-lg p-3">
                <div className="text-xs text-gray-400 mb-1">Текущая задача:</div>
                <div className="text-sm text-white mb-2">{currentTask.title}</div>
                {plan.length > 0 && (
                  <>
                    <div className="flex justify-between text-xs text-gray-600 mb-1">
                      <span>Живой план</span><span>{done}/{plan.length}</span>
                    </div>
                    <div className="h-1 bg-gray-700 rounded-full overflow-hidden">
                      <div className="h-full bg-indigo-500 rounded-full" style={{ width: `${plan.length ? (done/plan.length)*100 : 0}%` }} />
                    </div>
                  </>
                )}
              </div>
            ) : (
              <div className="text-xs text-gray-600">Ожидает задач</div>
            )}

            <div className="mt-3 flex gap-4 text-xs text-gray-600">
              <span>Выполнено задач: <span className="text-gray-400">{a.tasks_completed}</span></span>
            </div>
          </div>
        )
      })}
    </div>
  )
}

const COL_STATUS_COLOR: Record<string, string> = {
  backlog: 'text-gray-500', todo: 'text-gray-400',
  in_progress: 'text-indigo-400', review: 'text-amber-400',
  awaiting_approval: 'text-red-400', testing: 'text-purple-400',
  done: 'text-emerald-400', archived: 'text-gray-700',
}

const STATUS_LABEL: Record<string, string> = {
  backlog: 'Backlog', todo: 'К выполнению', in_progress: 'В работе',
  review: 'Проверка', awaiting_approval: 'Согласование',
  testing: 'Тестирование', done: 'Готово', archived: 'Архив',
}

function TasksTab({ tasks }: any) {
  const [filter, setFilter] = useState('')
  const filtered = tasks.filter((t: any) =>
    !filter || t.status === filter || t.assigned_to === filter
  )
  return (
    <div className="space-y-3">
      <div className="flex gap-2 flex-wrap">
        {['', 'in_progress', 'awaiting_approval', 'review', 'todo'].map(s => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            className={`text-xs px-3 py-1 rounded-full transition ${filter === s ? 'bg-indigo-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-white'}`}
          >
            {s ? STATUS_LABEL[s] : 'Все'}
          </button>
        ))}
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-800">
              <th className="text-left text-xs text-gray-500 px-4 py-3 font-medium">Задача</th>
              <th className="text-left text-xs text-gray-500 px-4 py-3 font-medium">Статус</th>
              <th className="text-left text-xs text-gray-500 px-4 py-3 font-medium">Агент</th>
              <th className="text-left text-xs text-gray-500 px-4 py-3 font-medium">Обновлено</th>
            </tr>
          </thead>
          <tbody>
            {filtered.slice(0, 50).map((t: any) => (
              <tr key={t.id} className="border-b border-gray-800/50 hover:bg-gray-800/30 transition">
                <td className="px-4 py-3 text-gray-200 max-w-xs">
                  <div className="truncate">{t.title}</div>
                </td>
                <td className="px-4 py-3">
                  <span className={`text-xs ${COL_STATUS_COLOR[t.status] ?? 'text-gray-500'}`}>
                    {STATUS_LABEL[t.status] ?? t.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-xs text-gray-500">{t.assigned_to ?? '—'}</td>
                <td className="px-4 py-3 text-xs text-gray-600">
                  {formatDistanceToNow(new Date(t.updated_at), { addSuffix: true, locale: ru })}
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr><td colSpan={4} className="text-center text-gray-600 py-8">Задач нет</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function APITab({ agents }: any) {
  return (
    <div className="space-y-4">
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <h2 className="text-sm font-semibold text-white mb-4">Провайдеры AI</h2>
        <div className="space-y-3">
          {['deepseek', 'google', 'codex'].map(p => {
            const using = agents.filter((a: any) => a.provider === p)
            return (
              <div key={p} className="flex items-center gap-4 py-2 border-b border-gray-800 last:border-0">
                <div className="flex-1">
                  <div className="text-sm text-white capitalize">{p}</div>
                  <div className="text-xs text-gray-500">
                    {using.length > 0 ? `Используют: ${using.map((a: any) => a.name).join(', ')}` : 'Не используется'}
                  </div>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded-full ${using.length > 0 ? 'bg-emerald-900/40 text-emerald-400' : 'bg-gray-800 text-gray-600'}`}>
                  {using.length > 0 ? 'Активен' : 'Не активен'}
                </span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

function LogsTab({ notifications }: any) {
  const PRIORITY_COLOR: Record<string, string> = {
    critical: 'text-red-400', high: 'text-amber-400',
    medium: 'text-emerald-400', info: 'text-blue-400',
  }
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-800">
            <th className="text-left text-xs text-gray-500 px-4 py-3 font-medium">Событие</th>
            <th className="text-left text-xs text-gray-500 px-4 py-3 font-medium">Приоритет</th>
            <th className="text-left text-xs text-gray-500 px-4 py-3 font-medium">Время</th>
          </tr>
        </thead>
        <tbody>
          {notifications.slice(0, 100).map((n: any) => (
            <tr key={n.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
              <td className="px-4 py-3">
                <div className="text-gray-200 text-sm">{n.title}</div>
                {n.body && <div className="text-gray-600 text-xs mt-0.5 line-clamp-1">{n.body}</div>}
              </td>
              <td className="px-4 py-3">
                <span className={`text-xs ${PRIORITY_COLOR[n.priority] ?? 'text-gray-500'}`}>
                  {n.priority}
                </span>
              </td>
              <td className="px-4 py-3 text-xs text-gray-600">
                {formatDistanceToNow(new Date(n.created_at), { addSuffix: true, locale: ru })}
              </td>
            </tr>
          ))}
          {notifications.length === 0 && (
            <tr><td colSpan={3} className="text-center text-gray-600 py-8">Логов нет</td></tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
