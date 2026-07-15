/* ADR-003 Section 9 — Agent performance and weekly summary metrics. */

import { useEffect, useState } from 'react'
import { AGENT_EMOJI, UI_EMOJI } from '../constants/agents.js'

const API_BASE = '/api'

function Bar({ pct }) {
  const w = Math.max(Math.min(pct, 100), 0)
  return (
    <div className="w-full bg-gray-100 rounded-full h-2 overflow-hidden mt-1">
      <div className="h-full rounded-full bg-gradient-to-r from-blue-400 to-blue-500 transition-all duration-500" style={{ width: `${w}%` }} />
    </div>
  )
}

export default function StatsPanel() {
  const [stats, setStats] = useState(null)
  const [agents, setAgents] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const [sr, ar] = await Promise.all([
          fetch(`${API_BASE}/stats`),
          fetch(`${API_BASE}/agents`),
        ])
        if (!sr.ok || !ar.ok) throw new Error('API failed')
        const sd = await sr.json()
        const ad = await ar.json()
        if (!cancelled) {
          setStats(sd)
          setAgents(ad)
        }
      } catch { /* ignore */ }
      finally { if (!cancelled) setLoading(false) }
    }
    load()
    return () => { cancelled = true }
  }, [])

  if (loading) {
    return <div className="p-3 space-y-3"><div className="h-3 bg-gray-100 rounded animate-pulse w-16" /><div className="h-8 bg-gray-100 rounded animate-pulse" /><div className="h-8 bg-gray-100 rounded animate-pulse" /><div className="h-8 bg-gray-100 rounded animate-pulse" /></div>
  }

  const agentStats = stats?.agents || {}
  const names = ['cici咪', 'coco咪', 'soso咪']
  const totals = names.map((n) => agentStats[n]?.total_calls || 0)
  const totalDone = totals.reduce((a, b) => a + b, 0)

  return (
    <div className="p-3 space-y-4 bg-white">
      <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">📊 Stats</h3>

      {/* Agent Performance */}
      <div className="space-y-3">
        {names.map((name) => {
          const s = agentStats[name] || {}
          const calls = s.total_calls || 0
          const rate = s.success_rate || 0
          const pct = (rate * 100).toFixed(0)
          const avg = s.avg_duration_ms || 0
          return (
            <div key={name} className="bg-white border border-gray-100 rounded-lg p-3">
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-1.5">
                  <span className="text-sm">{AGENT_EMOJI[name]}</span>
                  <span className="text-xs font-semibold text-gray-700">{name}</span>
                  <span className="text-[10px] text-gray-400">{calls} tasks</span>
                </div>
                <span className={`text-xs font-mono font-bold ${rate >= 0.8 ? 'text-green-600' : 'text-yellow-600'}`}>{pct}%</span>
              </div>
              <Bar pct={rate * 100} />
              <div className="flex gap-3 mt-1 text-[10px] text-gray-400 font-mono">
                <span>avg {(avg / 1000).toFixed(1)}s</span>
              </div>
            </div>
          )
        })}
      </div>

      {/* Weekly Summary */}
      <div className="border-t border-gray-100 pt-3">
        <h4 className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-2">Weekly Summary</h4>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="bg-gray-50 rounded-lg p-2.5">
            <span className="text-gray-400 text-[10px]">Tasks Done</span>
            <p className="text-sm font-bold text-gray-700 mt-0.5">{totalDone}</p>
          </div>
          <div className="bg-gray-50 rounded-lg p-2.5">
            <span className="text-gray-400 text-[10px]">Success Rate</span>
            <p className="text-sm font-bold text-green-600 mt-0.5">{names.length > 0 ? (agentStats[names[0]]?.success_rate * 100 || 0).toFixed(0) : 0}%</p>
          </div>
          <div className="bg-gray-50 rounded-lg p-2.5">
            <span className="text-gray-400 text-[10px]">Avg Cycle</span>
            <p className="text-sm font-bold text-gray-700 mt-0.5">--</p>
          </div>
          <div className="bg-gray-50 rounded-lg p-2.5">
            <span className="text-gray-400 text-[10px]">Automation</span>
            <p className="text-sm font-bold text-blue-600 mt-0.5">--</p>
          </div>
        </div>
      </div>
    </div>
  )
}
