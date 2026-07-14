import { useState } from 'react'

const SESSION_MOCK = [
  { id: 'sess-001', name: 'TeamChat 开发', directory: '/Users/yanxinluo/Documents/PycharmProjects/TeamChat', agents: { 'cici咪': 'ready', 'coco咪': 'ready', 'soso咪': 'ready' }, created: '2026-07-09', active: true },
  { id: 'sess-002', name: '新项目实验', directory: '/Users/yanxinluo/Documents/experiment', agents: { 'cici咪': 'pending', 'coco咪': 'pending', 'soso咪': 'pending' }, created: '2026-07-10', active: false },
]

const AGENT_EMOJI = { 'cici咪': '🏗️', 'coco咪': '⚡', 'soso咪': '🔍' }

const STATUS_ICON = { ready: '✅', pending: '⏳', failed: '❌' }
const STATUS_DOT = { ready: 'ready', pending: 'pending', failed: 'failed' }

export default function SessionManager({ open, onClose }) {
  const [sessions] = useState(SESSION_MOCK)
  const [activeId, setActiveId] = useState('sess-001')
  const [newName, setNewName] = useState('')
  const [newDir, setNewDir] = useState('')

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={onClose}>
      <div
        className="bg-white rounded-2xl shadow-xl border border-gray-200 w-full max-w-lg mx-4 max-h-[80vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <h2 className="text-base font-semibold text-gray-800">会话管理器</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-lg leading-none">&times;</button>
        </div>

        <div className="p-4 space-y-3">
          {sessions.map((sess) => {
            const isActive = sess.id === activeId
            return (
              <div
                key={sess.id}
                className={`border rounded-xl p-4 transition-all ${isActive ? 'border-blue-300 bg-blue-50/30' : 'border-gray-200 bg-white hover:border-gray-300'}`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2.5">
                    <span className={`inline-block w-3 h-3 rounded-full ${isActive ? 'bg-blue-500' : 'bg-gray-300'}`} />
                    <div>
                      <h3 className={`text-sm font-medium ${isActive ? 'text-blue-700' : 'text-gray-700'}`}>{sess.name}</h3>
                      <p className="text-xs text-gray-400 font-mono mt-0.5">{sess.directory}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setActiveId(sess.id)}
                      className={`text-xs px-3 py-1 rounded-lg font-medium transition-colors ${
                        isActive ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                      }`}
                    >
                      {isActive ? '✓ 当前' : 'Switch'}
                    </button>
                    <button className="text-gray-400 hover:text-gray-600 text-sm px-1">···</button>
                  </div>
                </div>
                <div className="mt-3 flex items-center gap-3 text-xs">
                  {['cici咪', 'coco咪', 'soso咪'].map((name) => (
                    <div key={name} className="flex items-center gap-1">
                      <span>{AGENT_EMOJI[name]}</span>
                      <span className={`session-dot ${STATUS_DOT[sess.agents[name]]}`} />
                    </div>
                  ))}
                  <span className="text-gray-300">|</span>
                  <span className="text-gray-400">{sess.created}</span>
                </div>
              </div>
            )
          })}
        </div>

        {/* New Session Form */}
        <div className="border-t border-gray-100 p-4">
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">+ 新建会话</h3>
          <div className="space-y-2.5">
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="会话名称"
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-200"
            />
            <input
              value={newDir}
              onChange={(e) => setNewDir(e.target.value)}
              placeholder="目录绝对路径 (例: /Users/.../project)"
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-200"
            />
            <button
              disabled={!newName || !newDir}
              className="w-full py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-500 disabled:bg-gray-200 disabled:text-gray-400 transition-colors"
            >
              Create
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
