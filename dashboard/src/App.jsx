import { useState, useEffect, useCallback, useRef } from 'react'
import { useWebSocket } from './hooks/useWebSocket.js'
import StatusBar from './components/StatusBar.jsx'
import TaskBoard from './components/TaskBoard.jsx'
import ActivityTimeline from './components/ActivityTimeline.jsx'
import MessageLog from './components/MessageLog.jsx'

const API_BASE = '/api'

function formatTime(iso) {
  try {
    const d = new Date(iso)
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch {
    return iso
  }
}

let taskCounter = 0

export default function App() {
  // State
  const [agents, setAgents] = useState([])
  const [tasks, setTasks] = useState([])
  const [timelineEvents, setTimelineEvents] = useState([])
  const [messageLog, setMessageLog] = useState([])
  const [sessionsByAgent, setSessionsByAgent] = useState({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // WebSocket
  const { messages: wsMessages, connectionStatus } = useWebSocket()
  const lastMsgCountRef = useRef(0)

  // Fetch initial data from REST API
  const fetchInitialData = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)

      const [agentsRes, sessionsRes, statsRes] = await Promise.all([
        fetch(`${API_BASE}/agents`),
        fetch(`${API_BASE}/sessions?limit=30`),
        fetch(`${API_BASE}/stats`),
      ])

      if (!agentsRes.ok || !sessionsRes.ok || !statsRes.ok) {
        throw new Error('API 请求失败')
      }

      const agentsData = await agentsRes.json()
      const sessionsData = await sessionsRes.json()
      const statsData = await statsRes.json()

      setAgents(agentsData)

      // Group sessions by agent
      const byAgent = {}
      for (const s of sessionsData) {
        if (!byAgent[s.agent_name]) byAgent[s.agent_name] = []
        byAgent[s.agent_name].push(s)
      }
      setSessionsByAgent(byAgent)

      // Convert sessions to tasks
      const initialTasks = sessionsData.map((s) => ({
        id: `session-${s.id}`,
        title: s.prompt.slice(0, 80),
        agent: s.agent_name,
        status: s.exit_code === 0 ? 'completed' : 'completed',
        exit_code: s.exit_code,
        duration_ms: s.duration_ms,
        time: formatTime(s.started_at),
        preview: s.output.slice(0, 100),
      }))
      setTasks(initialTasks)

      // Create timeline events from sessions
      const events = sessionsData.map((s) => ({
        id: `session-ev-${s.id}`,
        type: 'task_complete',
        agent: s.agent_name,
        description: `${s.agent_name} 完成任务 "${s.prompt.slice(0, 40)}..."`,
        time: formatTime(s.finished_at),
        success: s.exit_code === 0,
        icon: s.exit_code === 0 ? '✅' : '❌',
      }))
      setTimelineEvents(events.reverse())

    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchInitialData()
  }, [fetchInitialData])

  // Process WebSocket messages
  useEffect(() => {
    if (wsMessages.length <= lastMsgCountRef.current) return

    const newMessages = wsMessages.slice(lastMsgCountRef.current)
    lastMsgCountRef.current = wsMessages.length

    for (const msg of newMessages) {
      const now = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })

      if (msg.type === 'task_started') {
        const data = msg.data || {}
        taskCounter += 1
        const taskId = `task-${taskCounter}`

        // Add to tasks
        setTasks((prev) => [
          {
            id: taskId,
            title: (data.prompt || '新任务').slice(0, 80),
            agent: data.agent,
            status: 'running',
            time: now,
          },
          ...prev,
        ])

        // Add timeline event
        setTimelineEvents((prev) => [
          {
            id: `ev-${taskId}`,
            type: 'task_started',
            agent: data.agent,
            description: `${data.agent} 开始执行任务: "${(data.prompt || '').slice(0, 60)}..."`,
            time: now,
            icon: '🚀',
          },
          ...prev,
        ])

        // Mark agent busy
        setAgents((prev) =>
          prev.map((a) => (a.name === data.agent ? { ...a, is_busy: true } : a))
        )
      }

      if (msg.type === 'task_complete') {
        const data = msg.data || {}

        // Update task status
        setTasks((prev) =>
          prev.map((t) =>
            t.agent === data.agent && t.status === 'running'
              ? { ...t, status: 'completed', exit_code: data.success ? 0 : 1, duration_ms: data.duration_ms, preview: data.output_preview }
              : t
          )
        )

        // Add timeline event
        setTimelineEvents((prev) => [
          {
            id: `ev-complete-${Date.now()}`,
            type: 'task_complete',
            agent: data.agent,
            description: `${data.agent} 完成任务 (${(data.duration_ms / 1000).toFixed(1)}s)`,
            time: now,
            success: data.success,
            icon: data.success ? '✅' : '❌',
          },
          ...prev,
        ])

        // Mark agent free
        setAgents((prev) =>
          prev.map((a) => (a.name === data.agent ? { ...a, is_busy: false } : a))
        )
      }

      if (msg.type === 'message') {
        const data = msg.data || {}

        // Add to message log
        setMessageLog((prev) => [
          {
            id: data.id || `msg-${Date.now()}`,
            time: formatTime(data.timestamp) || now,
            from: data.from,
            to: data.to,
            content: data.content || '',
          },
          ...prev,
        ])

        // Add timeline event
        setTimelineEvents((prev) => [
          {
            id: `ev-msg-${Date.now()}`,
            type: 'message',
            agent: data.from || '系统',
            description: `${data.from || '系统'} → ${data.to || 'all'}: "${(data.content || '').slice(0, 60)}..."`,
            time: now,
            icon: '📨',
          },
          ...prev,
        ])
      }
    }
  }, [wsMessages])

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      {/* Header */}
      <header className="border-b border-gray-800/80 bg-gray-950/95 sticky top-0 z-10 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-2xl">🤖</span>
            <div>
              <h1 className="text-lg font-bold text-gray-100 tracking-tight">TeamChat</h1>
              <p className="text-[10px] text-gray-500 font-mono">实时 Agent 协作面板 v0.1</p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs">
            <span className={`status-dot ${connectionStatus === 'connected' ? 'connected' : 'disconnected'}`} />
            <span className={`font-mono ${connectionStatus === 'connected' ? 'text-green-400' : 'text-red-400'}`}>
              {connectionStatus === 'connected' ? '已连接' : connectionStatus === 'connecting' ? '连接中...' : '已断开'}
            </span>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        {/* Error banner */}
        {error && (
          <div className="bg-red-900/30 border border-red-800/40 rounded-lg px-4 py-3 text-sm text-red-300 flex items-center gap-2">
            <span>⚠️</span>
            <span>连接后端失败: {error} — 请确认后端在 localhost:8000 运行</span>
            <button onClick={fetchInitialData} className="ml-auto text-xs underline hover:text-red-200">
              重试
            </button>
          </div>
        )}

        {/* Loading skeleton */}
        {loading && !error && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="bg-gray-800/50 border border-gray-700/30 rounded-lg p-4 animate-pulse">
                  <div className="h-4 bg-gray-700/50 rounded w-20 mb-3" />
                  <div className="h-6 bg-gray-700/50 rounded w-32 mb-2" />
                  <div className="h-3 bg-gray-700/50 rounded w-24" />
                </div>
              ))}
            </div>
            <div className="bg-gray-900/40 border border-gray-700/30 rounded-lg p-8 animate-pulse">
              <div className="h-4 bg-gray-700/50 rounded w-40 mb-4" />
              <div className="h-20 bg-gray-700/30 rounded" />
            </div>
          </div>
        )}

        {/* Dashboard content */}
        {!loading && (
          <>
            {/* Status Bar */}
            <section>
              <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
                Agent 状态
              </h2>
              <StatusBar agents={agents} sessionsByAgent={sessionsByAgent} />
            </section>

            {/* Grid: TaskBoard left, ActivityTimeline right */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <section className="lg:col-span-2">
                <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
                  任务看板
                </h2>
                <TaskBoard tasks={tasks} />
              </section>
              <section>
                <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
                  活动时间线
                </h2>
                <ActivityTimeline events={timelineEvents} />
              </section>
            </div>

            {/* Message Log */}
            <section>
              <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
                Agent 对话日志
              </h2>
              <MessageLog messages={messageLog} />
            </section>
          </>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-800/60 mt-8">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between text-xs text-gray-600">
          <span>TeamChat Dashboard — Multi-AI-Agent Collaboration Platform</span>
          <span className="font-mono">
            {connectionStatus === 'connected'
              ? '🟢 已连接'
              : connectionStatus === 'connecting'
              ? '🟡 连接中...'
              : '🔴 已断开'}
          </span>
        </div>
      </footer>
    </div>
  )
}
