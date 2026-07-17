"""
Tests for `GitHubClient` in hakiapi/clients/github.py.
"""

from typing import Any
from unittest.mock import MagicMock, patch

from hakiapi.clients.github import GitHubClient


def _fake_base_init(
    self: Any, base_url: str | None = None, auth: Any = None, **kwargs: Any
) -> None:
    self.base_url = base_url
    self.auth = auth
    self.init_kwargs = kwargs
    self.session = MagicMock()


def _build_client(token: str | None = None, **kwargs: Any) -> GitHubClient:
    with patch("hakiapi.core.base_client.BaseAPIClient.__init__", new=_fake_base_init):
        return GitHubClient(token=token, **kwargs)


# Construction


def test_init_sets_github_base_url() -> None:
    gh = _build_client()
    assert gh.base_url == "https://api.github.com"


def test_init_without_token_creates_no_auth() -> None:
    with patch("hakiapi.clients.github.BearerTokenAuth") as mock_auth_cls:
        gh = _build_client(token=None)

    mock_auth_cls.assert_not_called()
    assert getattr(gh, "auth") is None


def test_init_with_token_creates_bearer_token_auth() -> None:
    with patch("hakiapi.clients.github.BearerTokenAuth") as mock_auth_cls:
        mock_auth_cls.return_value = "AUTH_OBJECT"
        gh = _build_client(token="secret-token")

    mock_auth_cls.assert_called_once_with("secret-token")
    assert getattr(gh, "auth") == "AUTH_OBJECT"


def test_init_forwards_extra_kwargs_to_base_client() -> None:
    gh = _build_client(token=None, timeout=15)
    assert getattr(gh, "init_kwargs", {}) == {"timeout": 15}


def test_init_sets_required_github_headers() -> None:
    gh = _build_client()

    mock_update = getattr(gh.session.headers, "update")
    mock_update.assert_called_once_with(
        {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "HakiAPI/0.1.0",
        }
    )


# get_user


def test_get_user_calls_get_with_correct_endpoint() -> None:
    gh = _build_client()
    with patch.object(gh, "get", return_value={"login": "octocat"}) as mock_get:
        result = gh.get_user("octocat")

        mock_get.assert_called_once_with("users/octocat")
        assert result == {"login": "octocat"}


def test_get_user_forwards_kwargs() -> None:
    gh = _build_client()
    with patch.object(gh, "get", return_value={}) as mock_get:
        gh.get_user("octocat", timeout=5)

        mock_get.assert_called_once_with("users/octocat", timeout=5)


# get_user_repos


def test_get_user_repos_calls_get_with_correct_endpoint() -> None:
    gh = _build_client()
    with patch.object(gh, "get", return_value=[{"name": "repo1"}]) as mock_get:
        result = gh.get_user_repos("octocat")

        mock_get.assert_called_once_with("users/octocat/repos")
        assert result == [{"name": "repo1"}]


def test_get_user_repos_forwards_kwargs() -> None:
    gh = _build_client()
    with patch.object(gh, "get", return_value=[]) as mock_get:
        gh.get_user_repos("octocat", params={"per_page": 100})

        mock_get.assert_called_once_with(
            "users/octocat/repos", params={"per_page": 100}
        )


# get_repo_languages


def test_get_repo_languages_calls_get_with_correct_endpoint() -> None:
    gh = _build_client()
    with patch.object(gh, "get", return_value={"Python": 1000}) as mock_get:
        result = gh.get_repo_languages("octocat", "hello-world")

        mock_get.assert_called_once_with("repos/octocat/hello-world/languages")
        assert result == {"Python": 1000}


# get_all_user_repos


def test_get_all_user_repos_calls_paginate_with_client_and_endpoint() -> None:
    gh = _build_client()
    sentinel = iter([{"name": "repo1"}])

    with patch(
        "hakiapi.clients.github.paginate", return_value=sentinel
    ) as mock_paginate:
        result = gh.get_all_user_repos("octocat")

    mock_paginate.assert_called_once_with(gh, "users/octocat/repos")
    assert result is sentinel


def test_get_all_user_repos_forwards_kwargs_to_paginate() -> None:
    gh = _build_client()

    with patch(
        "hakiapi.clients.github.paginate", return_value=iter([])
    ) as mock_paginate:
        gh.get_all_user_repos("octocat", params={"per_page": 5}, max_pages=2)

    mock_paginate.assert_called_once_with(
        gh, "users/octocat/repos", params={"per_page": 5}, max_pages=2
    )


# get_aggregate_user_languages


def test_aggregate_languages_sums_byte_counts_across_repos() -> None:
    gh = _build_client()
    with (
        patch.object(
            gh,
            "get_all_user_repos",
            return_value=iter([{"name": "repo1"}, {"name": "repo2"}]),
        ),
        patch.object(
            gh,
            "get_repo_languages",
            side_effect=[{"Python": 100, "HTML": 20}, {"Python": 50, "CSS": 10}],
        ),
    ):
        result = gh.get_aggregate_user_languages("octocat")

        assert result == {"Python": 150, "HTML": 20, "CSS": 10}


def test_aggregate_languages_calls_get_repo_languages_with_username_as_owner() -> None:
    gh = _build_client()
    with (
        patch.object(gh, "get_all_user_repos", return_value=iter([{"name": "repo1"}])),
        patch.object(gh, "get_repo_languages", return_value={}) as mock_get_lang,
    ):
        gh.get_aggregate_user_languages("octocat")

        mock_get_lang.assert_called_once_with("octocat", "repo1")


def test_aggregate_languages_skips_repos_missing_name_key() -> None:
    gh = _build_client()
    with (
        patch.object(
            gh, "get_all_user_repos", return_value=iter([{"id": 1}, {"name": "repo2"}])
        ),
        patch.object(
            gh, "get_repo_languages", return_value={"Python": 10}
        ) as mock_get_lang,
    ):
        result = gh.get_aggregate_user_languages("octocat")

        mock_get_lang.assert_called_once_with("octocat", "repo2")
        assert result == {"Python": 10}


def test_aggregate_languages_skips_repos_with_falsy_name() -> None:
    gh = _build_client()
    with (
        patch.object(
            gh,
            "get_all_user_repos",
            return_value=iter([{"name": ""}, {"name": "repo2"}]),
        ),
        patch.object(
            gh, "get_repo_languages", return_value={"Python": 10}
        ) as mock_get_lang,
    ):
        result = gh.get_aggregate_user_languages("octocat")

        mock_get_lang.assert_called_once_with("octocat", "repo2")
        assert result == {"Python": 10}


def test_aggregate_languages_continues_past_a_single_repo_failure() -> None:
    gh = _build_client()
    with (
        patch.object(
            gh,
            "get_all_user_repos",
            return_value=iter([{"name": "broken-repo"}, {"name": "good-repo"}]),
        ),
        patch.object(
            gh,
            "get_repo_languages",
            side_effect=[RuntimeError("404 repo deleted"), {"Python": 42}],
        ) as mock_get_lang,
    ):
        result = gh.get_aggregate_user_languages("octocat")

        assert result == {"Python": 42}
        assert mock_get_lang.call_count == 2


def test_aggregate_languages_returns_empty_dict_when_no_repos() -> None:
    gh = _build_client()
    with (
        patch.object(gh, "get_all_user_repos", return_value=iter([])),
        patch.object(gh, "get_repo_languages") as mock_get_lang,
    ):
        result = gh.get_aggregate_user_languages("octocat")

        assert result == {}
        mock_get_lang.assert_not_called()


def test_aggregate_languages_forwards_kwargs_to_get_all_user_repos() -> None:
    gh = _build_client()
    with patch.object(gh, "get_all_user_repos", return_value=iter([])) as mock_get_all:
        gh.get_aggregate_user_languages("octocat", params={"per_page": 5})

        mock_get_all.assert_called_once_with("octocat", params={"per_page": 5})


def test_aggregate_languages_does_not_forward_kwargs_to_get_repo_languages() -> None:
    gh = _build_client()
    with (
        patch.object(gh, "get_all_user_repos", return_value=iter([{"name": "repo1"}])),
        patch.object(gh, "get_repo_languages", return_value={}) as mock_get_lang,
    ):
        gh.get_aggregate_user_languages("octocat", params={"per_page": 5}, timeout=10)

        mock_get_lang.assert_called_once_with("octocat", "repo1")
