import { useState } from 'react'
import { UI_EMOJI } from '../constants/agents.js'

const COLUMNS = [
  { key: 'pending', label: 'Pending', icon: UI_EMOJI.clipboard, color: 'text-gray-500', defaultOpen: true },
  { key: 'running', label: 'Running', icon: UI_EMOJI.wrench, color: 'text-yellow-600', defaultOpen: true },
  { key: 'done', label: 'Done', icon: UI_EMOJI.check, color: 'text-green-600', defaultOpen: false },
]
const MAX_VISIBLE = 5
const STATUS_ICON = {
  pending: UI_EMOJI.clipboard,
  running: UI_EMOJI.refresh,
  done: UI_EMOJI.check,
  failed: UI_EMOJI.cross,
}

export default function CompactTaskBoard({ tasks }) {
  const [collapsed, setCollapsed] = useState({ running: false, pending: false, done: true })
  const grouped = {
    pending: tasks.filter((t) => t.status === 'pending' || t.status === 'todo'),
    running: tasks.filter((t) => t.status === 'running' || t.status === 'started'),
    done: tasks.filter((t) => t.status === 'completed' || t.status === 'done' || t.status === 'failed'),
  }
  const toggle = (key) => setCollapsed((p) => ({ ...p, [key]: !p[key] }))
  return (
    <div className="p-3 space-y-1 bg-white">
      <div className="flex items-center justify-between px-1 py-2">
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Tasks</h3>
        <button onClick={() => setCollapsed({})} className="text-[10px] text-gray-400 hover:text-gray-600">[-] fold</button>
      </div>
      {(!tasks || tasks.length === 0) && <p className="text-xs text-gray-400 text-center py-6">No tasks yet</p>}
      {COLUMNS.map((col) => {
        const items = grouped[col.key]
        const isCollapsed = collapsed[col.key] !== false
        const showItems = !isCollapsed ? items : items.slice(0, MAX_VISIBLE)
        const overflow = items.length - MAX_VISIBLE
        return (
          <div key={col.key}>
            <button onClick={() => toggle(col.key)} className="w-full flex items-center gap-2 px-1 py-2 text-xs hover:bg-gray-50 rounded transition-colors">
              <span>{col.icon}</span>
              <span className={`font-semibold ${col.color}`}>{col.label}</span>
              <span className="ml-auto text-gray-400 font-mono text-[11px]">{items.length}</span>
              {items.length > MAX_VISIBLE && <span className="text-gray-300 text-[10px]">{!isCollapsed ? '▲' : '▼'}</span>}
            </button>
            {showItems.slice(0, col.key === 'done' ? MAX_VISIBLE : items.length).map((task) => (
              <div key={task.id} className="ml-2 pl-2.5 border-l-2 border-gray-200 py-1.5 mb-0.5 hover:border-gray-400 transition-colors">
                <div className="flex items-start gap-1.5">
                  <span className="text-[10px] mt-0.5">{STATUS_ICON[task.status] || UI_EMOJI.clipboard}</span>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs text-gray-700 truncate leading-tight font-medium">{task.title}</p>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      <span className="text-[10px] text-gray-400 font-mono">{task.agent}</span>
                      {task.duration_ms != null && <><span className="text-gray-300">·</span><span className="text-[10px] text-gray-400 font-mono">{(task.duration_ms / 1000).toFixed(1)}s</span></>}
                    </div>
                  </div>
                </div>
              </div>
            ))}
            {isCollapsed && col.key === 'done' && overflow > 0 && (
              <button onClick={() => toggle(col.key)} className="w-full text-center text-[10px] text-gray-400 py-1 hover:text-gray-600">+{overflow} more</button>
            )}
          </div>
        )
      })}
    </div>
  )
}
