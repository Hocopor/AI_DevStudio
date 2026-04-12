'use client'
import { useEffect, useState, useRef } from 'react'
import { useParams } from 'next/navigation'
import { tasksApi } from '@/lib/api'
import Link from 'next/link'
import { ArrowLeft, CheckCircle2, Circle, Clock, Send } from 'lucide-react'
import { formatDistanceToNow, format } from 'date-fns'
import { ru } from 'date-fns/locale'
import { projectWS } from '@/lib/websocket'

const STATUS_LABEL: Record<string, string> = {
  backlog: 'Backlog', todo: 'К выполнению', in_progress: 'В работе',
  review: 'Проверка', awaiting_approval: 'Согласование',
  testing: 'Тестирование', done: 'Готово', archived: 'Архив',
}

const STATUS_COLOR: Record<string, string> = {
  backlog: 'bg-gray-800 text-gray-400',
  todo: 'bg-gray-800 text-gray-300',
  in_progress: 'bg-indigo-900/40 text-indigo-400',
  review: 'bg-amber-900/40 text-amber-400',
  awaiting_approval: 'bg-red-900/40 text-red-400',
  testing: 'bg-purple-900/40 text-purple-400',
  done: 'bg-emerald-900/40 text-emerald-400',
}

const PRIORITY_COLOR: Record<string, string> = {
  low: 'text-gray-500', medium: 'text-blue-400',
  high: 'text-amber-400', critical: 'text-red-400',
}

const PRIORITY_LABEL: Record<string, string> = {
  low: 'Низкий', medium: 'Средний', high: 'Высокий', critical: 'Критический',
}

const AUTHOR_LABELS: Record<string, string> = {
  owner: '👤 Вы',
  director: '🎩 Директор',
  backend_dev: '⚙️ Backend Dev',
}

const STEP_STATUS_ICON = {
  done: <CheckCircle2 size={15} className="text-emerald-400 shrink-0 mt-0.5" />,
  in_progress: <Clock size={15} className="text-indigo-400 shrink-0 mt-0.5 animate-pulse" />,
  pending: <Circle size={15} className="text-gray-600 shrink-0 mt-0.5" />,
  skipped: <Circle size={15} className="text-gray-700 shrink-0 mt-0.5" />,
}

export default function TaskDetailPage() {
  const { id: projectId, taskId } = useParams<{ id: string; taskId: string }>()
  const [task, setTask] = useState<any>(null)
  const [comments, setComments] = useState<any[]>([])
  const [comment, setComment] = useState('')
  const [sending, setSending] = useState(false)
  const commentsRef = useRef<HTMLDivElement>(null)

  const loadTask = async () => {
    const [t, c] = await Promise.all([
      tasksApi.get(taskId),
      tasksApi.getComments(taskId),
    ])
    setTask(t.data)
    setComments(c.data)
  }

  useEffect(() => {
    loadTask()
    const handler = (data: any) => {
      if (data.task_id === taskId) loadTask()
    }
    projectWS.on('task_comment_added', handler)
    projectWS.on('task_status_changed', handler)
    return () => {
      projectWS.off('task_comment_added', handler)
      projectWS.off('task_status_changed', handler)
    }
  }, [taskId])

  // Скролл к последнему комментарию
  useEffect(() => {
    if (commentsRef.current) {
      commentsRef.current.scrollTop = commentsRef.current.scrollHeight
    }
  }, [comments])

  const sendComment = async () => {
    if (!comment.trim() || sending) return
    setSending(true)
    try {
      await tasksApi.addComment(taskId, comment.trim(), 'owner')
      setComment('')
      await loadTask()
    } finally {
      setSending(false)
    }
  }

  if (!task) return (
    <div className="max-w-4xl mx-auto animate-pulse space-y-4">
      <div className="h-6 w-48 bg-gray-800 rounded" />
      <div className="h-32 bg-gray-900 rounded-xl border border-gray-800" />
    </div>
  )

  const plan = task.live_plan ?? { steps: [], notes: '' }

  return (
    <div className="max-w-4xl mx-auto space-y-5">
      {/* Назад */}
      <Link href={`/projects/${projectId}`} className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-300 transition">
        <ArrowLeft size={14} /> К проекту
      </Link>

      {/* Заголовок задачи */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="flex-1 min-w-0">
            <h1 className="text-xl font-bold text-white mb-3">{task.title}</h1>
            <div className="flex flex-wrap items-center gap-3">
              <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${STATUS_COLOR[task.status] ?? 'bg-gray-800 text-gray-400'}`}>
                {STATUS_LABEL[task.status] ?? task.status}
              </span>
              <span className={`text-xs font-medium ${PRIORITY_COLOR[task.priority]}`}>
                ↑ {PRIORITY_LABEL[task.priority] ?? task.priority}
              </span>
              {task.assigned_to && (
                <span className="text-xs text-gray-500">
                  {AUTHOR_LABELS[task.assigned_to] ?? task.assigned_to}
                </span>
              )}
              {task.tags?.map((t: string) => (
                <span key={t} className="text-xs bg-gray-800 text-gray-500 px-2 py-0.5 rounded">{t}</span>
              ))}
            </div>
          </div>
        </div>

        {task.description && (
          <div className="mt-4 text-sm text-gray-400 leading-relaxed border-t border-gray-800 pt-4">
            {task.description}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
        {/* Живой план */}
        <div className="lg:col-span-2">
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
            <h2 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
              📋 Живой план
              {plan.steps.length > 0 && (
                <span className="text-xs text-gray-500 font-normal">
                  {plan.steps.filter((s: any) => s.status === 'done').length}/{plan.steps.length}
                </span>
              )}
            </h2>

            {plan.steps.length === 0 ? (
              <div className="text-gray-600 text-xs text-center py-4">
                Агент ещё не составил план
              </div>
            ) : (
              <>
                {/* Прогресс */}
                <div className="mb-4 h-1 bg-gray-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-indigo-500 rounded-full transition-all"
                    style={{
                      width: `${(plan.steps.filter((s: any) => s.status === 'done').length / plan.steps.length) * 100}%`
                    }}
                  />
                </div>

                <div className="space-y-2.5">
                  {plan.steps.map((step: any, i: number) => (
                    <div key={i} className="flex items-start gap-2">
                      {STEP_STATUS_ICON[step.status as keyof typeof STEP_STATUS_ICON] ?? STEP_STATUS_ICON.pending}
                      <div>
                        <div className={`text-xs leading-snug ${
                          step.status === 'done' ? 'text-gray-500 line-through' :
                          step.status === 'in_progress' ? 'text-white' : 'text-gray-400'
                        }`}>
                          {step.step}
                        </div>
                        {step.note && (
                          <div className="text-xs text-gray-600 mt-0.5">{step.note}</div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>

                {plan.notes && (
                  <div className="mt-4 text-xs text-gray-500 border-t border-gray-800 pt-3">
                    {plan.notes}
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        {/* Комментарии */}
        <div className="lg:col-span-3 flex flex-col">
          <div className="bg-gray-900 border border-gray-800 rounded-xl flex flex-col h-[520px]">
            <div className="px-5 py-4 border-b border-gray-800">
              <h2 className="text-sm font-semibold text-white">💬 Комментарии ({comments.length})</h2>
            </div>

            {/* Лента комментариев */}
            <div ref={commentsRef} className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
              {comments.length === 0 ? (
                <div className="text-center text-gray-600 text-sm py-8">Комментариев пока нет</div>
              ) : comments.map((c: any) => (
                <CommentItem key={c.id} comment={c} />
              ))}
            </div>

            {/* Ввод комментария */}
            <div className="px-4 py-3 border-t border-gray-800">
              <div className="flex items-end gap-2">
                <textarea
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendComment() }
                  }}
                  rows={2}
                  placeholder="Написать комментарий... (Enter — отправить)"
                  className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500 resize-none"
                />
                <button
                  onClick={sendComment}
                  disabled={!comment.trim() || sending}
                  className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white p-2 rounded-lg transition"
                >
                  <Send size={16} />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function CommentItem({ comment }: { comment: any }) {
  const isOwner = comment.author === 'owner'
  const label = AUTHOR_LABELS[comment.author] ?? comment.author

  return (
    <div className={`flex ${isOwner ? 'flex-row-reverse' : 'flex-row'} gap-3`}>
      <div className={`max-w-[85%] ${isOwner ? 'items-end' : 'items-start'} flex flex-col`}>
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs text-gray-500">{label}</span>
          <span className="text-xs text-gray-700">
            {formatDistanceToNow(new Date(comment.created_at), { addSuffix: true, locale: ru })}
          </span>
        </div>
        <div className={`text-sm rounded-xl px-4 py-2.5 leading-relaxed whitespace-pre-wrap ${
          isOwner
            ? 'bg-indigo-600/30 border border-indigo-700/40 text-indigo-100'
            : 'bg-gray-800 border border-gray-700 text-gray-200'
        }`}>
          {comment.content}
        </div>
      </div>
    </div>
  )
}
