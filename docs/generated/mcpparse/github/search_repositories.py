import json

from mcptools.github.search_repositories import ParseResult, Repository


class SearchRepositoriesParseError(Exception):
    """Exception raised when parsing search_repositories results fails."""

    pass


def parse(result: str) -> ParseResult:
    """Parse search_repositories result into structured data.

    Args:
        result: Raw JSON string result from the tool

    Returns:
        ParseResult with structured repository search data

    Raises:
        SearchRepositoriesParseError: If parsing fails
    """
    try:
        data = json.loads(result)
    except json.JSONDecodeError as e:
        raise SearchRepositoriesParseError(f"Failed to parse JSON: {e}") from e

    try:
        repositories = [
            Repository(
                id=item["id"],
                name=item["name"],
                full_name=item["full_name"],
                description=item.get("description"),
                html_url=item["html_url"],
                language=item.get("language"),
                stargazers_count=item["stargazers_count"],
                forks_count=item["forks_count"],
                open_issues_count=item["open_issues_count"],
                updated_at=item["updated_at"],
                created_at=item["created_at"],
                private=item["private"],
                fork=item["fork"],
                archived=item["archived"],
                default_branch=item["default_branch"],
            )
            for item in data["items"]
        ]

        return ParseResult(
            total_count=data["total_count"],
            incomplete_results=data["incomplete_results"],
            repositories=repositories,
        )
    except KeyError as e:
        raise SearchRepositoriesParseError(f"Missing required field: {e}") from e
