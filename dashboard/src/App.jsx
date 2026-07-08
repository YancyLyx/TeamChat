import { useState, useEffect, useCallback, useRef } from 'react'
import { useWebSocket } from './hooks/useWebSocket.js'
import AgentCard from './components/AgentCard.jsx'
import TaskBoard from './components/TaskBoard.jsx'
import AgentPanel from './components/AgentPanel.jsx'
import CompactTaskBoard from './components/CompactTaskBoard.jsx'
import ChatRoom from './components/ChatRoom.jsx'

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
  const [agSessions, setAgSessions] = useState({})
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [rightSidebarOpen, setRightSidebarOpen] = useState(true)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // WebSocket
  const { messages: wsMessages, connectionStatus } = useWebSocket()
  const lastMsgCountRef = useRef(0)

  // Fetch initial data
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
        throw new Error('API request failed')
      }

      const agentsData = await agentsRes.json()
      const sessionsData = await sessionsRes.json()
      const statsData = await statsRes.json()

      const enrichedAgents = agentsData.map((a) => ({
        ...a,
        total_tasks: statsData?.agents?.[a.name]?.total_calls ?? a.total_tasks ?? 0,
        success_rate: statsData?.agents?.[a.name]?.success_rate ?? a.success_rate ?? 0,
        avg_duration_ms: statsData?.agents?.[a.name]?.avg_duration_ms ?? a.avg_duration_ms ?? 0,
      }))
      setAgents(enrichedAgents)

      const byAgent = {}
      for (const s of sessionsData) {
        if (!byAgent[s.agent_name]) byAgent[s.agent_name] = []
        byAgent[s.agent_name].push(s)
      }
      setAgSessions(byAgent)

      const initialTasks = sessionsData.map((s) => ({
        id: `session-${s.id}`,
        title: s.prompt.slice(0, 80),
        agent: s.agent_name,
        status: s.exit_code === 0 ? 'completed' : 'failed',
        exit_code: s.exit_code,
        duration_ms: s.duration_ms,
        time: formatTime(s.started_at),
        preview: s.output.slice(0, 100),
      }))
      setTasks(initialTasks)

    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchInitialData()
  }, [fetchInitialData])

  // Process WebSocket messages for task/agent state updates
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

        setTasks((prev) => [
          {
            id: taskId,
            title: (data.prompt || 'New task').slice(0, 80),
            agent: data.agent,
            status: 'running',
            time: now,
          },
          ...prev,
        ])

        setAgents((prev) =>
          prev.map((a) => (a.name === data.agent ? { ...a, is_busy: true } : a))
        )
      }

      if (msg.type === 'task_complete') {
        const data = msg.data || {}

        setTasks((prev) => {
          const serverId = data.session_id ? `session-${data.session_id}` : null
          let matched = false
          return prev.map((t) => {
            if (matched) return t
            if (serverId && t.id === serverId) {
              matched = true
              return { ...t, status: data.success ? 'completed' : 'failed', exit_code: data.success ? 0 : 1, duration_ms: data.duration_ms, preview: data.output_preview }
            }
            if (!serverId && t.agent === data.agent && t.status === 'running') {
              matched = true
              return { ...t, status: data.success ? 'completed' : 'failed', exit_code: data.success ? 0 : 1, duration_ms: data.duration_ms, preview: data.output_preview }
            }
            return t
          })
        })

        setAgents((prev) =>
          prev.map((a) => (a.name === data.agent ? { ...a, is_busy: false } : a))
        )
      }
    }
  }, [wsMessages])

  return (
    <div className="h-screen flex flex-col bg-gray-950 text-gray-100 overflow-hidden">
      {/* ====== Top Header ====== */}
      <header className="flex-shrink-0 border-b border-gray-800/80 bg-gray-950/95 px-4 py-2.5 flex items-center justify-between z-10">
        <div className="flex items-center gap-3">
          <span className="text-xl">🤖</span>
          <h1 className="text-base font-bold text-gray-100 tracking-tight">TeamChat</h1>
          <span className="text-[10px] text-gray-600 font-mono hidden sm:inline">v0.1</span>
        </div>
        <div className="flex items-center gap-3">
          {/* Toggle left sidebar */}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="text-xs text-gray-500 hover:text-gray-300 transition-colors px-2 py-1 rounded hover:bg-gray-800/50"
            title="Toggle agent panel"
          >
            {sidebarOpen ? '▶️ Agents' : '◀️ Agents'}
          </button>
          {/* Toggle right sidebar */}
          <button
            onClick={() => setRightSidebarOpen(!rightSidebarOpen)}
            className="text-xs text-gray-500 hover:text-gray-300 transition-colors px-2 py-1 rounded hover:bg-gray-800/50"
            title="Toggle task board"
          >
            {rightSidebarOpen ? '◀️ Tasks' : '▶️ Tasks'}
          </button>
          {/* Connection status */}
          <div className="flex items-center gap-1.5 text-xs">
            <span className={`inline-block w-2 h-2 rounded-full ${
              connectionStatus === 'connected' ? 'bg-green-500' :
              connectionStatus === 'connecting' ? 'bg-yellow-500 animate-pulse' : 'bg-red-500'
            }`} />
            <span className={`font-mono ${
              connectionStatus === 'connected' ? 'text-green-400' :
              connectionStatus === 'connecting' ? 'text-yellow-400' : 'text-red-400'
            }`}>
              {connectionStatus === 'connected' ? 'Connected' :
               connectionStatus === 'connecting' ? 'Connecting...' : 'Offline'}
            </span>
          </div>
        </div>
      </header>

      {/* ====== Error Banner ====== */}
      {error && (
        <div className="flex-shrink-0 bg-red-900/30 border-b border-red-800/40 px-4 py-2 text-xs text-red-300 flex items-center gap-2">
          <span>Warning</span>
          <span>{error}</span>
          <button onClick={fetchInitialData} className="ml-auto underline hover:text-red-200">Retry</button>
        </div>
      )}

      {/* ====== Main Content Area ====== */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Sidebar - Agent Status */}
        <aside
          className={`flex-shrink-0 border-r border-gray-800/60 bg-gray-900/50 overflow-y-auto transition-all duration-200 ${
            sidebarOpen ? 'w-56' : 'w-0 overflow-hidden'
          }`}
        >
          {sidebarOpen && (
            <AgentPanel agents={agents} sessionsByAgent={agSessions} />
          )}
        </aside>

        {/* Center - Chat Room */}
        <main className="flex-1 flex flex-col overflow-hidden min-w-0">
          <ChatRoom wsMessages={wsMessages} connectionStatus={connectionStatus} />
        </main>

        {/* Right Sidebar - Task Board */}
        <aside
          className={`flex-shrink-0 border-l border-gray-800/60 bg-gray-900/50 overflow-y-auto transition-all duration-200 ${
            rightSidebarOpen ? 'w-72' : 'w-0 overflow-hidden'
          }`}
        >
          {rightSidebarOpen && (
            <CompactTaskBoard tasks={tasks} />
          )}
        </aside>
      </div>
    </div>
  )
}
