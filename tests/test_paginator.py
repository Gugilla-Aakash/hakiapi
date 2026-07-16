"""
Tests for the `paginate` generator in the paginator module.

These tests verify that:
- Link header pagination (GitHub-style) and token-based pagination
  (Twitter/X-style) both work correctly.
- Next page URLs are resolved using only the URL path, while query
  parameters are always passed through `params`.
- Path resolution behaves the same whether the next URL points to the
  same host or a different one.
- Link header pagination takes priority when both a Link header and a
  `next_token` are present.
- The `max_pages` limit stops pagination after the expected number of
  requests.
- Pagination ends when there are no more pages to fetch.
- Invalid response formats raise a `ValueError`.
- Initial query parameters are handled correctly for both dictionaries
  and lists of tuples, including duplicate keys.
- The `pagination_token` is updated between requests instead of being
  added multiple times.
- Any extra keyword arguments are passed through to `client._request`
  on every request.
"""

from typing import Any, Iterable
import pytest

from hakiapi.core.paginator import paginate
from hakiapi.core.base_client import BaseAPIClient


class FakeResponse:
    """Minimal stand-in for requests.Response."""

    def __init__(
        self, json_data: Any, links: dict[str, dict[str, str]] | None = None
    ) -> None:
        self._json_data = json_data
        self.links = links or {}

    def json(self) -> Any:
        return self._json_data


# 2. Inherit from BaseAPIClient to cast the type for the linter
class FakeClient(BaseAPIClient):
    """
    Minimal stand-in for BaseAPIClient. Responses are consumed in
    order from a queue, one per call to `_request`. Every call is
    recorded in `self.calls` for assertion.
    """

    def __init__(self, base_url: str, responses: Iterable[FakeResponse]) -> None:
        # We purposely do not call super().__init__() here to avoid
        # initializing actual network sessions.
        self.base_url = base_url
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def _request(
        self,
        method: str,
        endpoint: str,
        raw_response: bool = True,
        params: Any = None,
        **kwargs: Any,
    ) -> FakeResponse:
        self.calls.append(
            {
                "method": method,
                "endpoint": endpoint,
                "raw_response": raw_response,
                "params": params,
                "kwargs": kwargs,
            }
        )
        return self._responses.pop(0)


# Link-header (GitHub-style) pagination


def test_link_header_pagination_yields_all_items_in_order() -> None:
    responses = [
        FakeResponse(
            [{"id": 1}, {"id": 2}],
            links={"next": {"url": "https://api.example.com/items?page=2"}},
        ),
        FakeResponse([{"id": 3}], links={}),
    ]
    client = FakeClient("https://api.example.com/", responses)

    items = list(paginate(client, "items"))

    assert items == [{"id": 1}, {"id": 2}, {"id": 3}]
    assert len(client.calls) == 2


def test_link_header_pagination_stops_when_no_next_link() -> None:
    responses = [FakeResponse([{"id": 1}], links={})]
    client = FakeClient("https://api.example.com/", responses)

    items = list(paginate(client, "items"))

    assert items == [{"id": 1}]
    assert len(client.calls) == 1


def test_link_header_endpoint_is_path_only() -> None:
    responses = [
        FakeResponse(
            [{"id": 1}],
            links={"next": {"url": "https://api.example.com/items?page=2"}},
        ),
        FakeResponse([{"id": 2}], links={}),
    ]
    client = FakeClient("https://api.example.com/", responses)

    list(paginate(client, "items"))

    assert client.calls[1]["endpoint"] == "items"


def test_link_header_query_carried_only_in_params_not_endpoint() -> None:
    responses = [
        FakeResponse(
            [{"id": 1}],
            links={"next": {"url": "https://api.example.com/items?page=2&per_page=50"}},
        ),
        FakeResponse([{"id": 2}], links={}),
    ]
    client = FakeClient("https://api.example.com/", responses)

    list(paginate(client, "items"))

    assert client.calls[1]["params"] == [("page", "2"), ("per_page", "50")]
    assert "?" not in client.calls[1]["endpoint"]
    assert client.calls[1]["endpoint"] == "items"


def test_link_header_resolution_identical_across_hosts() -> None:
    same_host = [
        FakeResponse(
            [{"id": 1}],
            links={"next": {"url": "https://api.example.com/v2/items?page=2"}},
        ),
        FakeResponse([{"id": 2}], links={}),
    ]
    other_host = [
        FakeResponse(
            [{"id": 1}],
            links={"next": {"url": "https://cdn.other-host.com/v2/items?page=2"}},
        ),
        FakeResponse([{"id": 2}], links={}),
    ]

    client_a = FakeClient("https://api.example.com/", same_host)
    client_b = FakeClient("https://api.example.com/", other_host)

    list(paginate(client_a, "v2/items"))
    list(paginate(client_b, "v2/items"))

    assert client_a.calls[1]["endpoint"] == client_b.calls[1]["endpoint"] == "v2/items"
    assert client_a.calls[1]["params"] == client_b.calls[1]["params"] == [("page", "2")]


def test_link_header_root_path_strips_leading_slash() -> None:
    responses = [
        FakeResponse(
            [{"id": 1}], links={"next": {"url": "https://api.example.com/items"}}
        ),
        FakeResponse([{"id": 2}], links={}),
    ]
    client = FakeClient("https://api.example.com/", responses)

    list(paginate(client, "items"))

    assert not client.calls[1]["endpoint"].startswith("/")


# Cursor/token (Twitter-style) pagination


def test_cursor_pagination_yields_all_items_in_order() -> None:
    responses = [
        FakeResponse({"data": [{"id": 1}], "meta": {"next_token": "abc"}}),
        FakeResponse({"data": [{"id": 2}], "meta": {}}),
    ]
    client = FakeClient("https://api.example.com/", responses)

    items = list(paginate(client, "tweets"))

    assert items == [{"id": 1}, {"id": 2}]


def test_cursor_pagination_reuses_same_endpoint() -> None:
    responses = [
        FakeResponse({"data": [{"id": 1}], "meta": {"next_token": "abc"}}),
        FakeResponse({"data": [{"id": 2}], "meta": {}}),
    ]
    client = FakeClient("https://api.example.com/", responses)

    list(paginate(client, "tweets"))  # type: ignore

    assert client.calls[0]["endpoint"] == "tweets"
    assert client.calls[1]["endpoint"] == "tweets"


def test_cursor_pagination_appends_pagination_token_without_duplicating() -> None:
    responses = [
        FakeResponse({"data": [{"id": 1}], "meta": {"next_token": "abc"}}),
        FakeResponse({"data": [{"id": 2}], "meta": {"next_token": "def"}}),
        FakeResponse({"data": [{"id": 3}], "meta": {}}),
    ]
    client = FakeClient("https://api.example.com/", responses)

    list(paginate(client, "tweets", params={"query": "python"}))

    assert client.calls[0]["params"] == [("query", "python")]
    assert client.calls[1]["params"] == [
        ("query", "python"),
        ("pagination_token", "abc"),
    ]
    assert client.calls[2]["params"] == [
        ("query", "python"),
        ("pagination_token", "def"),
    ]


def test_cursor_pagination_stops_when_next_token_missing() -> None:
    responses = [FakeResponse({"data": [{"id": 1}], "meta": {}})]
    client = FakeClient("https://api.example.com/", responses)

    items = list(paginate(client, "tweets"))

    assert items == [{"id": 1}]
    assert len(client.calls) == 1


def test_cursor_pagination_stops_when_meta_missing_entirely() -> None:
    responses = [FakeResponse({"data": [{"id": 1}]})]
    client = FakeClient("https://api.example.com/", responses)

    items = list(paginate(client, "tweets"))

    assert items == [{"id": 1}]
    assert len(client.calls) == 1


def test_cursor_pagination_stops_when_next_token_is_empty_string() -> None:
    responses = [FakeResponse({"data": [{"id": 1}], "meta": {"next_token": ""}})]
    client = FakeClient("https://api.example.com/", responses)

    items = list(paginate(client, "tweets"))

    assert items == [{"id": 1}]
    assert len(client.calls) == 1


# Style precedence


def test_link_header_takes_precedence_over_next_token() -> None:
    responses = [
        FakeResponse(
            {"data": [{"id": 1}], "meta": {"next_token": "should-be-ignored"}},
            links={"next": {"url": "https://api.example.com/items?page=2"}},
        ),
        FakeResponse({"data": [{"id": 2}]}, links={}),
    ]
    client = FakeClient("https://api.example.com/", responses)

    list(paginate(client, "items"))

    assert client.calls[1]["endpoint"] == "items"
    assert "pagination_token" not in dict(client.calls[1]["params"])


# max_pages safety valve


def test_max_pages_none_is_unlimited_by_default() -> None:
    responses = [
        FakeResponse(
            [{"id": 1}],
            links={"next": {"url": "https://api.example.com/items?page=2"}},
        ),
        FakeResponse(
            [{"id": 2}],
            links={"next": {"url": "https://api.example.com/items?page=3"}},
        ),
        FakeResponse([{"id": 3}], links={}),
    ]
    client = FakeClient("https://api.example.com/", responses)

    items = list(paginate(client, "items"))

    assert items == [{"id": 1}, {"id": 2}, {"id": 3}]
    assert len(client.calls) == 3


def test_max_pages_limits_number_of_requests() -> None:
    responses = [
        FakeResponse(
            [{"id": 1}],
            links={"next": {"url": "https://api.example.com/items?page=2"}},
        ),
        FakeResponse(
            [{"id": 2}],
            links={"next": {"url": "https://api.example.com/items?page=3"}},
        ),
        FakeResponse([{"id": 3}], links={}),
    ]
    client = FakeClient("https://api.example.com/", responses)

    items = list(paginate(client, "items", max_pages=2))

    assert items == [{"id": 1}, {"id": 2}]
    assert len(client.calls) == 2


def test_max_pages_still_yields_items_from_the_final_allowed_page() -> None:
    responses = [
        FakeResponse(
            [{"id": 1}, {"id": 2}],
            links={"next": {"url": "https://api.example.com/items?page=2"}},
        ),
        FakeResponse([{"id": 3}], links={}),
    ]
    client = FakeClient("https://api.example.com/", responses)

    items = list(paginate(client, "items", max_pages=1))

    assert items == [{"id": 1}, {"id": 2}]
    assert len(client.calls) == 1


def test_max_pages_zero_makes_no_requests() -> None:
    client = FakeClient("https://api.example.com/", responses=[])

    items = list(paginate(client, "items", max_pages=0))

    assert items == []
    assert len(client.calls) == 0


def test_max_pages_applies_to_cursor_style_too() -> None:
    responses = [
        FakeResponse({"data": [{"id": 1}], "meta": {"next_token": "abc"}}),
        FakeResponse({"data": [{"id": 2}], "meta": {"next_token": "def"}}),
        FakeResponse({"data": [{"id": 3}], "meta": {}}),
    ]
    client = FakeClient("https://api.example.com/", responses)

    items = list(paginate(client, "tweets", max_pages=2))

    assert items == [{"id": 1}, {"id": 2}]
    assert len(client.calls) == 2


def test_max_pages_exactly_matching_available_pages_fetches_all() -> None:
    responses = [
        FakeResponse(
            [{"id": 1}],
            links={"next": {"url": "https://api.example.com/items?page=2"}},
        ),
        FakeResponse([{"id": 2}], links={}),
    ]
    client = FakeClient("https://api.example.com/", responses)

    items = list(paginate(client, "items", max_pages=2))

    assert items == [{"id": 1}, {"id": 2}]
    assert len(client.calls) == 2


# Malformed response bodies


def test_non_list_non_dict_body_raises_value_error() -> None:
    responses = [FakeResponse("not a list or dict")]
    client = FakeClient("https://api.example.com/", responses)

    with pytest.raises(ValueError):
        list(paginate(client, "items"))


def test_dict_without_data_key_raises_value_error() -> None:
    responses = [FakeResponse({"results": [{"id": 1}]})]
    client = FakeClient("https://api.example.com/", responses)

    with pytest.raises(ValueError):
        list(paginate(client, "items"))


def test_dict_with_non_list_data_raises_value_error() -> None:
    responses = [FakeResponse({"data": "not-a-list"})]
    client = FakeClient("https://api.example.com/", responses)

    with pytest.raises(ValueError):
        list(paginate(client, "items"))


def test_error_raised_lazily_on_first_iteration() -> None:
    responses = [FakeResponse({"bad": "shape"})]
    client = FakeClient("https://api.example.com/", responses)

    gen = paginate(client, "items")
    assert client.calls == []

    with pytest.raises(ValueError):
        next(gen)


# Params normalization


def test_no_initial_params_sends_none() -> None:
    responses = [FakeResponse([{"id": 1}], links={})]
    client = FakeClient("https://api.example.com/", responses)

    list(paginate(client, "items"))

    assert client.calls[0]["params"] is None


def test_dict_params_converted_to_list_of_tuples() -> None:
    responses = [FakeResponse([{"id": 1}], links={})]
    client = FakeClient("https://api.example.com/", responses)

    list(paginate(client, "items", params={"sort": "asc", "limit": 10}))

    assert client.calls[0]["params"] == [("sort", "asc"), ("limit", 10)]


def test_list_of_tuples_params_preserves_duplicate_keys() -> None:
    responses = [FakeResponse([{"id": 1}], links={})]
    client = FakeClient("https://api.example.com/", responses)

    dup_params = [("tag", "python"), ("tag", "testing")]
    list(paginate(client, "items", params=dup_params))

    assert client.calls[0]["params"] == dup_params


def test_empty_dict_params_sends_none() -> None:
    responses = [FakeResponse([{"id": 1}], links={})]
    client = FakeClient("https://api.example.com/", responses)

    list(paginate(client, "items", params={}))

    assert client.calls[0]["params"] is None


# kwargs forwarding


def test_extra_kwargs_forwarded_to_every_request() -> None:
    responses = [
        FakeResponse(
            [{"id": 1}],
            links={"next": {"url": "https://api.example.com/items?page=2"}},
        ),
        FakeResponse([{"id": 2}], links={}),
    ]
    client = FakeClient("https://api.example.com/", responses)

    list(paginate(client, "items", headers={"X-Test": "1"}, timeout=5))

    for call in client.calls:
        assert call["kwargs"] == {"headers": {"X-Test": "1"}, "timeout": 5}


def test_max_pages_not_forwarded_as_a_request_kwarg() -> None:
    responses = [FakeResponse([{"id": 1}], links={})]
    client = FakeClient("https://api.example.com/", responses)

    list(paginate(client, "items", max_pages=5))

    assert "max_pages" not in client.calls[0]["kwargs"]


def test_every_request_uses_get_and_raw_response_true() -> None:
    responses = [FakeResponse([{"id": 1}], links={})]
    client = FakeClient("https://api.example.com/", responses)

    list(paginate(client, "items"))

    assert client.calls[0]["method"] == "GET"
    assert client.calls[0]["raw_response"] is True


# Empty results


def test_empty_item_list_with_no_next_page_yields_nothing() -> None:
    responses = [FakeResponse([], links={})]
    client = FakeClient("https://api.example.com/", responses)

    items = list(paginate(client, "items"))

    assert items == []


def test_empty_page_followed_by_populated_page() -> None:
    responses = [
        FakeResponse(
            [], links={"next": {"url": "https://api.example.com/items?page=2"}}
        ),
        FakeResponse([{"id": 1}], links={}),
    ]
    client = FakeClient("https://api.example.com/", responses)

    items = list(paginate(client, "items"))

    assert items == [{"id": 1}]
