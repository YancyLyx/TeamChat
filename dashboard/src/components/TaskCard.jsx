export default function TaskCard({ task }) {
  const statusIcon = task.status === 'completed'
    ? (task.exit_code === 0 ? '✅' : '❌')
    : task.status === 'running'
    ? '🔄'
    : '📝'

  const statusColor = task.status === 'completed'
    ? (task.exit_code === 0 ? 'border-l-green-500/60' : 'border-l-red-500/60')
    : task.status === 'running'
    ? 'border-l-yellow-500/60'
    : 'border-l-gray-500/60'

  return (
    <div data-testid="task-card" className={`task-card bg-gray-800/60 border border-gray-700/40 border-l-2 ${statusColor} rounded-lg p-3`}>
      <div className="flex items-start gap-2">
        <span className="text-sm mt-0.5">{statusIcon}</span>
        <div className="flex-1 min-w-0">
          <p className="text-sm text-gray-200 font-medium truncate">{task.title}</p>
          <div className="flex items-center gap-2 mt-1 text-xs text-gray-500">
            <span>{task.agent}</span>
            <span>·</span>
            <span className="font-mono">{task.time}</span>
          </div>
          {task.duration_ms != null && (
            <div className="mt-1 text-xs text-gray-500">
              耗时: <span className="font-mono text-gray-400">{(task.duration_ms / 1000).toFixed(1)}s</span>
            </div>
          )}
          {task.preview && (
            <p className="mt-1 text-xs text-gray-500 truncate">{task.preview}</p>
          )}
        </div>
      </div>
    </div>
  )
}
