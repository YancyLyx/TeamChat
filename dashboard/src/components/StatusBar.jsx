import AgentCard from './AgentCard.jsx'

export default function StatusBar({ agents, sessionsByAgent }) {
  if (!agents || agents.length === 0) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="bg-gray-800/50 border border-gray-700/30 rounded-lg p-4 animate-pulse">
            <div className="h-4 bg-gray-700/50 rounded w-20 mb-3" />
            <div className="h-6 bg-gray-700/50 rounded w-32 mb-2" />
            <div className="h-3 bg-gray-700/50 rounded w-24" />
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {agents.map((agent) => (
        <AgentCard
          key={agent.name}
          agent={agent}
          sessions={sessionsByAgent[agent.name] || []}
        />
      ))}
    </div>
  )
}
