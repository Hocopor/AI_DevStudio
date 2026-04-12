'use client'
import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { Plus, Trash2, Star, RefreshCw } from 'lucide-react'

const SETTINGS_TABS = ['Провайдеры AI', 'Codex OAuth', 'Уведомления']

export default function SettingsPage() {
  const [tab, setTab] = useState('Провайдеры AI')

  return (
    <div className="max-w-4xl mx-auto space-y-5">
      <h1 className="text-2xl font-bold text-white">Настройки</h1>

      <div className="flex gap-1 bg-gray-900 border border-gray-800 p-1 rounded-lg w-fit">
        {SETTINGS_TABS.map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-1.5 rounded-md text-sm transition ${tab === t ? 'bg-indigo-600 text-white' : 'text-gray-400 hover:text-white'}`}>
            {t}
          </button>
        ))}
      </div>

      {tab === 'Провайдеры AI' && <ProvidersTab />}
      {tab === 'Codex OAuth' && <CodexTab />}
      {tab === 'Уведомления' && <NotificationsTab />}
    </div>
  )
}

// ── Провайдеры AI ──────────────────────────────────────────

function ProvidersTab() {
  const PROVIDERS = [
    { id: 'deepseek', name: 'DeepSeek', type: 'api_key', envKey: 'DEEPSEEK_API_KEY', models: ['deepseek-chat', 'deepseek-reasoner'] },
    { id: 'google',   name: 'Google AI Studio', type: 'api_key', envKey: 'GOOGLE_AI_STUDIO_KEY', models: ['gemini-2.0-flash', 'gemini-1.5-pro'] },
    { id: 'codex',    name: 'Codex (OpenAI)', type: 'oauth', note: 'Настройка в разделе Codex OAuth', models: ['gpt-4o', 'gpt-4o-mini', 'o1'] },
  ]

  return (
    <div className="space-y-4">
      <p className="text-sm text-gray-500">
        API-ключи хранятся в файле <code className="text-indigo-400">.env</code> на сервере.
        Здесь можно просмотреть статус и доступные модели.
      </p>
      {PROVIDERS.map(p => (
        <div key={p.id} className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <div className="flex items-center justify-between mb-3">
            <div>
              <span className="text-white font-medium">{p.name}</span>
              {p.note && <div className="text-xs text-gray-500 mt-0.5">{p.note}</div>}
            </div>
            <span className={`text-xs px-2 py-0.5 rounded-full ${p.type === 'oauth' ? 'bg-indigo-900/40 text-indigo-400' : 'bg-emerald-900/40 text-emerald-400'}`}>
              {p.type === 'oauth' ? 'OAuth' : 'API Key'}
            </span>
          </div>
          {p.type === 'api_key' && (
            <div className="text-xs text-gray-600 mb-3">
              Переменная окружения: <code className="text-gray-400">{p.envKey}</code>
            </div>
          )}
          <div className="flex flex-wrap gap-2">
            {p.models.map(m => (
              <span key={m} className="text-xs bg-gray-800 text-gray-400 px-2 py-1 rounded font-mono">{m}</span>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Codex OAuth ────────────────────────────────────────────

function CodexTab() {
  const [accounts, setAccounts] = useState<any[]>([])
  const [showAdd, setShowAdd] = useState(false)
  const [form, setForm] = useState({ label: '', oauth_token: '', priority: 1 })
  const [saving, setSaving] = useState(false)

  const load = async () => {
    const res = await api.get('/codex-accounts')
    setAccounts(res.data)
  }

  useEffect(() => { load() }, [])

  const add = async () => {
    if (!form.label || !form.oauth_token) return
    setSaving(true)
    await api.post('/codex-accounts', form)
    setForm({ label: '', oauth_token: '', priority: 1 })
    setShowAdd(false)
    setSaving(false)
    load()
  }

  const setCurrent = async (id: string) => {
    await api.post(`/codex-accounts/${id}/set-current`)
    load()
  }

  const remove = async (id: string) => {
    await api.delete(`/codex-accounts/${id}`)
    load()
  }

  const toggleActive = async (id: string, is_active: boolean) => {
    await api.put(`/codex-accounts/${id}`, { is_active: !is_active })
    load()
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-400">Мультиаккаунт Codex OAuth.</p>
          <p className="text-xs text-gray-600 mt-0.5">При исчерпании лимита — автоматический переход на следующий по приоритету.</p>
        </div>
        <button onClick={() => setShowAdd(true)}
          className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm px-3 py-2 rounded-lg transition">
          <Plus size={14} /> Добавить
        </button>
      </div>

      {accounts.length === 0 ? (
        <div className="text-center py-12 text-gray-600 bg-gray-900 border border-gray-800 rounded-xl">
          Аккаунты не добавлены
        </div>
      ) : (
        <div className="space-y-3">
          {accounts.map((a: any) => (
            <div key={a.id} className={`bg-gray-900 border rounded-xl p-4 ${a.is_current ? 'border-indigo-700' : 'border-gray-800'}`}>
              <div className="flex items-center gap-3">
                {a.is_current && <span className="text-xs bg-indigo-900/50 text-indigo-400 px-2 py-0.5 rounded-full">Активный</span>}
                <span className="text-white font-medium flex-1">{a.label}</span>
                <span className="text-xs text-gray-500">Приоритет: {a.priority}</span>
                <span className={`text-xs px-2 py-0.5 rounded-full ${a.is_active ? 'bg-emerald-900/40 text-emerald-400' : 'bg-gray-800 text-gray-600'}`}>
                  {a.is_active ? 'Активен' : 'Отключён'}
                </span>
              </div>
              <div className="flex items-center gap-2 mt-3">
                {!a.is_current && (
                  <button onClick={() => setCurrent(a.id)}
                    className="flex items-center gap-1 text-xs bg-gray-800 hover:bg-gray-700 text-gray-300 px-3 py-1.5 rounded-lg transition">
                    <Star size={12} /> Сделать активным
                  </button>
                )}
                <button onClick={() => toggleActive(a.id, a.is_active)}
                  className="text-xs bg-gray-800 hover:bg-gray-700 text-gray-400 px-3 py-1.5 rounded-lg transition">
                  {a.is_active ? 'Отключить' : 'Включить'}
                </button>
                <button onClick={() => remove(a.id)}
                  className="flex items-center gap-1 text-xs text-red-700 hover:text-red-400 px-2 py-1.5 rounded-lg transition ml-auto">
                  <Trash2 size={12} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {showAdd && (
        <div className="bg-gray-900 border border-indigo-800 rounded-xl p-5 space-y-3">
          <h3 className="text-sm font-semibold text-white">Добавить аккаунт</h3>
          <input placeholder="Метка (например: account-1)" value={form.label}
            onChange={e => setForm(f => ({ ...f, label: e.target.value }))}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500" />
          <input placeholder="OAuth токен" type="password" value={form.oauth_token}
            onChange={e => setForm(f => ({ ...f, oauth_token: e.target.value }))}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500" />
          <div>
            <label className="block text-xs text-gray-500 mb-1">Приоритет (1 = первый)</label>
            <input type="number" min={1} value={form.priority}
              onChange={e => setForm(f => ({ ...f, priority: parseInt(e.target.value) }))}
              className="w-32 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500" />
          </div>
          <div className="flex gap-2">
            <button onClick={() => setShowAdd(false)} className="flex-1 bg-gray-800 text-gray-400 rounded-lg py-2 text-sm">Отмена</button>
            <button onClick={add} disabled={saving || !form.label || !form.oauth_token}
              className="flex-1 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg py-2 text-sm transition">
              {saving ? 'Добавляем...' : 'Добавить'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Уведомления ────────────────────────────────────────────

const NOTIF_TYPES = [
  { key: 'requires_decision', label: 'Требует решения', desc: 'Когда агент ждёт вашего ответа' },
  { key: 'blocker',           label: 'Блокеры',          desc: 'Задачи, зависшие более 2 часов' },
  { key: 'stage_complete',    label: 'Этап завершён',    desc: 'Проект перешёл на новый этап' },
  { key: 'system_error',      label: 'Системные ошибки', desc: 'Сбои агентов и сервисов' },
  { key: 'provider_limit',    label: 'Лимиты провайдеров', desc: 'Исчерпание лимитов API' },
  { key: 'digest',            label: 'Дайджест',         desc: 'Ежедневная сводка в 20:00' },
]

function NotificationsTab() {
  const [vkEnabled, setVkEnabled] = useState(true)
  const [types, setTypes] = useState<Record<string, boolean>>(
    Object.fromEntries(NOTIF_TYPES.map(t => [t.key, true]))
  )

  return (
    <div className="space-y-5">
      {/* VK */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <div className="text-white font-medium">VK уведомления</div>
            <div className="text-xs text-gray-500 mt-0.5">Личное сообщение в группу</div>
          </div>
          <ToggleSwitch checked={vkEnabled} onChange={setVkEnabled} />
        </div>
        <div className="text-xs text-gray-600">
          Токен группы и ID владельца настраиваются в <code className="text-gray-500">.env</code>
        </div>
      </div>

      {/* Типы */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <h3 className="text-sm font-semibold text-white mb-4">Типы уведомлений</h3>
        <div className="space-y-3">
          {NOTIF_TYPES.map(t => (
            <div key={t.key} className="flex items-center justify-between py-2 border-b border-gray-800 last:border-0">
              <div>
                <div className="text-sm text-white">{t.label}</div>
                <div className="text-xs text-gray-500">{t.desc}</div>
              </div>
              <ToggleSwitch
                checked={types[t.key]}
                onChange={v => setTypes(prev => ({ ...prev, [t.key]: v }))}
              />
            </div>
          ))}
        </div>
      </div>

      <div className="text-xs text-gray-600 text-center">
        Полная настройка уведомлений — в файле конфигурации системы
      </div>
    </div>
  )
}

function ToggleSwitch({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      onClick={() => onChange(!checked)}
      className={`relative w-10 h-5 rounded-full transition-colors ${checked ? 'bg-indigo-600' : 'bg-gray-700'}`}
    >
      <span className={`absolute top-0.5 w-4 h-4 bg-white rounded-full transition-transform ${checked ? 'translate-x-5' : 'translate-x-0.5'}`} />
    </button>
  )
}
