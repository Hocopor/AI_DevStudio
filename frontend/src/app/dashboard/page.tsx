'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { AlertCircle, Bot, CheckCircle2, Clock, DollarSign, Zap } from 'lucide-react'
import { dashboardApi } from '@/lib/api'
import { dashboardWS } from '@/lib/websocket'

const STATUS_COLOR: Record<string, string> = {
  active: 'bg-[var(--success)]',
  idle: 'bg-stone-500',
  error: 'bg-[var(--danger)]',
  disabled: 'bg-stone-700',
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
    <div className="space-y-6">
      <header className="page-header">
        <div>
          <div className="page-kicker">Command Overview</div>
          <h1 className="page-title">Тихая панель управления рабочим контуром.</h1>
          <p className="page-subtitle">
            Ключевые решения, состояние агентной команды и динамика активных проектов в одном собранном представлении.
          </p>
        </div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <StatChip label="Активных агентов" value={agents?.filter((a: any) => a.status === 'active').length ?? 0} />
          <StatChip label="Проектов в работе" value={active_projects?.length ?? 0} />
          <StatChip label="Срочных решений" value={requires_decision?.length ?? 0} />
        </div>
      </header>

      {requires_decision?.length > 0 && (
        <Section title="Критичные решения владельца" count={requires_decision.length} urgent>
          <div className="space-y-3">
            {requires_decision.map((n: any) => (
              <DecisionCard key={n.id} item={n} />
            ))}
          </div>
        </Section>
      )}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard icon={<CheckCircle2 size={16} />} label="Задач завершено сегодня" value={today_metrics?.tasks_done_today ?? 0} accent="success" />
        <MetricCard icon={<Zap size={16} />} label="Задач в работе" value={today_metrics?.tasks_in_progress ?? 0} accent="accent" />
        <MetricCard icon={<DollarSign size={16} />} label="AI-расход сегодня" value={`$${(today_metrics?.ai_cost_usd_today ?? 0).toFixed(4)}`} accent="warning" />
        <MetricCard icon={<Bot size={16} />} label="Активных агентов" value={agents?.filter((a: any) => a.status === 'active').length ?? 0} accent="neutral" />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <Section title="Блокеры" count={blockers?.length ?? 0}>
          {blockers?.length === 0 ? (
            <Empty text="Система работает без блокеров." />
          ) : (
            <div className="space-y-3">
              {blockers.map((b: any) => (
                <BlockerCard key={b.id} item={b} />
              ))}
            </div>
          )}
        </Section>

        <Section title="Состояние агентов">
          <div className="space-y-3">
            {agents?.map((a: any) => (
              <div key={a.id} className="panel-soft flex items-center gap-3 px-4 py-3">
                <span className={`h-2.5 w-2.5 rounded-full ${STATUS_COLOR[a.status] ?? 'bg-stone-500'}`} />
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium text-stone-100">{a.name}</div>
                  <div className="mt-1 text-xs text-stone-500">{a.model}</div>
                </div>
                <span className="pill pill-neutral">{a.status}</span>
              </div>
            ))}
          </div>
        </Section>
      </div>

      {active_projects?.length > 0 && (
        <Section title="Активные проекты">
          <div className="grid gap-4 lg:grid-cols-2">
            {active_projects.map((p: any) => (
              <Link key={p.id} href={`/projects/${p.id}`} className="panel-soft block p-4 transition hover:border-[rgba(226,182,132,0.18)] hover:bg-[rgba(255,255,255,0.03)]">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-medium text-stone-100">{p.title}</div>
                    <div className="mt-2 text-xs text-stone-500">{p.done_tasks} из {p.total_tasks} задач завершено</div>
                  </div>
                  <span className="pill pill-neutral">{p.progress_pct}%</span>
                </div>
                <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-[rgba(255,255,255,0.06)]">
                  <div className="h-full rounded-full bg-[linear-gradient(90deg,#8ca47c,#d6ad72)]" style={{ width: `${p.progress_pct}%` }} />
                </div>
                <div className="mt-3 text-xs text-stone-500">{p.in_progress_tasks} задач сейчас в работе</div>
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
    <section className="panel p-5 md:p-6">
      <div className="mb-5 flex items-center gap-3">
        <h2 className="text-sm font-semibold uppercase tracking-[0.18em] text-stone-200">{title}</h2>
        {count !== undefined && <span className={`pill ${urgent ? 'bg-[rgba(215,122,109,0.12)] text-[var(--danger)]' : 'pill-neutral'}`}>{count}</span>}
      </div>
      {children}
    </section>
  )
}

function MetricCard({ icon, label, value, accent }: any) {
  const accentClass =
    accent === 'success'
      ? 'text-[var(--success)] bg-[rgba(125,169,138,0.12)]'
      : accent === 'warning'
      ? 'text-[var(--warning)] bg-[rgba(214,173,114,0.12)]'
      : accent === 'accent'
      ? 'text-[var(--accent-strong)] bg-[rgba(201,155,107,0.12)]'
      : 'text-stone-300 bg-[rgba(255,255,255,0.05)]'

  return (
    <div className="metric-card">
      <div className="mb-4 flex items-center gap-3">
        <span className={`flex h-10 w-10 items-center justify-center rounded-2xl ${accentClass}`}>{icon}</span>
        <span className="text-xs uppercase tracking-[0.16em] text-stone-500">{label}</span>
      </div>
      <div className="text-3xl font-semibold text-stone-50">{value}</div>
    </div>
  )
}

function DecisionCard({ item }: any) {
  return (
    <div className="rounded-[20px] border border-[rgba(215,122,109,0.16)] bg-[rgba(215,122,109,0.08)] p-4">
      <div className="flex items-start gap-3">
        <AlertCircle size={16} className="mt-0.5 shrink-0 text-[var(--danger)]" />
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium text-stone-100">{item.title}</div>
          {item.body && <div className="mt-2 text-sm leading-6 text-stone-400">{item.body}</div>}
        </div>
        {item.task_id && (
          <Link href={`/projects/${item.project_id}/tasks/${item.task_id}`} className="text-xs uppercase tracking-[0.16em] text-[var(--accent)]">
            Открыть
          </Link>
        )}
      </div>
    </div>
  )
}

function BlockerCard({ item }: any) {
  return (
    <div className="panel-soft flex items-start gap-3 px-4 py-4">
      <Clock size={16} className="mt-0.5 shrink-0 text-[var(--warning)]" />
      <div className="min-w-0 flex-1">
        <div className="text-sm font-medium text-stone-100">{item.title}</div>
        <div className="mt-1 text-xs text-stone-500">{item.assigned_to} • завис {item.hours_stuck}ч назад</div>
      </div>
      {item.task_id && (
        <Link href={`/projects/${item.project_id}/tasks/${item.task_id}`} className="text-xs uppercase tracking-[0.16em] text-[var(--accent)]">
          Открыть
        </Link>
      )}
    </div>
  )
}

function StatChip({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-[rgba(255,255,255,0.03)] px-4 py-3">
      <div className="text-[0.68rem] uppercase tracking-[0.16em] text-stone-500">{label}</div>
      <div className="mt-2 text-xl font-semibold text-stone-100">{value}</div>
    </div>
  )
}

function Empty({ text }: { text: string }) {
  return <div className="rounded-[20px] border border-dashed border-white/10 px-4 py-10 text-center text-sm text-stone-500">{text}</div>
}

function PageSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="page-header min-h-[180px]" />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="metric-card h-36" />
        ))}
      </div>
      <div className="grid gap-6 xl:grid-cols-2">
        {[...Array(2)].map((_, i) => (
          <div key={i} className="panel h-72" />
        ))}
      </div>
    </div>
  )
}
