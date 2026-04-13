'use client'

import { useEffect, useState } from 'react'
import { Plus, RefreshCw, Star, Trash2 } from 'lucide-react'
import { api } from '@/lib/api'

const SETTINGS_TABS = ['Провайдеры AI', 'Codex OAuth', 'Уведомления']

export default function SettingsPage() {
  const [tab, setTab] = useState('Провайдеры AI')

  return (
    <div className="space-y-6">
      <header className="page-header">
        <div>
          <div className="page-kicker">System Settings</div>
          <h1 className="page-title">Настройки инфраструктуры и доступа.</h1>
          <p className="page-subtitle">
            Провайдеры, OAuth-аккаунты и уведомления собраны в строгую панель без лишней перегрузки.
          </p>
        </div>
      </header>

      <div className="flex flex-wrap gap-2">
        {SETTINGS_TABS.map((t) => (
          <button key={t} onClick={() => setTab(t)} className={tab === t ? 'btn-primary !py-2 !text-xs !tracking-[0.16em]' : 'btn-secondary !py-2 !text-xs !tracking-[0.16em]'}>
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

function ProvidersTab() {
  const providers = [
    { id: 'deepseek', name: 'DeepSeek', type: 'api_key', envKey: 'DEEPSEEK_API_KEY', models: ['deepseek-chat', 'deepseek-reasoner'] },
    { id: 'google', name: 'Google AI Studio', type: 'api_key', envKey: 'GOOGLE_AI_STUDIO_KEY', models: ['gemini-2.0-flash', 'gemini-1.5-pro'] },
    { id: 'codex', name: 'Codex (OpenAI)', type: 'oauth', note: 'Настраивается в разделе Codex OAuth', models: ['gpt-4o', 'gpt-4o-mini', 'o1'] },
  ]

  return (
    <div className="grid gap-4 lg:grid-cols-3">
      {providers.map((p) => (
        <div key={p.id} className="panel p-5">
          <div className="flex items-center justify-between">
            <div className="text-base font-medium text-stone-100">{p.name}</div>
            <span className="pill pill-neutral">{p.type === 'oauth' ? 'OAuth' : 'API key'}</span>
          </div>
          {p.note && <div className="mt-3 text-sm text-stone-500">{p.note}</div>}
          {p.type === 'api_key' && <div className="mt-3 text-xs text-stone-500">Переменная окружения: <code className="text-stone-300">{p.envKey}</code></div>}
          <div className="mt-4 flex flex-wrap gap-2">
            {p.models.map((m) => (
              <span key={m} className="pill pill-neutral !normal-case !tracking-[0.04em]">{m}</span>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

function CodexTab() {
  const [accounts, setAccounts] = useState<any[]>([])
  const [showAdd, setShowAdd] = useState(false)
  const [form, setForm] = useState({ label: '', oauth_token: '', priority: 1 })
  const [saving, setSaving] = useState(false)

  const load = async () => {
    const res = await api.get('/codex-accounts')
    setAccounts(res.data)
  }

  useEffect(() => {
    load()
  }, [])

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
        <p className="max-w-2xl text-sm leading-6 text-stone-400">При исчерпании лимита система автоматически переключается на следующий аккаунт по приоритету.</p>
        <button onClick={() => setShowAdd(true)} className="btn-primary !px-3 !py-2 !text-xs">
          <Plus size={12} />
          Добавить
        </button>
      </div>

      {accounts.length === 0 ? (
        <div className="panel px-6 py-16 text-center text-stone-500">Аккаунты пока не добавлены.</div>
      ) : (
        <div className="space-y-3">
          {accounts.map((a: any) => (
            <div key={a.id} className="panel p-4">
              <div className="flex flex-col gap-3 md:flex-row md:items-center">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium text-stone-100">{a.label}</span>
                    {a.is_current && <span className="pill pill-neutral">active</span>}
                    <span className="pill pill-neutral">priority {a.priority}</span>
                  </div>
                  <div className="mt-2 text-xs text-stone-500">{a.is_active ? 'Аккаунт участвует в ротации.' : 'Аккаунт отключён.'}</div>
                </div>
                <div className="flex flex-wrap gap-2">
                  {!a.is_current && (
                    <button onClick={() => setCurrent(a.id)} className="btn-secondary !px-3 !py-2 !text-xs">
                      <Star size={12} />
                      Сделать активным
                    </button>
                  )}
                  <button onClick={() => toggleActive(a.id, a.is_active)} className="btn-secondary !px-3 !py-2 !text-xs">
                    <RefreshCw size={12} />
                    {a.is_active ? 'Отключить' : 'Включить'}
                  </button>
                  <button onClick={() => remove(a.id)} className="btn-secondary !px-3 !py-2 !text-xs">
                    <Trash2 size={12} />
                    Удалить
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {showAdd && (
        <div className="panel p-5">
          <div className="page-kicker">New OAuth Account</div>
          <div className="mt-2 text-xl font-semibold text-stone-100">Добавить аккаунт</div>
          <div className="mt-4 grid gap-4 md:grid-cols-[1fr_1fr_160px]">
            <input placeholder="Метка" value={form.label} onChange={(e) => setForm((f) => ({ ...f, label: e.target.value }))} className="input-base" />
            <input placeholder="OAuth токен" type="password" value={form.oauth_token} onChange={(e) => setForm((f) => ({ ...f, oauth_token: e.target.value }))} className="input-base" />
            <input type="number" min={1} value={form.priority} onChange={(e) => setForm((f) => ({ ...f, priority: parseInt(e.target.value) }))} className="input-base" />
          </div>
          <div className="mt-4 flex gap-3">
            <button onClick={() => setShowAdd(false)} className="btn-secondary flex-1">Отмена</button>
            <button onClick={add} disabled={saving || !form.label || !form.oauth_token} className="btn-primary flex-1">
              {saving ? 'Добавляем...' : 'Добавить'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function NotificationsTab() {
  const [vkEnabled, setVkEnabled] = useState(true)
  const [types, setTypes] = useState<Record<string, boolean>>({
    requires_decision: true,
    blocker: true,
    stage_complete: true,
    system_error: true,
    provider_limit: true,
    digest: true,
  })

  const notifTypes = [
    { key: 'requires_decision', label: 'Требует решения', desc: 'Когда агент ждёт вашего ответа' },
    { key: 'blocker', label: 'Блокеры', desc: 'Задачи, зависшие более 2 часов' },
    { key: 'stage_complete', label: 'Этап завершён', desc: 'Проект перешёл на новый этап' },
    { key: 'system_error', label: 'Системные ошибки', desc: 'Сбои агентов и сервисов' },
    { key: 'provider_limit', label: 'Лимиты провайдеров', desc: 'Исчерпание лимитов API' },
    { key: 'digest', label: 'Дайджест', desc: 'Ежедневная сводка в 20:00' },
  ]

  return (
    <div className="space-y-4">
      <div className="panel p-5">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-base font-medium text-stone-100">VK уведомления</div>
            <div className="mt-2 text-sm text-stone-500">Токен сообщества и ID владельца задаются через `.env`.</div>
          </div>
          <ToggleSwitch checked={vkEnabled} onChange={setVkEnabled} />
        </div>
      </div>

      <div className="panel p-5">
        <div className="text-sm font-semibold uppercase tracking-[0.16em] text-stone-300">Типы уведомлений</div>
        <div className="mt-4 space-y-3">
          {notifTypes.map((t) => (
            <div key={t.key} className="panel-soft flex items-center justify-between px-4 py-3">
              <div>
                <div className="text-sm text-stone-100">{t.label}</div>
                <div className="mt-1 text-xs text-stone-500">{t.desc}</div>
              </div>
              <ToggleSwitch checked={types[t.key]} onChange={(v) => setTypes((prev) => ({ ...prev, [t.key]: v }))} />
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function ToggleSwitch({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button onClick={() => onChange(!checked)} className={`relative h-6 w-11 rounded-full transition ${checked ? 'bg-[var(--accent)]' : 'bg-stone-700'}`}>
      <span className={`absolute top-1 h-4 w-4 rounded-full bg-white transition ${checked ? 'translate-x-6' : 'translate-x-1'}`} />
    </button>
  )
}
