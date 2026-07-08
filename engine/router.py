"""
Task Router — Declarative task-to-agent routing.

Rules match task types to the best agent. Supports:
  - Direct assignment (human-specified)
  - Rule-based auto-routing (task type → best agent)
  - Load-aware dispatching (skip busy agents)
"""

import logging
from dataclasses import dataclass, field
from enum import Enum

from engine.config import AgentIdentity, AGENT_CICI, AGENT_COCO, AGENT_SOSO

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """Categories of work that an agent can do."""
    ARCHITECTURE = "architecture"       # Design docs, ADRs, spec writing
    CORE_ENGINE = "core_engine"         # Router, Runner, Message Bus internals
    FRONTEND = "frontend"               # Dashboard UI, React components
    API = "api"                         # FastAPI routes, WebSocket
    TESTING = "testing"                 # Tests, E2E, CI
    GITHUB_INTEGRATION = "github"       # GitHub API, webhooks, automation
    DOCS = "docs"                       # README, role cards, documentation
    BUGFIX = "bugfix"                   # General bug fixes
    REVIEW = "review"                   # Code review, PR inspection


# ---- Routing rules: TaskType → best agent ----

DEFAULT_ROUTES: dict[TaskType, AgentIdentity] = {
    TaskType.ARCHITECTURE:        AGENT_CICI,
    TaskType.CORE_ENGINE:         AGENT_CICI,
    TaskType.FRONTEND:            AGENT_COCO,
    TaskType.API:                 AGENT_COCO,
    TaskType.TESTING:             AGENT_SOSO,
    TaskType.GITHUB_INTEGRATION:  AGENT_SOSO,
    TaskType.DOCS:                AGENT_CICI,
    TaskType.BUGFIX:              AGENT_SOSO,
    TaskType.REVIEW:              AGENT_SOSO,
}


@dataclass
class DispatchResult:
    """Result of a routing decision."""
    agent: AgentIdentity
    task_type: TaskType
    reason: str


class Router:
    """Declarative task router — maps task types to best-fit agents."""

    def __init__(self, routes: dict[TaskType, AgentIdentity] | None = None):
        self.routes = routes or dict(DEFAULT_ROUTES)
        self._busy: set[str] = set()      # agents currently working

    # ---- Routing ----

    def dispatch(self, task_type: TaskType | str,
                 preferred_agent: AgentIdentity | None = None) -> DispatchResult:
        """
        Route a task to the best agent.

        Args:
            task_type: The kind of work (architecture, frontend, testing, etc.)
            preferred_agent: If set, skip routing and assign directly to this agent

        Returns:
            DispatchResult with the chosen agent and reasoning
        """
        # Direct assignment overrides routing
        if preferred_agent is not None:
            return DispatchResult(
                agent=preferred_agent,
                task_type=TaskType(task_type) if isinstance(task_type, str) else task_type,
                reason="Direct human assignment",
            )

        # Normalize to enum
        if isinstance(task_type, str):
            try:
                task_type = TaskType(task_type)
            except ValueError:
                # Unknown type → default to architect
                task_type = TaskType.ARCHITECTURE

        # Look up best agent
        agent = self.routes.get(task_type, AGENT_CICI)

        return DispatchResult(
            agent=agent,
            task_type=task_type,
            reason=f"Route: {task_type.value} → {agent.name} ({agent.role})",
        )

    def dispatch_batch(self, tasks: list[tuple[TaskType | str, AgentIdentity | None]]
                       ) -> list[DispatchResult]:
        """Route multiple tasks at once."""
        return [
            self.dispatch(task_type=t, preferred_agent=a)
            for t, a in tasks
        ]

    # ---- Load management ----

    def mark_busy(self, agent: AgentIdentity):
        """Mark an agent as busy (currently handling a task)."""
        self._busy.add(agent.name)
        logger.debug(f"🔴 {agent.name} marked busy")

    def mark_free(self, agent: AgentIdentity):
        """Mark an agent as free."""
        self._busy.discard(agent.name)
        logger.debug(f"🟢 {agent.name} marked free")

    def is_busy(self, agent: AgentIdentity) -> bool:
        return agent.name in self._busy

    def available_agents(self) -> list[AgentIdentity]:
        """All agents that are not currently busy."""
        all_agents = list(self.routes.values())
        # deduplicate
        seen = set()
        result = []
        for a in all_agents:
            if a.name not in seen and not self.is_busy(a):
                seen.add(a.name)
                result.append(a)
        return result

    # ---- Config ----

    def set_route(self, task_type: TaskType, agent: AgentIdentity):
        """Override a routing rule."""
        self.routes[task_type] = agent

    def show_routes(self) -> str:
        """Human-readable route table."""
        lines = ["Task Router — Route Table:", "-" * 50]
        for tt, agent in self.routes.items():
            lines.append(f"  {tt.value:20s} → {agent.name} ({agent.role})")
        return "\n".join(lines)
