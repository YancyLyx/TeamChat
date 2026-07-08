export default function ActivityTimeline({ events }) {
  if (!events || events.length === 0) {
    return (
      <div data-testid="activity-timeline" className="bg-gray-900/40 border border-gray-700/30 rounded-lg p-6 text-center">
        <p className="text-gray-500 text-sm">等待活动事件……</p>
      </div>
    )
  }

  return (
    <div className="bg-gray-900/40 border border-gray-700/30 rounded-lg overflow-hidden">
      <div className="px-4 py-2 border-b border-gray-700/30">
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide">活动时间线</h3>
      </div>
      <div className="max-h-96 overflow-y-auto p-4 space-y-0">
        {events.map((evt, i) => (
          <div key={evt.id || i} className="relative flex gap-3 pb-4 last:pb-0">
            {/* Timeline line */}
            {i < events.length - 1 && (
              <div className="absolute left-[11px] top-5 bottom-0 w-px bg-gray-700/50" />
            )}

            {/* Timeline dot */}
            <div className={`flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-xs
              ${evt.type === 'task_started' ? 'bg-blue-900/50 text-blue-300' : ''}
              ${evt.type === 'task_complete' ? (evt.success ? 'bg-green-900/50 text-green-300' : 'bg-red-900/50 text-red-300') : ''}
              ${evt.type === 'message' ? 'bg-purple-900/50 text-purple-300' : ''}
              ${!['task_started', 'task_complete', 'message'].includes(evt.type) ? 'bg-gray-800 text-gray-400' : ''}
            `}>
              {evt.icon || (
                evt.type === 'task_started' ? '🚀' :
                evt.type === 'task_complete' ? (evt.success ? '✅' : '❌') :
                evt.type === 'message' ? '📨' : '📝'
              )}
            </div>

            {/* Event content */}
            <div className="flex-1 min-w-0 pt-0.5">
              <div className="flex items-center gap-2 text-xs">
                <span className="font-medium text-gray-300">{evt.agent}</span>
                <span className="text-gray-600">·</span>
                <span className="text-gray-500 font-mono text-[10px]">{evt.time}</span>
              </div>
              <p className="text-xs text-gray-400 mt-0.5 leading-relaxed">
                {evt.description}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
