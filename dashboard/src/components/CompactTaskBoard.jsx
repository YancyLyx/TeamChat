import { useState } from 'react'

const COLUMNS = [
  { key: 'running', label: 'In Progress', icon: '🔧', color: 'text-yellow-400' },
  { key: 'todo', label: 'Todo', icon: '📋', color: 'text-gray-400' },
  { key: 'completed', label: 'Done', icon: '✅', color: 'text-green-400' },
]

const MAX_VISIBLE = 5

export default function CompactTaskBoard({ tasks }) {
  const [collapsed, setCollapsed] = useState({})

  const grouped = {
    todo: tasks.filter((t) => t.status === 'pending' || t.status === 'todo'),
    running: tasks.filter((t) => t.status === 'running' || t.status === 'started'),
    completed: tasks.filter((t) => t.status === 'completed' || t.status === 'done' || t.status === 'failed'),
  }

  const toggleCollapse = (key) => {
    setCollapsed((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  const hasTasks = tasks && tasks.length > 0

  return (
    <div className="p-3 space-y-2">
      <h3 className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider px-1 mb-3">Tasks</h3>

      {!hasTasks && (
        <p className="text-xs text-gray-600 text-center py-6">No tasks yet</p>
      )}

      {COLUMNS.map((col) => {
        const items = grouped[col.key]
        const isCollapsed = collapsed[col.key]
        const showItems = isCollapsed ? items : items.slice(0, MAX_VISIBLE)
        const overflow = items.length - MAX_VISIBLE

        return (
          <div key={col.key}>
            <button
              onClick={() => toggleCollapse(col.key)}
              className="w-full flex items-center gap-2 px-1 py-1.5 text-xs hover:bg-gray-800/30 rounded transition-colors"
            >
              <span>{col.icon}</span>
              <span className={`font-medium ${col.color}`}>{col.label}</span>
              <span className="ml-auto text-gray-600 font-mono">{items.length}</span>
              <span className="text-gray-700 text-[10px]">{isCollapsed ? '▲' : items.length > MAX_VISIBLE ? '▼' : ''}</span>
            </button>

            {showItems.map((task) => (
              <div
                key={task.id}
                className="ml-1 pl-2 border-l-2 border-gray-700/30 py-1.5 mb-0.5 hover:border-gray-500/50 transition-colors"
              >
                <div className="flex items-start gap-1.5">
                  <span className="text-[10px] mt-0.5">
                    {task.status === 'running' ? '🔄' :
                     task.status === 'failed' || task.exit_code === 1 ? '❌' : '✅'}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-[11px] text-gray-300 truncate leading-tight">{task.title}</p>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      <span className="text-[9px] text-gray-600 font-mono">{task.agent}</span>
                      {task.duration_ms != null && (
                        <>
                          <span className="text-gray-700">·</span>
                          <span className="text-[9px] text-gray-600 font-mono">{(task.duration_ms / 1000).toFixed(1)}s</span>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))}

            {!isCollapsed && overflow > 0 && (
              <button
                onClick={() => toggleCollapse(col.key)}
                className="w-full text-center text-[10px] text-gray-600 py-1 hover:text-gray-400 transition-colors"
              >
                +{overflow} more
              </button>
            )}
          </div>
        )
      })}
    </div>
  )
}
