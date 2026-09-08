"""Async HTTP client with retries and basic response handling."""

from __future__ import annotations

import asyncio
import random
import time
from typing import Any, TypeVar
from urllib.parse import urlsplit

import httpx
from typing_extensions import Self

from .circuit_breaker import CircuitBreaker, CircuitOpenError, CircuitState
from .exceptions import (
    AuthenticationError,
    ClientError,
    HakiAPIError,
    RateLimitError,
    RequestTimeoutError,
    ServerError,
)
from .governer import PredictiveGovernor

T = TypeVar("T", bound="AsyncBaseAPIClient")

_ALLOWED_SCHEMES = {"http", "https"}
_ALLOWED_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_MAX_RETRY_AFTER_SECONDS = 300.0  # clamp ceiling regardless of what server sends


class AsyncBaseAPIClient:
    def __init__(
        self,
        base_url: str,
        auth: Any | None = None,
        timeout: float = 10.0,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        max_response_bytes: int = 10 * 1024 * 1024,
        headers: dict[str, str] | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        enable_circuit_breaker: bool = True,
        governor: PredictiveGovernor | None = None,
        enable_governor: bool = True,
    ) -> None:
        self.base_url = self._validate_base_url(base_url)
        self.timeout = timeout
        self.max_retries = max(0, max_retries)
        self.backoff_factor = max(0.0, backoff_factor)
        self.max_response_bytes = max_response_bytes

        # Wire Circuit Breaker
        self.enable_circuit_breaker = enable_circuit_breaker
        self.circuit_breaker = (
            circuit_breaker or CircuitBreaker() if enable_circuit_breaker else None
        )

        # Wire Predictive Governor
        self.enable_governor = enable_governor
        self.governor = governor or PredictiveGovernor() if enable_governor else None

        default_headers = {"User-Agent": "hakiapi-async-client/1.0"}
        if headers:
            default_headers.update(headers)

        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            auth=auth,
            timeout=self.timeout,
            headers=default_headers,
            follow_redirects=False,
        )
        self._closed = False

    # Validation helpers

    @staticmethod
    def _validate_base_url(base_url: str) -> str:
        parts = urlsplit(base_url)
        if parts.scheme not in _ALLOWED_SCHEMES:
            raise ValueError(
                f"Unsupported base_url scheme {parts.scheme!r}; "
                f"only {sorted(_ALLOWED_SCHEMES)} are allowed."
            )
        if not parts.netloc:
            raise ValueError(f"base_url {base_url!r} is missing a host.")
        return base_url.rstrip("/")

    @staticmethod
    def _validate_endpoint(endpoint: str) -> str:
        stripped = endpoint.lstrip("/")
        # Only allow relative endpoints
        parts = urlsplit(endpoint)
        if parts.scheme or parts.netloc:
            raise ValueError(
                f"endpoint must be a relative path, got absolute/host-qualified "
                f"value: {endpoint!r}"
            )
        return stripped

    # Client lifecycle

    async def close(self) -> None:
        if self._closed:
            return
        await self.client.aclose()
        self._closed = True

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    def __repr__(self) -> str:  # Keep repr safe
        return f"{self.__class__.__name__}(base_url={self.base_url!r})"

    # Retry helpers

    @staticmethod
    def _parse_retry_after(response: httpx.Response) -> float | None:
        raw = response.headers.get("Retry-After")
        if not raw:
            return None
        try:
            seconds = float(raw)
        except ValueError:
            # Ignore HTTP-date format
            return None
        if seconds < 0:
            return None
        return min(seconds, _MAX_RETRY_AFTER_SECONDS)

    # Request handling

    async def _request(
        self, method: str, endpoint: str, raw_response: bool = False, **kwargs: Any
    ) -> Any:
        method = method.upper()
        if method not in _ALLOWED_METHODS:
            raise ValueError(f"Unsupported HTTP method: {method!r}")

        safe_endpoint = self._validate_endpoint(endpoint)
        request_timeout = kwargs.pop("timeout", self.timeout)

        attempt = 0
        last_exc: Exception | None = None

        while True:
            # 1. Pre-Flight Circuit Check: Fast-fail if downstream service is down
            if self.circuit_breaker and self.circuit_breaker.state == CircuitState.OPEN:
                cooldown_left = self.circuit_breaker.recovery_timeout - (
                    time.monotonic() - self.circuit_breaker._last_failure_time
                )
                raise CircuitOpenError(
                    message=f"Circuit breaker is OPEN for {self.base_url}. Fast-failing request.",
                    retry_after=max(0.0, cooldown_left),
                )

            # 2. Pre-Flight Rate-Limit Governor Check: Local async sleep pacing
            if self.governor:
                wait_time = self.governor.get_wait_time(self.base_url)
                if wait_time > 0:
                    await asyncio.sleep(wait_time)

            # 3. Execute Request
            try:
                response = await self.client.request(
                    method=method,
                    url=safe_endpoint,
                    timeout=request_timeout,
                    **kwargs,
                )
            except httpx.TimeoutException as e:
                if self.circuit_breaker:
                    self.circuit_breaker._on_failure()
                last_exc = RequestTimeoutError(
                    message="Request timed out.",
                    timeout_duration=float(request_timeout)
                    if request_timeout
                    else None,
                )
                if attempt >= self.max_retries:
                    raise last_exc from e
                await self._sleep_backoff(attempt)
                attempt += 1
                continue
            except httpx.RequestError as e:
                if self.circuit_breaker:
                    self.circuit_breaker._on_failure()
                last_exc = HakiAPIError(message=str(e))
                if attempt >= self.max_retries:
                    raise last_exc from e
                await self._sleep_backoff(attempt)
                attempt += 1
                continue

            # 4. Update Governor with Response Headers
            if self.governor:
                self.governor.update_from_headers(self.base_url, dict(response.headers))

            # 5. Track Circuit State based on Status Code
            if response.status_code >= 500:
                if self.circuit_breaker:
                    self.circuit_breaker._on_failure()
            else:
                # 4xx or 2xx means the server is actively responding
                if self.circuit_breaker:
                    self.circuit_breaker._on_success()

            # 6. Retry Logic for specific statuses (429, 50x)
            if response.status_code in _RETRYABLE_STATUS and attempt < self.max_retries:
                retry_after = self._parse_retry_after(response)
                await response.aclose()
                if retry_after is not None:
                    await asyncio.sleep(retry_after)
                else:
                    await self._sleep_backoff(attempt)
                attempt += 1
                continue

            return await self._handle_response(response, raw_response)

    async def _sleep_backoff(self, attempt: int) -> None:
        delay = self.backoff_factor * (2**attempt)
        delay += random.uniform(0, self.backoff_factor)  # Add a little randomness
        await asyncio.sleep(delay)

    async def _handle_response(
        self, response: httpx.Response, raw_response: bool
    ) -> Any:
        # Too many requests
        if response.status_code == 429:
            raise RateLimitError(
                message="Rate limit exceeded.",
                status_code=response.status_code,
                retry_after=self._parse_retry_after(response),
                response=response,
            )

        # Auth errors
        if response.status_code in (401, 403):
            raise AuthenticationError(
                message="Authentication failed.",
                status_code=response.status_code,
                response=response,
            )

        # Client-side errors
        if 400 <= response.status_code < 500:
            raise ClientError(
                message=f"HTTP {response.status_code} Client Error",
                status_code=response.status_code,
                response=response,
            )

        # Server-side errors
        if response.status_code >= 500:
            raise ServerError(
                message=f"HTTP {response.status_code} Server Error",
                status_code=response.status_code,
                response=response,
            )

        # Reject unusually large responses
        content_length = response.headers.get("Content-Length")
        body_len = (
            int(content_length)
            if content_length and content_length.isdigit()
            else len(response.content)
        )
        if body_len > self.max_response_bytes:
            raise HakiAPIError(
                message=(
                    f"Response body ({body_len} bytes) exceeds max_response_bytes "
                    f"({self.max_response_bytes})."
                )
            )

        if raw_response:
            return response

        try:
            return response.json()
        except ValueError:
            return response.text

    # HTTP methods

    async def get(self, endpoint: str, **kwargs: Any) -> Any:
        return await self._request("GET", endpoint, **kwargs)

    async def post(self, endpoint: str, **kwargs: Any) -> Any:
        return await self._request("POST", endpoint, **kwargs)

    async def put(self, endpoint: str, **kwargs: Any) -> Any:
        return await self._request("PUT", endpoint, **kwargs)

    async def delete(self, endpoint: str, **kwargs: Any) -> Any:
        return await self._request("DELETE", endpoint, **kwargs)

    async def patch(self, endpoint: str, **kwargs: Any) -> Any:
        return await self._request("PATCH", endpoint, **kwargs)
