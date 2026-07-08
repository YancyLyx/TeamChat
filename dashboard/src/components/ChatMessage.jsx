const AGENT_COLORS = {
  'cici咪': { border: 'border-blue-500/30', bg: 'bg-blue-900/10', name: 'text-blue-300', badge: 'bg-blue-900/50 text-blue-200' },
  'coco咪': { border: 'border-emerald-500/30', bg: 'bg-emerald-900/10', name: 'text-emerald-300', badge: 'bg-emerald-900/50 text-emerald-200' },
  'soso咪': { border: 'border-purple-500/30', bg: 'bg-purple-900/10', name: 'text-purple-300', badge: 'bg-purple-900/50 text-purple-200' },
}

const AGENT_EMOJI = {
  'cici咪': '🏗️',
  'coco咪': '⚡',
  'soso咪': '🔍',
}

function formatTime(iso) {
  try {
    const d = new Date(iso)
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch {
    return iso
  }
}

function highlightMentions(text) {
  if (!text) return null
  const parts = text.split(/(@(?:cici咪|coco咪|soso咪))/g)
  return parts.map((part, i) => {
    if (part.startsWith('@')) {
      const agent = part.slice(1)
      const colors = AGENT_COLORS[agent]
      return (
        <span key={i} className={`inline-block px-1.5 py-0.5 rounded text-xs font-medium ${colors ? colors.badge : 'bg-gray-700/50 text-gray-200'}`}>
          {part}
        </span>
      )
    }
    return part
  })
}

export default function ChatMessage({ message }) {
  const { kind, agent, content, timestamp } = message

  if (kind === 'human') {
    return (
      <div className="flex justify-end mb-3">
        <div className="max-w-[75%] min-w-[120px]">
          <div className="flex items-center justify-end gap-2 mb-1">
            <span className="text-[10px] text-gray-500 font-mono">{formatTime(timestamp)}</span>
            <span className="text-xs text-gray-300 font-medium">你</span>
            <span className="text-sm">🧑</span>
          </div>
          <div className="bg-indigo-800/40 border border-indigo-600/30 rounded-2xl rounded-tr-sm px-4 py-2.5 text-sm text-gray-100 leading-relaxed whitespace-pre-wrap break-words">
            {highlightMentions(content)}
          </div>
        </div>
      </div>
    )
  }

  if (kind === 'agent_reply' || kind === 'agent_message' || (kind === undefined && agent)) {
    const colors = AGENT_COLORS[agent] || { border: 'border-gray-600/30', bg: 'bg-gray-800/40', name: 'text-gray-300', badge: 'bg-gray-700/50 text-gray-200' }
    const emoji = AGENT_EMOJI[agent] || '🤖'

    return (
      <div className="flex justify-start mb-3">
        <div className="max-w-[75%] min-w-[120px]">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-sm">{emoji}</span>
            <span className={`text-xs font-medium ${colors.name}`}>{agent}</span>
            <span className="text-[10px] text-gray-500 font-mono">{formatTime(timestamp)}</span>
          </div>
          <div className={`${colors.bg} border ${colors.border} rounded-2xl rounded-tl-sm px-4 py-2.5 text-sm text-gray-200 leading-relaxed whitespace-pre-wrap break-words`}>
            {content}
          </div>
        </div>
      </div>
    )
  }

  if (kind === 'system') {
    return (
      <div className="flex justify-center mb-3">
        <div className="bg-gray-800/30 border border-gray-700/20 rounded-lg px-4 py-1.5 text-xs text-gray-500 italic max-w-[80%] text-center">
          {content}
        </div>
      </div>
    )
  }

  if (kind === 'task_event') {
    const isStart = message.type === 'task_started'
    return (
      <div className="flex justify-start mb-2 pl-2">
        <div className="flex items-center gap-2 text-xs text-gray-500 font-mono">
          <span>{isStart ? '🚀' : '✅'}</span>
          <span>{agent}</span>
          <span className="text-gray-600">|</span>
          <span className="truncate max-w-[300px]">{content}</span>
        </div>
      </div>
    )
  }

  return (
    <div className="flex justify-start mb-3">
      <div className="bg-gray-800/40 border border-gray-700/30 rounded-lg px-4 py-2 text-sm text-gray-400">
        {content || JSON.stringify(message)}
      </div>
    </div>
  )
}
