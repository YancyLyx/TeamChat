/* ADR-003 Section 9 — Engine runtime observability. */

import { useEffect, useState } from 'react'
import { AGENT_EMOJI, AGENT_NAMES, UI_EMOJI } from '../constants/agents.js'

const API_BASE = '/api'

function ModeBadge({ mode }) {
  if (mode === 'serial') {
    return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-yellow-100 text-yellow-700">Serial</span>
  }
  return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-green-100 text-green-700">Parallel</span>
}

export default function LivePanel({ recentEvents = [] }) {
  const [engine, setEngine] = useState({ mode: 'parallel', active_agents: [], queue_length: 0 })
  const [loading, setLoading] = useState(true)

  const fetchEngine = async () => {
    try {
      const res = await fetch(`${API_BASE}/engine`)
      if (res.ok) {
        setEngine(await res.json())
      }
    } catch { /* ignore */ }
    finally { setLoading(false) }
  }

  useEffect(() => {
    fetchEngine()
    const interval = setInterval(fetchEngine, 5000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="p-3 space-y-3 bg-white">
      <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">🔴 Live</h3>

      {loading ? (
        <div className="space-y-3">
          <div className="h-3 bg-gray-100 rounded animate-pulse w-12" />
          <div className="h-8 bg-gray-100 rounded animate-pulse" />
          <div className="h-8 bg-gray-100 rounded animate-pulse" />
          <div className="h-8 bg-gray-100 rounded animate-pulse" />
        </div>
      ) : (
        <>
          {/* Current mode */}
          <div className="bg-gray-50 rounded-lg p-2.5">
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-gray-400 font-semibold uppercase">Engine Mode</span>
              <ModeBadge mode={engine.mode} />
            </div>
            {engine.queue_length > 0 && (
              <p className="text-[10px] text-gray-400 font-mono mt-1">queue: {engine.queue_length} waiting</p>
            )}
          </div>

          {/* Active agents */}
          <div>
            <p className="text-[10px] text-gray-400 font-semibold uppercase mb-1.5 px-0.5">Active Agents</p>
            <div className="space-y-1">
              {engine.active_agents.map((a) => (
                <div key={a.name} className="flex items-center gap-2 px-2 py-1.5 bg-gray-50 rounded-lg text-xs">
                  <span className="text-sm">{AGENT_EMOJI[a.name] || UI_EMOJI.fallback}</span>
                  <span className="text-gray-700 font-medium flex-1">{a.name}</span>
                  {a.is_busy ? (
                    <span className="inline-flex items-center gap-1 text-[10px] text-red-500 font-mono"><span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />executing</span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-[10px] text-green-600 font-mono"><span className="w-1.5 h-1.5 rounded-full bg-green-500" />idle</span>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Recent events */}
          <div>
            <p className="text-[10px] text-gray-400 font-semibold uppercase mb-1.5 px-0.5">Recent Events</p>
            {recentEvents.length === 0 ? (
              <p className="text-xs text-gray-400 text-center py-3">No events yet</p>
            ) : (
              <div className="space-y-1 max-h-48 overflow-y-auto">
                {recentEvents.slice(-10).map((evt, i) => {
                  const icon = evt.type === 'task_started' ? '🚀' : evt.type === 'task_complete' ? (evt.data?.success ? '✅' : '❌') : evt.type === 'chat_message' ? '💬' : evt.type === 'system_message' ? 'ℹ️' : '➜'
                  const label = evt.data?.agent || evt.data?.from || evt.type
                  const desc = evt.data?.prompt || evt.data?.content || (evt.data?.output_preview || '').slice(0, 50) || evt.type
                  return (
                    <div key={i} className="flex items-start gap-2 px-2 py-1 text-[10px] font-mono text-gray-500 bg-gray-50 rounded leading-relaxed">
                      <span className="flex-shrink-0">{icon}</span>
                      <span className="text-gray-400 flex-shrink-0">{label}</span>
                      <span className="truncate">{desc.slice(0, 40)}</span>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
