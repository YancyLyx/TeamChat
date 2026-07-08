import { useState, useEffect, useRef, useCallback } from 'react'
import ChatMessage from './ChatMessage.jsx'
import ChatInput from './ChatInput.jsx'

const API_BASE = '/api'

function formatTime(iso) {
  try {
    const d = new Date(iso)
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch {
    return iso
  }
}

export default function ChatRoom({ wsMessages, connectionStatus }) {
  const [chatMessages, setChatMessages] = useState([])
  const [loading, setLoading] = useState(true)
  const scrollRef = useRef(null)
  const lastWsCountRef = useRef(0)
  const pendingRef = useRef(false)

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [chatMessages])  // eslint-disable-line react-hooks/exhaustive-deps

  // Fetch initial data from REST API
  const fetchInitial = useCallback(async () => {
    try {
      setLoading(true)
      const [agentsRes, sessionsRes] = await Promise.all([
        fetch(`${API_BASE}/agents`),
        fetch(`${API_BASE}/sessions?limit=30`),
      ])

      if (!agentsRes.ok || !sessionsRes.ok) {
        throw new Error('API request failed')
      }

      const agentsData = await agentsRes.json()
      const sessionsData = await sessionsRes.json()

      const initial = []

      // Add welcome message
      initial.push({
        id: 'welcome',
        kind: 'system',
        agent: 'system',
        content: '欢迎来到 TeamChat！使用 @cici咪 @coco咪 @soso咪 向 agent 发送消息。',
        timestamp: new Date().toISOString(),
      })

      // Convert previous sessions to chat messages
      for (const s of sessionsData) {
        const agentName = s.agent_name
        initial.push({
          id: `session-${s.id}-prompt`,
          kind: 'task_event',
          agent: agentName,
          content: s.prompt.slice(0, 80),
          type: 'task_started',
          timestamp: s.started_at,
        })
        initial.push({
          id: `session-${s.id}-result`,
          kind: 'agent_reply',
          agent: agentName,
          content: s.output.slice(0, 300),
          timestamp: s.finished_at,
        })
      }

      setChatMessages(initial)
    } catch (err) {
      // Show error in chat
      setChatMessages([
        {
          id: 'error',
          kind: 'system',
          agent: 'system',
          content: `无法加载历史数据: ${err.message}。WebSocket 连接后将自动接收新消息。`,
          timestamp: new Date().toISOString(),
        },
      ])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchInitial()
  }, [fetchInitial])

  // Send a message via POST /api/chat
  const handleSend = useCallback(async (content) => {
    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content }),
      })
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}))
        throw new Error(errData.detail || `HTTP ${res.status}`)
      }
      const data = await res.json()
      return data
    } catch (err) {
      // Add error message to chat
      setChatMessages((prev) => [
        ...prev,
        {
          id: `send-error-${Date.now()}`,
          kind: 'system',
          agent: 'system',
          content: `发送失败: ${err.message}`,
          timestamp: new Date().toISOString(),
        },
      ])
      throw err
    }
  }, [])

  // Process incoming WebSocket messages
  useEffect(() => {
    if (wsMessages.length <= lastWsCountRef.current) return
    if (pendingRef.current) return  // avoid re-entry during state updates

    const newMsgs = wsMessages.slice(lastWsCountRef.current)
    lastWsCountRef.current = wsMessages.length

    pendingRef.current = true

    const additions = []

    for (const msg of newMsgs) {
      if (msg.type === 'chat_message') {
        const data = msg.data || {}
        additions.push({
          id: data.id || `chat-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
          kind: data.kind || 'agent_message',
          agent: data.agent || 'system',
          content: data.content || '',
          timestamp: data.timestamp || new Date().toISOString(),
        })
      } else if (msg.type === 'connected') {
        additions.push({
          id: `connected-${Date.now()}`,
          kind: 'system',
          agent: 'system',
          content: '已连接 TeamChat 实时通道',
          timestamp: msg.data?.timestamp || new Date().toISOString(),
        })
      } else if (msg.type === 'task_started') {
        const data = msg.data || {}
        additions.push({
          id: `ts-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
          kind: 'task_event',
          agent: data.agent || 'system',
          content: data.prompt || '开始执行任务',
          type: 'task_started',
          timestamp: data.timestamp || new Date().toISOString(),
        })
      } else if (msg.type === 'task_complete') {
        const data = msg.data || {}
        const status = data.success ? '完成' : '失败'
        additions.push({
          id: `tc-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
          kind: 'task_event',
          agent: data.agent || 'system',
          content: `${status}任务 ${data.duration_ms ? '(' + (data.duration_ms / 1000).toFixed(1) + 's)' : ''}`,
          type: 'task_complete',
          timestamp: data.timestamp || new Date().toISOString(),
        })
      } else if (msg.type === 'message') {
        const data = msg.data || {}
        additions.push({
          id: data.id || `bus-msg-${Date.now()}`,
          kind: 'agent_message',
          agent: data.from || 'system',
          content: `${data.from || '?'} → ${data.to || 'all'}: ${data.content || ''}`,
          timestamp: data.timestamp || new Date().toISOString(),
        })
      } else if (msg.type === 'pong') {
        // ignore
      }
    }

    if (additions.length > 0) {
      setChatMessages((prev) => [...prev, ...additions])
    }

    pendingRef.current = false
  }, [wsMessages])

  return (
    <div className="flex flex-col h-full">
      {/* Message list */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto px-4 py-4 space-y-0"
        style={{ scrollBehavior: 'smooth' }}
      >
        {loading && (
          <div className="space-y-3 py-8">
            {[1, 2, 3].map((i) => (
              <div key={i} className="flex gap-3 animate-pulse">
                <div className="w-8 h-8 rounded-full bg-gray-700/50" />
                <div className="flex-1">
                  <div className="h-3 bg-gray-700/30 rounded w-24 mb-2" />
                  <div className="h-12 bg-gray-700/30 rounded-xl" />
                </div>
              </div>
            ))}
          </div>
        )}

        {!loading && chatMessages.length === 0 && (
          <div className="flex items-center justify-center h-full text-gray-500 text-sm">
            暂无消息
          </div>
        )}

        {chatMessages.map((msg, i) => (
          <ChatMessage key={msg.id || i} message={msg} />
        ))}

        {/* Bottom spacer */}
        <div className="h-2" />
      </div>

      {/* Connection status bar */}
      <div className="px-4 py-1 border-t border-gray-800/40 flex items-center gap-2">
        <span className={`inline-block w-1.5 h-1.5 rounded-full ${
          connectionStatus === 'connected' ? 'bg-green-500 shadow-[0_0_4px_rgba(34,197,94,0.5)]' :
          connectionStatus === 'connecting' ? 'bg-yellow-500 animate-pulse' : 'bg-red-500'
        }`} />
        <span className={`text-[10px] font-mono ${
          connectionStatus === 'connected' ? 'text-green-500/70' :
          connectionStatus === 'connecting' ? 'text-yellow-500/70' : 'text-red-500/70'
        }`}>
          {connectionStatus === 'connected' ? 'WebSocket 已连接' :
           connectionStatus === 'connecting' ? '连接中...' : '已断开'}
        </span>
      </div>

      {/* Input */}
      <ChatInput onSend={handleSend} disabled={connectionStatus !== 'connected'} />
    </div>
  )
}
