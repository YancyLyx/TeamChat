import { useState, useEffect, useRef, useCallback } from 'react'
import ChatMessage from './ChatMessage.jsx'
import ChatInput from './ChatInput.jsx'

const API_BASE = '/api'
const AGENT_EMOJI = { 'cici\u54aa': '\U0001f3d7\ufe0f', 'coco\u54aa': '\u26a1', 'soso\u54aa': '\U0001f50d' }

function ft(iso) { try { return new Date(iso).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) } catch { return iso } }

export default function ChatRoom({ wsMessages, connectionStatus }) {
  const [chatMessages, setChatMessages] = useState([])
  const [loading, setLoading] = useState(true)
  const [resolvedApprovals, setResolvedApprovals] = useState(() => new Set())
  const scrollRef = useRef(null)
  const lastWcRef = useRef(0)
  const penRef = useRef(false)
  const seenIds = useRef(new Set())

  useEffect(() => { if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight }, [chatMessages])

  const handleApprovalDecision = useCallback((messageId, decision) => {
    setResolvedApprovals((prev) => new Set(prev).add(messageId))
    setChatMessages((prev) => [
      ...prev,
      {
        id: `approval-result-${messageId}`,
        kind: 'system',
        agent: 'system',
        content: decision === 'allow' ? '已允许工具执行' : '已拒绝工具执行',
        timestamp: new Date().toISOString(),
      },
    ])
  }, [])

  const fetchInit = useCallback(async () => {
    try {
      setLoading(true)
      const [agentsRes, sessionsRes] = await Promise.all([
        fetch(`${API_BASE}/agents`),
        fetch(`${API_BASE}/sessions?limit=30&tag=prod`),
      ])
      if (!agentsRes.ok || !sessionsRes.ok) throw new Error('API request failed')
      const sessionsData = await sessionsRes.json()
      const initial = []
      initial.push({ id: 'welcome', kind: 'system', agent: 'system', content: '\u6b22\u8fce\u6765\u5230 TeamChat\uff01\u4f7f\u7528 @cici\u54aa @coco\u54aa @soso\u54aa \u5411 agent \u53d1\u9001\u6d88\u606f\u3002', timestamp: new Date().toISOString() })
      for (const s of sessionsData) {
        if (s.id) { seenIds.current.add(`session-${s.id}-prompt`); seenIds.current.add(`session-${s.id}-result`) }
        initial.push({ id: `session-${s.id}-prompt`, kind: 'task_event', agent: s.agent_name, content: s.prompt.slice(0, 80), type: 'task_started', timestamp: s.started_at })
        initial.push({ id: `session-${s.id}-result`, kind: 'agent', agent: s.agent_name, content: s.output.slice(0, 300), timestamp: s.finished_at })
      }
      for (const m of initial) { if (m.id) seenIds.current.add(m.id) }
      setChatMessages(initial)
    } catch (err) { setChatMessages([{ id: 'error', kind: 'system', agent: 'system', content: `\u52a0\u8f7d\u5386\u53f2\u5931\u8d25: ${err.message}`, timestamp: new Date().toISOString() }]) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { fetchInit() }, [fetchInit])

  const handleSend = useCallback(async (content) => {
    try {
      const res = await fetch(`${API_BASE}/chat`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ content }) })
      if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || `HTTP ${res.status}`) }
      return await res.json()
    } catch (err) {
      setChatMessages(p => [...p, { id: `se-${Date.now()}`, kind: 'system', agent: 'system', content: `\u53d1\u9001\u5931\u8d25: ${err.message}`, timestamp: new Date().toISOString() }])
      throw err
    }
  }, [])

  useEffect(() => {
    if (wsMessages.length <= lastWcRef.current || penRef.current) return
    const nms = wsMessages.slice(lastWcRef.current)
    lastWcRef.current = wsMessages.length
    penRef.current = true
    const adds = []
    for (const m of nms) {
      if (m.type === 'chat_message') {
        const d = m.data || {}; const mid = d.id || `c-${Date.now()}`
        if (mid && seenIds.current.has(mid)) continue; if (mid) seenIds.current.add(mid)
        const km = { human: 'human', agent_reply: 'agent', agent_message: 'agent', system: 'system', approval: 'approval', thinking: 'thinking' }
        adds.push({ id: mid, kind: km[d.kind] || (d.agent === 'human' ? 'human' : 'agent'), agent: d.agent || 'system', content: d.content || '', timestamp: d.timestamp || new Date().toISOString(), thinking_sections: d.thinking_sections, tool_name: d.tool_name, tool_input: d.tool_input })
      } else if (m.type === 'connected') {
        adds.push({ id: `cc-${Date.now()}`, kind: 'system', agent: 'system', content: '\u5df2\u8fde\u63a5 TeamChat \u5b9e\u65f6\u901a\u9053', timestamp: new Date().toISOString() })
      } else if (m.type === 'task_started') {
        const d = m.data || {}; const mid = d.session_id ? `task-${d.session_id}-s` : `ts-${Date.now()}`
        if (seenIds.current.has(mid)) continue; seenIds.current.add(mid)
        adds.push({ id: mid, kind: 'task_event', agent: d.agent || 'system', content: d.prompt || '\u5f00\u59cb\u6267\u884c\u4efb\u52a1', type: 'task_started', timestamp: d.timestamp || new Date().toISOString() })
      } else if (m.type === 'task_complete') {
        const d = m.data || {}; const mid = d.session_id ? `task-${d.session_id}-c` : `tc-${Date.now()}`
        if (seenIds.current.has(mid)) continue; seenIds.current.add(mid)
        adds.push({ id: mid, kind: 'task_event', agent: d.agent || 'system', content: `${d.success ? '\u5b8c\u6210' : '\u5931\u8d25'}\u4efb\u52a1${d.duration_ms ? ' (' + (d.duration_ms / 1000).toFixed(1) + 's)' : ''}`, type: 'task_complete', timestamp: d.timestamp || new Date().toISOString() })
      } else if (m.type === 'system_message') {
        const d = m.data || {}
        adds.push({ id: `sm-${Date.now()}`, kind: 'system', agent: 'system', content: d.content || '', timestamp: d.timestamp || new Date().toISOString() })
      } else if (m.type === 'message') {
        const d = m.data || {}
        adds.push({ id: d.id || `bm-${Date.now()}`, kind: 'system', agent: d.from || 'system', content: `${d.from || '?'} \u2192 ${d.to || 'all'}: ${d.content || ''}`, timestamp: d.timestamp || new Date().toISOString() })
      }
    }
    if (adds.length > 0) setChatMessages(p => [...p, ...adds])
    penRef.current = false
    if (seenIds.current.size > 500) seenIds.current = new Set([...seenIds.current].slice(-200))
  }, [wsMessages])

  return (
    <div className="flex flex-col h-full bg-white">
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4" style={{ scrollBehavior: 'smooth' }}>
        {loading && (
          <div className="space-y-3 py-8">
            {[1, 2, 3].map((i) => (
              <div key={i} className="flex gap-3 animate-pulse">
                <div className="w-8 h-8 rounded-full bg-gray-200" />
                <div className="flex-1"><div className="h-3 bg-gray-200 rounded w-24 mb-2" /><div className="h-12 bg-gray-100 rounded-xl" /></div>
              </div>
            ))}
          </div>
        )}
        {!loading && chatMessages.length === 0 && <div className="flex items-center justify-center h-full text-gray-400 text-sm">\u6682\u65e0\u6d88\u606f</div>}
        {chatMessages.map((msg, i) => {
          if (msg.kind === 'approval' && resolvedApprovals.has(msg.id)) return null
          const enriched = msg.kind === 'approval'
            ? {
                ...msg,
                onApprove: () => handleApprovalDecision(msg.id, 'allow'),
                onDeny: () => handleApprovalDecision(msg.id, 'deny'),
              }
            : msg
          return <ChatMessage key={msg.id || i} message={enriched} />
        })}
        <div className="h-2" />
      </div>
      <div className="px-4 py-1 border-t border-gray-100 flex items-center gap-2 bg-white">
        <span className={`inline-block w-1.5 h-1.5 rounded-full ${connectionStatus === 'connected' ? 'bg-green-500' : connectionStatus === 'connecting' ? 'bg-yellow-500 animate-pulse' : 'bg-red-500'}`} />
        <span className={`text-[10px] font-mono ${connectionStatus === 'connected' ? 'text-green-600' : connectionStatus === 'connecting' ? 'text-yellow-600' : 'text-red-600'}`}>
          {connectionStatus === 'connected' ? 'WebSocket \u5df2\u8fde\u63a5' : connectionStatus === 'connecting' ? '\u8fde\u63a5\u4e2d...' : '\u5df2\u65ad\u5f00'}
        </span>
      </div>
      <ChatInput onSend={handleSend} disabled={connectionStatus !== 'connected'} />
    </div>
  )
}
