import time
from typing import Any, TypeVar

import requests
from requests.auth import AuthBase
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
from .retry import create_retry_adapter

T = TypeVar("T", bound="BaseAPIClient")


class BaseAPIClient:
    def __init__(
        self,
        base_url: str,
        auth: AuthBase | tuple[str, str] | None = None,
        timeout: float = 10.0,
        circuit_breaker: CircuitBreaker | None = None,
        enable_circuit_breaker: bool = True,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        # Wire Circuit Breaker
        self.enable_circuit_breaker = enable_circuit_breaker
        self.circuit_breaker = (
            circuit_breaker or CircuitBreaker() if enable_circuit_breaker else None
        )

        self.session = requests.Session()

        if auth is not None:
            self.session.auth = auth

        adapter = create_retry_adapter()
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def _request(
        self, method: str, endpoint: str, raw_response: bool = False, **kwargs: Any
    ) -> Any:
        # 1. Pre-Flight Circuit Check: Fast-fail if downstream service is down
        if self.circuit_breaker and self.circuit_breaker.state == CircuitState.OPEN:
            cooldown_left = self.circuit_breaker.recovery_timeout - (
                time.monotonic() - self.circuit_breaker._last_failure_time
            )
            raise CircuitOpenError(
                message=f"Circuit breaker is OPEN for {self.base_url}. Fast-failing request.",
                retry_after=max(0.0, cooldown_left),
            )

        full_url = f"{self.base_url}/{endpoint.lstrip('/')}"
        request_timeout = kwargs.pop("timeout", self.timeout)

        # 2. Execute Request with Circuit State Tracking
        try:
            response = self.session.request(
                method=method,
                url=full_url,
                timeout=request_timeout,
                **kwargs,
            )
        except requests.exceptions.Timeout as e:
            if self.circuit_breaker:
                self.circuit_breaker._on_failure()
            raise RequestTimeoutError(
                message="Request timed out.",
                timeout_duration=float(request_timeout) if request_timeout else None,
            ) from e
        except requests.exceptions.RequestException as e:
            if self.circuit_breaker:
                self.circuit_breaker._on_failure()
            raise HakiAPIError(message=str(e)) from e

        # 3. Handle Server Errors (Trips Circuit)
        if response.status_code >= 500:
            if self.circuit_breaker:
                self.circuit_breaker._on_failure()
            raise ServerError(
                message=f"HTTP {response.status_code} Server Error",
                status_code=response.status_code,
                response=response,
            )

        # 4. Success / Client-side Response (Proves Server is Healthy -> Reset Circuit)
        if self.circuit_breaker:
            self.circuit_breaker._on_success()

        # Rate limiting
        if response.status_code == 429:
            retry_after_str = response.headers.get("Retry-After")
            retry_after = None
            if retry_after_str:
                try:
                    retry_after = float(retry_after_str)
                except ValueError:
                    pass

            raise RateLimitError(
                message="Rate limit exceeded.",
                status_code=response.status_code,
                retry_after=retry_after,
                response=response,
            )

        # Authentication
        if response.status_code in (401, 403):
            raise AuthenticationError(
                message="Authentication failed.",
                status_code=response.status_code,
                response=response,
            )

        # Client errors (4xx)
        if 400 <= response.status_code < 500:
            raise ClientError(
                message=f"HTTP {response.status_code} Client Error",
                status_code=response.status_code,
                response=response,
            )

        if raw_response:
            return response

        try:
            return response.json()
        except ValueError:
            return response.text

    def get(self, endpoint: str, **kwargs: Any) -> Any:
        return self._request("GET", endpoint, **kwargs)

    def post(self, endpoint: str, **kwargs: Any) -> Any:
        return self._request("POST", endpoint, **kwargs)

    def put(self, endpoint: str, **kwargs: Any) -> Any:
        return self._request("PUT", endpoint, **kwargs)

    def delete(self, endpoint: str, **kwargs: Any) -> Any:
        return self._request("DELETE", endpoint, **kwargs)

    def patch(self, endpoint: str, **kwargs: Any) -> Any:
        return self._request("PATCH", endpoint, **kwargs)
