import { useState, useEffect, useCallback } from 'react'
import { AGENT_NAMES, AGENT_EMOJI } from '../constants/agents.js'
import { ACTIVE_SESSION_KEY } from '../constants/session.js'

const API_BASE = '/api/session-manager'

const emptyAgents = () => Object.fromEntries(AGENT_NAMES.map((n) => [n, null]))

const SESSION_STATUS_CLASS = { ready: 'ready', failed: 'failed' }
const SESSION_STATUS_LABEL = { ready: '✅', failed: '❌' }

function apiToUi(row) {
  const agents = emptyAgents()
  if (row.claude_id) agents['cici咪'] = 'ready'
  if (row.codex_id) agents['coco咪'] = 'ready'
  if (row.cursor_id) agents['soso咪'] = 'ready'
  return {
    id: row.id,
    name: row.name,
    directory: row.directory,
    agents,
    created: (row.created_at || '').slice(0, 10),
    active: false,
  }
}

export default function SessionManager({ open, onClose, onActiveChange }) {
  const [sessions, setSessions] = useState([])
  const [activeId, setActiveId] = useState(null)
  const [newName, setNewName] = useState('')
  const [newDir, setNewDir] = useState('')
  const [menuId, setMenuId] = useState(null)
  const [renameId, setRenameId] = useState(null)
  const [renameVal, setRenameVal] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const loadSessions = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(API_BASE)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const rows = await res.json()
      const mapped = rows.map(apiToUi)
      setSessions(mapped)
      const stored = localStorage.getItem(ACTIVE_SESSION_KEY)
      const storedId = stored ? Number(stored) : null
      const active = mapped.find((s) => s.id === storedId) || mapped[0] || null
      setActiveId(active?.id ?? null)
      if (active && onActiveChange) onActiveChange(active.name)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [onActiveChange])

  useEffect(() => {
    if (open) loadSessions()
  }, [open, loadSessions])

  useEffect(() => {
    if (!onActiveChange) return
    const active = sessions.find((s) => s.id === activeId)
    if (active) onActiveChange(active.name)
  }, [activeId, sessions, onActiveChange])

  if (!open) return null

  const handleCreate = async () => {
    if (!newName.trim() || !newDir.trim()) return
    setError(null)
    try {
      const res = await fetch(API_BASE, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newName.trim(), directory: newDir.trim() }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail || `HTTP ${res.status}`)
      }
      const created = apiToUi(await res.json())
      setSessions((prev) => [...prev, created])
      setActiveId(created.id)
      localStorage.setItem(ACTIVE_SESSION_KEY, String(created.id))
      setNewName('')
      setNewDir('')
    } catch (err) {
      setError(err.message)
    }
  }

  const handleDelete = async (id) => {
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/${id}`, { method: 'DELETE' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setSessions((prev) => {
        const next = prev.filter((s) => s.id !== id)
        if (activeId === id) {
          const fallback = next[0]?.id ?? null
          setActiveId(fallback)
          if (fallback) localStorage.setItem(ACTIVE_SESSION_KEY, String(fallback))
          else localStorage.removeItem(ACTIVE_SESSION_KEY)
        }
        return next
      })
      setMenuId(null)
    } catch (err) {
      setError(err.message)
    }
  }

  const handleRename = (id) => {
    const s = sessions.find((x) => x.id === id)
    if (!s) return
    setRenameId(id)
    setRenameVal(s.name)
    setMenuId(null)
  }

  const confirmRename = async (id) => {
    if (!renameVal.trim()) { setRenameId(null); return }
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: renameVal.trim() }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const updated = apiToUi(await res.json())
      setSessions((prev) => prev.map((s) => s.id === id ? updated : s))
      setRenameId(null)
    } catch (err) {
      setError(err.message)
    }
  }

  const handleSwitch = (id) => {
    setActiveId(id)
    localStorage.setItem(ACTIVE_SESSION_KEY, String(id))
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-xl border border-gray-200 w-full max-w-lg mx-4 max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <h2 className="text-base font-semibold text-gray-800">Session Manager</h2>
          <button onClick={onClose} aria-label="Close session manager" className="text-gray-400 hover:text-gray-600 text-lg leading-none">&times;</button>
        </div>

        {error && (
          <div className="mx-4 mt-3 px-3 py-2 text-xs text-red-600 bg-red-50 border border-red-100 rounded-lg">{error}</div>
        )}

        <div className="p-4 space-y-3">
          {loading && sessions.length === 0 && (
            <p className="text-xs text-gray-400 text-center py-4">Loading sessions...</p>
          )}
          {!loading && sessions.length === 0 && (
            <p className="text-xs text-gray-400 text-center py-4">No sessions yet — create one below.</p>
          )}
          {sessions.map((s) => {
            const isActive = s.id === activeId
            return (
              <div key={s.id} className={`border rounded-xl p-4 transition-all relative ${isActive ? 'border-blue-300 bg-blue-50/30' : 'border-gray-200 bg-white hover:border-gray-300'}`}>
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2.5 flex-1 min-w-0">
                    <span className={`inline-block w-3 h-3 rounded-full flex-shrink-0 ${isActive ? 'bg-blue-500' : 'bg-gray-300'}`} />
                    {renameId === s.id ? (
                      <input value={renameVal} onChange={e => setRenameVal(e.target.value)}
                        onKeyDown={e => { if (e.key === 'Enter') confirmRename(s.id); if (e.key === 'Escape') setRenameId(null) }}
                        onBlur={() => confirmRename(s.id)}
                        className="text-sm font-medium text-gray-700 border border-blue-300 rounded px-1.5 py-0.5 outline-none w-full max-w-[200px]" autoFocus />
                    ) : (
                      <div className="min-w-0">
                        <h3 className={`text-sm font-medium truncate ${isActive ? 'text-blue-700' : 'text-gray-700'}`}>{s.name}</h3>
                        <p className="text-xs text-gray-400 font-mono truncate mt-0.5">{s.directory}</p>
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-1.5 flex-shrink-0 ml-2">
                    <button onClick={() => handleSwitch(s.id)}
                      className={`text-xs px-2.5 py-1 rounded-lg font-medium transition-colors ${isActive ? 'bg-blue-100 text-blue-700 cursor-default' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>
                      {isActive ? '✓' : 'Switch'}
                    </button>
                    <div className="relative">
                      <button onClick={(e) => { e.stopPropagation(); setMenuId(menuId === s.id ? null : s.id) }} className="text-gray-400 hover:text-gray-600 text-sm px-1 py-1 rounded hover:bg-gray-100 leading-none" aria-label="Session menu">···</button>
                      {menuId === s.id && (
                        <div className="absolute right-0 top-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-30 py-1 min-w-[120px]" onMouseDown={(e) => e.stopPropagation()}>
                          <button onClick={() => handleRename(s.id)} className="w-full text-left px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-50">Rename</button>
                          <button onClick={() => { navigator.clipboard?.writeText(s.directory); setMenuId(null) }} className="w-full text-left px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-50">Copy Path</button>
                          <div className="border-t border-gray-100 my-1" />
                          <button onClick={() => handleDelete(s.id)} className="w-full text-left px-3 py-1.5 text-xs text-red-500 hover:bg-red-50">Delete</button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
                <div className="mt-3 flex items-center gap-3 text-xs">
                  {AGENT_NAMES.map((n) => {
                    const status = s.agents[n]
                    const initialized = status === 'ready' || status === 'failed'
                    return (
                      <div key={n} className="flex items-center gap-1">
                        <span>{AGENT_EMOJI[n]}</span>
                        {initialized ? (
                          <span className={`session-dot ${SESSION_STATUS_CLASS[status]}`} title={SESSION_STATUS_LABEL[status]} />
                        ) : (
                          <span className="text-gray-300 text-[10px] font-mono">--</span>
                        )}
                      </div>
                    )
                  })}
                  <span className="text-gray-300">|</span>
                  <span className="text-gray-400">{s.created}</span>
                </div>
              </div>
            )
          })}
        </div>

        <div className="border-t border-gray-100 p-4">
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">+ New Session</h3>
          <div className="space-y-2.5">
            <input value={newName} onChange={e => setNewName(e.target.value)} placeholder="Session name" className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-200" />
            <input value={newDir} onChange={e => setNewDir(e.target.value)} placeholder="Absolute directory path" className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-200" />
            <button disabled={!newName || !newDir} onClick={handleCreate} className="w-full py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-500 disabled:bg-gray-200 disabled:text-gray-400 transition-colors">Create</button>
          </div>
        </div>
      </div>
    </div>
  )
}
