/**
 * DagGraph — 需求树（feature）的 DAG 可视化（ADR-005 Stats L2）。
 *
 * 数据驱动：完全由 nodes 数组渲染，tasks 变化（WS task_table_updated）→ 重绘。
 * 布局：按依赖深度分层（0 层 = 无依赖），同层横排；running 节点"亮灯"（呼吸动画）。
 */
import { useMemo } from 'react'

const NODE_COLORS = {
  done: '#22c55e',
  running: '#3b82f6',
  pending: '#d1d5db',
  failed: '#ef4444',
  abandoned: '#9ca3af',
}

// #97 方案 A：agent 颜色（避开状态色：绿done/蓝running/红failed/灰pending）
const AGENT_COLORS = {
  'cici咪': '#8b5cf6',   // 紫
  'coco咪': '#14b8a6',   // 青
  'soso咪': '#f59e0b',   // 橙
}

// 分层：BFS 按依赖深度（0 = 无依赖，n = 依赖链最长 n）
function computeLayers(nodes) {
  const byId = Object.fromEntries(nodes.map((n) => [n.id, n]))
  const depth = {}
  let changed = true
  while (changed) {
    changed = false
    for (const n of nodes) {
      if (n.id in depth) continue
      if (!n.depends_on || n.depends_on.length === 0) {
        depth[n.id] = 0
        changed = true
        continue
      }
      const deps = n.depends_on.filter((d) => d in depth)
      if (deps.length === n.depends_on.length) {
        depth[n.id] = 1 + Math.max(...deps.map((d) => depth[d]))
        changed = true
      }
    }
  }
  for (const n of nodes) if (!(n.id in depth)) depth[n.id] = 0
  const layers = []
  for (const n of nodes) {
    const d = depth[n.id]
    ;(layers[d] ||= []).push(n)
  }
  return { layers, depth, byId }
}

export default function DagGraph({ nodes, height = 120 }) {
  const { layers, depth, byId } = useMemo(() => computeLayers(nodes || []), [nodes])

  const W = 360
  const ROW = 26
  const NODE_R = 6
  const LAYER_X = 40 // 左侧留空间放标题

  if (!nodes || nodes.length === 0) return null

  // 坐标：y = 层 * ROW + 中心；x = 层内居中
  const pos = {}
  layers.forEach((layer, d) => {
    const n = layer.length
    layer.forEach((node, i) => {
      pos[node.id] = {
        x: LAYER_X + (W - LAYER_X - 20) * (n === 1 ? 0.5 : i / (n - 1)),
        y: d * ROW + 14,
      }
    })
  })

  // 连线：依赖 → 被依赖（下层 → 上层）
  const edges = []
  for (const n of nodes) {
    for (const depId of n.depends_on || []) {
      if (!pos[depId] || !pos[n.id]) continue
      const a = pos[depId]
      const b = pos[n.id]
      edges.push(
        <line key={`${depId}-${n.id}`} x1={a.x} y1={a.y} x2={b.x} y2={b.y}
          stroke="#cbd5e1" strokeWidth="1" />
      )
    }
  }

  const maxDepth = Math.max(0, ...layers.map((l, i) => (l.length ? i : 0)))
  const svgHeight = Math.max(height, maxDepth * ROW + 30)

  return (
    <svg width="100%" height={svgHeight} viewBox={`0 0 ${W} ${svgHeight}`} className="block">
      {edges}
      {nodes.map((n) => {
        const p = pos[n.id] || { x: 20, y: 10 }
        const color = NODE_COLORS[n.status] || '#d1d5db'
        const running = n.status === 'running'
        const agentColor = AGENT_COLORS[n.agent] || '#9ca3af'
        return (
          <g key={n.id}>
            {/* 审查/复审节点：虚线框（agent 色）——一眼看出验证链路 */}
            {(n.task_type === 'review' || n.task_type === 'verify') && (
              <circle cx={p.x} cy={p.y} r={NODE_R + 5} fill="none"
                stroke={agentColor} strokeWidth="1" strokeDasharray="3 2" />
            )}
            {/* agent 外圈（颜色区分谁在执行） */}
            <circle cx={p.x} cy={p.y} r={NODE_R + 1.5} fill="none"
              stroke={agentColor} strokeWidth="1.5" />
            <circle cx={p.x} cy={p.y} r={NODE_R} fill={color}
              className={running ? 'dag-running' : ''}>
              <title>{`#${n.id} ${n.title} (${n.agent}, ${n.status})`}</title>
            </circle>
            {/* 标注：只显示 #id（agent 由外圈颜色区分，不占文字空间） */}
            <text x={p.x + 10} y={p.y + 3} fontSize="8" fill={agentColor}
              fontFamily="monospace">
              #{n.id}
            </text>
          </g>
        )
      })}
      <style>{`
        .dag-running { animation: dagPulse 1.2s ease-in-out infinite; }
        @keyframes dagPulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.45; }
        }
      `}</style>
    </svg>
  )
}
