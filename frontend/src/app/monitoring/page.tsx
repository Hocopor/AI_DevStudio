'use client'
import { useEffect, useState, useCallback } from 'react'
import { agentsApi, tasksApi, notificationsApi, financeApi, codexApi } from '@/lib/api'
import { formatDistanceToNow } from 'date-fns'
import { ru } from 'date-fns/locale'

const TABS = ['Агенты', 'Задачи', 'API', 'Логи']

const AGENT_STATUS_COLOR: Record<string, string> = {
  active: 'bg-emerald-400', idle: 'bg-gray-500', error: 'bg-red-500', disabled: 'bg-gray-700',
}

const TASK_STATUS_LABEL: Record<string, string> = {
  backlog: 'Backlog', todo: 'К выполнению', in_progress: 'В работе',
  review: 'Проверка', awaiting_approval: 'Согласование',
  testing: 'Тестирование', done: 'Готово', archived: 'Архив',
}

const TASK_STATUS_COLOR: Record<string, string> = {
  in_progress: 'text-indigo-400', awaiting_approval: 'text-red-400',
  review: 'text-amber-400', done: 'text-emerald-400',
  todo: 'text-gray-400', backlog: 'text-gray-600',
}

const PRIORITY_DOT: Record<string, string> = {
  critical: 'bg-red-500', high: 'bg-amber-500', medium: 'bg-emerald-500', info: 'bg-blue-500',
}

const PRIORITY_COLOR: Record<string, string> = {
  critical: 'text-red-400', high: 'text-amber-400', medium: 'text-emerald-400', info: 'text-blue-400',
}

export default function MonitoringPage() {
  const [tab, setTab] = useState('Агенты')
  const [agents, setAgents] = useState<any[]>([])
  const [tasks, setTasks] = useState<any[]>([])
  const [notifications, setNotifications] = useState<any[]>([])
  const [apiSummary, setApiSummary] = useState<any>(null)
  const [codexAccounts, setCodexAccounts] = useState<any[]>([])

  const load = useCallback(async () => {
    const [ag, tk, notif, fin, codex] = await Promise.all([
      agentsApi.list(),
      tasksApi.list(),
      notificationsApi.list(),
      financeApi.summary('day'),
      codexApi.list(),
    ])
    setAgents(ag.data)
    setTasks(tk.data)
    setNotifications(notif.data)
    setApiSummary(fin.data)
    setCodexAccounts(codex.data)
  }, [])

  useEffect(() => { load(); const iv = setInterval(load, 15000); return () => clearInterval(iv) }, [load])

  return (
    <div className="max-w-6xl mx-auto space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Мониторинг</h1>
        <span className="text-xs text-gray-600">Обновление каждые 15 сек</span>
      </div>
      <div className="flex gap-1 bg-gray-900 border border-gray-800 p-1 rounded-lg w-fit">
        {TABS.map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-1.5 rounded-md text-sm transition ${tab === t ? 'bg-indigo-600 text-white' : 'text-gray-400 hover:text-white'}`}>
            {t}
          </button>
        ))}
      </div>
      {tab === 'Агенты' && <AgentsTab agents={agents} tasks={tasks} />}
      {tab === 'Задачи'  && <TasksTab tasks={tasks} />}
      {tab === 'API'     && <APITab summary={apiSummary} codexAccounts={codexAccounts} />}
      {tab === 'Логи'    && <LogsTab notifications={notifications} />}
    </div>
  )
}

function AgentsTab({ agents, tasks }: any) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {agents.map((a: any) => {
        const task = tasks.find((t: any) => t.id === a.current_task_id)
        const steps = task?.live_plan?.steps ?? []
        const done = steps.filter((s: any) => s.status === 'done').length
        return (
          <div key={a.id} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <div className="flex items-center gap-3 mb-3">
              <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${AGENT_STATUS_COLOR[a.status] ?? 'bg-gray-500'}`} />
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-white font-medium text-sm">{a.name}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    a.status === 'active' ? 'bg-emerald-900/40 text-emerald-400' :
                    a.status === 'error'  ? 'bg-red-900/40 text-red-400' : 'bg-gray-800 text-gray-500'
                  }`}>
                    {a.status === 'active' ? 'Работает' : a.status === 'idle' ? 'Ожидает' : a.status}
                  </span>
                </div>
                <div className="text-xs text-gray-600 mt-0.5">{a.provider} / {a.model}</div>
              </div>
              <div className="text-xs text-gray-600 text-right">
                <div>{a.tasks_completed} задач</div>
              </div>
            </div>
            {task ? (
              <div className="bg-gray-800/50 rounded-lg p-3">
                <div className="text-xs text-gray-500 mb-1">Текущая задача:</div>
                <div className="text-sm text-white mb-2 line-clamp-2">{task.title}</div>
                {steps.length > 0 && (
                  <>
                    <div className="flex justify-between text-xs text-gray-600 mb-1">
                      <span>Живой план</span><span>{done}/{steps.length}</span>
                    </div>
                    <div className="h-1 bg-gray-700 rounded-full overflow-hidden mb-2">
                      <div className="h-full bg-indigo-500 rounded-full"
                        style={{ width: `${steps.length ? (done / steps.length) * 100 : 0}%` }} />
                    </div>
                    {steps.slice(0, 3).map((s: any, i: number) => (
                      <div key={i} className="flex items-center gap-1.5 text-xs text-gray-500">
                        <span>{s.status === 'done' ? '✅' : s.status === 'in_progress' ? '🔄' : '⏳'}</span>
                        <span className={s.status === 'done' ? 'line-through text-gray-700' : ''}>{s.step}</span>
                      </div>
                    ))}
                    {steps.length > 3 && <div className="text-xs text-gray-700 mt-1">+{steps.length - 3} шагов</div>}
                  </>
                )}
              </div>
            ) : (
              <div className="text-xs text-gray-700 bg-gray-800/30 rounded-lg p-2 text-center">Ожидает задач</div>
            )}
          </div>
        )
      })}
    </div>
  )
}

function TasksTab({ tasks }: any) {
  const [filter, setFilter] = useState('')
  const filters = [
    { v: '', l: 'Все' }, { v: 'in_progress', l: 'В работе' },
    { v: 'awaiting_approval', l: 'Согласование' }, { v: 'review', l: 'Проверка' },
    { v: 'todo', l: 'К выполнению' }, { v: 'done', l: 'Готово' },
  ]
  const filtered = filter ? tasks.filter((t: any) => t.status === filter) : tasks

  return (
    <div className="space-y-3">
      <div className="flex gap-2 flex-wrap">
        {filters.map(f => (
          <button key={f.v} onClick={() => setFilter(f.v)}
            className={`text-xs px-3 py-1 rounded-full transition ${
              filter === f.v ? 'bg-indigo-600 text-white' : 'bg-gray-900 border border-gray-800 text-gray-400 hover:text-white'
            }`}>
            {f.l}{f.v && ` (${tasks.filter((t: any) => t.status === f.v).length})`}
          </button>
        ))}
      </div>
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-800">
              {['Задача', 'Статус', 'Агент', 'Обновлено'].map(h => (
                <th key={h} className="text-left text-xs text-gray-500 px-4 py-3 font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.slice(0, 100).map((t: any) => (
              <tr key={t.id} className="border-b border-gray-800/50 hover:bg-gray-800/20">
                <td className="px-4 py-3 max-w-xs"><div className="text-gray-200 truncate">{t.title}</div></td>
                <td className="px-4 py-3">
                  <span className={`text-xs ${TASK_STATUS_COLOR[t.status] ?? 'text-gray-500'}`}>
                    {TASK_STATUS_LABEL[t.status] ?? t.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-xs text-gray-500 font-mono">{t.assigned_to ?? '—'}</td>
                <td className="px-4 py-3 text-xs text-gray-600">
                  {formatDistanceToNow(new Date(t.updated_at), { addSuffix: true, locale: ru })}
                </td>
              </tr>
            ))}
            {filtered.length === 0 && <tr><td colSpan={4} className="text-center text-gray-600 py-8">Задач нет</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function APITab({ summary, codexAccounts }: any) {
  const fmt$ = (v: number) => v < 0.001 ? `$${v.toFixed(6)}` : `$${v.toFixed(4)}`
  const fmtK = (v: number) => v > 1000 ? `${(v / 1000).toFixed(1)}K` : String(v)

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: 'Расход сегодня', value: summary ? fmt$(summary.total_cost_usd) : '—', color: 'text-amber-400' },
          { label: 'Токенов сегодня', value: summary ? fmtK(summary.total_tokens) : '—', color: 'text-white' },
          { label: 'API запросов', value: summary?.by_provider?.reduce((s: number, p: any) => s + p.calls, 0) ?? '—', color: 'text-white' },
        ].map(m => (
          <div key={m.label} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <div className="text-xs text-gray-500 mb-1">{m.label}</div>
            <div className={`text-2xl font-bold font-mono ${m.color}`}>{m.value}</div>
          </div>
        ))}
      </div>

      {/* Codex аккаунты */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <h2 className="text-sm font-semibold text-white mb-3">Codex OAuth — Аккаунты</h2>
        {codexAccounts.length === 0
          ? <div className="text-sm text-gray-600 text-center py-3">Аккаунты не добавлены</div>
          : codexAccounts.map((a: any) => (
            <div key={a.id} className={`flex items-center gap-3 px-3 py-2 rounded-lg border mb-2 last:mb-0 ${
              a.is_current ? 'border-indigo-700/40 bg-indigo-900/10' : 'border-gray-800'
            }`}>
              <span className={`w-2 h-2 rounded-full ${a.is_active ? 'bg-emerald-400' : 'bg-gray-600'}`} />
              <span className="text-sm text-white flex-1">{a.label}</span>
              {a.is_current && <span className="text-xs bg-indigo-900/50 text-indigo-400 px-2 py-0.5 rounded-full">Активный</span>}
              <span className="text-xs text-gray-600">#{a.priority}</span>
            </div>
          ))
        }
      </div>

      {/* По провайдерам */}
      {summary?.by_provider?.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-white mb-3">По провайдерам (сегодня)</h2>
          {summary.by_provider.map((p: any) => (
            <div key={p.provider} className="flex items-center gap-4 py-2.5 border-b border-gray-800 last:border-0">
              <span className="text-sm text-white capitalize flex-1">{p.provider}</span>
              <span className="text-xs text-gray-500">{p.calls} req</span>
              <span className="text-xs text-gray-500">{fmtK(p.tokens_in + p.tokens_out)} tok</span>
              <span className="text-xs font-mono text-amber-400">{fmt$(p.cost_usd)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function LogsTab({ notifications }: any) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-800">
            {['Событие', 'Тип', 'Приоритет', 'Время'].map(h => (
              <th key={h} className="text-left text-xs text-gray-500 px-4 py-3 font-medium">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {notifications.slice(0, 100).map((n: any) => (
            <tr key={n.id} className={`border-b border-gray-800/50 hover:bg-gray-800/20 ${n.is_read ? 'opacity-40' : ''}`}>
              <td className="px-4 py-3 max-w-sm">
                <div className="flex items-center gap-2">
                  <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${PRIORITY_DOT[n.priority] ?? 'bg-gray-500'}`} />
                  <span className="text-gray-200 truncate">{n.title}</span>
                </div>
                {n.body && <div className="text-gray-600 text-xs mt-0.5 pl-3.5 line-clamp-1">{n.body}</div>}
              </td>
              <td className="px-4 py-3 text-xs text-gray-600 font-mono">{n.type}</td>
              <td className="px-4 py-3">
                <span className={`text-xs ${PRIORITY_COLOR[n.priority] ?? 'text-gray-500'}`}>{n.priority}</span>
              </td>
              <td className="px-4 py-3 text-xs text-gray-600">
                {formatDistanceToNow(new Date(n.created_at), { addSuffix: true, locale: ru })}
              </td>
            </tr>
          ))}
          {notifications.length === 0 && <tr><td colSpan={4} className="text-center text-gray-600 py-8">Логов нет</td></tr>}
        </tbody>
      </table>
    </div>
  )
}
