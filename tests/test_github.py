"""
Tests for `GitHubClient` in hakiapi/clients/github.py.
"""

from typing import Any
from unittest.mock import MagicMock, patch

from hakiapi.clients.github import GitHubClient
from hakiapi.core.exceptions import HakiAPIError


def _fake_base_init(
    self: Any, base_url: str | None = None, auth: Any = None, **kwargs: Any
) -> None:
    self.base_url = base_url
    self.auth = auth
    self.init_kwargs = kwargs
    self.session = MagicMock()


def _build_client(token: str | None = None, **kwargs: Any) -> Any:
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
    assert gh.auth is None


def test_init_with_token_creates_bearer_token_auth() -> None:
    with patch("hakiapi.clients.github.BearerTokenAuth") as mock_auth_cls:
        mock_auth_cls.return_value = "AUTH_OBJECT"
        gh = _build_client(token="secret-token")

    mock_auth_cls.assert_called_once_with("secret-token")
    assert gh.auth == "AUTH_OBJECT"


def test_init_forwards_extra_kwargs_to_base_client() -> None:
    gh = _build_client(token=None, timeout=15)
    assert getattr(gh, "init_kwargs", {}) == {"timeout": 15}


def test_init_sets_required_github_headers() -> None:
    gh = _build_client()

    mock_update = gh.session.headers.update
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


# search_users


def test_search_users_calls_get_with_correct_endpoint_and_query() -> None:
    gh = _build_client()
    with patch.object(
        gh, "get", return_value={"total_count": 1, "items": [{"login": "octocat"}]}
    ) as mock_get:
        result = gh.search_users("octocat")

        mock_get.assert_called_once_with("search/users", params={"q": "octocat"})
        assert result == {"total_count": 1, "items": [{"login": "octocat"}]}


def test_search_users_merges_extra_params_with_query() -> None:
    gh = _build_client()
    with patch.object(gh, "get", return_value={}) as mock_get:
        gh.search_users("octocat", params={"per_page": 5})

        mock_get.assert_called_once_with(
            "search/users", params={"per_page": 5, "q": "octocat"}
        )


def test_search_users_forwards_non_params_kwargs() -> None:
    gh = _build_client()
    with patch.object(gh, "get", return_value={}) as mock_get:
        gh.search_users("octocat", timeout=5)

        mock_get.assert_called_once_with(
            "search/users", params={"q": "octocat"}, timeout=5
        )


# get_all_search_users


def test_get_all_search_users_calls_paginate_with_query_param() -> None:
    gh = _build_client()

    # Using list() forces the lazy generator to execute and trigger paginate
    with patch(
        "hakiapi.clients.github.paginate", return_value=iter([{"login": "octocat"}])
    ) as mock_paginate:
        result = list(gh.get_all_search_users("octocat"))

    mock_paginate.assert_called_once_with(gh, "search/users", params={"q": "octocat"})
    assert result == [{"login": "octocat"}]


def test_get_all_search_users_merges_extra_params_with_query() -> None:
    gh = _build_client()
    with patch(
        "hakiapi.clients.github.paginate", return_value=iter([])
    ) as mock_paginate:
        list(gh.get_all_search_users("octocat", params={"per_page": 10}, max_pages=2))

    mock_paginate.assert_called_once_with(
        gh, "search/users", params={"per_page": 10, "q": "octocat"}, max_pages=2
    )


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

    with patch(
        "hakiapi.clients.github.paginate", return_value=iter([{"name": "repo1"}])
    ) as mock_paginate:
        result = list(gh.get_all_user_repos("octocat"))

    mock_paginate.assert_called_once_with(gh, "users/octocat/repos")
    assert result == [{"name": "repo1"}]


def test_get_all_user_repos_forwards_kwargs_to_paginate() -> None:
    gh = _build_client()

    with patch(
        "hakiapi.clients.github.paginate", return_value=iter([])
    ) as mock_paginate:
        list(gh.get_all_user_repos("octocat", params={"per_page": 5}, max_pages=2))

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
            # We now correctly throw the expected HakiAPIError here
            side_effect=[HakiAPIError("404 repo deleted"), {"Python": 42}],
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


# get_user_authored_activity


def test_get_user_authored_activity_fetches_prs_and_issues() -> None:
    gh = _build_client()

    pr_response = {
        "total_count": 2,
        "items": [{"title": "Fix bug"}, {"title": "Add feature"}],
    }
    issue_response = {
        "total_count": 1,
        "items": [{"title": "Report bug"}],
    }

    with patch.object(
        gh,
        "get",
        side_effect=[pr_response, issue_response],
    ) as mock_get:
        result = gh.get_user_authored_activity("octocat")

    assert mock_get.call_count == 2

    mock_get.assert_any_call(
        "search/issues",
        params={"q": "author:octocat type:pr", "per_page": 5},
    )
    mock_get.assert_any_call(
        "search/issues",
        params={"q": "author:octocat type:issue", "per_page": 5},
    )

    assert result == {
        "pull_requests": {
            "total_count": 2,
            "recent_items": pr_response["items"],
        },
        "issues": {
            "total_count": 1,
            "recent_items": issue_response["items"],
        },
    }


def test_get_user_authored_activity_forwards_kwargs() -> None:
    gh = _build_client()

    with patch.object(
        gh,
        "get",
        side_effect=[
            {"total_count": 0, "items": []},
            {"total_count": 0, "items": []},
        ],
    ) as mock_get:
        gh.get_user_authored_activity("octocat", timeout=10)

    assert mock_get.call_args_list[0].kwargs["timeout"] == 10
    assert mock_get.call_args_list[1].kwargs["timeout"] == 10


# execute_graphql


def test_execute_graphql_posts_query_and_returns_data() -> None:
    gh = _build_client()

    graphql_data = {"user": {"login": "octocat"}}

    with patch.object(
        gh,
        "post",
        return_value={"data": graphql_data},
    ) as mock_post:
        result = gh.execute_graphql("query { viewer { login } }")

    mock_post.assert_called_once_with(
        "graphql",
        json={"query": "query { viewer { login } }"},
    )
    assert result == graphql_data


def test_execute_graphql_includes_variables() -> None:
    gh = _build_client()

    variables = {"login": "octocat"}

    with patch.object(
        gh,
        "post",
        return_value={"data": {}},
    ) as mock_post:
        gh.execute_graphql("query Test {}", variables=variables)

    mock_post.assert_called_once_with(
        "graphql",
        json={
            "query": "query Test {}",
            "variables": variables,
        },
    )


def test_execute_graphql_raises_hakiapi_error_when_errors_present() -> None:
    gh = _build_client()

    with patch.object(
        gh,
        "post",
        return_value={
            "errors": [
                {"message": "Bad query"},
                {"message": "Unauthorized"},
            ]
        },
    ):
        try:
            gh.execute_graphql("query {}")
            assert False, "Expected HakiAPIError"
        except HakiAPIError as exc:
            assert str(exc) == "GraphQL Error(s): Bad query, Unauthorized"


def test_execute_graphql_uses_default_error_message() -> None:
    gh = _build_client()

    with patch.object(
        gh,
        "post",
        return_value={"errors": [{}]},
    ):
        try:
            gh.execute_graphql("query {}")
            assert False, "Expected HakiAPIError"
        except HakiAPIError as exc:
            assert str(exc) == "GraphQL Error(s): Unknown GraphQL error"


def test_execute_graphql_forwards_kwargs() -> None:
    gh = _build_client()

    with patch.object(
        gh,
        "post",
        return_value={"data": {}},
    ) as mock_post:
        gh.execute_graphql("query {}", timeout=5)

    mock_post.assert_called_once_with(
        "graphql",
        json={"query": "query {}"},
        timeout=5,
    )


# get_user_contributions


def test_get_user_contributions_calls_execute_graphql() -> None:
    gh = _build_client()

    expected = {"user": {"contributionsCollection": {}}}

    with patch.object(
        gh,
        "execute_graphql",
        return_value=expected,
    ) as mock_exec:
        result = gh.get_user_contributions("octocat")

    query = mock_exec.call_args.args[0]
    variables = mock_exec.call_args.kwargs["variables"]

    assert "contributionsCollection" in query
    assert variables == {"login": "octocat"}
    assert result == expected


def test_get_user_contributions_includes_date_filters() -> None:
    gh = _build_client()

    with patch.object(
        gh,
        "execute_graphql",
        return_value={},
    ) as mock_exec:
        gh.get_user_contributions(
            "octocat",
            from_date="2024-01-01T00:00:00Z",
            to_date="2024-12-31T23:59:59Z",
        )

    assert mock_exec.call_args.kwargs["variables"] == {
        "login": "octocat",
        "from": "2024-01-01T00:00:00Z",
        "to": "2024-12-31T23:59:59Z",
    }


def test_get_user_contributions_forwards_kwargs() -> None:
    gh = _build_client()

    with patch.object(
        gh,
        "execute_graphql",
        return_value={},
    ) as mock_exec:
        gh.get_user_contributions("octocat", timeout=15)

    assert mock_exec.call_args.kwargs["timeout"] == 15


def test_execute_graphql_omits_variables_when_none() -> None:
    gh = _build_client()

    with patch.object(
        gh,
        "post",
        return_value={"data": {}},
    ) as mock_post:
        gh.execute_graphql("query Test", variables=None)

    mock_post.assert_called_once_with(
        "graphql",
        json={"query": "query Test"},
    )


def test_get_user_contributions_only_includes_from_date() -> None:
    gh = _build_client()

    with patch.object(
        gh,
        "execute_graphql",
        return_value={},
    ) as mock_exec:
        gh.get_user_contributions(
            "octocat",
            from_date="2024-01-01T00:00:00Z",
        )

    query = mock_exec.call_args.args[0]
    variables = mock_exec.call_args.kwargs["variables"]

    assert "contributionsCollection" in query
    assert variables == {
        "login": "octocat",
        "from": "2024-01-01T00:00:00Z",
    }
