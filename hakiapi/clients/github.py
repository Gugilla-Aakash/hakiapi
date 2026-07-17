from typing import Any, Iterator

from hakiapi.core.base_client import BaseAPIClient
from hakiapi.core.auth import BearerTokenAuth
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

    def get_user_repos(self, username: str, **kwargs: Any) -> list[dict[str, Any]]:
        """Fetch a single page of public repositories of a GitHub user."""
        return self.get(f"users/{username}/repos", **kwargs)

    def get_all_user_repos(
        self, username: str, **kwargs: Any
    ) -> Iterator[dict[str, Any]]:
        """Fetch ALL public repositories using automatic pagination."""
        return paginate(self, f"users/{username}/repos", **kwargs)

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
            except Exception:
                # Shield the iteration sequence if a single repo is deleted or inaccessible
                continue

        return aggregate_languages
