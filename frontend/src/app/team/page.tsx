'use client'

import { useEffect, useState } from 'react'
import { Settings, Plus, Trash2, ChevronDown, ChevronUp, Share2 } from 'lucide-react'
import { agentsApi, api } from '@/lib/api'

const STATUS_COLOR: Record<string, string> = {
  active: 'bg-[var(--success)]',
  idle: 'bg-stone-500',
  error: 'bg-[var(--danger)]',
  disabled: 'bg-stone-700',
}

const STATUS_LABEL: Record<string, string> = {
  active: 'Работает',
  idle: 'Ожидает',
  error: 'Ошибка',
  disabled: 'Отключён',
}

const PROVIDERS = ['deepseek', 'google', 'codex']
const MODELS: Record<string, string[]> = {
  deepseek: ['deepseek-chat', 'deepseek-reasoner'],
  google: ['gemini-2.0-flash', 'gemini-1.5-pro', 'gemini-1.5-flash'],
  codex: ['gpt-4o', 'gpt-4o-mini', 'o1', 'o1-mini'],
}

export default function TeamPage() {
  const [agents, setAgents] = useState<any[]>([])
  const [skills, setSkills] = useState<any[]>([])
  const [expanded, setExpanded] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const load = async () => {
    const [ag, sk] = await Promise.all([agentsApi.list(), api.get('/skills')])
    setAgents(ag.data)
    setSkills(sk.data)
    setLoading(false)
  }

  useEffect(() => {
    load()
  }, [])

  if (loading) {
    return (
      <div className="space-y-4 animate-pulse">
        <div className="page-header min-h-[170px]" />
        {[...Array(4)].map((_, i) => (
          <div key={i} className="panel h-28" />
        ))}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <header className="page-header">
        <div>
          <div className="page-kicker">Agent Console</div>
          <h1 className="page-title">Команда и её операционные настройки.</h1>
          <p className="page-subtitle">
            Управление провайдерами, моделями, системными промптами и skills в одном плотном реестре.
          </p>
        </div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <AgentStat label="Всего агентов" value={agents.length} />
          <AgentStat label="Активных" value={agents.filter((a) => a.status === 'active').length} />
          <AgentStat label="Skills" value={skills.length} />
        </div>
      </header>

      <div className="space-y-4">
        {agents.map((agent) => (
          <AgentCard
            key={agent.id}
            agent={agent}
            agentSkills={skills.filter((s) => s.agent_id === agent.id)}
            allAgents={agents}
            expanded={expanded === agent.id}
            onToggle={() => setExpanded(expanded === agent.id ? null : agent.id)}
            onReload={load}
          />
        ))}
      </div>
    </div>
  )
}

function AgentCard({ agent, agentSkills, allAgents, expanded, onToggle, onReload }: any) {
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState({ provider: agent.provider, model: agent.model, system_prompt: agent.system_prompt || '' })
  const [saving, setSaving] = useState(false)
  const [showSkillForm, setShowSkillForm] = useState(false)

  const save = async () => {
    setSaving(true)
    await agentsApi.update(agent.id, form)
    setSaving(false)
    setEditing(false)
    onReload()
  }

  const trigger = async () => {
    await agentsApi.trigger(agent.id)
  }

  return (
    <section className="panel overflow-hidden">
      <div className="flex cursor-pointer flex-col gap-4 px-5 py-5 transition hover:bg-white/[0.02] md:flex-row md:items-center" onClick={onToggle}>
        <span className={`mt-1 h-2.5 w-2.5 rounded-full shrink-0 ${STATUS_COLOR[agent.status] ?? 'bg-stone-500'}`} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-base font-medium text-stone-100">{agent.name}</span>
            <span className="pill pill-neutral">{agent.role}</span>
            <span className="pill pill-neutral">{STATUS_LABEL[agent.status] ?? agent.status}</span>
          </div>
          <div className="mt-2 text-xs text-stone-500">
            {agent.provider} / {agent.model} • {agent.tasks_completed} задач выполнено • {agentSkills.length} skills
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={(e) => { e.stopPropagation(); trigger() }} className="btn-primary !px-3 !py-2 !text-xs">
            Запустить
          </button>
          {expanded ? <ChevronUp size={16} className="text-stone-500" /> : <ChevronDown size={16} className="text-stone-500" />}
        </div>
      </div>

      {expanded && (
        <div className="border-t border-white/10 px-5 py-5">
          <div className="grid gap-5 xl:grid-cols-[0.95fr_1.05fr]">
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold uppercase tracking-[0.16em] text-stone-300">Настройки</h3>
                {!editing && (
                  <button onClick={() => setEditing(true)} className="btn-secondary !px-3 !py-2 !text-xs">
                    <Settings size={12} />
                    Редактировать
                  </button>
                )}
              </div>

              {editing ? (
                <div className="space-y-4">
                  <div className="grid gap-4 md:grid-cols-2">
                    <div>
                      <label className="mb-2 block text-xs uppercase tracking-[0.14em] text-stone-500">Провайдер</label>
                      <select
                        value={form.provider}
                        onChange={(e) => setForm((f) => ({ ...f, provider: e.target.value, model: MODELS[e.target.value]?.[0] || '' }))}
                        className="input-base"
                      >
                        {PROVIDERS.map((p) => <option key={p} value={p}>{p}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="mb-2 block text-xs uppercase tracking-[0.14em] text-stone-500">Модель</label>
                      <select value={form.model} onChange={(e) => setForm((f) => ({ ...f, model: e.target.value }))} className="input-base">
                        {(MODELS[form.provider] || [form.model]).map((m) => <option key={m} value={m}>{m}</option>)}
                      </select>
                    </div>
                  </div>
                  <div>
                    <label className="mb-2 block text-xs uppercase tracking-[0.14em] text-stone-500">Системный промпт</label>
                    <textarea
                      rows={8}
                      value={form.system_prompt}
                      onChange={(e) => setForm((f) => ({ ...f, system_prompt: e.target.value }))}
                      className="input-base resize-none font-mono"
                    />
                  </div>
                  <div className="flex gap-3">
                    <button onClick={() => setEditing(false)} className="btn-secondary flex-1">Отмена</button>
                    <button onClick={save} disabled={saving} className="btn-primary flex-1">{saving ? 'Сохраняем...' : 'Сохранить'}</button>
                  </div>
                </div>
              ) : (
                <div className="grid gap-3 md:grid-cols-3">
                  <InfoBox label="Провайдер" value={agent.provider} />
                  <InfoBox label="Модель" value={agent.model} />
                  <InfoBox label="Задач выполнено" value={agent.tasks_completed} />
                </div>
              )}
            </div>

            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold uppercase tracking-[0.16em] text-stone-300">Skills</h3>
                <button onClick={() => setShowSkillForm(true)} className="btn-secondary !px-3 !py-2 !text-xs">
                  <Plus size={12} />
                  Добавить
                </button>
              </div>

              {agentSkills.length === 0 ? (
                <div className="panel-soft px-4 py-8 text-center text-sm text-stone-500">Skills пока не добавлены.</div>
              ) : (
                <div className="space-y-3">
                  {agentSkills.map((skill: any) => (
                    <SkillCard key={skill.id} skill={skill} allAgents={allAgents} onReload={onReload} />
                  ))}
                </div>
              )}

              {showSkillForm && <AddSkillForm agentId={agent.id} onClose={() => setShowSkillForm(false)} onCreated={onReload} />}
            </div>
          </div>
        </div>
      )}
    </section>
  )
}

function AgentStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-[rgba(255,255,255,0.03)] px-4 py-3">
      <div className="text-[0.68rem] uppercase tracking-[0.16em] text-stone-500">{label}</div>
      <div className="mt-2 text-xl font-semibold text-stone-100">{value}</div>
    </div>
  )
}

function InfoBox({ label, value }: any) {
  return (
    <div className="panel-soft p-4">
      <div className="text-[0.68rem] uppercase tracking-[0.14em] text-stone-500">{label}</div>
      <div className="mt-2 text-sm font-medium text-stone-100">{value}</div>
    </div>
  )
}

function SkillCard({ skill, allAgents, onReload }: any) {
  const [showDistribute, setShowDistribute] = useState(false)
  const [selected, setSelected] = useState<string[]>([])

  const deleteSkill = async () => {
    await api.delete(`/skills/${skill.id}`)
    onReload()
  }

  const distribute = async () => {
    await api.post(`/skills/${skill.id}/distribute`, { target_agent_ids: selected })
    setShowDistribute(false)
    onReload()
  }

  return (
    <div className="panel-soft p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium text-stone-100">{skill.name}</span>
            <span className="pill pill-neutral">v{skill.version}</span>
            {!skill.is_active && <span className="pill pill-neutral">inactive</span>}
          </div>
          {skill.description && <div className="mt-2 text-sm text-stone-400">{skill.description}</div>}
        </div>
        <div className="flex items-center gap-1">
          <button onClick={() => setShowDistribute(!showDistribute)} className="btn-secondary !px-2.5 !py-2">
            <Share2 size={13} />
          </button>
          <button onClick={deleteSkill} className="btn-secondary !px-2.5 !py-2">
            <Trash2 size={13} />
          </button>
        </div>
      </div>

      {showDistribute && (
        <div className="mt-4 border-t border-white/10 pt-4">
          <div className="text-xs uppercase tracking-[0.14em] text-stone-500">Распространить на агентов</div>
          <div className="mt-3 flex flex-wrap gap-3">
            {allAgents.filter((a: any) => a.id !== skill.agent_id).map((a: any) => (
              <label key={a.id} className="flex items-center gap-2 text-sm text-stone-300">
                <input
                  type="checkbox"
                  checked={selected.includes(a.id)}
                  onChange={(e) => setSelected((prev) => e.target.checked ? [...prev, a.id] : prev.filter((x) => x !== a.id))}
                  className="accent-[var(--accent)]"
                />
                {a.name}
              </label>
            ))}
          </div>
          <button onClick={distribute} disabled={selected.length === 0} className="btn-primary mt-4 !px-3 !py-2 !text-xs">
            Распространить
          </button>
        </div>
      )}
    </div>
  )
}

function AddSkillForm({ agentId, onClose, onCreated }: any) {
  const [form, setForm] = useState({ name: '', description: '', content: '' })
  const [saving, setSaving] = useState(false)

  const save = async () => {
    if (!form.name || !form.content) return
    setSaving(true)
    await api.post('/skills', { agent_id: agentId, ...form })
    onCreated()
    onClose()
  }

  return (
    <div className="panel-soft p-4">
      <div className="text-xs uppercase tracking-[0.14em] text-stone-500">Новый skill</div>
      <div className="mt-4 space-y-3">
        <input placeholder="Название *" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} className="input-base" />
        <input placeholder="Описание" value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} className="input-base" />
        <textarea rows={5} placeholder="Содержимое *" value={form.content} onChange={(e) => setForm((f) => ({ ...f, content: e.target.value }))} className="input-base resize-none font-mono" />
      </div>
      <div className="mt-4 flex gap-3">
        <button onClick={onClose} className="btn-secondary flex-1">Отмена</button>
        <button onClick={save} disabled={saving || !form.name || !form.content} className="btn-primary flex-1">
          {saving ? 'Сохраняем...' : 'Создать'}
        </button>
      </div>
    </div>
  )
}
