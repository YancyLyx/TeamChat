"""
GitHub Adapter — Agent-native GitHub API client.

Allows each agent to act on GitHub under their own identity:
  - Create / list / assign Issues
  - Create PRs, post reviews
  - Handle webhook events (Phase 4)
"""

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from engine.config import AgentIdentity, Config, ALL_AGENTS

logger = logging.getLogger(__name__)

# ---- Data types ----


@dataclass
class IssueInfo:
    number: int
    title: str
    state: str       # "open" | "closed"
    url: str
    assignee: str | None = None
    labels: list[str] | None = None
    body: str = ""


@dataclass
class PRInfo:
    number: int
    title: str
    state: str       # "open" | "closed" | "merged"
    url: str
    head_branch: str
    base_branch: str
    author: str = ""
    body: str = ""


# ---- Client ----


class GitHubClient:
    """Thin wrapper around GitHub REST API with per-agent authentication."""

    BASE_URL = "https://api.github.com"

    def __init__(self, config: Config, agent: AgentIdentity):
        self.config = config
        self.agent = agent
        self._token = config.get_token(agent)
        self._client: httpx.AsyncClient | None = None
        self._repo_path = f"/repos/{config.repo_owner}/{config.repo_name}"

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                    "User-Agent": f"TeamChat/{self.agent.cli}",
                },
                timeout=30.0,
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    # ---- Issues ----

    async def create_issue(self, title: str, body: str = "",
                           labels: list[str] | None = None,
                           assignee: str | None = None) -> IssueInfo:
        """Create a GitHub Issue. Returns the created issue info."""
        payload: dict[str, Any] = {"title": title, "body": body}
        if labels:
            payload["labels"] = labels
        if assignee:
            payload["assignees"] = [assignee]

        resp = await self.client.post(f"{self._repo_path}/issues", json=payload)
        resp.raise_for_status()
        data = resp.json()

        issue = IssueInfo(
            number=data["number"],
            title=data["title"],
            state=data["state"],
            url=data["html_url"],
            assignee=data.get("assignee", {}).get("login") if data.get("assignee") else None,
            labels=[lb["name"] for lb in data.get("labels", [])],
            body=data.get("body", ""),
        )
        logger.info(f"📝 {self.agent.name} created Issue #{issue.number}: {issue.title}")
        return issue

    async def list_issues(self, state: str = "open",
                          labels: str | None = None) -> list[IssueInfo]:
        """List repo issues."""
        params: dict[str, str] = {"state": state}
        if labels:
            params["labels"] = labels

        resp = await self.client.get(f"{self._repo_path}/issues", params=params)
        resp.raise_for_status()

        return [
            IssueInfo(
                number=item["number"],
                title=item["title"],
                state=item["state"],
                url=item["html_url"],
                assignee=item.get("assignee", {}).get("login") if item.get("assignee") else None,
                labels=[lb["name"] for lb in item.get("labels", [])],
                body=item.get("body", ""),
            )
            for item in resp.json()
            if "pull_request" not in item  # filter out PRs
        ]

    async def comment_on_issue(self, issue_number: int, body: str):
        """Post a comment on an issue."""
        resp = await self.client.post(
            f"{self._repo_path}/issues/{issue_number}/comments",
            json={"body": body},
        )
        resp.raise_for_status()
        logger.info(f"💬 {self.agent.name} commented on Issue #{issue_number}")

    async def close_issue(self, issue_number: int):
        """Close an issue."""
        resp = await self.client.patch(
            f"{self._repo_path}/issues/{issue_number}",
            json={"state": "closed"},
        )
        resp.raise_for_status()
        logger.info(f"🔒 {self.agent.name} closed Issue #{issue_number}")

    # ---- Pull Requests ----

    async def create_pr(self, title: str, head: str, base: str = "main",
                        body: str = "") -> PRInfo:
        """Create a pull request."""
        resp = await self.client.post(
            f"{self._repo_path}/pulls",
            json={"title": title, "head": head, "base": base, "body": body},
        )
        resp.raise_for_status()
        data = resp.json()

        pr = PRInfo(
            number=data["number"],
            title=data["title"],
            state=data["state"],
            url=data["html_url"],
            head_branch=data["head"]["ref"],
            base_branch=data["base"]["ref"],
            author=data["user"]["login"],
            body=data.get("body", ""),
        )
        logger.info(f"🔀 {self.agent.name} created PR #{pr.number}: {pr.title}")
        return pr

    async def list_prs(self, state: str = "open") -> list[PRInfo]:
        """List pull requests."""
        resp = await self.client.get(
            f"{self._repo_path}/pulls", params={"state": state}
        )
        resp.raise_for_status()

        return [
            PRInfo(
                number=item["number"],
                title=item["title"],
                state=item["state"],
                url=item["html_url"],
                head_branch=item["head"]["ref"],
                base_branch=item["base"]["ref"],
                author=item["user"]["login"],
                body=item.get("body", ""),
            )
            for item in resp.json()
        ]

    async def merge_pr(self, pr_number: int, method: str = "squash"):
        """Merge a pull request."""
        resp = await self.client.put(
            f"{self._repo_path}/pulls/{pr_number}/merge",
            json={"merge_method": method},
        )
        resp.raise_for_status()
        logger.info(f"✅ {self.agent.name} merged PR #{pr_number}")

    async def request_review(self, pr_number: int, reviewers: list[str]):
        """Request review from specific GitHub users."""
        resp = await self.client.post(
            f"{self._repo_path}/pulls/{pr_number}/requested_reviewers",
            json={"reviewers": reviewers},
        )
        resp.raise_for_status()
        logger.info(f"👀 {self.agent.name} requested review on PR #{pr_number} from {reviewers}")


# ---- Factory ----


def create_github_client(config: Config, agent: AgentIdentity) -> GitHubClient:
    """Create a GitHub client for a specific agent."""
    token = config.get_token(agent)
    if not token:
        raise ValueError(
            f"No GitHub token found for {agent.name}. "
            f"Set {agent.token_env} environment variable."
        )
    return GitHubClient(config, agent)
