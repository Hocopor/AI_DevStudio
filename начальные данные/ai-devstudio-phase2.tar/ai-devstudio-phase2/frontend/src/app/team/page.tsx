'use client'
import { useEffect, useState } from 'react'
import { agentsApi, api } from '@/lib/api'
import { Settings, Plus, Trash2, ChevronDown, ChevronUp, Share2 } from 'lucide-react'

const STATUS_COLOR: Record<string, string> = {
  active:   'bg-emerald-400',
  idle:     'bg-gray-500',
  error:    'bg-red-500',
  disabled: 'bg-gray-700',
}
const STATUS_LABEL: Record<string, string> = {
  active: 'Работает', idle: 'Ожидает', error: 'Ошибка', disabled: 'Отключён',
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
    const [ag, sk] = await Promise.all([
      agentsApi.list(),
      api.get('/skills'),
    ])
    setAgents(ag.data)
    setSkills(sk.data)
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  if (loading) return (
    <div className="max-w-5xl mx-auto space-y-3 animate-pulse">
      {[...Array(5)].map((_, i) => <div key={i} className="h-20 bg-gray-900 rounded-xl border border-gray-800" />)}
    </div>
  )

  return (
    <div className="max-w-5xl mx-auto space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Команда</h1>
        <div className="text-sm text-gray-500">{agents.filter(a => a.status === 'active').length} активных из {agents.length}</div>
      </div>

      <div className="space-y-3">
        {agents.map((agent) => (
          <AgentCard
            key={agent.id}
            agent={agent}
            agentSkills={skills.filter(s => s.agent_id === agent.id)}
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
    <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
      {/* Заголовок */}
      <div className="flex items-center gap-4 px-5 py-4 cursor-pointer hover:bg-gray-800/30 transition" onClick={onToggle}>
        <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${STATUS_COLOR[agent.status] ?? 'bg-gray-500'}`} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3">
            <span className="text-white font-medium">{agent.name}</span>
            <span className="text-xs text-gray-500">{agent.role}</span>
            <span className={`text-xs px-2 py-0.5 rounded-full ${
              agent.status === 'active' ? 'bg-emerald-900/40 text-emerald-400' :
              agent.status === 'error' ? 'bg-red-900/40 text-red-400' :
              'bg-gray-800 text-gray-500'
            }`}>
              {STATUS_LABEL[agent.status] ?? agent.status}
            </span>
          </div>
          <div className="text-xs text-gray-600 mt-0.5">
            {agent.provider} / {agent.model} · {agent.tasks_completed} задач выполнено · {agentSkills.length} skills
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={(e) => { e.stopPropagation(); trigger() }}
            className="text-xs bg-indigo-900/40 text-indigo-400 hover:bg-indigo-900/60 px-3 py-1 rounded-lg transition"
          >
            Запустить
          </button>
          {expanded ? <ChevronUp size={16} className="text-gray-600" /> : <ChevronDown size={16} className="text-gray-600" />}
        </div>
      </div>

      {/* Развёрнутая панель */}
      {expanded && (
        <div className="border-t border-gray-800 px-5 py-5 space-y-5">
          {/* Настройки провайдера */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-white">Настройки</h3>
              {!editing && (
                <button onClick={() => setEditing(true)} className="flex items-center gap-1 text-xs text-gray-400 hover:text-white transition">
                  <Settings size={12} /> Редактировать
                </button>
              )}
            </div>

            {editing ? (
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Провайдер</label>
                    <select
                      value={form.provider}
                      onChange={e => setForm(f => ({ ...f, provider: e.target.value, model: MODELS[e.target.value]?.[0] || '' }))}
                      className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500"
                    >
                      {PROVIDERS.map(p => <option key={p} value={p}>{p}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Модель</label>
                    <select
                      value={form.model}
                      onChange={e => setForm(f => ({ ...f, model: e.target.value }))}
                      className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500"
                    >
                      {(MODELS[form.provider] || [form.model]).map(m => <option key={m} value={m}>{m}</option>)}
                    </select>
                  </div>
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Системный промпт (оставь пустым для дефолтного)</label>
                  <textarea
                    rows={6}
                    value={form.system_prompt}
                    onChange={e => setForm(f => ({ ...f, system_prompt: e.target.value }))}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm font-mono focus:outline-none focus:border-indigo-500 resize-none"
                  />
                </div>
                <div className="flex gap-2">
                  <button onClick={() => setEditing(false)} className="flex-1 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg py-2 text-sm transition">
                    Отмена
                  </button>
                  <button onClick={save} disabled={saving} className="flex-1 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg py-2 text-sm transition">
                    {saving ? 'Сохраняем...' : 'Сохранить'}
                  </button>
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-3 gap-3 text-sm">
                <InfoBox label="Провайдер" value={agent.provider} />
                <InfoBox label="Модель" value={agent.model} />
                <InfoBox label="Задач выполнено" value={agent.tasks_completed} />
              </div>
            )}
          </div>

          {/* Skills */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-white">Skills ({agentSkills.length})</h3>
              <button
                onClick={() => setShowSkillForm(true)}
                className="flex items-center gap-1 text-xs text-gray-400 hover:text-white transition"
              >
                <Plus size={12} /> Добавить
              </button>
            </div>

            {agentSkills.length === 0 ? (
              <div className="text-xs text-gray-600 py-2">Skills отсутствуют</div>
            ) : (
              <div className="space-y-2">
                {agentSkills.map((skill: any) => (
                  <SkillCard key={skill.id} skill={skill} allAgents={allAgents} onReload={onReload} />
                ))}
              </div>
            )}

            {showSkillForm && (
              <AddSkillForm
                agentId={agent.id}
                onClose={() => setShowSkillForm(false)}
                onCreated={onReload}
              />
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function InfoBox({ label, value }: any) {
  return (
    <div className="bg-gray-800/50 rounded-lg p-3">
      <div className="text-xs text-gray-500 mb-1">{label}</div>
      <div className="text-sm text-white font-mono">{value}</div>
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
    <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm text-white font-medium">{skill.name}</span>
            <span className="text-xs text-gray-600">v{skill.version}</span>
            {!skill.is_active && <span className="text-xs text-gray-600">(отключён)</span>}
          </div>
          {skill.description && <div className="text-xs text-gray-500 mt-0.5">{skill.description}</div>}
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <button onClick={() => setShowDistribute(!showDistribute)} className="p-1 text-gray-600 hover:text-indigo-400 transition" title="Распространить">
            <Share2 size={13} />
          </button>
          <button onClick={deleteSkill} className="p-1 text-gray-600 hover:text-red-400 transition">
            <Trash2 size={13} />
          </button>
        </div>
      </div>

      {showDistribute && (
        <div className="mt-3 pt-3 border-t border-gray-700">
          <div className="text-xs text-gray-400 mb-2">Распространить на агентов:</div>
          <div className="flex flex-wrap gap-2 mb-2">
            {allAgents.filter((a: any) => a.id !== skill.agent_id).map((a: any) => (
              <label key={a.id} className="flex items-center gap-1 cursor-pointer">
                <input
                  type="checkbox"
                  checked={selected.includes(a.id)}
                  onChange={e => setSelected(prev => e.target.checked ? [...prev, a.id] : prev.filter(x => x !== a.id))}
                  className="accent-indigo-500"
                />
                <span className="text-xs text-gray-400">{a.name}</span>
              </label>
            ))}
          </div>
          <button onClick={distribute} disabled={selected.length === 0}
            className="text-xs bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white px-3 py-1 rounded-lg transition">
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
    <div className="mt-3 pt-3 border-t border-gray-700 space-y-3">
      <div className="text-xs font-medium text-white">Новый Skill</div>
      <input placeholder="Название *" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
        className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500" />
      <input placeholder="Описание" value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
        className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500" />
      <textarea rows={4} placeholder="Содержимое (промпт / инструкция) *" value={form.content}
        onChange={e => setForm(f => ({ ...f, content: e.target.value }))}
        className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm font-mono focus:outline-none focus:border-indigo-500 resize-none" />
      <div className="flex gap-2">
        <button onClick={onClose} className="flex-1 bg-gray-800 text-gray-400 rounded-lg py-1.5 text-sm">Отмена</button>
        <button onClick={save} disabled={saving || !form.name || !form.content}
          className="flex-1 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg py-1.5 text-sm transition">
          {saving ? 'Сохраняем...' : 'Создать'}
        </button>
      </div>
    </div>
  )
}
