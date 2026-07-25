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

    def get_user(self, username: str, **kwargs: Any) -> dict[str, Any]:
        """Fetch a GitHub user's profile."""
        return self.get(f"users/{username}", **kwargs)

    def search_users(self, query: str, **kwargs: Any) -> dict[str, Any]:
        """
        Search GitHub users matching a query string.

        Returns the raw GitHub search response, e.g.:
        {"total_count": N, "incomplete_results": bool, "items": [...]}
        """
        # Safely cast to a dictionary, protecting against list-of-tuples
        params: dict[str, Any] = dict(kwargs.pop("params", None) or {})
        params["q"] = query

        return self.get("search/users", params=params, **kwargs)

    def get_all_search_users(
        self, query: str, **kwargs: Any
    ) -> Iterator[dict[str, Any]]:
        """
        Search GitHub users matching a query string, auto-paginating
        through every page of results (GitHub's Link-header pagination).
        """
        params: dict[str, Any] = dict(kwargs.pop("params", None) or {})
        params["q"] = query

        # Delegated directly to the paginator using yield from
        yield from paginate(self, "search/users", params=params, **kwargs)

    def get_user_repos(self, username: str, **kwargs: Any) -> list[dict[str, Any]]:
        """Fetch a single page of public repositories of a GitHub user."""
        return self.get(f"users/{username}/repos", **kwargs)

    def get_all_user_repos(
        self, username: str, **kwargs: Any
    ) -> Iterator[dict[str, Any]]:
        """Fetch ALL public repositories using automatic pagination."""
        # Delegated directly to the paginator using yield from
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

        # Pull all repos lazily via our paginator engine
        repos = self.get_all_user_repos(username, **kwargs)

        for repo in repos:
            repo_name = repo.get("name")
            if not repo_name:
                continue

            try:
                # Query the specific byte-breakdown for this exact repo pointer
                languages = self.get_repo_languages(username, repo_name)
                for lang, bytes_count in languages.items():
                    aggregate_languages[lang] = (
                        aggregate_languages.get(lang, 0) + bytes_count
                    )
            except HakiAPIError:
                # Shield the iteration sequence if a single repo is deleted or inaccessible
                continue

        return aggregate_languages
