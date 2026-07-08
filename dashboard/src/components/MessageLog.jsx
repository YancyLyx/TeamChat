export default function MessageLog({ messages }) {
  if (!messages || messages.length === 0) {
    return (
      <div className="bg-gray-900/40 border border-gray-700/30 rounded-lg p-6 text-center">
        <p className="text-gray-500 text-sm">等待 agent 间消息……</p>
      </div>
    )
  }

  return (
    <div className="bg-gray-900/40 border border-gray-700/30 rounded-lg overflow-hidden">
      <div className="px-4 py-2 border-b border-gray-700/30 flex items-center gap-2">
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide">对话日志</h3>
        <span className="ml-auto text-xs text-gray-600 font-mono">{messages.length} 条</span>
      </div>
      <div className="max-h-64 overflow-y-auto p-3 space-y-1.5 font-mono text-xs">
        {messages.map((msg, i) => (
          <div key={msg.id || i} className="flex gap-2 leading-relaxed">
            <span className="text-gray-600 shrink-0">[{msg.time}]</span>
            <span className="text-cyan-400 shrink-0">{msg.from}</span>
            <span className="text-gray-600 shrink-0">→</span>
            <span className="text-purple-400 shrink-0">{msg.to}</span>
            <span className="text-gray-400 truncate">: {msg.content}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
