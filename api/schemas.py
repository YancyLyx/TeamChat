"""
Pydantic models for TeamChat REST API and WebSocket messages.

Used for request validation, response serialization, and OpenAPI schema generation.
"""

from pydantic import BaseModel, Field


class AgentInfo(BaseModel):
    """Agent identity and current status."""
    name: str
    role: str
    cli: str
    is_busy: bool
    total_tasks: int = 0
    success_rate: float = 0.0
    avg_duration_ms: float = 0.0


class SessionRow(BaseModel):
    """One session record from the SQLite store."""
    id: int
    agent_name: str
    task_type: str
    prompt: str
    output: str
    exit_code: int
    duration_ms: int
    started_at: str
    finished_at: str
    tag: str = "prod"
    created_at: str

    @property
    def success(self) -> bool:
        return self.exit_code == 0

    @property
    def output_preview(self) -> str:
        return self.output[:200] + "..." if len(self.output) > 200 else self.output


class TaskRequest(BaseModel):
    """Submit a new task to an agent."""
    agent: str = Field(..., description="Agent name: cici咪, coco咪, or soso咪")
    prompt: str = Field(..., description="Task prompt for the agent")
    context: str = Field("", description="Optional context to prepend to the prompt")


class TaskResult(BaseModel):
    """Result from executing a task on an agent."""
    agent_name: str
    task_prompt: str
    output: str
    exit_code: int
    duration_ms: int
    token_usage: dict = Field(default_factory=dict)
    started_at: str = ""
    finished_at: str = ""

    @property
    def success(self) -> bool:
        return self.exit_code == 0


class StatsResponse(BaseModel):
    """Aggregated stats for all agents."""
    agents: dict[str, dict]


class WSMessage(BaseModel):
    """A WebSocket push message frame."""
    type: str = Field(..., description="Event type: task_started | task_complete | message | connected | pong")
    data: dict = Field(default_factory=dict)
