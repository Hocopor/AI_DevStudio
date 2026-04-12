'use client'
import { useEffect, useState } from 'react'
import { financeApi } from '@/lib/api'
import { DollarSign, Zap, BarChart2, List } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { ru } from 'date-fns/locale'

type Period = 'day' | 'week' | 'month' | 'all'

const PERIODS: { key: Period; label: string }[] = [
  { key: 'day',   label: 'Сегодня' },
  { key: 'week',  label: 'Неделя' },
  { key: 'month', label: 'Месяц' },
  { key: 'all',   label: 'Всё время' },
]

const AGENT_NAMES: Record<string, string> = {
  director:     'Директор',
  analyst:      'Аналитик',
  pm:           'Продукт-менеджер',
  backend_dev:  'Backend Dev',
  frontend_dev: 'Frontend Dev',
  ux_ui:        'UX/UI',
  qa:           'QA',
  devops:       'DevOps',
  marketer:     'Маркетолог',
  copywriter:   'Копирайтер',
  smm:          'SMM',
  seo:          'SEO',
  finance:      'Финансист',
}

const PROVIDER_COLOR: Record<string, string> = {
  deepseek: 'bg-blue-500',
  google:   'bg-emerald-500',
  codex:    'bg-purple-500',
}

function fmt$(v: number) {
  return v < 0.001 ? `$${v.toFixed(6)}` : v < 1 ? `$${v.toFixed(4)}` : `$${v.toFixed(2)}`
}
function fmtK(v: number) {
  return v > 1_000_000 ? `${(v / 1_000_000).toFixed(1)}M` : v > 1000 ? `${(v / 1000).toFixed(1)}K` : String(v)
}

export default function FinancePage() {
  const [period, setPeriod] = useState<Period>('month')
  const [summary, setSummary] = useState<any>(null)
  const [logs, setLogs] = useState<any[]>([])
  const [tab, setTab] = useState<'overview' | 'log'>('overview')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    Promise.all([
      financeApi.summary(period),
      financeApi.usageLog({ limit: 100 }),
    ]).then(([s, l]) => {
      setSummary(s.data)
      setLogs(l.data)
      setLoading(false)
    })
  }, [period])

  return (
    <div className="max-w-5xl mx-auto space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Финансы</h1>
        <div className="text-xs text-gray-500">Расходы на AI API</div>
      </div>

      {/* Период */}
      <div className="flex gap-1 bg-gray-900 border border-gray-800 p-1 rounded-lg w-fit">
        {PERIODS.map(({ key, label }) => (
          <button key={key} onClick={() => setPeriod(key)}
            className={`px-4 py-1.5 rounded-md text-sm transition ${period === key ? 'bg-indigo-600 text-white' : 'text-gray-400 hover:text-white'}`}>
            {label}
          </button>
        ))}
      </div>

      {loading ? <Skeleton /> : !summary ? null : (
        <>
          {/* Главные метрики */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard icon={<DollarSign size={18} className="text-amber-400" />}
              label="Общие расходы" value={fmt$(summary.total_cost_usd)} />
            <MetricCard icon={<Zap size={18} className="text-indigo-400" />}
              label="Токенов всего" value={fmtK(summary.total_tokens)} />
            <MetricCard icon={<BarChart2 size={18} className="text-emerald-400" />}
              label="Токенов входящих" value={fmtK(summary.total_tokens_in)} />
            <MetricCard icon={<BarChart2 size={18} className="text-blue-400" />}
              label="Токенов исходящих" value={fmtK(summary.total_tokens_out)} />
          </div>

          {/* Вкладки */}
          <div className="flex gap-1 bg-gray-900 border border-gray-800 p-1 rounded-lg w-fit">
            {[{ key: 'overview', label: 'Обзор' }, { key: 'log', label: 'Лог запросов' }].map(t => (
              <button key={t.key} onClick={() => setTab(t.key as any)}
                className={`px-4 py-1.5 rounded-md text-sm transition ${tab === t.key ? 'bg-indigo-600 text-white' : 'text-gray-400 hover:text-white'}`}>
                {t.label}
              </button>
            ))}
          </div>

          {tab === 'overview' && <OverviewTab summary={summary} />}
          {tab === 'log' && <LogTab logs={logs} />}
        </>
      )}
    </div>
  )
}

function OverviewTab({ summary }: { summary: any }) {
  const maxProvCost = Math.max(...(summary.by_provider?.map((p: any) => p.cost_usd) ?? [1]))
  const maxAgentCost = Math.max(...(summary.by_agent?.map((a: any) => a.cost_usd) ?? [1]))

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
      {/* По провайдерам */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <h2 className="text-sm font-semibold text-white mb-4">По провайдерам</h2>
        {summary.by_provider?.length === 0
          ? <Empty text="Данных нет" />
          : summary.by_provider?.map((p: any) => (
            <div key={p.provider} className="mb-4 last:mb-0">
              <div className="flex justify-between text-sm mb-1.5">
                <div className="flex items-center gap-2">
                  <span className={`w-2.5 h-2.5 rounded-full ${PROVIDER_COLOR[p.provider] ?? 'bg-gray-500'}`} />
                  <span className="text-white capitalize">{p.provider}</span>
                  <span className="text-gray-600 text-xs">{p.calls} запросов</span>
                </div>
                <div className="text-right">
                  <span className="text-white text-xs font-mono">{fmt$(p.cost_usd)}</span>
                  <span className="text-gray-600 text-xs ml-2">{fmtK(p.tokens_in + p.tokens_out)} tok</span>
                </div>
              </div>
              <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${PROVIDER_COLOR[p.provider] ?? 'bg-gray-500'}`}
                  style={{ width: `${maxProvCost > 0 ? (p.cost_usd / maxProvCost) * 100 : 0}%` }}
                />
              </div>
            </div>
          ))}
      </div>

      {/* По агентам */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <h2 className="text-sm font-semibold text-white mb-4">По агентам</h2>
        {summary.by_agent?.length === 0
          ? <Empty text="Данных нет" />
          : summary.by_agent?.map((a: any) => (
            <div key={a.agent_id} className="mb-4 last:mb-0">
              <div className="flex justify-between text-sm mb-1.5">
                <div className="flex items-center gap-2">
                  <span className="text-white">{AGENT_NAMES[a.agent_id] ?? a.agent_id}</span>
                  <span className="text-gray-600 text-xs">{a.calls} запросов</span>
                </div>
                <span className="text-white text-xs font-mono">{fmt$(a.cost_usd)}</span>
              </div>
              <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-indigo-500 rounded-full"
                  style={{ width: `${maxAgentCost > 0 ? (a.cost_usd / maxAgentCost) * 100 : 0}%` }}
                />
              </div>
            </div>
          ))}
      </div>

      {/* График по дням */}
      {summary.daily?.length > 0 && (
        <div className="lg:col-span-2 bg-gray-900 border border-gray-800 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-white mb-4">Динамика расходов (последние 30 дней)</h2>
          <DailyChart data={summary.daily} />
        </div>
      )}
    </div>
  )
}

function DailyChart({ data }: { data: any[] }) {
  const maxCost = Math.max(...data.map((d: any) => d.cost_usd), 0.0001)
  return (
    <div className="flex items-end gap-1 h-32">
      {data.map((d: any) => (
        <div key={d.day} className="flex-1 flex flex-col items-center gap-1 group relative">
          <div
            className="w-full bg-indigo-600/70 hover:bg-indigo-500 rounded-sm transition"
            style={{ height: `${(d.cost_usd / maxCost) * 100}%`, minHeight: d.cost_usd > 0 ? 2 : 0 }}
          />
          {/* Tooltip */}
          <div className="absolute bottom-full mb-1 bg-gray-800 text-xs text-white px-2 py-1 rounded opacity-0 group-hover:opacity-100 pointer-events-none whitespace-nowrap z-10">
            {d.day}<br />{fmt$(d.cost_usd)} · {d.calls} запросов
          </div>
        </div>
      ))}
    </div>
  )
}

function LogTab({ logs }: { logs: any[] }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
      {logs.length === 0 ? (
        <Empty text="Логов нет" />
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-800">
              {['Агент', 'Провайдер', 'Модель', 'Токены вх.', 'Токены исх.', 'Стоимость', 'Время'].map(h => (
                <th key={h} className="text-left text-xs text-gray-500 px-4 py-3 font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {logs.map((l: any) => (
              <tr key={l.id} className="border-b border-gray-800/50 hover:bg-gray-800/20 transition">
                <td className="px-4 py-2.5 text-gray-300">{AGENT_NAMES[l.agent_id] ?? l.agent_id ?? '—'}</td>
                <td className="px-4 py-2.5">
                  <span className={`text-xs px-2 py-0.5 rounded-full capitalize ${
                    l.provider === 'deepseek' ? 'bg-blue-900/40 text-blue-400' :
                    l.provider === 'google'   ? 'bg-emerald-900/40 text-emerald-400' :
                    'bg-purple-900/40 text-purple-400'
                  }`}>{l.provider}</span>
                </td>
                <td className="px-4 py-2.5 text-xs text-gray-500 font-mono">{l.model}</td>
                <td className="px-4 py-2.5 text-xs text-gray-400 font-mono">{fmtK(l.tokens_input)}</td>
                <td className="px-4 py-2.5 text-xs text-gray-400 font-mono">{fmtK(l.tokens_output)}</td>
                <td className="px-4 py-2.5 text-xs text-amber-400 font-mono">{fmt$(l.cost_usd)}</td>
                <td className="px-4 py-2.5 text-xs text-gray-600">
                  {formatDistanceToNow(new Date(l.created_at), { addSuffix: true, locale: ru })}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

function MetricCard({ icon, label, value }: any) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <div className="flex items-center gap-2 mb-2">{icon}<span className="text-xs text-gray-500">{label}</span></div>
      <div className="text-2xl font-bold text-white font-mono">{value}</div>
    </div>
  )
}

function Empty({ text }: { text: string }) {
  return <div className="text-center text-gray-600 text-sm py-8">{text}</div>
}

function Skeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      <div className="grid grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => <div key={i} className="h-24 bg-gray-900 rounded-xl border border-gray-800" />)}
      </div>
      <div className="grid grid-cols-2 gap-5">
        {[...Array(2)].map((_, i) => <div key={i} className="h-48 bg-gray-900 rounded-xl border border-gray-800" />)}
      </div>
    </div>
  )
}
