from __future__ import annotations

import json

from mcptools.github import list_commits, search_repositories

from .api import CommitInfo, RepoCommits


def get_commits_of_top_repos(
    username: str,
    top_n_repos: int,
    last_n_commits: int,
) -> list[RepoCommits]:
    """Fetch top repos by stars and their latest commits."""
    # Get user's repos sorted by stars
    repos_result = search_repositories.run_parsed(
        search_repositories.Params(
            query=f"user:{username}",
            sort=search_repositories.Sort.stars,
            order=search_repositories.Order.desc,
            perPage=top_n_repos,
        )
    )

    result = []
    for repo in repos_result.repositories[:top_n_repos]:
        # Get latest commits for this repo
        commits_raw = list_commits.run(
            list_commits.Params(
                owner=username,
                repo=repo.name,
                perPage=last_n_commits,
            )
        )

        commits_data = json.loads(commits_raw)
        commits = [
            CommitInfo(
                sha=c["sha"][:7],
                message=c["commit"]["message"].split("\n")[0],
                url=c["html_url"],
            )
            for c in commits_data[:last_n_commits]
        ]

        result.append(
            RepoCommits(
                name=repo.name,
                stars=repo.stargazers_count,
                commits=commits,
            )
        )

    return result
