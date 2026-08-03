import { useMemo, useState } from 'react'
import { AGENT_NAMES, UI_EMOJI } from '../constants/agents.js'

const GROUPS = [
  { key: 'running', label: 'Running', icon: UI_EMOJI.refresh, color: 'text-blue-600' },
  { key: 'waiting', label: 'Waiting', icon: UI_EMOJI.hourglass, color: 'text-amber-600' },
  { key: 'pending', label: 'Pending', icon: UI_EMOJI.clipboard, color: 'text-gray-600' },
  { key: 'done', label: 'Done', icon: UI_EMOJI.check, color: 'text-green-600' },
  { key: 'failed', label: 'Failed', icon: UI_EMOJI.cross, color: 'text-red-600' },
  { key: 'abandoned', label: '已放弃', icon: UI_EMOJI.warning, color: 'text-gray-400' },
]

const DONE_SHOW_LIMIT = 5  // Done 列表默认显示数量（用户要求）

const STATUS_ICON = {
  running: UI_EMOJI.refresh,
  waiting: UI_EMOJI.hourglass,
  pending: UI_EMOJI.clipboard,
  done: UI_EMOJI.check,
  failed: UI_EMOJI.warning,
  abandoned: UI_EMOJI.warning,
}

function isBlocked(task, byId) {
  return (task.depends_on || []).some((depId) => {
    const dep = byId[depId]
    return !dep || dep.status !== 'done'
  })
}

function groupTasks(tasks, byId) {
  const groups = Object.fromEntries(GROUPS.map((g) => [g.key, []]))
  for (const task of tasks) {
    if (task.status === 'running') groups.running.push(task)
    else if (task.status === 'pending') {
      if (isBlocked(task, byId)) groups.waiting.push(task)
      else groups.pending.push(task)
    } else if (task.status === 'done') groups.done.push(task)
    else if (task.status === 'failed') groups.failed.push(task)
    else if (task.status === 'abandoned') groups.abandoned.push(task)
  }
  // Done 倒序（最新在前，用户要求）；Failed/已放弃 也倒序（最新问题最显眼）
  groups.done.sort((a, b) => b.id - a.id)
  groups.failed.sort((a, b) => b.id - a.id)
  groups.abandoned.sort((a, b) => b.id - a.id)
  return groups
}

function TaskCard({ task, byId, busy, onAction, reassignFor, reassignTarget, onStartReassign, onReassignTargetChange, onCancelReassign }) {
  const waitingDeps = (task.depends_on || []).filter((depId) => {
    const dep = byId[depId]
    return !dep || dep.status !== 'done'
  })
  const doneDeps = (task.depends_on || []).filter((depId) => {
    const dep = byId[depId]
    return dep && dep.status === 'done'
  })
  const failed = task.status === 'failed' || task.status === 'abandoned'
  const statusIcon = STATUS_ICON[task.status === 'abandoned' ? 'abandoned' : task.status] || UI_EMOJI.fallback

  return (
    <div className="bg-white border border-gray-100 rounded-lg p-2.5" data-testid={`task-${task.id}`}>
      <div className="flex items-start gap-2">
        <span className="text-sm mt-0.5">{statusIcon}</span>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium text-gray-700 truncate leading-snug">
            #{task.id} {task.title}
          </p>
          <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[10px] text-gray-400">
            <span className="font-mono">{task.agent}</span>
            {task.github_issue && (
              <span className="font-mono text-blue-600">{task.github_issue}</span>
            )}
            {waitingDeps.length > 0 && waitingDeps.map((depId) => (
              <span key={depId} className="inline-flex items-center gap-0.5 bg-amber-50 text-amber-700 border border-amber-200 rounded px-1 py-0.5">
                ⏳ 等 #{depId} 完成
              </span>
            ))}
            {task.status === 'running' && doneDeps.length > 0 && doneDeps.map((depId) => (
              <span key={depId} className="inline-flex items-center gap-0.5 bg-green-50 text-green-700 border border-green-200 rounded px-1 py-0.5">
                依赖 #{depId} ✓
              </span>
            ))}
            {task.status === 'running' && task.started_at && (
              <span className="font-mono">开始于 {new Date(task.started_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
            )}
          </div>

          {failed && (
            <div className="mt-1.5 space-y-1">
              <p className="text-[10px] text-red-600 break-words leading-snug">
                {task.retry_count > 0 ? `重试 ${task.retry_count} 次` : '执行失败'}
                {task.last_error ? `: ${task.last_error}` : ''}
              </p>
              <div className="flex flex-wrap gap-1.5">
                {reassignFor === task.id ? (
                  <>
                    <select
                      value={reassignTarget}
                      onChange={(e) => onReassignTargetChange(e.target.value)}
                      className="text-[10px] px-1.5 py-1 border border-gray-200 rounded-lg outline-none focus:border-blue-400 bg-white text-gray-600"
                      aria-label="选择转派 agent"
                    >
                      {AGENT_NAMES.map((name) => <option key={name} value={name}>{name}</option>)}
                    </select>
                    <button
                      onClick={() => onAction(task, 'reassign', reassignTarget)}
                      disabled={busy === task.id}
                      className="px-2 py-1 text-[10px] font-medium text-white bg-blue-600 rounded hover:bg-blue-500 disabled:opacity-50"
                    >
                      确认转派
                    </button>
                    <button
                      onClick={onCancelReassign}
                      className="px-2 py-1 text-[10px] font-medium text-gray-600 bg-white border border-gray-200 rounded hover:bg-gray-100"
                    >
                      取消
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      onClick={() => onAction(task, 'retry')}
                      disabled={busy === task.id}
                      className="px-2 py-1 text-[10px] font-medium text-white bg-blue-600 rounded hover:bg-blue-500 disabled:opacity-50"
                    >
                      重试
                    </button>
                    <button
                      onClick={() => onStartReassign(task)}
                      disabled={busy === task.id}
                      className="px-2 py-1 text-[10px] font-medium text-gray-700 bg-gray-100 border border-gray-200 rounded hover:bg-gray-200 disabled:opacity-50"
                    >
                      转派
                    </button>
                    <button
                      onClick={() => onAction(task, 'abandon')}
                      disabled={busy === task.id}
                      className="px-2 py-1 text-[10px] font-medium text-red-600 bg-red-50 border border-red-200 rounded hover:bg-red-100 disabled:opacity-50"
                    >
                      放弃
                    </button>
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default function TasksBoard({ tasks = [], sessionId = null, onUpdateTask }) {
  const [agentFilter, setAgentFilter] = useState('')
  const [busyId, setBusyId] = useState(null)
  const [error, setError] = useState(null)
  const [reassignFor, setReassignFor] = useState(null)
  const [reassignTarget, setReassignTarget] = useState('coco咪')
  const [doneExpanded, setDoneExpanded] = useState(false)
  const [abandonedExpanded, setAbandonedExpanded] = useState(false)

  const byId = useMemo(() => Object.fromEntries(tasks.map((t) => [t.id, t])), [tasks])
  const filtered = useMemo(() => tasks.filter((t) => (
    (!agentFilter || t.agent === agentFilter) &&
    (sessionId == null || t.teamchat_session_id === sessionId)
  )), [tasks, agentFilter, sessionId])

  const groups = useMemo(() => groupTasks(filtered, byId), [filtered, byId])

  const startReassign = (task) => {
    setReassignTarget(task.agent === 'coco咪' ? 'soso咪' : 'coco咪')
    setReassignFor(task.id)
  }

  const handleAction = async (task, action, targetAgent = 'cici咪') => {
    if (!onUpdateTask) return
    setBusyId(task.id)
    setError(null)
    const body = action === 'retry'
      ? { status: 'pending', retry_count: 0, last_error: '' }
      : action === 'reassign'
        ? { status: 'pending', agent: targetAgent, retry_count: 0, last_error: '' }
        : { status: 'abandoned' }
    try {
      await onUpdateTask(task.id, body)
    } catch (err) {
      setError(err.message || '更新任务失败')
    } finally {
      setBusyId(null)
      setReassignFor(null)
    }
  }

  return (
    <div className="p-3 space-y-3 bg-white" data-testid="tasks-board">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">📋 Tasks</h3>
        <select
          value={agentFilter}
          onChange={(e) => setAgentFilter(e.target.value)}
          className="text-[10px] px-2 py-1 border border-gray-200 rounded-lg outline-none focus:border-blue-400 bg-white text-gray-600"
          aria-label="按 agent 筛选"
        >
          <option value="">全部 agent</option>
          {AGENT_NAMES.map((name) => <option key={name} value={name}>{name}</option>)}
        </select>
      </div>

      {error && <div className="px-2.5 py-2 text-[10px] text-red-600 bg-red-50 border border-red-100 rounded-lg">{error}</div>}

      {filtered.length === 0 ? (
        <p className="text-xs text-gray-400 text-center py-6">暂无任务</p>
      ) : (
        GROUPS.map((group) => {
          const items = groups[group.key] || []
          if (items.length === 0) return null
          // Done 默认显示 5 个（用户要求），可展开全部；已放弃默认折叠
          const collapsed = group.key === 'done'
            ? !doneExpanded && items.length > DONE_SHOW_LIMIT
            : group.key === 'abandoned' ? !abandonedExpanded : false
          const shown = group.key === 'done' && !doneExpanded
            ? items.slice(0, DONE_SHOW_LIMIT)
            : items
          return (
            <div key={group.key} data-testid={`tasks-group-${group.key}`}>
              <div className="flex items-center gap-1.5 px-0.5 pb-1">
                <span>{group.icon}</span>
                <span className={`text-[10px] font-semibold uppercase tracking-wider ${group.color}`}>{group.label}</span>
                <span className="ml-auto text-[10px] text-gray-400 font-mono">{items.length}</span>
              </div>
              <div className="space-y-1.5">
                {shown.map((task) => (
                  <TaskCard
                    key={task.id}
                    task={task}
                    byId={byId}
                    busy={busyId}
                    onAction={handleAction}
                    reassignFor={reassignFor}
                    reassignTarget={reassignTarget}
                    onStartReassign={startReassign}
                    onReassignTargetChange={setReassignTarget}
                    onCancelReassign={() => setReassignFor(null)}
                  />
                ))}
              </div>
              {group.key === 'done' && items.length > DONE_SHOW_LIMIT && (
                <button
                  onClick={() => setDoneExpanded(!doneExpanded)}
                  className="text-[10px] text-blue-500 hover:text-blue-700 mt-1 px-0.5"
                >
                  {doneExpanded ? '▲ 折叠' : `▼ 展开全部 (${items.length})`}
                </button>
              )}
              {group.key === 'abandoned' && items.length > 0 && (
                <button
                  onClick={() => setAbandonedExpanded(!abandonedExpanded)}
                  className="text-[10px] text-gray-400 hover:text-gray-600 mt-1 px-0.5"
                >
                  {abandonedExpanded ? '▲ 折叠' : `▼ 展开 (${items.length})`}
                </button>
              )}
            </div>
          )
        })
      )}
    </div>
  )
}
