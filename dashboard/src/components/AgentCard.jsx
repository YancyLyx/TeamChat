import { useState } from 'react'
import { AGENT_INFO, UI_EMOJI } from '../constants/agents.js'

export default function AgentCard({ agent, sessions = [], compact }) {
  const [expanded, setExpanded] = useState(false)
  const info = AGENT_INFO[agent.name] || { emoji: UI_EMOJI.fallback, border: 'border-gray-300', nameColor: 'text-gray-700', role: agent.role || '' }
  const statusClass = agent.is_busy ? 'busy' : 'idle'
  const rate = (agent.success_rate * 100).toFixed(0)

  if (compact) {
    return (
      <div className="flex items-center gap-2.5 px-3 py-2.5 cursor-pointer hover:bg-gray-50 rounded-lg transition-colors" onClick={() => setExpanded(!expanded)}>
        <span className="text-lg">{info.emoji}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5">
            <span className={`text-sm font-medium ${info.nameColor}`}>{agent.name}</span>
            <span className={`status-dot ${statusClass}`} />
          </div>
          <p className="text-xs text-gray-400">{agent.total_tasks} tasks · {rate}%</p>
        </div>
      </div>
    )
  }

  return (
    <div className={`bg-white border ${expanded ? info.border : 'border-gray-200'} rounded-xl p-3.5 shadow-sm cursor-pointer transition-all hover:shadow-md`} onClick={() => setExpanded(!expanded)}>
      <div className="flex items-center gap-3">
        <span className="text-xl">{info.emoji}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className={`font-semibold text-sm ${info.nameColor}`}>{agent.name}</h3>
            <span className={`status-dot ${statusClass}`} />
          </div>
          <p className="text-xs text-gray-400 mt-0.5">{info.role}</p>
        </div>
      </div>
      <div className="mt-3 flex items-center gap-3 text-xs">
        <span className="text-gray-500"><strong className="text-gray-700">{agent.total_tasks}</strong> tasks</span>
        <span className="text-gray-300">|</span>
        <span className={agent.success_rate >= 0.8 ? 'text-green-600' : 'text-yellow-600'}><strong>{rate}%</strong></span>
      </div>
      {agent.avg_duration_ms > 0 && <div className="mt-1 text-xs text-gray-400">avg {(agent.avg_duration_ms / 1000).toFixed(1)}s</div>}
      {expanded && sessions.length > 0 && (
        <div className="mt-3 pt-3 border-t border-gray-100 space-y-1.5 max-h-40 overflow-y-auto">
          <p className="text-[10px] text-gray-400 font-semibold uppercase">最近会话</p>
          {sessions.slice(0, 5).map((s) => (
            <div key={s.id} className="bg-gray-50 rounded-lg p-2 text-xs">
              <div className="flex justify-between text-gray-400">
                <span className="font-mono text-gray-300">{s.task_type}</span>
                <span className={s.exit_code === 0 ? 'text-green-500' : 'text-red-400'}>{s.duration_ms}ms</span>
              </div>
              <p className="text-gray-500 truncate mt-0.5">{s.prompt.slice(0, 60)}</p>
            </div>
          ))}
        </div>
      )}
      {expanded && sessions.length === 0 && <div className="mt-3 pt-3 border-t border-gray-100 text-xs text-gray-400">暂无会话记录</div>}
    </div>
  )
}
