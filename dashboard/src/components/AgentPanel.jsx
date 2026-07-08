import { useState } from 'react'

const AGENT_ICONS = {
  'cici咪': '🏗️',
  'coco咪': '⚡',
  'soso咪': '🔍',
}

export default function AgentPanel({ agents, sessionsByAgent }) {
  const [expandedAgent, setExpandedAgent] = useState(null)

  if (!agents || agents.length === 0) {
    return (
      <div className="p-3 space-y-2">
        {[1, 2, 3].map((i) => (
          <div key={i} className="bg-gray-800/30 rounded-lg p-3 animate-pulse">
            <div className="h-3 bg-gray-700/30 rounded w-16 mb-2" />
            <div className="h-3 bg-gray-700/30 rounded w-24" />
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="p-3 space-y-2">
      <h3 className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider px-1 mb-3">Agents</h3>

      {agents.map((agent) => {
        const isExpanded = expandedAgent === agent.name
        const statusClass = agent.is_busy ? 'busy' : 'idle'
        const statusLabel = agent.is_busy ? 'busy' : 'idle'
        const successRate = (agent.success_rate * 100).toFixed(0)
        const icon = AGENT_ICONS[agent.name] || '🤖'
        const sessions = sessionsByAgent[agent.name] || []

        return (
          <div key={agent.name}>
            <button
              onClick={() => setExpandedAgent(isExpanded ? null : agent.name)}
              className={`w-full text-left bg-gray-800/50 border rounded-lg p-3 transition-colors hover:bg-gray-800/80 ${
                isExpanded ? 'border-blue-500/40' : 'border-gray-700/30'
              }`}
            >
              <div className="flex items-center gap-2.5">
                <span className="text-lg">{icon}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="text-sm font-medium text-gray-200 truncate">{agent.name}</span>
                    <span className={`inline-block w-1.5 h-1.5 rounded-full ${
                      agent.is_busy ? 'bg-yellow-400 animate-pulse' : 'bg-gray-500'
                    }`} title={statusLabel} />
                  </div>
                  <p className="text-[10px] text-gray-500 truncate">{agent.role}</p>
                </div>
                <div className="text-right">
                  <p className="text-xs font-mono text-gray-400">{agent.total_tasks}</p>
                  <p className={`text-[10px] font-mono ${agent.success_rate >= 0.8 ? 'text-green-500' : 'text-yellow-500'}`}>
                    {successRate}%
                  </p>
                </div>
              </div>
            </button>

            {/* Expanded: recent sessions */}
            {isExpanded && sessions.length > 0 && (
              <div className="mt-1 ml-3 pl-3 border-l-2 border-blue-500/20 space-y-1 max-h-40 overflow-y-auto">
                {sessions.slice(0, 5).map((s) => (
                  <div key={s.id} className="bg-gray-800/30 rounded p-2 text-[10px]">
                    <div className="flex justify-between text-gray-500">
                      <span className="font-mono">{s.task_type}</span>
                      <span className={s.exit_code === 0 ? 'text-green-500' : 'text-red-400'}>
                        {s.duration_ms}ms
                      </span>
                    </div>
                    <p className="text-gray-400 truncate mt-0.5">{s.prompt.slice(0, 60)}</p>
                  </div>
                ))}
              </div>
            )}

            {isExpanded && sessions.length === 0 && (
              <div className="mt-1 ml-3 pl-3 border-l-2 border-gray-700/20 text-[10px] text-gray-600">
                No sessions yet
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
