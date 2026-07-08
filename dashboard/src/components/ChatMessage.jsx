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

/**
 * Parse agent message content into segments for rendering.
 * Splits at THINKING: and TOOL_CALLS: line markers, wrapping
 * each section in a collapsible <details> element.
 */
function parseSections(text) {
  if (!text || typeof text !== 'string') return [{ type: 'text', content: text || '' }]

  const lines = text.split('\n')
  const segments = []
  let current = []
  let mode = 'text'
  let modeHeading = ''

  const flush = (nextMode) => {
    if (current.length > 0) {
      const joined = current.join('\n')
      if (mode === 'thinking' || mode === 'tool_calls') {
        segments.push({ type: mode, heading: modeHeading, content: joined })
      } else {
        segments.push({ type: 'text', content: joined })
      }
    }
    current = []
    mode = nextMode
  }

  for (const line of lines) {
    const trimmed = line.trim()
    // Match lines that start with THINKING: or TOOL_CALLS: (case-insensitive)
    const thinkingMatch = trimmed.match(/^THINKING[\s]*:/i)
    const toolMatch = trimmed.match(/^TOOL_CALLS[\s]*:/i)

    if (thinkingMatch) {
      flush('thinking')
      modeHeading = 'THINKING'
      const rest = line.slice(line.indexOf(':') + 1).trim()
      if (rest) current.push(rest)
    } else if (toolMatch) {
      flush('tool_calls')
      modeHeading = 'TOOL_CALLS'
      const rest = line.slice(line.indexOf(':') + 1).trim()
      if (rest) current.push(rest)
    } else {
      current.push(line)
    }
  }

  // Flush remaining content
  flush('text')

  return segments
}

function RenderAgentContent({ text }) {
  const segments = parseSections(text)
  // Fast path: no collapsible sections
  if (segments.length === 1 && segments[0].type === 'text') {
    return <span className="whitespace-pre-wrap">{highlightMentions(segments[0].content)}</span>
  }

  return (
    <div className="space-y-2">
      {segments.map((seg, i) => {
        if (seg.type === 'text') {
          return <div key={i} className="whitespace-pre-wrap">{highlightMentions(seg.content)}</div>
        }
        const isThinking = seg.type === 'thinking'
        return (
          <details key={i} className="bg-gray-900/40 border border-gray-700/30 rounded-lg overflow-hidden">
            <summary className="flex items-center gap-2 px-3 py-2 text-xs font-mono cursor-pointer hover:bg-gray-800/40 transition-colors select-none">
              <span className="text-yellow-400">{isThinking ? '💭' : '🔧'}</span>
              <span className="text-gray-300 font-semibold">{seg.heading}</span>
              <span className="ml-auto text-gray-600 text-[10px]">展开/折叠</span>
            </summary>
            <div className="px-3 pb-2 pt-1 text-xs text-gray-400 font-mono leading-relaxed whitespace-pre-wrap border-t border-gray-700/20">
              {seg.content}
            </div>
          </details>
        )
      })}
    </div>
  )
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
          <div className={`${colors.bg} border ${colors.border} rounded-2xl rounded-tl-sm px-4 py-2.5 text-sm text-gray-200 leading-relaxed break-words`}>
            <RenderAgentContent text={content} />
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
