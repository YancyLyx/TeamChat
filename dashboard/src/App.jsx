import { useState, useEffect, useCallback, useRef } from 'react'
import { useWebSocket } from './hooks/useWebSocket.js'
import AgentCard from './components/AgentCard.jsx'
import ChatRoom from './components/ChatRoom.jsx'
import SessionManager from './components/SessionManager.jsx'
import StatsPanel from './components/StatsPanel.jsx'
import LivePanel from './components/LivePanel.jsx'
import TasksBoard from './components/TasksBoard.jsx'
import { UI_EMOJI } from './constants/agents.js'
import { normalizeAgentMetrics } from './utils/metrics.js'

const API_BASE = '/api'

export default function App() {
  const [agents, setAgents] = useState([])
  const [tasks, setTasks] = useState([])
  const [agSessions, setAgSessions] = useState({})
  const [leftOpen, setLeftOpen] = useState(true)
  const [rightOpen, setRightOpen] = useState(true)
  const [rightTab, setRightTab] = useState('tasks')
  const [showSM, setShowSM] = useState(false)
  const [sessionLabel, setSessionLabel] = useState('加载中...')
  const [activeSessionId, setActiveSessionId] = useState(() => {
    try { const v = localStorage.getItem('teamchat_active_session_id'); return v ? Number(v) : null }
    catch { return null }
  })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const { messages: wsMessages, connectionStatus } = useWebSocket()
  const lastMcRef = useRef(0)
 const [liveEvents, setLiveEvents] = useState([])
  const liveEventsDedup = useRef(new Map())
  const [agentMetrics, setAgentMetrics] = useState({})
  const [l3Stats, setL3Stats] = useState(null)

  const fetchData = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const [ar, sr, str, tr, er] = await Promise.all([
        fetch(`${API_BASE}/agents`),
        fetch(`${API_BASE}/sessions?limit=30`),
        fetch(`${API_BASE}/stats?teamchat_session_id=${activeSessionId ?? 1}`),
        fetch(`${API_BASE}/tasks/table`),
        fetch(`${API_BASE}/engine`),
      ])
      if (!ar.ok || !sr.ok || !str.ok || !tr.ok) throw new Error('API failed')
      const ad = await ar.json(), sd = await sr.json(), st = await str.json()
      const tableRows = await tr.json()
      const engineData = er.ok ? await er.json() : { active_agents: [] }
      const busyMap = {}
      for (const a of engineData.active_agents || []) { busyMap[a.name] = a.is_busy }
      setAgentMetrics(normalizeAgentMetrics(st, sd))
      setL3Stats(st.l3 ?? null)
      setAgents(ad.map((a) => ({
        ...a,
        is_busy: busyMap[a.name] ?? a.is_busy ?? false,
        total_tasks: st?.agents?.[a.name]?.total_calls ?? a.total_tasks ?? 0,
        success_rate: st?.agents?.[a.name]?.success_rate ?? a.success_rate ?? 0,
        avg_duration_ms: st?.agents?.[a.name]?.avg_duration_ms ?? a.avg_duration_ms ?? 0,
        total_tokens: st?.agents?.[a.name]?.total_tokens ?? a.total_tokens ?? 0,
      })))
      const ba = {}
      for (const s of sd) {
        if (!ba[s.agent_name]) ba[s.agent_name] = []
        ba[s.agent_name].push(s)
      }
      setAgSessions(ba)
      setTasks(tableRows)
    } catch (err) { setError(err.message) }
    finally { setLoading(false) }
  }, [activeSessionId])

  useEffect(() => { fetchData() }, [fetchData])

  // Poll /api/engine every 2s to keep agent sidebar status current
  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch(`${API_BASE}/engine`)
        if (!res.ok) return
        const data = await res.json()
        const busyMap = {}
        for (const a of data.active_agents || []) {
          busyMap[a.name] = a.is_busy
        }
        setAgents(p => p.map(a => ({
          ...a,
          is_busy: busyMap[a.name] ?? false,
        })))
      } catch { /* ignore */ }
    }
    const interval = setInterval(poll, 2000)
    return () => clearInterval(interval)
  }, [])
 
  // Load the default/active session from the API on mount
  useEffect(() => {
    let cancelled = false
    const loadDefaultSession = async () => {
      try {
        const res = await fetch('/api/session-manager')
        if (!res.ok) throw new Error('')
        const sessions = await res.json()
        if (cancelled) return
        const stored = localStorage.getItem('teamchat_active_session_id')
        const storedId = stored ? Number(stored) : null
        const active = sessions.find((s) => s.id === storedId) || sessions[0]
        if (active) {
          setSessionLabel(active.name)
          setActiveSessionId(active.id)
        } else {
          setSessionLabel('默认工作区')
        }
      } catch {
        if (!cancelled) setSessionLabel('默认工作区')
      }
    }
    loadDefaultSession()
    return () => { cancelled = true }
  }, [])

  const handleSessionChange = useCallback((name) => {
    setSessionLabel(name)
    const stored = localStorage.getItem('teamchat_active_session_id')
    setActiveSessionId(stored ? Number(stored) : null)
  }, [])

  const handleUpdateTask = useCallback(async (taskId, body) => {
    const res = await fetch(`${API_BASE}/tasks/table/${taskId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || `HTTP ${res.status}`)
    }
    const updated = await res.json()
    setTasks((prev) => {
      const idx = prev.findIndex((t) => t.id === taskId)
      if (idx >= 0) {
        const next = [...prev]
        next[idx] = { ...next[idx], ...updated }
        return next
      }
      return [...prev, updated]
    })
    return updated
  }, [])

  useEffect(() => {
    if (wsMessages.length <= lastMcRef.current) return
    const nm = wsMessages.slice(lastMcRef.current)
    lastMcRef.current = wsMessages.length
    for (const m of nm) {
      if (m.type === 'task_started') {
        const d = m.data || {}
        setAgents(p => p.map(a => a.name === d.agent ? { ...a, is_busy: true, busy_since: Date.now() } : a))
      } else if (m.type === 'task_table_updated') {
        const d = m.data || {}
        const tid = d.id != null ? d.id : null
        if (tid) {
          setTasks(p => {
            const idx = p.findIndex(t => t.id === tid)
            const row = { ...d }
            if (idx >= 0) { const next = [...p]; next[idx] = { ...next[idx], ...row }; return next }
            return [row, ...p]
          })
        }
      } else if (m.type === 'task_complete') {
        const d = m.data || {}
        setAgents(p => p.map(a => a.name === d.agent ? { ...a, is_busy: false, busy_since: null } : a))
      }

      if (m.type !== 'pong' && m.type !== 'connected') {
        const eventKey = `${m.type}|${m.data?.agent || m.data?.from || ''}|${m.data?.content || m.data?.prompt || m.data?.output_preview || ''}`.slice(0, 200)
        const now = Date.now()
        if (liveEventsDedup.current.has(eventKey) && now - liveEventsDedup.current.get(eventKey) < 3000) continue
        liveEventsDedup.current.set(eventKey, now)
        if (liveEventsDedup.current.size > 200) {
          liveEventsDedup.current = new Map([...liveEventsDedup.current.entries()].slice(-100))
        }
        setLiveEvents((prev) => [...prev.slice(-19), m])
      }
    }
  }, [wsMessages])

  return (
    <div className="h-screen flex flex-col bg-gray-50 text-gray-800 overflow-hidden">
      {/* Header */}
      <header className="flex-shrink-0 border-b border-gray-200 bg-white px-4 py-2.5 flex items-center justify-between z-10">
        <div className="flex items-center gap-3">
          <span className="text-lg">{UI_EMOJI.robot}</span>
          <h1 className="text-base font-bold text-gray-800 tracking-tight">TeamChat</h1>
          <button onClick={() => setShowSM(true)} className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg px-2.5 py-1.5 transition-colors ml-2">{UI_EMOJI.folder} {sessionLabel} ▾</button>
          <span className="text-[10px] text-gray-400 font-mono hidden sm:inline">v0.1</span>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setLeftOpen(!leftOpen)} className="text-xs text-gray-400 hover:text-gray-600 px-2 py-1 rounded hover:bg-gray-100">{leftOpen ? '◀' : '▶'}</button>
          <button onClick={() => setRightOpen(!rightOpen)} className="text-xs text-gray-400 hover:text-gray-600 px-2 py-1 rounded hover:bg-gray-100">{rightOpen ? '▶' : '◀'}</button>
          <div className="flex items-center gap-1.5 text-xs ml-2">
            <span className={`inline-block w-2 h-2 rounded-full ${connectionStatus === 'connected' ? 'bg-green-500' : connectionStatus === 'connecting' ? 'bg-yellow-500 animate-pulse' : 'bg-red-500'}`} />
            <span className={`font-mono ${connectionStatus === 'connected' ? 'text-green-600' : connectionStatus === 'connecting' ? 'text-yellow-600' : 'text-red-600'}`}>{connectionStatus === 'connected' ? 'Connected' : connectionStatus === 'connecting' ? 'Connecting...' : 'Offline'}</span>
          </div>
        </div>
      </header>

      {error && <div className="flex-shrink-0 bg-red-50 border-b border-red-200 px-4 py-2 text-xs text-red-700 flex items-center gap-2"><span>{UI_EMOJI.warning}</span><span>{error}</span><button onClick={fetchData} className="ml-auto underline hover:text-red-800">Retry</button></div>}

      <div className="flex-1 flex overflow-hidden">
        <aside className={`flex-shrink-0 border-r border-gray-200 bg-white overflow-y-auto transition-all duration-200 ${leftOpen ? 'w-56' : 'w-0 overflow-hidden'}`}>
          {leftOpen && <div className="p-3 space-y-2"><h3 className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider px-1 mb-2">Agents</h3>{loading ? [1,2,3].map(i => <div key={i} className="bg-gray-100 rounded-xl p-3 animate-pulse"><div className="h-3 bg-gray-200 rounded w-16 mb-2" /><div className="h-3 bg-gray-200 rounded w-24" /></div>) : agents.map(a => <AgentCard key={a.name} agent={a} sessions={agSessions[a.name] || []} />)}</div>}
        </aside>
        <main className="flex-1 flex flex-col overflow-hidden min-w-0">
          <ChatRoom wsMessages={wsMessages} connectionStatus={connectionStatus} sessionId={activeSessionId} />
        </main>
        <aside className={`flex-shrink-0 border-l border-gray-200 bg-white overflow-y-auto transition-all duration-200 ${rightOpen ? 'w-72' : 'w-0 overflow-hidden'}`}>
        {rightOpen && (
            <>
              <div className="flex border-b border-gray-100">
                <button onClick={() => setRightTab('tasks')} className={`flex-1 text-xs py-2 font-medium transition-colors ${rightTab === 'tasks' ? 'text-blue-600 border-b-2 border-blue-500' : 'text-gray-400 hover:text-gray-600'}`}>Tasks</button>
                <button onClick={() => setRightTab('stats')} className={`flex-1 text-xs py-2 font-medium transition-colors ${rightTab === 'stats' ? 'text-blue-600 border-b-2 border-blue-500' : 'text-gray-400 hover:text-gray-600'}`}>Stats</button>
                <button onClick={() => setRightTab('live')} className={`flex-1 text-xs py-2 font-medium transition-colors ${rightTab === 'live' ? 'text-blue-600 border-b-2 border-blue-500' : 'text-gray-400 hover:text-gray-600'}`}>Live</button>
              </div>
              {rightTab === 'tasks' ? <TasksBoard tasks={tasks} sessionId={activeSessionId} onUpdateTask={handleUpdateTask} /> : rightTab === 'stats' ? <StatsPanel agentMetrics={agentMetrics} l3Stats={l3Stats} sessionId={activeSessionId} /> : <LivePanel recentEvents={liveEvents} />}
            </>
          )}
        </aside>
      </div>

      <SessionManager open={showSM} onClose={() => setShowSM(false)} onActiveChange={handleSessionChange} />
    </div>
  )
}
