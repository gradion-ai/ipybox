from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, confloat

from . import CLIENT


class Params(BaseModel):
    model_config = ConfigDict(
        use_enum_values=True,
    )
    author: Optional[str] = None
    """
    Author username or email address to filter commits by
    """
    owner: str
    """
    Repository owner
    """
    page: Optional[confloat(ge=1.0)] = None
    """
    Page number for pagination (min 1)
    """
    perPage: Optional[confloat(ge=1.0, le=100.0)] = None
    """
    Results per page for pagination (min 1, max 100)
    """
    repo: str
    """
    Repository name
    """
    sha: Optional[str] = None
    """
    Commit SHA, branch or tag name to list commits of. If not provided, uses the default branch of the repository. If a commit SHA is provided, will list commits up to that SHA.
    """


def run(params: Params) -> str:
    """Get list of commits of a branch in a GitHub repository. Returns at least 30 results per page by default, but can return more if specified using the perPage parameter (up to 100)."""
    return CLIENT.run_sync(tool_name="list_commits", tool_args=params.model_dump(exclude_none=True))
