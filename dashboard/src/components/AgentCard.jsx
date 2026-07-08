import { useState } from 'react'

const AGENT_ICONS = {
  'cici咪': '🏗️',
  'coco咪': '⚡',
  'soso咪': '🔍',
}

export default function AgentCard({ agent, sessions = [] }) {
  const [expanded, setExpanded] = useState(false)

  const statusClass = agent.is_busy ? 'busy' : 'idle'
  const statusLabel = agent.is_busy ? '忙碌' : '空闲'
  const successRate = (agent.success_rate * 100).toFixed(0)
  const icon = AGENT_ICONS[agent.name] || '🤖'

  return (
    <div
      data-testid="agent-card"
      className={`bg-gray-800/80 border rounded-lg p-4 cursor-pointer transition-all
        ${expanded ? 'border-blue-500/50 col-span-3' : 'border-gray-700/50 hover:border-gray-600'}`}
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex items-center gap-3">
        <span className="text-xl">{icon}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-gray-100 truncate">{agent.name}</h3>
            <span className={`status-dot ${statusClass}`} title={statusLabel} />
          </div>
          <p className="text-xs text-gray-400 truncate">{agent.role}</p>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
        <div className="bg-gray-900/60 rounded p-2">
          <span className="text-gray-500">任务</span>
          <p className="text-gray-200 font-mono font-bold">{agent.total_tasks}</p>
        </div>
        <div className="bg-gray-900/60 rounded p-2">
          <span className="text-gray-500">成功率</span>
          <p className={`font-mono font-bold ${agent.success_rate >= 0.8 ? 'text-green-400' : 'text-yellow-400'}`}>
            {successRate}%
          </p>
        </div>
      </div>

      {agent.avg_duration_ms > 0 && (
        <div className="mt-2 text-xs text-gray-500">
          平均耗时: <span className="font-mono text-gray-400">{(agent.avg_duration_ms / 1000).toFixed(1)}s</span>
        </div>
      )}

      {/* Expanded: recent sessions */}
      {expanded && sessions.length > 0 && (
        <div className="mt-3 pt-3 border-t border-gray-700/50 space-y-2 max-h-48 overflow-y-auto">
          <p className="text-xs text-gray-500 font-semibold uppercase tracking-wide">最近会话</p>
          {sessions.map((s) => (
            <div key={s.id} className="bg-gray-900/40 rounded p-2 text-xs">
              <div className="flex justify-between text-gray-400">
                <span className="font-mono text-gray-500">{s.task_type}</span>
                <span className={s.exit_code === 0 ? 'text-green-500' : 'text-red-400'}>
                  {s.duration_ms}ms
                </span>
              </div>
              <p className="text-gray-300 truncate mt-1">{s.prompt.slice(0, 80)}</p>
            </div>
          ))}
        </div>
      )}

      {expanded && sessions.length === 0 && (
        <div className="mt-3 pt-3 border-t border-gray-700/50 text-xs text-gray-500">
          暂无会话记录
        </div>
      )}
    </div>
  )
}
