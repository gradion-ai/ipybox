from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, confloat

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
