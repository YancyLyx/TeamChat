import { useState, useEffect, useRef, useCallback } from 'react'
import ChatMessage from './ChatMessage.jsx'
import ChatInput from './ChatInput.jsx'
import { WELCOME_MESSAGE, UI_EMOJI } from '../constants/agents.js'

const API_BASE = '/api'

export default function ChatRoom({ wsMessages, connectionStatus, sessionId }) {
  const [chatMessages, setChatMessages] = useState([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [resolvedApprovals, setResolvedApprovals] = useState(() => new Set())
  const scrollRef = useRef(null)
  const lastWcRef = useRef(0)
  const penRef = useRef(false)
  const seenIds = useRef(new Set())
  const dedupTimestamps = useRef({})
  const recentKeys = useRef(new Map())

  useEffect(() => { if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight }, [chatMessages])

  const handleApprovalDecision = useCallback(async (messageId, decision, requestId) => {
    if (requestId) {
      try {
        const res = await fetch(`${API_BASE}/approval`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ request_id: requestId, decision }),
        })
        if (!res.ok) {
          const err = await res.json().catch(() => ({}))
          setChatMessages((prev) => [...prev, {
            id: `approval-error-${messageId}`,
            kind: 'system',
            agent: 'system',
            content: err.detail || `审批请求失败 (${res.status})`,
            timestamp: new Date().toISOString(),
          }])
          return
        }
      } catch {
        setChatMessages((prev) => [...prev, {
          id: `approval-error-${messageId}`,
          kind: 'system',
          agent: 'system',
          content: '审批请求失败：无法连接 API',
          timestamp: new Date().toISOString(),
        }])
        return
      }
    }
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
        fetch(`${API_BASE}/sessions?limit=30&tag=prod${sessionId != null ? `&teamchat_session_id=${sessionId}` : ''}`),
      ])
      if (!agentsRes.ok || !sessionsRes.ok) throw new Error('API request failed')
      const sessionsData = await sessionsRes.json()
      const ordered = [...sessionsData].reverse()
      const initial = []
      initial.push({ id: 'welcome', kind: 'system', agent: 'system', content: WELCOME_MESSAGE, timestamp: new Date().toISOString() })
      for (const s of ordered) {
        if (s.agent_name === 'human') {
          const hid = `session-${s.id}-human`
          seenIds.current.add(hid)
          initial.push({ id: hid, kind: 'human', agent: 'human', content: s.prompt, timestamp: s.started_at })
          continue
        }
        if (s.id) { seenIds.current.add(`session-${s.id}-prompt`); seenIds.current.add(`session-${s.id}-result`) }
        initial.push({ id: `session-${s.id}-prompt`, kind: 'task_event', agent: s.agent_name, content: s.prompt.slice(0, 80), type: 'task_started', timestamp: s.started_at })
        initial.push({ id: `session-${s.id}-result`, kind: 'agent', agent: s.agent_name, content: s.output.slice(0, 300), timestamp: s.finished_at })
      }
      for (const m of initial) { if (m.id) seenIds.current.add(m.id) }
      setChatMessages(initial)
    } catch (err) { setChatMessages([{ id: 'error', kind: 'system', agent: 'system', content: `加载历史失败: ${err.message}`, timestamp: new Date().toISOString() }]) }
    finally { setLoading(false) }
  }, [sessionId])

  useEffect(() => { fetchInit() }, [fetchInit])

  const handleRefresh = useCallback(async () => {
    setRefreshing(true)
    try {
      await fetchInit()
    } finally {
      setRefreshing(false)
    }
  }, [fetchInit])

  const handleSend = useCallback(async (content) => {
    try {
      const body = { content }
      if (sessionId != null) body.teamchat_session_id = sessionId
      const res = await fetch(`${API_BASE}/chat`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || `HTTP ${res.status}`) }
      return await res.json()
    } catch (err) {
      setChatMessages(p => [...p, { id: `se-${Date.now()}`, kind: 'system', agent: 'system', content: `发送失败: ${err.message}`, timestamp: new Date().toISOString() }])
      throw err
    }
  }, [sessionId])

  useEffect(() => {
    if (wsMessages.length <= lastWcRef.current || penRef.current) return
    const nms = wsMessages.slice(lastWcRef.current)
    lastWcRef.current = wsMessages.length
    penRef.current = true
    const adds = []
    for (const m of nms) {
      // Universal 3s dedup: skip if the same raw event arrived recently
      const raw = m.data || {}
      const recentKey = `${m.type}|${raw.agent || raw.from || ''}|${raw.content || raw.prompt || raw.message || JSON.stringify(raw)}`.slice(0, 200)
      const now = Date.now()
      if (recentKeys.current.has(recentKey)) {
        if (now - recentKeys.current.get(recentKey) < 3000) continue
      }
      recentKeys.current.set(recentKey, now)
      if (recentKeys.current.size > 200) {
        const oldestKeys = [...recentKeys.current.entries()].sort((a, b) => a[1] - b[1]).slice(-100).map(([k]) => k)
        recentKeys.current = new Map(oldestKeys.map((k) => [k, recentKeys.current.get(k)]))
      }

      if (m.type === 'chat_message') {
        const d = m.data || {}
        const mid = d.id || `c-${d.agent || 'unknown'}-${d.timestamp || ''}-${adds.length}-${Date.now()}`
        if (mid && seenIds.current.has(mid)) continue; if (mid) seenIds.current.add(mid)
        // Legacy dedup — kept for backward compatibility
        const dedupKey = `${d.kind}|${d.agent}|${d.content}`
        if (dedupKey) {
          const lastSeen = dedupTimestamps.current[dedupKey] || 0
          if (Date.now() - lastSeen < 3000) continue
          dedupTimestamps.current[dedupKey] = Date.now()
        }
        const km = { human: 'human', agent_reply: 'agent', agent_message: 'agent', system: 'system', approval: 'approval', thinking: 'thinking' }
        adds.push({ id: mid, kind: km[d.kind] || (d.agent === 'human' ? 'human' : 'agent'), agent: d.agent || 'system', content: d.content || '', timestamp: d.timestamp || new Date().toISOString(), thinking_sections: d.thinking_sections, tool_name: d.tool_name, tool_input: d.tool_input })
      } else if (m.type === 'connected') {
        if (seenIds.current.has('ws-connected')) continue
        seenIds.current.add('ws-connected')
        adds.push({ id: `cc-${Date.now()}`, kind: 'system', agent: 'system', content: '已连接 TeamChat 实时通道', timestamp: new Date().toISOString() })
      } else if (m.type === 'task_started') {
        const d = m.data || {}; const mid = d.session_id ? `task-${d.session_id}-s` : `ts-${Date.now()}`
        if (seenIds.current.has(mid)) continue; seenIds.current.add(mid)
        adds.push({ id: mid, kind: 'task_event', agent: d.agent || 'system', content: d.prompt || '开始执行任务', type: 'task_started', timestamp: d.timestamp || new Date().toISOString() })
      } else if (m.type === 'task_complete') {
        const d = m.data || {}; const mid = d.session_id ? `task-${d.session_id}-c` : `tc-${Date.now()}`
        if (seenIds.current.has(mid)) continue; seenIds.current.add(mid)
        adds.push({ id: mid, kind: 'task_event', agent: d.agent || 'system', content: `${d.success ? '完成' : '失败'}任务${d.duration_ms ? ' (' + (d.duration_ms / 1000).toFixed(1) + 's)' : ''}`, type: 'task_complete', timestamp: d.timestamp || new Date().toISOString() })
      } else if (m.type === 'system_message') {
        const d = m.data || {}
        adds.push({ id: `sm-${Date.now()}`, kind: 'system', agent: 'system', content: d.content || '', timestamp: d.timestamp || new Date().toISOString() })
      } else if (m.type === 'message') {
        const d = m.data || {}
        adds.push({ id: d.id || `bm-${Date.now()}`, kind: 'system', agent: d.from || 'system', content: `${d.from || '?'} → ${d.to || 'all'}: ${d.content || ''}`, timestamp: d.timestamp || new Date().toISOString() })
      }
    }
    if (adds.length > 0) setChatMessages(p => [...p, ...adds])
    penRef.current = false
    if (seenIds.current.size > 500) seenIds.current = new Set([...seenIds.current].slice(-200))
  }, [wsMessages])

  return (
    <div className="flex flex-col h-full bg-white">
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4" style={{ scrollBehavior: 'smooth' }}>
        {/* Refresh header */}
        <div className="flex items-center justify-between mb-3 px-0.5">
          <span className="text-xs text-gray-400 font-medium select-none">
            {chatMessages.length > 0 ? `${chatMessages.length} 条消息` : "" }
          </span>
          <button
            onClick={handleRefresh}
            disabled={refreshing || loading}
            className="flex items-center justify-center w-8 h-8 min-w-8 shrink-0 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors active:bg-gray-200 touch-manipulation"
            title="刷新消息"
          >
            <span className={`inline-block text-base leading-none ${refreshing ? 'animate-spin' : '' }`}>
              {UI_EMOJI.refresh}
            </span>
          </button>
        </div>
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
        {!loading && chatMessages.length === 0 && <div className="flex items-center justify-center h-full text-gray-400 text-sm">暂无消息</div>}
        {chatMessages.map((msg, i) => {
          if (msg.kind === 'approval' && resolvedApprovals.has(msg.id)) return null
          const enriched = msg.kind === 'approval'
            ? {
                ...msg,
                onApprove: () => handleApprovalDecision(msg.id, 'allow', msg.request_id),
                onDeny: () => handleApprovalDecision(msg.id, 'deny', msg.request_id),
              }
            : msg
          return <ChatMessage key={msg.id || i} message={enriched} />
        })}
        <div className="h-2" />
      </div>
      <div className="px-4 py-1 border-t border-gray-100 flex items-center gap-2 bg-white">
        <span className={`inline-block w-1.5 h-1.5 rounded-full ${connectionStatus === 'connected' ? 'bg-green-500' : connectionStatus === 'connecting' ? 'bg-yellow-500 animate-pulse' : 'bg-red-500'}`} />
        <span className={`text-[10px] font-mono ${connectionStatus === 'connected' ? 'text-green-600' : connectionStatus === 'connecting' ? 'text-yellow-600' : 'text-red-600'}`}>
          {connectionStatus === 'connected' ? 'WebSocket 已连接' : connectionStatus === 'connecting' ? '连接中...' : '已断开'}
        </span>
      </div>
      <ChatInput onSend={handleSend} disabled={connectionStatus !== 'connected'} />
    </div>
  )
}
