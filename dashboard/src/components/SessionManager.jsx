import { useState, useEffect } from 'react'
import { AGENT_NAMES, AGENT_EMOJI } from '../constants/agents.js'

const emptyAgents = () => Object.fromEntries(AGENT_NAMES.map((n) => [n, null]))  // null = uninitialized, no dot

const MOCK_SESSIONS = [
  {
    id: 'sess-001',
    name: 'TeamChat develop',
    directory: '/Users/yanxinluo/Documents/PycharmProjects/TeamChat',
    agents: { 'cici咪': 'ready', 'coco咪': 'ready', 'soso咪': 'ready' },
    created: '2026-07-09',
    active: true,
  },
]

const SESSION_STATUS_CLASS = { ready: 'ready', failed: 'failed' }
const SESSION_STATUS_LABEL = { ready: '✅', failed: '❌' }

export default function SessionManager({ open, onClose, onActiveChange }) {
  const [sessions, setSessions] = useState(MOCK_SESSIONS)
  const [activeId, setActiveId] = useState('sess-001')
  const [newName, setNewName] = useState('')
  const [newDir, setNewDir] = useState('')
  const [menuId, setMenuId] = useState(null)  // which session menu is open
  const [renameId, setRenameId] = useState(null)  // which session is being renamed
  const [renameVal, setRenameVal] = useState('')

  useEffect(() => {
    if (!onActiveChange) return
    const active = sessions.find((s) => s.id === activeId)
    if (active) onActiveChange(active.name)
  }, [activeId, sessions, onActiveChange])

  if (!open) return null

  const handleCreate = () => {
    if (!newName.trim() || !newDir.trim()) return
    setSessions((prev) => [...prev, { id: `sess-${Date.now()}`, name: newName.trim(), directory: newDir.trim(), agents: emptyAgents(), created: new Date().toISOString().slice(0, 10), active: false }])
    setNewName(''); setNewDir('')
  }

  const handleDelete = (id) => {
    setSessions((prev) => {
      const next = prev.filter((s) => s.id !== id)
      if (activeId === id) setActiveId(next[0]?.id ?? null)
      return next
    })
    setMenuId(null)
  }

  const handleRename = (id) => {
    const s = sessions.find((x) => x.id === id)
    if (!s) return
    setRenameId(id); setRenameVal(s.name); setMenuId(null)
  }

  const confirmRename = (id) => {
    if (!renameVal.trim()) { setRenameId(null); return }
    setSessions((prev) => prev.map((s) => s.id === id ? { ...s, name: renameVal.trim() } : s))
    setRenameId(null)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-xl border border-gray-200 w-full max-w-lg mx-4 max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <h2 className="text-base font-semibold text-gray-800">Session Manager</h2>
          <button onClick={onClose} aria-label="Close session manager" className="text-gray-400 hover:text-gray-600 text-lg leading-none">&times;</button>
        </div>

        {/* Session list */}
        <div className="p-4 space-y-3">
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
                    <button onClick={() => setActiveId(s.id)}
                      className={`text-xs px-2.5 py-1 rounded-lg font-medium transition-colors ${isActive ? 'bg-blue-100 text-blue-700 cursor-default' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>
                      {isActive ? '✓' : 'Switch'}
                    </button>
                    {/* 3-dot menu */}
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
                {/* Agent status row — only show dots for initialized agents with status */}
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

        {/* New Session Form */}
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
