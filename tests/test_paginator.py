"""
Tests for paginator.paginate().
"""

from typing import Any, Optional
from unittest.mock import MagicMock
import pytest
from hakiapi.core.paginator import paginate

# Helpers


class FakeResponse:
    """Mimics the bits of requests.Response that paginate() touches."""

    def __init__(
        self, json_data: Any, links: Optional[dict[str, dict[str, str]]] = None
    ) -> None:
        self._json_data = json_data
        self.links = links or {}

    def json(self) -> Any:
        return self._json_data


@pytest.fixture
def mock_client() -> MagicMock:
    client = MagicMock()
    return client


def call_kwargs(mock_client: MagicMock, call_index: int) -> dict[str, Any]:
    return mock_client._request.call_args_list[call_index].kwargs


def call_params_dict(mock_client: MagicMock, call_index: int) -> dict[str, Any]:
    """params are passed as a list of tuples (or None); normalize to a dict for easy asserts."""
    params = call_kwargs(mock_client, call_index)["params"]
    return dict(params) if params else {}


# GitHub-style pagination (Link header, bare list responses)


class TestGitHubStylePagination:
    def test_single_page_no_link_header(self, mock_client: MagicMock) -> None:
        mock_client._request.return_value = FakeResponse([{"id": 1}, {"id": 2}])

        items = list(paginate(mock_client, "repos/x/x/issues"))

        assert items == [{"id": 1}, {"id": 2}]
        assert mock_client._request.call_count == 1

    def test_follows_link_header_across_pages(self, mock_client: MagicMock) -> None:
        mock_client._request.side_effect = [
            FakeResponse(
                [{"id": 1}],
                links={
                    "next": {
                        "url": "https://api.github.com/repos/x/x/issues?page=2&per_page=30"
                    }
                },
            ),
            FakeResponse(
                [{"id": 2}],
                links={
                    "next": {
                        "url": "https://api.github.com/repos/x/x/issues?page=3&per_page=30"
                    }
                },
            ),
            FakeResponse([{"id": 3}]),  # no "next" -> stop
        ]

        items = list(paginate(mock_client, "repos/x/x/issues"))

        assert items == [{"id": 1}, {"id": 2}, {"id": 3}]
        assert mock_client._request.call_count == 3

    def test_link_header_endpoint_and_params_extracted_correctly(
        self, mock_client: MagicMock
    ) -> None:
        mock_client._request.side_effect = [
            FakeResponse(
                [{"id": 1}],
                links={
                    "next": {
                        "url": "https://api.github.com/repos/x/x/issues?page=2&per_page=30"
                    }
                },
            ),
            FakeResponse([{"id": 2}]),
        ]

        list(paginate(mock_client, "repos/x/x/issues"))

        args = mock_client._request.call_args_list[1].args
        assert args[1] == "repos/x/x/issues"
        assert call_params_dict(mock_client, 1) == {"page": "2", "per_page": "30"}

    def test_initial_params_preserved_on_first_call(
        self, mock_client: MagicMock
    ) -> None:
        mock_client._request.return_value = FakeResponse([{"id": 1}])

        list(paginate(mock_client, "repos/x/x/issues", params={"state": "open"}))

        assert call_params_dict(mock_client, 0) == {"state": "open"}


# Twitter-style pagination (data / meta.next_token)


class TestTwitterStylePagination:
    def test_follows_next_token(self, mock_client: MagicMock) -> None:
        mock_client._request.side_effect = [
            FakeResponse({"data": [{"id": "t1"}], "meta": {"next_token": "TOK_A"}}),
            FakeResponse({"data": [{"id": "t2"}], "meta": {"next_token": "TOK_B"}}),
            FakeResponse({"data": [{"id": "t3"}], "meta": {}}),
        ]

        items = list(paginate(mock_client, "tweets/search/recent"))

        assert items == [{"id": "t1"}, {"id": "t2"}, {"id": "t3"}]
        assert mock_client._request.call_count == 3

    def test_pagination_token_updates_without_duplicating(
        self, mock_client: MagicMock
    ) -> None:
        mock_client._request.side_effect = [
            FakeResponse({"data": [{"id": "t1"}], "meta": {"next_token": "TOK_A"}}),
            FakeResponse({"data": [{"id": "t2"}], "meta": {"next_token": "TOK_B"}}),
            FakeResponse({"data": [{"id": "t3"}], "meta": {}}),
        ]

        list(paginate(mock_client, "tweets/search/recent", params={"query": "python"}))

        # page 1: no pagination_token yet, original query param present
        assert call_params_dict(mock_client, 0) == {"query": "python"}
        # page 2: token from page 1's response, query param still present (not dropped)
        assert call_params_dict(mock_client, 1) == {
            "query": "python",
            "pagination_token": "TOK_A",
        }
        # page 3: token updated to TOK_B, not duplicated, query still present
        assert call_params_dict(mock_client, 2) == {
            "query": "python",
            "pagination_token": "TOK_B",
        }

    def test_endpoint_unchanged_across_pages(self, mock_client: MagicMock) -> None:
        mock_client._request.side_effect = [
            FakeResponse({"data": [{"id": "t1"}], "meta": {"next_token": "TOK_A"}}),
            FakeResponse({"data": [{"id": "t2"}], "meta": {}}),
        ]

        list(paginate(mock_client, "tweets/search/recent"))

        endpoints = [c.args[1] for c in mock_client._request.call_args_list]
        assert endpoints == ["tweets/search/recent", "tweets/search/recent"]


# Google-style pagination (messages / nextPageToken)


class TestGoogleStylePagination:
    def test_follows_next_page_token(self, mock_client: MagicMock) -> None:
        mock_client._request.side_effect = [
            FakeResponse({"messages": [{"id": "m1"}], "nextPageToken": "PT_A"}),
            FakeResponse({"messages": [{"id": "m2"}], "nextPageToken": "PT_B"}),
            FakeResponse({"messages": [{"id": "m3"}]}),
        ]

        items = list(paginate(mock_client, "users/me/messages"))

        assert items == [{"id": "m1"}, {"id": "m2"}, {"id": "m3"}]
        assert mock_client._request.call_count == 3

    def test_query_param_survives_pagetoken_updates(
        self, mock_client: MagicMock
    ) -> None:
        """The exact bug class we hit in GmailClient.list() -- here it's
        handled correctly since existing params are preserved, only
        'pageToken' is swapped out."""
        mock_client._request.side_effect = [
            FakeResponse({"messages": [{"id": "m1"}], "nextPageToken": "PT_A"}),
            FakeResponse({"messages": [{"id": "m2"}], "nextPageToken": "PT_B"}),
            FakeResponse({"messages": [{"id": "m3"}]}),
        ]

        list(paginate(mock_client, "users/me/messages", params={"q": "is:unread"}))

        for i in range(3):
            assert call_params_dict(mock_client, i)["q"] == "is:unread"
        assert "pageToken" not in call_params_dict(mock_client, 0)
        assert call_params_dict(mock_client, 1)["pageToken"] == "PT_A"
        assert call_params_dict(mock_client, 2)["pageToken"] == "PT_B"


# max_pages safety valve


class TestMaxPages:
    def test_stops_after_max_pages(self, mock_client: MagicMock) -> None:
        def infinite_pages(*_args: Any, **_kwargs: Any) -> FakeResponse:
            return FakeResponse(
                {"messages": [{"id": "x"}], "nextPageToken": "ALWAYS_MORE"}
            )

        mock_client._request.side_effect = infinite_pages

        items = list(paginate(mock_client, "users/me/messages", max_pages=3))

        assert len(items) == 3
        assert mock_client._request.call_count == 3

    def test_max_pages_zero_fetches_nothing(self, mock_client: MagicMock) -> None:
        items = list(paginate(mock_client, "users/me/messages", max_pages=0))

        assert items == []
        mock_client._request.assert_not_called()

    def test_max_pages_none_is_unbounded_default(self, mock_client: MagicMock) -> None:
        mock_client._request.side_effect = [
            FakeResponse({"messages": [{"id": "1"}], "nextPageToken": "A"}),
            FakeResponse({"messages": [{"id": "2"}], "nextPageToken": "B"}),
            FakeResponse({"messages": [{"id": "3"}]}),
        ]

        items = list(paginate(mock_client, "users/me/messages"))

        assert len(items) == 3

    def test_max_pages_larger_than_available_pages_fetches_all(
        self, mock_client: MagicMock
    ) -> None:
        mock_client._request.side_effect = [
            FakeResponse({"messages": [{"id": "1"}], "nextPageToken": "A"}),
            FakeResponse({"messages": [{"id": "2"}]}),
        ]

        items = list(paginate(mock_client, "users/me/messages", max_pages=10))

        assert len(items) == 2
        assert mock_client._request.call_count == 2


# Response shape handling / errors


class TestResponseShapeHandling:
    def test_bare_list_response(self, mock_client: MagicMock) -> None:
        mock_client._request.return_value = FakeResponse([{"id": 1}])

        items = list(paginate(mock_client, "some/endpoint"))

        assert items == [{"id": 1}]

    def test_dict_without_data_or_messages_raises(self, mock_client: MagicMock) -> None:
        mock_client._request.return_value = FakeResponse({"unexpected": "shape"})

        with pytest.raises(ValueError, match="expected a list response"):
            list(paginate(mock_client, "some/endpoint"))

    def test_non_list_non_dict_response_raises(self, mock_client: MagicMock) -> None:
        mock_client._request.return_value = FakeResponse("just a string")

        with pytest.raises(ValueError, match="Unexpected response format"):
            list(paginate(mock_client, "some/endpoint"))

    def test_empty_items_list_with_no_continuation_stops(
        self, mock_client: MagicMock
    ) -> None:
        mock_client._request.return_value = FakeResponse({"messages": []})

        items = list(paginate(mock_client, "users/me/messages"))

        assert items == []
        assert mock_client._request.call_count == 1

    def test_empty_page_but_token_present_continues(
        self, mock_client: MagicMock
    ) -> None:
        """An empty page shouldn't stop pagination if the API still hands back a token."""
        mock_client._request.side_effect = [
            FakeResponse({"messages": [], "nextPageToken": "A"}),
            FakeResponse({"messages": [{"id": "1"}]}),
        ]

        items = list(paginate(mock_client, "users/me/messages"))

        assert items == [{"id": "1"}]
        assert mock_client._request.call_count == 2


# Request construction


class TestRequestConstruction:
    def test_uses_get_and_raw_response(self, mock_client: MagicMock) -> None:
        mock_client._request.return_value = FakeResponse([{"id": 1}])

        list(paginate(mock_client, "some/endpoint"))

        call = mock_client._request.call_args_list[0]
        assert call.args[0] == "GET"
        assert call.args[1] == "some/endpoint"
        assert call.kwargs["raw_response"] is True

    def test_extra_kwargs_forwarded_every_call(self, mock_client: MagicMock) -> None:
        mock_client._request.side_effect = [
            FakeResponse(
                [{"id": 1}], links={"next": {"url": "https://api.github.com/x?page=2"}}
            ),
            FakeResponse([{"id": 2}]),
        ]

        list(paginate(mock_client, "x", timeout=5))

        for call in mock_client._request.call_args_list:
            assert call.kwargs["timeout"] == 5

    def test_no_params_sends_none(self, mock_client: MagicMock) -> None:
        mock_client._request.return_value = FakeResponse([{"id": 1}])

        list(paginate(mock_client, "some/endpoint"))

        assert call_kwargs(mock_client, 0)["params"] is None

    def test_accepts_params_as_list_of_tuples(self, mock_client: MagicMock) -> None:
        mock_client._request.return_value = FakeResponse([{"id": 1}])

        list(
            paginate(
                mock_client,
                "some/endpoint",
                params=[("state", "open"), ("state", "closed")],
            )
        )

        params = call_kwargs(mock_client, 0)["params"]
        assert ("state", "open") in params
        assert ("state", "closed") in params
