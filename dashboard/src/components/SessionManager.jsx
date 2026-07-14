import { useState } from 'react'

const MOCK_SESSIONS = [
  { id: 'sess-001', name: 'TeamChat develop', directory: '/Users/yanxinluo/Documents/PycharmProjects/TeamChat', agents: { 'cici\u54aa': 'ready', 'coco\u54aa': 'ready', 'soso\u54aa': 'ready' }, created: '2026-07-09', active: true },
  { id: 'sess-002', name: 'New experiment', directory: '/Users/yanxinluo/Documents/experiment', agents: { 'cici\u54aa': 'pending', 'coco\u54aa': 'pending', 'soso\u54aa': 'pending' }, created: '2026-07-10', active: false },
]

const AE = { 'cici\u54aa': '\U0001f3d7\ufe0f', 'coco\u54aa': '\u26a1', 'soso\u54aa': '\U0001f50d' }
const SI = { ready: '\u2705', pending: '\u23f3', failed: '\u274c' }
const SD = { ready: 'ready', pending: 'pending', failed: 'failed' }

export default function SessionManager({ open, onClose }) {
  const [sessions, setSessions] = useState(MOCK_SESSIONS)
  const [activeId, setActiveId] = useState('sess-001')
  const [newName, setNewName] = useState('')
  const [newDir, setNewDir] = useState('')
  if (!open) return null

  const handleCreate = () => {
    if (!newName.trim() || !newDir.trim()) return
    const id = `sess-${Date.now()}`
    setSessions((prev) => [
      ...prev,
      {
        id,
        name: newName.trim(),
        directory: newDir.trim(),
        agents: { 'cici\u54aa': 'pending', 'coco\u54aa': 'pending', 'soso\u54aa': 'pending' },
        created: new Date().toISOString().slice(0, 10),
        active: false,
      },
    ])
    setNewName('')
    setNewDir('')
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-xl border border-gray-200 w-full max-w-lg mx-4 max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <h2 className="text-base font-semibold text-gray-800">Session Manager</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-lg leading-none">&times;</button>
        </div>
        <div className="p-4 space-y-3">
          {sessions.map((s) => {
            const isActive = s.id === activeId
            return (
              <div key={s.id} className={`border rounded-xl p-4 transition-all ${isActive ? 'border-blue-300 bg-blue-50/30' : 'border-gray-200 bg-white hover:border-gray-300'}`}>
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2.5">
                    <span className={`inline-block w-3 h-3 rounded-full ${isActive ? 'bg-blue-500' : 'bg-gray-300'}`} />
                    <div>
                      <h3 className={`text-sm font-medium ${isActive ? 'text-blue-700' : 'text-gray-700'}`}>{s.name}</h3>
                      <p className="text-xs text-gray-400 font-mono mt-0.5">{s.directory}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button onClick={() => setActiveId(s.id)} className={`text-xs px-3 py-1 rounded-lg font-medium transition-colors ${isActive ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>{isActive ? '\u2713 Current' : 'Switch'}</button>
                    <button className="text-gray-400 hover:text-gray-600 text-sm px-1">\u00b7\u00b7\u00b7</button>
                  </div>
                </div>
                <div className="mt-3 flex items-center gap-3 text-xs">
                  {['cici\u54aa', 'coco\u54aa', 'soso\u54aa'].map((n) => <div key={n} className="flex items-center gap-1"><span>{AE[n]}</span><span className={`session-dot ${SD[s.agents[n]]}`} /></div>)}
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
