from collections.abc import Iterator
from typing import Any

from hakiapi.core.auth import BearerTokenAuth
from hakiapi.core.base_client import BaseAPIClient
from hakiapi.core.exceptions import HakiAPIError
from hakiapi.core.paginator import paginate


class GitHubClient(BaseAPIClient):
    def __init__(self, token: str | None = None, **kwargs: Any) -> None:
        auth_obj = BearerTokenAuth(token) if token else None

        super().__init__(
            base_url="https://api.github.com",
            auth=auth_obj,
            **kwargs,
        )

        self.session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "HakiAPI/0.1.0",
            }
        )

    # REST API: Profiles & Repositories
    def get_user(self, username: str, **kwargs: Any) -> dict[str, Any]:
        """Fetch a GitHub user's profile."""
        return self.get(f"users/{username}", **kwargs)

    def search_users(self, query: str, **kwargs: Any) -> dict[str, Any]:
        """
        Search GitHub users matching a query string.

        Returns the raw GitHub search response, e.g.:
        {"total_count": N, "incomplete_results": bool, "items": [...]}
        """
        params: dict[str, Any] = dict(kwargs.pop("params", None) or {})
        params["q"] = query

        return self.get("search/users", params=params, **kwargs)

    def get_all_search_users(
        self, query: str, **kwargs: Any
    ) -> Iterator[dict[str, Any]]:
        """
        Search GitHub users matching a query string, auto-paginating
        through every page of results.
        """
        params: dict[str, Any] = dict(kwargs.pop("params", None) or {})
        params["q"] = query

        yield from paginate(self, "search/users", params=params, **kwargs)

    def get_user_repos(self, username: str, **kwargs: Any) -> list[dict[str, Any]]:
        """Fetch a single page of public repositories of a GitHub user."""
        return self.get(f"users/{username}/repos", **kwargs)

    def get_all_user_repos(
        self, username: str, **kwargs: Any
    ) -> Iterator[dict[str, Any]]:
        """Fetch ALL public repositories using automatic pagination."""
        yield from paginate(self, f"users/{username}/repos", **kwargs)

    def get_repo_languages(
        self, owner: str, repo: str, **kwargs: Any
    ) -> dict[str, int]:
        """Fetch the exact byte breakdown of all languages used in a specific repository."""
        return self.get(f"repos/{owner}/{repo}/languages", **kwargs)

    def get_aggregate_user_languages(
        self, username: str, **kwargs: Any
    ) -> dict[str, int]:
        """
        Iterate through all of a user's repositories and get a repository-independent
        map of all languages used, down to the smallest byte.
        """
        aggregate_languages: dict[str, int] = {}
        repos = self.get_all_user_repos(username, **kwargs)

        for repo in repos:
            repo_name = repo.get("name")
            if not repo_name:
                continue

            try:
                languages = self.get_repo_languages(username, repo_name)
                for lang, bytes_count in languages.items():
                    aggregate_languages[lang] = (
                        aggregate_languages.get(lang, 0) + bytes_count
                    )
            except HakiAPIError:
                continue

        return aggregate_languages

    # REST API: Search & Activity

    def get_user_authored_activity(
        self, username: str, **kwargs: Any
    ) -> dict[str, Any]:
        """
        Fetches authored Pull Requests and Issues across GitHub for collaboration signals.
        Returns total counts and a short list of recent items for both.
        """
        pr_query = f"author:{username} type:pr"
        issue_query = f"author:{username} type:issue"

        # Fetch up to 5 recent PRs
        prs = self.get("search/issues", params={"q": pr_query, "per_page": 5}, **kwargs)
        # Fetch up to 5 recent issues
        issues = self.get(
            "search/issues", params={"q": issue_query, "per_page": 5}, **kwargs
        )

        return {
            "pull_requests": {
                "total_count": prs.get("total_count", 0),
                "recent_items": prs.get("items", []),
            },
            "issues": {
                "total_count": issues.get("total_count", 0),
                "recent_items": issues.get("items", []),
            },
        }

    # GraphQL Engine

    def execute_graphql(
        self, query: str, variables: dict[str, Any] | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        """
        The low-level execution engine for all GraphQL requests.
        Safely traps GraphQL '200 OK' payloads that contain hidden query errors.
        """
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        response_data = self.post("graphql", json=payload, **kwargs)

        # GraphQL notoriously returns 200 OK even if the query fails, putting the error in the body
        if "errors" in response_data:
            error_msgs = [
                err.get("message", "Unknown GraphQL error")
                for err in response_data["errors"]
            ]
            raise HakiAPIError(f"GraphQL Error(s): {', '.join(error_msgs)}")

        return response_data.get("data", {})

    def get_user_contributions(
        self,
        username: str,
        from_date: str | None = None,
        to_date: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Fetches contribution count and calendar data via GraphQL.
        Note: from_date and to_date must be ISO 8601 strings (e.g. '2023-01-01T00:00:00Z').
        """
        query = """
        query($login: String!, $from: DateTime, $to: DateTime) {
            user(login: $login) {
                contributionsCollection(from: $from, to: $to) {
                    contributionCalendar {
                        totalContributions
                    }
                    totalCommitContributions
                    totalIssueContributions
                    totalPullRequestContributions
                }
            }
        }
        """
        variables: dict[str, Any] = {"login": username}
        if from_date:
            variables["from"] = from_date
        if to_date:
            variables["to"] = to_date

        return self.execute_graphql(query, variables=variables, **kwargs)
