import { useState, useEffect, useCallback, useRef } from 'react'
import { useWebSocket } from './hooks/useWebSocket.js'
import AgentCard from './components/AgentCard.jsx'
import ChatRoom from './components/ChatRoom.jsx'
import SessionManager from './components/SessionManager.jsx'
import StatsPanel from './components/StatsPanel.jsx'
import LivePanel from './components/LivePanel.jsx'
import { UI_EMOJI } from './constants/agents.js'
import { normalizeAgentMetrics } from './utils/metrics.js'

const API_BASE = '/api'
let tc = 0

export default function App() {
  const [agents, setAgents] = useState([])
  const [tasks, setTasks] = useState([])
  const [agSessions, setAgSessions] = useState({})
  const [agentMetrics, setAgentMetrics] = useState({})
  const [leftOpen, setLeftOpen] = useState(true)
  const [rightOpen, setRightOpen] = useState(true)
  const [rightTab, setRightTab] = useState('stats')
  const [showSM, setShowSM] = useState(false)
  const [sessionLabel, setSessionLabel] = useState('TeamChat develop')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const { messages: wsMessages, connectionStatus } = useWebSocket()
  const lastMcRef = useRef(0)
  const [liveEvents, setLiveEvents] = useState([])

  const fetchData = useCallback(async () => {
    try {
      setLoading(true); setError(null)
      const [ar, sr, str, tr] = await Promise.all([
        fetch(`${API_BASE}/agents`),
        fetch(`${API_BASE}/sessions?limit=30&tag=prod`),
        fetch(`${API_BASE}/stats`),
        fetch(`${API_BASE}/tasks/table`),
      ])
      if (!ar.ok || !sr.ok || !str.ok) throw new Error('API failed')
      const ad = await ar.json(), sd = await sr.json(), st = await str.json()
      const tableRows = tr.ok ? await tr.json() : []
      const metrics = normalizeAgentMetrics(st, sd)
      setAgentMetrics(metrics)
      setAgents(ad.map((a) => ({ ...a, ...(metrics[a.name] || {}) })))
      const ba = {}; for (const s of sd) { if (!ba[s.agent_name]) ba[s.agent_name] = []; ba[s.agent_name].push(s) }; setAgSessions(ba)
      const sessionTasks = sd.map((s) => ({ id: `session-${s.id}`, title: s.prompt.slice(0, 80), agent: s.agent_name, status: s.exit_code === 0 ? 'done' : 'failed', exit_code: s.exit_code, duration_ms: s.duration_ms, time: new Date(s.started_at).toLocaleTimeString(), preview: s.output.slice(0, 100) }))
      const tableTasks = tableRows.map((t) => ({
        id: `table-${t.id}`,
        title: t.title,
        agent: t.agent,
        status: t.status === 'done' ? 'done' : t.status === 'failed' ? 'failed' : t.status,
        duration_ms: null,
        preview: t.output_summary || '',
      }))
      setTasks([...tableTasks, ...sessionTasks])
    } catch (err) { setError(err.message) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { fetchData() }, [fetchData])

  useEffect(() => {
    if (wsMessages.length <= lastMcRef.current) return
    const nm = wsMessages.slice(lastMcRef.current); lastMcRef.current = wsMessages.length
    for (const m of nm) {
      if (m.type === 'task_started') { const d = m.data || {}; tc += 1; setTasks(p => [{ id: `t-${tc}`, title: (d.prompt || '').slice(0, 80), agent: d.agent, status: 'running', time: new Date().toLocaleTimeString() }, ...p]); setAgents(p => p.map(a => a.name === d.agent ? { ...a, is_busy: true } : a)) }
      if (m.type === 'task_table_updated') {
        const d = m.data || {}
        const tid = d.id ? `table-${d.id}` : null
        if (tid) {
          setTasks(p => {
            const idx = p.findIndex(t => t.id === tid)
            const row = { id: tid, title: (d.title || '').slice(0, 80), agent: d.agent, status: d.status === 'done' ? 'done' : d.status === 'failed' ? 'failed' : d.status, duration_ms: d.duration_ms, preview: d.output_summary || '' }
            if (idx >= 0) { const next = [...p]; next[idx] = { ...next[idx], ...row }; return next }
            return [row, ...p]
          })
        }
      }
      if (m.type === 'task_complete') {
        const d = m.data || {}
        setTasks(p => {
          const si = d.session_id ? `session-${d.session_id}` : null
          let mt = false
          return p.map(t => {
            if (mt) return t
            if (si && t.id === si) { mt = true; return { ...t, status: d.success ? 'done' : 'failed', exit_code: d.success ? 0 : 1, duration_ms: d.duration_ms, preview: d.output_preview } }
            if (!si && t.agent === d.agent && t.status === 'running') { mt = true; return { ...t, status: d.success ? 'done' : 'failed', exit_code: d.success ? 0 : 1, duration_ms: d.duration_ms, preview: d.output_preview } }
            return t
          })
        })
        setAgents(p => p.map(a => a.name === d.agent ? { ...a, is_busy: false } : a))
        fetchData()
      }
      if (m.type !== 'pong' && m.type !== 'connected') {
        setLiveEvents((prev) => [...prev.slice(-19), m])
      }
    }
  }, [wsMessages, fetchData])

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
          <ChatRoom wsMessages={wsMessages} connectionStatus={connectionStatus} />
        </main>
        <aside className={`flex-shrink-0 border-l border-gray-200 bg-white overflow-y-auto transition-all duration-200 ${rightOpen ? 'w-72' : 'w-0 overflow-hidden'}`}>
          {rightOpen && (
            <>
              <div className="flex border-b border-gray-100">
                <button onClick={() => setRightTab('stats')} className={`flex-1 text-xs py-2 font-medium transition-colors ${rightTab === 'stats' ? 'text-blue-600 border-b-2 border-blue-500' : 'text-gray-400 hover:text-gray-600'}`}>Stats</button>
                <button onClick={() => setRightTab('live')} className={`flex-1 text-xs py-2 font-medium transition-colors ${rightTab === 'live' ? 'text-blue-600 border-b-2 border-blue-500' : 'text-gray-400 hover:text-gray-600'}`}>Live</button>
              </div>
              {rightTab === 'stats' ? <StatsPanel agentMetrics={agentMetrics} /> : <LivePanel recentEvents={liveEvents} />}
            </>
          )}
        </aside>
      </div>

      <SessionManager open={showSM} onClose={() => setShowSM(false)} onActiveChange={setSessionLabel} />
    </div>
  )
}
