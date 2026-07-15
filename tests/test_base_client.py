"""
Test suite for base_client.py
"""

from typing import Any
from unittest.mock import MagicMock, patch
import json as json_mod

import pytest
import requests
from requests.adapters import HTTPAdapter

# FIXED: Corrected the linkage paths to point to the `core` module
from hakiapi.core import base_client
from hakiapi.core.base_client import BaseAPIClient
from hakiapi.core.exceptions import (
    HakiAPIError,
    ClientError,
    ServerError,
    RateLimitError,
    AuthenticationError,
    RequestTimeoutError,
)


def make_response(
    status_code: int = 200,
    json_data: dict[str, Any] | None = None,
    text_data: str | None = None,
    headers: dict[str, str] | None = None,
) -> requests.Response:
    """Helper to generate a mock HTTP response."""
    response = requests.models.Response()
    response.status_code = status_code
    response.headers.update(headers or {})
    if json_data is not None:
        response._content = json_mod.dumps(json_data).encode("utf-8")
    elif text_data is not None:
        response._content = text_data.encode("utf-8")
    else:
        response._content = b""
    return response


@pytest.fixture
def client() -> BaseAPIClient:
    return BaseAPIClient(base_url="https://api.example.com")


class TestInit:
    def test_strips_trailing_slash_from_base_url(self) -> None:
        c = BaseAPIClient(base_url="https://api.example.com/")
        assert c.base_url == "https://api.example.com"

    def test_strips_multiple_trailing_slashes(self) -> None:
        c = BaseAPIClient(base_url="https://api.example.com///")
        assert c.base_url == "https://api.example.com"

    def test_default_timeout(self) -> None:
        c = BaseAPIClient(base_url="https://api.example.com")
        assert c.timeout == 10.0

    def test_custom_timeout(self) -> None:
        c = BaseAPIClient(base_url="https://api.example.com", timeout=5.0)
        assert c.timeout == 5.0

    def test_creates_a_session(self) -> None:
        c = BaseAPIClient(base_url="https://api.example.com")
        assert isinstance(c.session, requests.Session)

    def test_auth_none_by_default(self) -> None:
        c = BaseAPIClient(base_url="https://api.example.com")
        assert c.session.auth is None

    def test_auth_is_set_when_provided(self) -> None:
        auth = ("user", "pass")
        c = BaseAPIClient(base_url="https://api.example.com", auth=auth)
        assert c.session.auth == auth

    def test_retry_adapter_mounted_on_http_and_https(self) -> None:
        c = BaseAPIClient(base_url="https://api.example.com")
        assert isinstance(c.session.adapters["http://"], HTTPAdapter)
        assert isinstance(c.session.adapters["https://"], HTTPAdapter)

    def test_create_retry_adapter_called_on_init(self) -> None:
        with patch.object(
            base_client, "create_retry_adapter", return_value=HTTPAdapter()
        ) as mock_factory:
            BaseAPIClient(base_url="https://api.example.com")
            mock_factory.assert_called_once()


class TestContextManagerAndClose:
    def test_close_closes_session(self, client: BaseAPIClient) -> None:
        client.session.close = MagicMock()  # type: ignore
        client.close()
        client.session.close.assert_called_once()

    def test_enter_returns_self(self, client: BaseAPIClient) -> None:
        with client as c:
            assert c is client

    def test_exit_calls_close(self, client: BaseAPIClient) -> None:
        client.close = MagicMock()  # type: ignore
        with client:
            pass
        client.close.assert_called_once()

    def test_exit_closes_even_on_exception(self, client: BaseAPIClient) -> None:
        client.close = MagicMock()  # type: ignore
        with pytest.raises(ValueError):
            with client:
                raise ValueError("boom")
        client.close.assert_called_once()


class TestUrlConstruction:
    def test_joins_base_url_and_endpoint(self, client: BaseAPIClient) -> None:
        client.session.request = MagicMock(return_value=make_response(json_data={}))  # type: ignore
        client.get("users")
        assert (
            client.session.request.call_args.kwargs["url"]
            == "https://api.example.com/users"
        )

    def test_strips_leading_slash_from_endpoint(self, client: BaseAPIClient) -> None:
        client.session.request = MagicMock(return_value=make_response(json_data={}))  # type: ignore
        client.get("/users")
        assert (
            client.session.request.call_args.kwargs["url"]
            == "https://api.example.com/users"
        )

    def test_nested_endpoint_path(self, client: BaseAPIClient) -> None:
        client.session.request = MagicMock(return_value=make_response(json_data={}))  # type: ignore
        client.get("/users/123/posts")
        assert (
            client.session.request.call_args.kwargs["url"]
            == "https://api.example.com/users/123/posts"
        )


class TestTimeoutHandling:
    def test_uses_default_timeout_when_not_overridden(
        self, client: BaseAPIClient
    ) -> None:
        client.session.request = MagicMock(return_value=make_response(json_data={}))  # type: ignore
        client.get("users")
        assert client.session.request.call_args.kwargs["timeout"] == 10.0

    def test_per_request_timeout_overrides_default(self, client: BaseAPIClient) -> None:
        client.session.request = MagicMock(return_value=make_response(json_data={}))  # type: ignore
        client.get("users", timeout=2.5)
        assert client.session.request.call_args.kwargs["timeout"] == 2.5

    def test_timeout_not_leaked_into_request_kwargs_twice(
        self, client: BaseAPIClient
    ) -> None:
        client.session.request = MagicMock(return_value=make_response(json_data={}))  # type: ignore
        client.get("users", timeout=2.5)
        assert (
            list(client.session.request.call_args.kwargs.keys()).count("timeout") == 1
        )


class TestTransportErrors:
    def test_timeout_raises_request_timeout_error(self, client: BaseAPIClient) -> None:
        client.session.request = MagicMock(side_effect=requests.exceptions.Timeout())  # type: ignore
        with pytest.raises(RequestTimeoutError) as exc_info:
            client.get("users")
        assert exc_info.value.timeout_duration == 10.0
        assert exc_info.value.status_code is None
        assert exc_info.value.response is None

    def test_timeout_error_uses_overridden_timeout_value(
        self, client: BaseAPIClient
    ) -> None:
        client.session.request = MagicMock(side_effect=requests.exceptions.Timeout())  # type: ignore
        with pytest.raises(RequestTimeoutError) as exc_info:
            client.get("users", timeout=3.0)
        assert exc_info.value.timeout_duration == 3.0

    def test_generic_request_exception_raises_haki_api_error(
        self, client: BaseAPIClient
    ) -> None:
        client.session.request = MagicMock(
            side_effect=requests.exceptions.ConnectionError("network down")
        )  # type: ignore
        with pytest.raises(HakiAPIError) as exc_info:
            client.get("users")
        assert not isinstance(exc_info.value, RequestTimeoutError)

    def test_haki_api_error_message_preserved(self, client: BaseAPIClient) -> None:
        client.session.request = MagicMock(
            side_effect=requests.exceptions.ConnectionError("network down")
        )  # type: ignore
        with pytest.raises(HakiAPIError) as exc_info:
            client.get("users")
        assert "network down" in exc_info.value.message


class TestStatusCodeMapping:
    def test_429_raises_rate_limit_error(self, client: BaseAPIClient) -> None:
        client.session.request = MagicMock(
            return_value=make_response(status_code=429, headers={"Retry-After": "30"})
        )  # type: ignore
        with pytest.raises(RateLimitError) as exc_info:
            client.get("users")
        assert exc_info.value.status_code == 429
        assert exc_info.value.retry_after == 30.0
        assert isinstance(exc_info.value, ClientError)

    def test_429_without_retry_after_header(self, client: BaseAPIClient) -> None:
        client.session.request = MagicMock(return_value=make_response(status_code=429))  # type: ignore
        with pytest.raises(RateLimitError) as exc_info:
            client.get("users")
        assert exc_info.value.retry_after is None

    def test_429_with_non_numeric_retry_after_falls_back_to_none(
        self, client: BaseAPIClient
    ) -> None:
        client.session.request = MagicMock(
            return_value=make_response(
                status_code=429,
                headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"},
            )
        )  # type: ignore
        with pytest.raises(RateLimitError) as exc_info:
            client.get("users")
        assert exc_info.value.retry_after is None

    def test_401_raises_authentication_error(self, client: BaseAPIClient) -> None:
        client.session.request = MagicMock(return_value=make_response(status_code=401))  # type: ignore
        with pytest.raises(AuthenticationError) as exc_info:
            client.get("users")
        assert exc_info.value.status_code == 401
        assert isinstance(exc_info.value, ClientError)

    def test_403_raises_authentication_error(self, client: BaseAPIClient) -> None:
        client.session.request = MagicMock(return_value=make_response(status_code=403))  # type: ignore
        with pytest.raises(AuthenticationError) as exc_info:
            client.get("users")
        assert exc_info.value.status_code == 403

    @pytest.mark.parametrize("status_code", [400, 404, 409, 422, 499])
    def test_4xx_raises_client_error(
        self, client: BaseAPIClient, status_code: int
    ) -> None:
        client.session.request = MagicMock(
            return_value=make_response(status_code=status_code)
        )  # type: ignore
        with pytest.raises(ClientError) as exc_info:
            client.get("users")
        assert exc_info.value.status_code == status_code
        assert not isinstance(exc_info.value, (RateLimitError, AuthenticationError))

    @pytest.mark.parametrize("status_code", [500, 502, 503, 599])
    def test_5xx_raises_server_error(
        self, client: BaseAPIClient, status_code: int
    ) -> None:
        client.session.request = MagicMock(
            return_value=make_response(status_code=status_code)
        )  # type: ignore
        with pytest.raises(ServerError) as exc_info:
            client.get("users")
        assert exc_info.value.status_code == status_code
        assert not isinstance(exc_info.value, ClientError)

    def test_429_takes_precedence_over_generic_client_error(
        self, client: BaseAPIClient
    ) -> None:
        client.session.request = MagicMock(return_value=make_response(status_code=429))  # type: ignore
        with pytest.raises(RateLimitError):
            client.get("users")

    def test_401_takes_precedence_over_generic_client_error(
        self, client: BaseAPIClient
    ) -> None:
        client.session.request = MagicMock(return_value=make_response(status_code=401))  # type: ignore
        with pytest.raises(AuthenticationError):
            client.get("users")

    def test_error_exceptions_carry_response_object(
        self, client: BaseAPIClient
    ) -> None:
        response = make_response(status_code=500)
        client.session.request = MagicMock(return_value=response)  # type: ignore
        with pytest.raises(ServerError) as exc_info:
            client.get("users")
        assert exc_info.value.response is response

    def test_error_str_includes_status_code(self, client: BaseAPIClient) -> None:
        client.session.request = MagicMock(return_value=make_response(status_code=404))  # type: ignore
        with pytest.raises(ClientError) as exc_info:
            client.get("users")
        assert "404" in str(exc_info.value)


class TestSuccessResponses:
    def test_returns_parsed_json_on_success(self, client: BaseAPIClient) -> None:
        client.session.request = MagicMock(
            return_value=make_response(
                status_code=200, json_data={"id": 1, "name": "haki"}
            )
        )  # type: ignore
        result = client.get("users/1")
        assert result == {"id": 1, "name": "haki"}

    def test_returns_text_when_body_is_not_json(self, client: BaseAPIClient) -> None:
        client.session.request = MagicMock(
            return_value=make_response(status_code=200, text_data="plain text response")
        )  # type: ignore
        result = client.get("users/1")
        assert result == "plain text response"

    def test_returns_empty_text_for_empty_body(self, client: BaseAPIClient) -> None:
        client.session.request = MagicMock(return_value=make_response(status_code=204))  # type: ignore
        result = client.delete("users/1")
        assert result == ""

    def test_raw_response_true_returns_response_object(
        self, client: BaseAPIClient
    ) -> None:
        response = make_response(status_code=200, json_data={"ok": True})
        client.session.request = MagicMock(return_value=response)  # type: ignore
        result = client.get("users/1", raw_response=True)
        assert result is response

    def test_raw_response_bypasses_json_parsing(self, client: BaseAPIClient) -> None:
        response = make_response(status_code=200, text_data="not json {{{")
        client.session.request = MagicMock(return_value=response)  # type: ignore
        result = client.get("users/1", raw_response=True)
        assert result is response

    @pytest.mark.parametrize("status_code", [200, 201, 204, 299, 300, 399])
    def test_sub_400_status_codes_do_not_raise(
        self, client: BaseAPIClient, status_code: int
    ) -> None:
        client.session.request = MagicMock(
            return_value=make_response(status_code=status_code, json_data={"ok": True})
        )  # type: ignore
        result = client.get("users")
        assert result == {"ok": True}


class TestHttpVerbMethods:
    @pytest.mark.parametrize(
        "verb, expected_method",
        [
            ("get", "GET"),
            ("post", "POST"),
            ("put", "PUT"),
            ("delete", "DELETE"),
            ("patch", "PATCH"),
        ],
    )
    def test_verb_method_sends_correct_http_method(
        self, client: BaseAPIClient, verb: str, expected_method: str
    ) -> None:
        client.session.request = MagicMock(return_value=make_response(json_data={}))  # type: ignore
        getattr(client, verb)("users")
        assert client.session.request.call_args.kwargs["method"] == expected_method

    def test_post_forwards_json_kwarg(self, client: BaseAPIClient) -> None:
        client.session.request = MagicMock(return_value=make_response(json_data={}))  # type: ignore
        client.post("users", json={"name": "haki"})
        assert client.session.request.call_args.kwargs["json"] == {"name": "haki"}

    def test_get_forwards_params_kwarg(self, client: BaseAPIClient) -> None:
        client.session.request = MagicMock(return_value=make_response(json_data={}))  # type: ignore
        client.get("users", params={"page": 2})
        assert client.session.request.call_args.kwargs["params"] == {"page": 2}

    def test_put_forwards_data_kwarg(self, client: BaseAPIClient) -> None:
        client.session.request = MagicMock(return_value=make_response(json_data={}))  # type: ignore
        client.put("users/1", data={"name": "updated"})
        assert client.session.request.call_args.kwargs["data"] == {"name": "updated"}

    def test_patch_forwards_headers_kwarg(self, client: BaseAPIClient) -> None:
        client.session.request = MagicMock(return_value=make_response(json_data={}))  # type: ignore
        client.patch("users/1", headers={"X-Custom": "1"})
        assert client.session.request.call_args.kwargs["headers"] == {"X-Custom": "1"}

    def test_delete_with_no_body(self, client: BaseAPIClient) -> None:
        client.session.request = MagicMock(return_value=make_response(status_code=204))  # type: ignore
        client.delete("users/1")
        assert client.session.request.call_args.kwargs["method"] == "DELETE"


class TestRealRetryAdapterIntegration:
    def test_real_retry_adapter_mounts_successfully(self) -> None:
        c = BaseAPIClient(base_url="https://api.example.com")
        adapter = c.session.adapters["https://"]
        assert isinstance(adapter, HTTPAdapter)
        assert adapter.max_retries.total == 3
        assert 429 in adapter.max_retries.status_forcelist
        assert adapter.max_retries.raise_on_status is False
