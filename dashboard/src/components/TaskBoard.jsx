import TaskCard from './TaskCard.jsx'

const COLUMNS = [
  { key: 'todo', label: '待处理', icon: '📋', color: 'border-t-gray-600' },
  { key: 'running', label: '进行中', icon: '🔧', color: 'border-t-yellow-500/60' },
  { key: 'completed', label: '已完成', icon: '✅', color: 'border-t-green-500/60' },
]

export default function TaskBoard({ tasks }) {
  if (!tasks || tasks.length === 0) {
    return (
      <div className="bg-gray-900/40 border border-gray-700/30 rounded-lg p-8 text-center">
        <p className="text-gray-500 text-sm">暂无任务。提交新任务后将出现在这里。</p>
      </div>
    )
  }

  const grouped = {
    todo: tasks.filter((t) => t.status === 'pending' || t.status === 'todo'),
    running: tasks.filter((t) => t.status === 'running' || t.status === 'started'),
    completed: tasks.filter((t) => t.status === 'completed' || t.status === 'done'),
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {COLUMNS.map((col) => (
        <div key={col.key} className="bg-gray-900/40 border border-gray-700/30 border-t-2 rounded-lg overflow-hidden"
             style={{ borderTopColor: 'inherit' }}>
          <div className={`px-3 py-2 border-b border-gray-700/30 flex items-center gap-2 ${col.color}`}>
            <span className="text-sm">{col.icon}</span>
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide">{col.label}</h3>
            <span className="ml-auto text-xs text-gray-600 font-mono">{grouped[col.key].length}</span>
          </div>
          <div className="p-3 space-y-2 min-h-[120px]">
            {grouped[col.key].length === 0 ? (
              <p className="text-xs text-gray-600 text-center py-4">—</p>
            ) : (
              grouped[col.key].map((task) => (
                <TaskCard key={task.id} task={task} />
              ))
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
