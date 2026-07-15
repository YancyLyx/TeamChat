import { useState } from 'react'
import { AGENT_INFO, UI_EMOJI } from '../constants/agents.js'
import { formatTokens } from '../utils/metrics.js'

const AGENT_ROLE_CARDS = {
  'cici咪': {
    cli: 'claude --print',
    personality: '稳健 · 文档驱动 · 善于拆解任务',
    specialty: '系统架构 / ADR / 任务拆分',
  },
  'coco咪': {
    cli: 'codex exec',
    personality: '敏捷 · 全栈开发 · 快速迭代',
    specialty: 'React / FastAPI / 前端工程',
  },
  'soso咪': {
    cli: 'cursor-agent',
    personality: '细致 · QA 驱动 · 测试覆盖',
    specialty: 'E2E 测试 / CI/CD / Bug 定位',
  },
}

export default function AgentCard({ agent, sessions = [], compact }) {
  const [expanded, setExpanded] = useState(false)
  const info = AGENT_INFO[agent.name] || { emoji: UI_EMOJI.fallback, border: 'border-gray-300', nameColor: 'text-gray-700', role: agent.role || '' }
  const card = AGENT_ROLE_CARDS[agent.name]
  const statusClass = agent.is_busy ? 'busy' : 'idle'
  const rate = (agent.success_rate * 100).toFixed(0)
  const totalTasks = agent.total_tasks ?? agent.total_calls ?? 0

  if (compact) {
    return (
      <div className="flex items-center gap-2.5 px-3 py-2.5 cursor-pointer hover:bg-gray-50 rounded-lg transition-colors" onClick={() => setExpanded(!expanded)}>
        <span className="text-lg">{info.emoji}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5">
            <span className={`text-sm font-medium ${info.nameColor}`}>{agent.name}</span>
            <span className={`status-dot ${statusClass}`} />
          </div>
          <p className="text-xs text-gray-400">{totalTasks} tasks · {rate}%</p>
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
        <span className="text-gray-500"><strong className="text-gray-700">{totalTasks}</strong> tasks</span>
        <span className="text-gray-300">|</span>
        <span className={agent.success_rate >= 0.8 ? 'text-green-600' : 'text-yellow-600'}><strong>{rate}%</strong></span>
      </div>
      <div className="mt-1 text-xs text-gray-400">
        avg {((agent.avg_duration_ms || 0) / 1000).toFixed(1)}s · {formatTokens(agent.total_tokens)} tokens
      </div>

      {/* Expanded: role card with personality + recent sessions */}
      {expanded && (
        <div className="mt-3 pt-3 border-t border-gray-100 space-y-2">
          {/* Role info */}
          {card && (
            <div className="bg-gray-50 rounded-lg p-2.5 space-y-1.5 text-xs">
              <div className="flex items-center gap-2 text-gray-500">
                <span className="font-mono text-[10px] bg-gray-200 text-gray-600 px-1.5 py-0.5 rounded">CLI</span>
                <span className="font-mono text-gray-600">{card.cli}</span>
              </div>
              <div className="text-gray-500">
                <span className="font-medium text-gray-600">角色卡:</span> {card.personality}
              </div>
              <div className="text-gray-500">
                <span className="font-medium text-gray-600">专长:</span> {card.specialty}
              </div>
            </div>
          )}

          {/* Recent sessions */}
          {sessions.length > 0 && (
            <>
              <p className="text-[10px] text-gray-400 font-semibold uppercase">最近会话</p>
              <div className="space-y-1.5 max-h-32 overflow-y-auto">
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
            </>
          )}
          {sessions.length === 0 && (
            <div className="text-xs text-gray-400">暂无会话记录</div>
          )}
        </div>
      )}
    </div>
  )
}
