"""Tests for AsyncBaseAPIClient."""

from __future__ import annotations

import json

import httpx
import pytest

from hakiapi.core.async_base_client import AsyncBaseAPIClient
from hakiapi.core.exceptions import (
    AuthenticationError,
    ClientError,
    HakiAPIError,
    RateLimitError,
    RequestTimeoutError,
    ServerError,
)

# Mark async tests individually


def make_client(handler, **kwargs) -> AsyncBaseAPIClient:
    """Create a client backed by MockTransport."""
    client = AsyncBaseAPIClient(base_url="https://api.example.com", **kwargs)
    client.client = httpx.AsyncClient(
        base_url=client.base_url,
        transport=httpx.MockTransport(handler),
        follow_redirects=False,
    )
    return client


def json_response(
    status_code: int, payload: dict, headers: dict | None = None
) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        content=json.dumps(payload).encode(),
        headers=headers or {},
    )


class TestSuccessfulRequests:
    @pytest.mark.asyncio
    async def test_get_returns_parsed_json(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "GET"
            assert request.url.path == "/users/1"
            return json_response(200, {"id": 1, "name": "Aakash"})

        client = make_client(handler)
        result = await client.get("/users/1")
        assert result == {"id": 1, "name": "Aakash"}
        await client.close()

    @pytest.mark.asyncio
    async def test_post_returns_parsed_json(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "POST"
            return json_response(201, {"created": True})

        client = make_client(handler)
        result = await client.post("/users", json={"name": "Aakash"})
        assert result == {"created": True}
        await client.close()

    @pytest.mark.parametrize("verb", ["put", "delete", "patch"])
    @pytest.mark.asyncio
    async def test_other_verbs(self, verb):
        def handler(request: httpx.Request) -> httpx.Response:
            return json_response(200, {"ok": True, "method": request.method})

        client = make_client(handler)
        method_fn = getattr(client, verb)
        result = await method_fn("/thing/1")
        assert result["ok"] is True
        await client.close()

    @pytest.mark.asyncio
    async def test_non_json_body_returns_text(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"plain text body")

        client = make_client(handler)
        result = await client.get("/plain")
        assert result == "plain text body"
        await client.close()

    @pytest.mark.asyncio
    async def test_raw_response_returns_httpx_response(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return json_response(200, {"a": 1})

        client = make_client(handler)
        result = await client.get("/raw", raw_response=True)
        assert isinstance(result, httpx.Response)
        assert result.status_code == 200
        await client.close()


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_401_raises_authentication_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, content=b"{}")

        client = make_client(handler, max_retries=0)
        with pytest.raises(AuthenticationError) as exc_info:
            await client.get("/secure")
        assert exc_info.value.status_code == 401
        await client.close()

    @pytest.mark.asyncio
    async def test_403_raises_authentication_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(403, content=b"{}")

        client = make_client(handler, max_retries=0)
        with pytest.raises(AuthenticationError):
            await client.get("/secure")
        await client.close()

    @pytest.mark.asyncio
    async def test_404_raises_client_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, content=b"{}")

        client = make_client(handler, max_retries=0)
        with pytest.raises(ClientError) as exc_info:
            await client.get("/missing")
        assert exc_info.value.status_code == 404
        await client.close()

    @pytest.mark.asyncio
    async def test_500_raises_server_error_after_retries_exhausted(self):
        calls = {"count": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["count"] += 1
            return httpx.Response(500, content=b"{}")

        client = make_client(handler, max_retries=2, backoff_factor=0.01)
        with pytest.raises(ServerError) as exc_info:
            await client.get("/broken")
        assert exc_info.value.status_code == 500
        # Initial request + retries
        assert calls["count"] == 3
        await client.close()

    @pytest.mark.asyncio
    async def test_timeout_raises_request_timeout_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("timed out", request=request)

        client = make_client(handler, max_retries=0)
        with pytest.raises(RequestTimeoutError):
            await client.get("/slow")
        await client.close()

    @pytest.mark.asyncio
    async def test_connect_error_raises_haki_api_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused", request=request)

        client = make_client(handler, max_retries=0)
        with pytest.raises(HakiAPIError):
            await client.get("/unreachable")
        await client.close()

    @pytest.mark.asyncio
    async def test_response_over_max_bytes_raises_haki_api_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            big_payload = json.dumps({"data": "x" * 1000}).encode()
            return httpx.Response(200, content=big_payload)

        client = make_client(handler, max_response_bytes=100)
        with pytest.raises(HakiAPIError):
            await client.get("/huge")
        await client.close()


class TestRetryLogic:
    @pytest.mark.asyncio
    async def test_429_retries_then_succeeds(self):
        calls = {"count": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["count"] += 1
            if calls["count"] < 3:
                return httpx.Response(429, headers={"Retry-After": "0"}, content=b"{}")
            return json_response(200, {"ok": True})

        client = make_client(handler, max_retries=5, backoff_factor=0.01)
        result = await client.get("/rate-limited")
        assert result == {"ok": True}
        assert calls["count"] == 3
        await client.close()

    @pytest.mark.asyncio
    async def test_429_raises_rate_limit_error_when_retries_exhausted(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, headers={"Retry-After": "0"}, content=b"{}")

        client = make_client(handler, max_retries=1, backoff_factor=0.01)
        with pytest.raises(RateLimitError) as exc_info:
            await client.get("/rate-limited")
        assert exc_info.value.status_code == 429
        await client.close()

    @pytest.mark.asyncio
    async def test_retry_after_is_clamped(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, headers={"Retry-After": "99999"}, content=b"{}")

        client = make_client(handler, max_retries=0)
        with pytest.raises(RateLimitError) as exc_info:
            await client.get("/rate-limited")
        assert exc_info.value.retry_after == 300.0
        await client.close()

    @pytest.mark.asyncio
    async def test_invalid_retry_after_falls_back_to_none(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                429, headers={"Retry-After": "not-a-number"}, content=b"{}"
            )

        client = make_client(handler, max_retries=0)
        with pytest.raises(RateLimitError) as exc_info:
            await client.get("/rate-limited")
        assert exc_info.value.retry_after is None
        await client.close()

    @pytest.mark.asyncio
    async def test_client_error_is_not_retried(self):
        calls = {"count": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["count"] += 1
            return httpx.Response(400, content=b"{}")

        client = make_client(handler, max_retries=5, backoff_factor=0.01)
        with pytest.raises(ClientError):
            await client.get("/bad-request")
        assert calls["count"] == 1  # Client errors shouldn't retry
        await client.close()


class TestSecurityValidations:
    def test_invalid_base_url_scheme_rejected(self):
        with pytest.raises(ValueError):
            AsyncBaseAPIClient(base_url="ftp://api.example.com")

    def test_missing_host_rejected(self):
        with pytest.raises(ValueError):
            AsyncBaseAPIClient(base_url="https://")

    @pytest.mark.asyncio
    async def test_absolute_url_endpoint_rejected(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return json_response(200, {})

        client = make_client(handler)
        with pytest.raises(ValueError):
            await client.get("http://evil.com/steal")
        await client.close()

    @pytest.mark.asyncio
    async def test_protocol_relative_endpoint_rejected(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return json_response(200, {})

        client = make_client(handler)
        with pytest.raises(ValueError):
            await client.get("//evil.com/steal")
        await client.close()

    @pytest.mark.asyncio
    async def test_unsupported_method_rejected(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return json_response(200, {})

        client = make_client(handler)
        with pytest.raises(ValueError):
            await client._request("TRACE", "/x")
        await client.close()

    @pytest.mark.asyncio
    async def test_redirects_not_followed_by_default(self):
        client = AsyncBaseAPIClient(base_url="https://api.example.com")
        assert client.client.follow_redirects is False
        await client.close()

    def test_repr_does_not_leak_auth(self):
        client = AsyncBaseAPIClient(
            base_url="https://api.example.com",
            auth=("user", "supersecretpassword"),
        )
        assert "supersecretpassword" not in repr(client)
        assert "user" not in repr(client)


class TestLifecycle:
    @pytest.mark.asyncio
    async def test_context_manager_closes_client(self):
        async with AsyncBaseAPIClient(base_url="https://api.example.com") as client:
            assert client._closed is False
        assert client._closed is True

    @pytest.mark.asyncio
    async def test_close_is_idempotent(self):
        client = AsyncBaseAPIClient(base_url="https://api.example.com")
        await client.close()
        await client.close()  # Safe to call twice
        assert client._closed is True
