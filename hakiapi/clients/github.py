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

    # REST API: README Existence Check

    def check_readme_exists(self, owner: str, repo_name: str, **kwargs: Any) -> bool:
        """
        Check if a repository has a README using GitHub's canonical README REST endpoint.
        Returns True if HTTP 200, False if HTTP 404 or error.
        """
        try:
            response = self._request(
                "HEAD",
                f"repos/{owner}/{repo_name}/readme",
                raw_response=True,
                timeout=kwargs.pop("timeout", 5.0),
                **kwargs,
            )
            return response.status_code == 200
        except Exception:
            return False

    def check_top_repos_readmes(
        self, owner: str, repos: list[dict[str, Any]], top_n: int = 5, **kwargs: Any
    ) -> dict[str, bool]:
        """
        Check README presence for the top N owned (non-forked) repos sorted by stars.
        Returns a dict mapping repo_name -> has_readme (bool).
        """
        owned_repos = [r for r in repos if not r.get("fork", False)]
        top_repos = sorted(
            owned_repos,
            key=lambda r: r.get("stargazers_count", 0),
            reverse=True,
        )[:top_n]

        results = {}
        for r in top_repos:
            repo_name = r.get("name")
            if repo_name:
                results[repo_name] = self.check_readme_exists(
                    owner, repo_name, **kwargs
                )
        return results

    # GraphQL Engine & Advanced Profile Fetching

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
        Fetch 365-day contribution calendar (including weekly breakdown)
        and lifetime PR/issue counts via GraphQL.
        Note: from_date and to_date must be ISO 8601 strings (e.g. '2023-01-01T00:00:00Z').
        """
        query = """
        query($login: String!, $from: DateTime, $to: DateTime) {
            user(login: $login) {
                contributionsCollection(from: $from, to: $to) {
                    contributionCalendar {
                        totalContributions
                        weeks {
                            contributionDays {
                                contributionCount
                                date
                            }
                        }
                    }
                }
                pullRequests(first: 5, orderBy: {field: CREATED_AT, direction: DESC}) {
                    totalCount
                    nodes {
                        title
                        url
                        createdAt
                        repository {
                            name
                        }
                    }
                }
                issues(first: 5, orderBy: {field: CREATED_AT, direction: DESC}) {
                    totalCount
                    nodes {
                        title
                        url
                        createdAt
                        repository {
                            name
                        }
                    }
                }
            }
        }
        """
        variables: dict[str, Any] = {"login": username}
        if from_date:
            variables["from"] = from_date
        if to_date:
            variables["to"] = to_date

        data = self.execute_graphql(query, variables=variables, **kwargs)
        user_data = data.get("user")
        if not user_data:
            return {}

        calendar = user_data.get("contributionsCollection", {}).get(
            "contributionCalendar", {}
        )
        prs = user_data.get("pullRequests", {})
        issues = user_data.get("issues", {})

        return {
            "recent_contributions_365_days": {
                "total_contributions": calendar.get("totalContributions", 0),
                "weeks": calendar.get("weeks", []),
            },
            "lifetime_activity": {
                "pull_requests": {
                    "total_count": prs.get("totalCount", 0),
                    "recent_items": prs.get("nodes", []),
                },
                "issues": {
                    "total_count": issues.get("totalCount", 0),
                    "recent_items": issues.get("nodes", []),
                },
            },
        }

    def fetch_full_profile_data(self, username: str, **kwargs: Any) -> dict[str, Any]:
        """Fetch and aggregate all profile data from GraphQL and REST API."""
        contrib_data = self.get_user_contributions(username, **kwargs)

        # Fetch up to 100 recent updated repositories via REST
        repos = self.get_user_repos(
            username, params={"per_page": 100, "sort": "updated"}, **kwargs
        )

        # Build language breakdown
        lang_breakdown: dict[str, int] = {}
        for r in repos:
            lang = r.get("language")
            if lang:
                lang_breakdown[lang] = lang_breakdown.get(lang, 0) + 1

        # Check README presence for top 5 owned repos
        readme_statuses = self.check_top_repos_readmes(
            username, repos, top_n=5, **kwargs
        )

        # Attach has_readme flag directly onto repository objects
        for r in repos:
            r_name = r.get("name")
            if r_name in readme_statuses:
                r["has_readme"] = readme_statuses[r_name]
            else:
                r["has_readme"] = None  # Not checked (outside top N)

        return {
            "username": username,
            "repositories": {
                "items": repos,
                "language_breakdown": lang_breakdown,
            },
            "recent_contributions_365_days": contrib_data.get(
                "recent_contributions_365_days", {}
            ),
            "lifetime_activity": contrib_data.get("lifetime_activity", {}),
            "readme_statuses": readme_statuses,
        }
