/* ADR-003 Section 8/9 — Agent performance, process efficiency, and human liberation metrics. */
/* L1/L2/L3 sub-tabs per Issue #71 spec. */

import { useEffect, useState } from 'react'
import { AGENT_EMOJI, AGENT_NAMES } from '../constants/agents.js'
import { formatTokens, weeklySummary, liberationMetrics } from '../utils/metrics.js'

const API_BASE = '/api'

function Bar({ pct }) {
  const w = Math.max(Math.min(pct, 100), 0)
  return (
    <div className="w-full bg-gray-100 rounded-full h-2 overflow-hidden mt-1">
      <div className="h-full rounded-full bg-gradient-to-r from-blue-400 to-blue-500 transition-all duration-500" style={{ width: `${w}%` }} />
    </div>
  )
}

export default function StatsPanel({ agentMetrics = {} }) {
  const [subTab, setSubTab] = useState('L1')
  const [engine, setEngine] = useState(null)
  const [taskStats, setTaskStats] = useState(null)
  const [humanMessages, setHumanMessages] = useState(0)
  const [loadingL2, setLoadingL2] = useState(true)
  const [features, setFeatures] = useState([])
  const [featuresLoading, setFeaturesLoading] = useState(false)
  const summary = weeklySummary(agentMetrics)
  const liberation = liberationMetrics({ agentMetrics, summary, taskStats, humanMessages })

  useEffect(() => {
    if (subTab !== 'FEAT') return
    let cancelled = false
    setFeaturesLoading(true)
    ;(async () => {
      try {
        const res = await fetch(`${API_BASE}/tasks/features?teamchat_session_id=1`)
        if (!cancelled && res.ok) {
          const data = await res.json()
          setFeatures(data.features || [])
        }
      } catch { /* ignore */ }
      finally { if (!cancelled) setFeaturesLoading(false) }
    })()
    return () => { cancelled = true }
  }, [subTab])

  useEffect(() => {
    if (subTab !== 'L3') return
    let cancelled = false
    ;(async () => {
      try {
        const res = await fetch(`${API_BASE}/sessions?limit=200`)
        if (!cancelled && res.ok) {
          const rows = await res.json()
          setHumanMessages(rows.filter((s) => s.agent_name === 'human').length)
        }
      } catch { /* ignore */ }
    })()
    return () => { cancelled = true }
  }, [subTab])

  useEffect(() => {
    if (subTab !== 'L2') return
    let cancelled = false
    setLoadingL2(true)
    ;(async () => {
      try {
        const [er, tr] = await Promise.all([
          fetch(`${API_BASE}/engine`),
          fetch(`${API_BASE}/tasks/table/stats`),
        ])
        if (!cancelled) {
          setEngine(er.ok ? await er.json() : null)
          setTaskStats(tr.ok ? await tr.json() : null)
        }
      } catch { /* ignore */ }
      finally { if (!cancelled) setLoadingL2(false) }
    })()
    return () => { cancelled = true }
  }, [subTab])

  return (
    <div className="p-3 space-y-4 bg-white">
      {/* Sub-tab nav：L1 效能 / L2 流程 / L3 解放 / 📦 Features（需求树聚合） */}
      <div className="flex border-b border-gray-100 -mx-3 px-3">
        {['L1', 'L2', 'L3', 'FEAT'].map((tab) => (
          <button key={tab} onClick={() => setSubTab(tab)}
            className={`flex-1 text-xs py-1.5 font-medium transition-colors ${subTab === tab ? 'text-blue-600 border-b-2 border-blue-500' : 'text-gray-400 hover:text-gray-600'}`}>
            {tab === 'L1' ? 'L1 效能' : tab === 'L2' ? 'L2 流程' : tab === 'L3' ? 'L3 解放' : '📦 Features'}
          </button>
        ))}
      </div>

      {/* L1 — Agent Performance */}
      {subTab === 'L1' && (
        <div className="space-y-3">
          {AGENT_NAMES.map((name) => {
            const s = agentMetrics[name] || {}
            const calls = s.total_tasks || 0
            const rate = s.success_rate || 0
            const pct = (rate * 100).toFixed(0)
            const avg = s.avg_duration_ms || 0
            const tokens = s.total_tokens || 0
            const toolCalls = s.tool_calls || 0
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
                <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-1 text-[10px] text-gray-400 font-mono">
                  <span>avg {(avg / 1000).toFixed(1)}s</span>
                  <span>{formatTokens(tokens)} tokens</span>
                  <span>{toolCalls} tool calls</span>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* L2 — Process Efficiency */}
      {subTab === 'L2' && (
        <div className="space-y-3">
          {loadingL2 ? (
            <div className="space-y-2"><div className="h-3 bg-gray-100 rounded animate-pulse w-12" /><div className="h-8 bg-gray-100 rounded animate-pulse" /><div className="h-8 bg-gray-100 rounded animate-pulse" /></div>
          ) : (
            <>
              <div className="bg-gray-50 rounded-lg p-2.5 space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-gray-400 font-semibold uppercase">Engine Mode</span>
                  <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-semibold ${engine?.mode === 'serial' ? 'bg-yellow-100 text-yellow-700' : 'bg-green-100 text-green-700'}`}>
                    {engine?.mode === 'serial' ? 'Serial' : 'Parallel'}
                  </span>
                </div>
                <p className="text-[10px] text-gray-400 font-mono">queue: {engine?.queue_length ?? 0}</p>
              </div>
              <div className="bg-gray-50 rounded-lg p-2.5 space-y-1.5">
                <p className="text-[10px] text-gray-400 font-semibold uppercase">Task Stats</p>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="bg-white rounded-lg p-2"><span className="text-gray-400 text-[10px]">Total</span><p className="text-sm font-bold text-gray-700">{taskStats?.total || 0}</p></div>
                  <div className="bg-white rounded-lg p-2"><span className="text-gray-400 text-[10px]">Done</span><p className="text-sm font-bold text-green-600">{taskStats?.done || 0}</p></div>
                  <div className="bg-white rounded-lg p-2"><span className="text-gray-400 text-[10px]">Pending</span><p className="text-sm font-bold text-yellow-600">{taskStats?.pending || 0}</p></div>
                  <div className="bg-white rounded-lg p-2"><span className="text-gray-400 text-[10px]">Running</span><p className="text-sm font-bold text-blue-600">{taskStats?.running || 0}</p></div>
                </div>
                <p className="text-[10px] text-gray-400 font-mono">completion: {((taskStats?.completion_rate || 0) * 100).toFixed(0)}%</p>
              </div>
            </>
          )}
        </div>
      )}

      {/* L3 — Human Liberation */}
      {subTab === 'L3' && (
        <div className="space-y-3">
          <div className="bg-gray-50 rounded-lg p-2.5 space-y-1.5">
            <p className="text-[10px] text-gray-400 font-semibold uppercase">Human Liberation</p>
            <div className="bg-white rounded-lg p-2.5 space-y-2 text-xs">
              <div><span className="text-gray-400">Automation Rate</span><div className="flex items-center gap-2 mt-0.5"><Bar pct={liberation.automation_rate} /><span className="text-xs font-bold text-gray-700 font-mono">{liberation.automation_rate.toFixed(0)}%</span></div></div>
              <div><span className="text-gray-400">Manual Interventions</span><p className="text-sm font-bold text-gray-700 mt-0.5">{liberation.manual_interventions}</p></div>
              <div><span className="text-gray-400">Message to Completion</span><p className="text-sm font-bold text-gray-700 mt-0.5">{liberation.message_to_completion}</p></div>
            </div>
          </div>
        </div>
      )}

      {/* 📦 Features — 需求树聚合（feature_id） */}
      {subTab === 'FEAT' && (
        <div className="space-y-3">
          {featuresLoading ? (
            <div className="space-y-2"><div className="h-3 bg-gray-100 rounded animate-pulse w-16" /><div className="h-12 bg-gray-100 rounded animate-pulse" /></div>
          ) : features.length === 0 ? (
            <p className="text-xs text-gray-400 text-center py-6">暂无需求树</p>
          ) : (
            features.map((f) => (
              <div key={f.feature_id} className="bg-white border border-gray-100 rounded-lg p-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-semibold text-gray-700 truncate max-w-[70%]" title={f.title}>{f.title}</span>
                  <span className="text-[10px] text-gray-400 font-mono">{f.total} 节点 · 深度 {f.depth}</span>
                </div>
                <Bar pct={f.completion_rate * 100} />
                <div className="flex flex-wrap gap-x-2 gap-y-0.5 mt-1 text-[10px] text-gray-400 font-mono">
                  <span className="text-green-600">done {f.done}</span>
                  <span className="text-red-600">failed {f.failed}</span>
                  <span className="text-gray-500">放弃 {f.abandoned}</span>
                  <span className="text-blue-600">running {f.running}</span>
                  <span className="text-yellow-600">pending {f.pending}</span>
                  <span className="ml-auto">完成率 {(f.completion_rate * 100).toFixed(0)}%</span>
                </div>
                {f.duration_sec > 0 && (
                  <p className="text-[10px] text-gray-400 font-mono mt-0.5">总时长 {(f.duration_sec / 60).toFixed(0)}min</p>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {/* Weekly Summary */}
      <div className="border-t border-gray-100 pt-3">
        <h4 className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-2">Weekly Summary</h4>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="bg-gray-50 rounded-lg p-2.5">
            <span className="text-gray-400 text-[10px]">Tasks Done</span>
            <p className="text-sm font-bold text-gray-700 mt-0.5">{summary.total_success}</p>
          </div>
          <div className="bg-gray-50 rounded-lg p-2.5">
            <span className="text-gray-400 text-[10px]">Success Rate</span>
            <p className="text-sm font-bold text-green-600 mt-0.5">{(summary.success_rate * 100).toFixed(0)}%</p>
          </div>
          <div className="bg-gray-50 rounded-lg p-2.5">
            <span className="text-gray-400 text-[10px]">Avg Cycle</span>
            <p className="text-sm font-bold text-gray-700 mt-0.5">{(summary.avg_cycle_ms / 1000).toFixed(1)}s</p>
          </div>
          <div className="bg-gray-50 rounded-lg p-2.5">
            <span className="text-gray-400 text-[10px]">Tokens</span>
            <p className="text-sm font-bold text-blue-600 mt-0.5">{formatTokens(summary.total_tokens)}</p>
          </div>
        </div>
      </div>
    </div>
  )
}
