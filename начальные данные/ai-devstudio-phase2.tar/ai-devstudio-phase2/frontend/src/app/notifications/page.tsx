'use client'
import { useEffect, useState } from 'react'
import { notificationsApi } from '@/lib/api'
import { formatDistanceToNow } from 'date-fns'
import { ru } from 'date-fns/locale'
import { Bell, CheckCheck } from 'lucide-react'

const PRIORITY_STYLE: Record<string, string> = {
  critical: 'border-l-red-500 bg-red-900/5',
  high:     'border-l-amber-500 bg-amber-900/5',
  medium:   'border-l-emerald-600 bg-gray-900',
  info:     'border-l-blue-600 bg-gray-900',
}
const PRIORITY_DOT: Record<string, string> = {
  critical: 'bg-red-500', high: 'bg-amber-500', medium: 'bg-emerald-500', info: 'bg-blue-500',
}

export default function NotificationsPage() {
  const [items, setItems] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<boolean | undefined>(false)

  const load = async () => {
    const res = await notificationsApi.list(filter)
    setItems(res.data)
    setLoading(false)
  }

  useEffect(() => { load() }, [filter])

  const markAllRead = async () => {
    await notificationsApi.markAllRead()
    load()
  }

  const markRead = async (id: string) => {
    await notificationsApi.markRead(id)
    setItems(prev => prev.map(n => n.id === id ? { ...n, is_read: true } : n))
  }

  return (
    <div className="max-w-3xl mx-auto space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Уведомления</h1>
        <button onClick={markAllRead} className="flex items-center gap-2 text-sm text-gray-400 hover:text-white transition">
          <CheckCheck size={16} /> Все прочитаны
        </button>
      </div>

      {/* Фильтр */}
      <div className="flex gap-2">
        {[
          { label: 'Новые', value: false },
          { label: 'Все', value: undefined },
        ].map(({ label, value }) => (
          <button
            key={label}
            onClick={() => setFilter(value)}
            className={`px-4 py-1.5 rounded-lg text-sm transition ${filter === value ? 'bg-indigo-600 text-white' : 'bg-gray-900 border border-gray-800 text-gray-400 hover:text-white'}`}
          >
            {label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="space-y-2">{[...Array(4)].map((_, i) => <div key={i} className="h-16 bg-gray-900 rounded-xl border border-gray-800 animate-pulse" />)}</div>
      ) : items.length === 0 ? (
        <div className="text-center py-20 text-gray-600">
          <Bell size={40} className="mx-auto mb-3 opacity-20" />
          <div>Уведомлений нет</div>
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((n: any) => (
            <div
              key={n.id}
              onClick={() => !n.is_read && markRead(n.id)}
              className={`border border-gray-800 border-l-4 rounded-xl p-4 cursor-pointer transition ${PRIORITY_STYLE[n.priority] ?? 'bg-gray-900'} ${n.is_read ? 'opacity-50' : 'hover:border-gray-700'}`}
            >
              <div className="flex items-start gap-3">
                <span className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${PRIORITY_DOT[n.priority] ?? 'bg-gray-500'}`} />
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-white font-medium">{n.title}</div>
                  {n.body && <div className="text-xs text-gray-400 mt-1">{n.body}</div>}
                  <div className="flex items-center gap-3 mt-2 text-xs text-gray-600">
                    <span>{n.type}</span>
                    <span>·</span>
                    <span>{formatDistanceToNow(new Date(n.created_at), { addSuffix: true, locale: ru })}</span>
                    {n.vk_sent && <span className="text-blue-600">· VK ✓</span>}
                  </div>
                </div>
                {!n.is_read && <span className="w-2 h-2 rounded-full bg-indigo-500 shrink-0 mt-1" />}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
