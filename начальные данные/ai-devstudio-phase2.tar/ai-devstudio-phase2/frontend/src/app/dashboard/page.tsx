'use client'
import { useEffect, useState } from 'react'
import { dashboardApi } from '@/lib/api'
import { dashboardWS } from '@/lib/websocket'
import { AlertCircle, Clock, CheckCircle2, Zap, DollarSign, Bot } from 'lucide-react'
import Link from 'next/link'
import { formatDistanceToNow } from 'date-fns'
import { ru } from 'date-fns/locale'

const STATUS_COLOR: Record<string, string> = {
  active: 'bg-emerald-400',
  idle:   'bg-gray-500',
  error:  'bg-red-500',
  disabled: 'bg-gray-700',
}

const PRIORITY_COLOR: Record<string, string> = {
  critical: 'text-red-400',
  high:     'text-amber-400',
  medium:   'text-emerald-400',
  info:     'text-blue-400',
}

export default function DashboardPage() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  const load = async () => {
    try {
      const res = await dashboardApi.get()
      setData(res.data)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    dashboardWS.connect('/ws/dashboard')
    // При любом событии — обновить дашборд
    const handler = () => load()
    dashboardWS.on('task_status_changed', handler)
    dashboardWS.on('notification', handler)
    dashboardWS.on('project_updated', handler)
    return () => {
      dashboardWS.off('task_status_changed', handler)
      dashboardWS.off('notification', handler)
      dashboardWS.off('project_updated', handler)
    }
  }, [])

  if (loading) return <PageSkeleton />

  const { requires_decision, blockers, agents, active_projects, today_metrics } = data || {}

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-white">Дашборд</h1>

      {/* Требуют решения */}
      {requires_decision?.length > 0 && (
        <Section title="🔴 Требует вашего решения" count={requires_decision.length} urgent>
          <div className="space-y-2">
            {requires_decision.map((n: any) => (
              <DecisionCard key={n.id} item={n} />
            ))}
          </div>
        </Section>
      )}

      {/* Метрики */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard icon={<CheckCircle2 size={18} className="text-emerald-400"/>} label="Задач завершено сегодня" value={today_metrics?.tasks_done_today ?? 0} />
        <MetricCard icon={<Zap size={18} className="text-indigo-400"/>} label="Задач в работе" value={today_metrics?.tasks_in_progress ?? 0} />
        <MetricCard icon={<DollarSign size={18} className="text-amber-400"/>} label="Расход на AI сегодня" value={`$${(today_metrics?.ai_cost_usd_today ?? 0).toFixed(4)}`} />
        <MetricCard icon={<Bot size={18} className="text-blue-400"/>} label="Активных агентов" value={agents?.filter((a: any) => a.status === 'active').length ?? 0} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Блокеры */}
        <Section title="🟡 Блокеры" count={blockers?.length ?? 0}>
          {blockers?.length === 0
            ? <Empty text="Блокеров нет" />
            : blockers.map((b: any) => <BlockerCard key={b.id} item={b} />)
          }
        </Section>

        {/* Агенты */}
        <Section title="Состояние агентов">
          <div className="space-y-2">
            {agents?.map((a: any) => (
              <div key={a.id} className="flex items-center gap-3 py-2 px-3 bg-gray-800/50 rounded-lg">
                <span className={`w-2 h-2 rounded-full ${STATUS_COLOR[a.status] ?? 'bg-gray-500'}`} />
                <span className="text-sm text-white font-medium flex-1">{a.name}</span>
                <span className="text-xs text-gray-500">{a.model}</span>
                <span className={`text-xs px-2 py-0.5 rounded-full ${
                  a.status === 'active' ? 'bg-emerald-900/40 text-emerald-400' :
                  a.status === 'error'  ? 'bg-red-900/40 text-red-400' :
                  'bg-gray-800 text-gray-500'
                }`}>
                  {a.status === 'active' ? 'Работает' : a.status === 'idle' ? 'Ожидает' : a.status}
                </span>
              </div>
            ))}
          </div>
        </Section>
      </div>

      {/* Прогресс проектов */}
      {active_projects?.length > 0 && (
        <Section title="Активные проекты">
          <div className="space-y-3">
            {active_projects.map((p: any) => (
              <Link key={p.id} href={`/projects/${p.id}`} className="block hover:bg-gray-800/30 rounded-lg transition px-1">
                <div className="flex items-center gap-4">
                  <span className="text-sm text-white flex-1 truncate">{p.title}</span>
                  <span className="text-xs text-gray-500 shrink-0">{p.progress_pct}%</span>
                </div>
                <div className="mt-1.5 h-1.5 bg-gray-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-indigo-500 rounded-full transition-all"
                    style={{ width: `${p.progress_pct}%` }}
                  />
                </div>
                <div className="flex justify-between mt-1 text-xs text-gray-600">
                  <span>{p.done_tasks} / {p.total_tasks} задач</span>
                  <span>{p.in_progress_tasks} в работе</span>
                </div>
              </Link>
            ))}
          </div>
        </Section>
      )}
    </div>
  )
}

function Section({ title, count, urgent, children }: any) {
  return (
    <div className={`bg-gray-900 rounded-xl border p-5 ${urgent ? 'border-red-800/60' : 'border-gray-800'}`}>
      <div className="flex items-center gap-2 mb-4">
        <h2 className="text-sm font-semibold text-white">{title}</h2>
        {count !== undefined && count > 0 && (
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${urgent ? 'bg-red-900/40 text-red-400' : 'bg-gray-800 text-gray-400'}`}>
            {count}
          </span>
        )}
      </div>
      {children}
    </div>
  )
}

function MetricCard({ icon, label, value }: any) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <div className="flex items-center gap-2 mb-2">{icon}<span className="text-xs text-gray-500">{label}</span></div>
      <div className="text-2xl font-bold text-white">{value}</div>
    </div>
  )
}

function DecisionCard({ item }: any) {
  return (
    <div className="flex items-start gap-3 bg-red-900/10 border border-red-800/40 rounded-lg p-3">
      <AlertCircle size={16} className="text-red-400 mt-0.5 shrink-0" />
      <div className="flex-1 min-w-0">
        <div className="text-sm text-white font-medium">{item.title}</div>
        {item.body && <div className="text-xs text-gray-400 mt-1 line-clamp-2">{item.body}</div>}
      </div>
      {item.task_id && (
        <Link href={`/projects/${item.project_id}/tasks/${item.task_id}`} className="text-xs text-indigo-400 hover:text-indigo-300 shrink-0 mt-0.5">
          Открыть →
        </Link>
      )}
    </div>
  )
}

function BlockerCard({ item }: any) {
  return (
    <div className="flex items-start gap-3 bg-amber-900/10 border border-amber-800/30 rounded-lg p-3">
      <Clock size={16} className="text-amber-400 mt-0.5 shrink-0" />
      <div className="flex-1 min-w-0">
        <div className="text-sm text-white">{item.title}</div>
        <div className="text-xs text-gray-500 mt-0.5">{item.assigned_to} · завис {item.hours_stuck}ч назад</div>
      </div>
      {item.task_id && (
        <Link href={`/projects/${item.project_id}/tasks/${item.task_id}`} className="text-xs text-indigo-400 hover:text-indigo-300 shrink-0 mt-0.5">
          Открыть →
        </Link>
      )}
    </div>
  )
}

function Empty({ text }: { text: string }) {
  return <div className="text-center text-gray-600 text-sm py-4">{text}</div>
}

function PageSkeleton() {
  return (
    <div className="max-w-6xl mx-auto space-y-6 animate-pulse">
      <div className="h-8 bg-gray-800 rounded w-40" />
      <div className="grid grid-cols-4 gap-4">{[...Array(4)].map((_, i) => <div key={i} className="h-24 bg-gray-900 rounded-xl border border-gray-800" />)}</div>
      <div className="grid grid-cols-2 gap-6">{[...Array(2)].map((_, i) => <div key={i} className="h-48 bg-gray-900 rounded-xl border border-gray-800" />)}</div>
    </div>
  )
}
