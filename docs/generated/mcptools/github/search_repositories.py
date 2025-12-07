from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, confloat

from . import CLIENT


class Order(Enum):
    asc = "asc"
    desc = "desc"


class Sort(Enum):
    stars = "stars"
    forks = "forks"
    help_wanted_issues = "help-wanted-issues"
    updated = "updated"


class Params(BaseModel):
    model_config = ConfigDict(
        use_enum_values=True,
    )
    minimal_output: Optional[bool] = True
    """
    Return minimal repository information (default: true). When false, returns full GitHub API repository objects.
    """
    order: Optional[Order] = None
    """
    Sort order
    """
    page: Optional[confloat(ge=1.0)] = None
    """
    Page number for pagination (min 1)
    """
    perPage: Optional[confloat(ge=1.0, le=100.0)] = None
    """
    Results per page for pagination (min 1, max 100)
    """
    query: str
    """
    Repository search query. Examples: 'machine learning in:name stars:>1000 language:python', 'topic:react', 'user:facebook'. Supports advanced search syntax for precise filtering.
    """
    sort: Optional[Sort] = None
    """
    Sort repositories by field, defaults to best match
    """


def run(params: Params) -> str:
    """Find GitHub repositories by name, description, readme, topics, or other metadata. Perfect for discovering projects, finding examples, or locating specific repositories across GitHub."""
    return CLIENT.run_sync(tool_name="search_repositories", tool_args=params.model_dump(exclude_none=True))


class Repository(BaseModel):
    """A GitHub repository from search results."""

    model_config = ConfigDict(
        use_enum_values=True,
    )
    id: int = Field(..., title="Repository ID")
    name: str = Field(..., title="Repository Name")
    full_name: str = Field(..., title="Full Name")
    description: str | None = Field(None, title="Description")
    html_url: str = Field(..., title="HTML URL")
    language: str | None = Field(None, title="Primary Language")
    stargazers_count: int = Field(..., title="Stars")
    forks_count: int = Field(..., title="Forks")
    open_issues_count: int = Field(..., title="Open Issues")
    updated_at: str = Field(..., title="Last Updated")
    created_at: str = Field(..., title="Created At")
    private: bool = Field(..., title="Is Private")
    fork: bool = Field(..., title="Is Fork")
    archived: bool = Field(..., title="Is Archived")
    default_branch: str = Field(..., title="Default Branch")


class ParseResult(BaseModel):
    """Parsed result containing structured repository search data."""

    model_config = ConfigDict(
        use_enum_values=True,
    )
    total_count: int = Field(..., title="Total Count")
    incomplete_results: bool = Field(..., title="Incomplete Results")
    repositories: list[Repository] = Field(..., title="Repositories")


def run_parsed(params: Params) -> ParseResult:
    """Run tool and return parsed structured data.

    Args:
        params: Tool parameters

    Returns:
        ParseResult with structured repository search data
    """
    from mcpparse.github.search_repositories import parse

    result = run(params)
    return parse(result)
