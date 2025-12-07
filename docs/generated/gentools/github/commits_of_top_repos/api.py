from __future__ import annotations

from pydantic import BaseModel, Field


class CommitInfo(BaseModel):
    """Information about a single commit."""

    sha: str = Field(..., title="Short SHA")
    message: str = Field(..., title="First line of commit message")
    url: str = Field(..., title="Link to commit on GitHub")


class RepoCommits(BaseModel):
    """Repository with its latest commits."""

    name: str = Field(..., title="Repository name")
    stars: int = Field(..., title="Star count")
    commits: list[CommitInfo] = Field(..., title="Latest commits")


def run(
    username: str,
    top_n_repos: int = 3,
    last_n_commits: int = 5,
) -> list[RepoCommits]:
    """Get latest commits from a GitHub user's most starred repositories.

    Args:
        username: GitHub username to search repos for
        top_n_repos: Number of top repos to fetch (default: 3)
        last_n_commits: Number of latest commits per repo (default: 5)

    Returns:
        List of RepoCommits with repo info and latest commits
    """
    from .impl import get_commits_of_top_repos

    return get_commits_of_top_repos(username, top_n_repos, last_n_commits)
