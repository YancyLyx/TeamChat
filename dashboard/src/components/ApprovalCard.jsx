export default function ApprovalCard({ tool_name, tool_input, onApprove, onDeny, agent }) {
  const inputStr = typeof tool_input === 'object' ? JSON.stringify(tool_input, null, 2) : String(tool_input || '')

  return (
    <div className="flex justify-center mb-3">
      <div className="w-full max-w-lg bg-yellow-50 border border-yellow-300 rounded-xl shadow-sm overflow-hidden">
        <div className="px-4 py-3 border-b border-yellow-200/60 flex items-center gap-2">
          <span className="text-sm">🔧</span>
          <span className="text-sm font-medium text-yellow-800">{agent || '系统'} 请求执行</span>
        </div>
        <div className="px-4 py-3">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xs font-mono bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded font-semibold">{tool_name || 'Tool'}</span>
          </div>
          <pre className="bg-white border border-gray-200 rounded-lg p-3 text-xs font-mono text-gray-600 overflow-x-auto whitespace-pre-wrap max-h-32 overflow-y-auto">
            {inputStr}
          </pre>
        </div>
        <div className="px-4 py-3 bg-yellow-100/50 border-t border-yellow-200/60 flex items-center justify-end gap-3">
          <button
            onClick={onDeny}
            className="px-5 py-1.5 text-sm font-medium text-gray-600 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
          >
            Deny
          </button>
          <button
            onClick={onApprove}
            className="px-5 py-1.5 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-500 transition-colors"
          >
            Allow
          </button>
        </div>
      </div>
    </div>
  )
}
