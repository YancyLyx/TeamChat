import { AGENT_NAMES } from '../constants/agents.js'

export function tokenTotal(tokenUsage = {}) {
  const input = Number(tokenUsage.input_tokens || tokenUsage.prompt_tokens || 0)
  const output = Number(tokenUsage.output_tokens || tokenUsage.completion_tokens || 0)
  const total = Number(tokenUsage.total_tokens || tokenUsage.tokens || 0)
  return total || input + output
}

export function formatTokens(value) {
  const tokens = Number(value || 0)
  if (tokens >= 1000000) return `${(tokens / 1000000).toFixed(1)}M`
  if (tokens >= 1000) return `${(tokens / 1000).toFixed(1)}K`
  return `${tokens}`
}

export function normalizeAgentMetrics(stats = {}, sessions = []) {
  const statsByAgent = stats.agents || {}
  return Object.fromEntries(AGENT_NAMES.map((name) => {
    const apiStats = statsByAgent[name] || {}
    const agentSessions = sessions.filter((s) => s.agent_name === name)
    const totalTasks = Number(apiStats.total_calls ?? agentSessions.length ?? 0)
    const successful = Number(apiStats.total_success ?? agentSessions.filter((s) => s.exit_code === 0).length)
    const successRate = totalTasks > 0
      ? Number(apiStats.success_rate ?? successful / totalTasks)
      : 0
    const avgDuration = Number(apiStats.avg_duration_ms ?? (
      agentSessions.length
        ? agentSessions.reduce((sum, s) => sum + Number(s.duration_ms || 0), 0) / agentSessions.length
        : 0
    ))
    const totalTokens = Number(apiStats.total_tokens ?? tokenTotal(apiStats.token_usage)) ||
      agentSessions.reduce((sum, s) => sum + tokenTotal(s.token_usage), 0)
    const toolCalls = Number(apiStats.tool_calls ?? 0)

    return [name, {
      total_tasks: totalTasks,
      total_success: successful,
      success_rate: successRate,
      avg_duration_ms: avgDuration,
      total_tokens: totalTokens,
      token_usage: apiStats.token_usage || {},
      tool_calls: toolCalls,
    }]
  }))
}

export function weeklySummary(agentMetrics = {}) {
  const values = AGENT_NAMES.map((name) => agentMetrics[name] || {})
  const totalTasks = values.reduce((sum, m) => sum + Number(m.total_tasks || 0), 0)
  const totalSuccess = values.reduce((sum, m) => sum + Number(m.total_success || 0), 0)
  const weightedDuration = values.reduce((sum, m) => (
    sum + Number(m.avg_duration_ms || 0) * Number(m.total_tasks || 0)
  ), 0)
  return {
    total_tasks: totalTasks,
    total_success: totalSuccess,
    success_rate: totalTasks ? totalSuccess / totalTasks : 0,
    avg_cycle_ms: totalTasks ? weightedDuration / totalTasks : 0,
    total_tokens: values.reduce((sum, m) => sum + Number(m.total_tokens || 0), 0),
  }
}

export function formatDuration(ms) {
  const value = Number(ms || 0)
  if (value <= 0) return '—'
  if (value < 60_000) return `${(value / 1000).toFixed(1)}s`
  if (value < 3_600_000) return `${(value / 60_000).toFixed(1)} min`
  return `${(value / 3_600_000).toFixed(1)} h`
}

export function liberationMetrics({ agentMetrics = {}, summary = {}, taskStats = null, humanMessages = 0 } = {}) {
  const automationRate = taskStats?.completion_rate != null
    ? taskStats.completion_rate * 100
    : (summary.success_rate || 0) * 100
  const manualInterventions = humanMessages + Object.values(agentMetrics)
    .reduce((sum, m) => sum + Number(m.tool_calls || 0), 0)
  return {
    automation_rate: automationRate,
    manual_interventions: manualInterventions,
    message_to_completion: formatDuration(summary.avg_cycle_ms),
  }
}
