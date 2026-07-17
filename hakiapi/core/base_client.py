import requests
from typing import Any, TypeVar
from requests.auth import AuthBase

from .retry import create_retry_adapter
from .exceptions import (
    HakiAPIError,
    ClientError,
    ServerError,
    RateLimitError,
    AuthenticationError,
    RequestTimeoutError,
)

T = TypeVar("T", bound="BaseAPIClient")


class BaseAPIClient:
    def __init__(
        self,
        base_url: str,
        auth: AuthBase | tuple[str, str] | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        self.session = requests.Session()

        if auth is not None:
            self.session.auth = auth

        adapter = create_retry_adapter()
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def close(self) -> None:
        self.session.close()

    def __enter__(self: T) -> T:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def _request(
        self, method: str, endpoint: str, raw_response: bool = False, **kwargs: Any
    ) -> Any:
        full_url = f"{self.base_url}/{endpoint.lstrip('/')}"

        # Safely extract timeout to pass to the exception engine if needed
        request_timeout = kwargs.pop("timeout", self.timeout)

        try:
            response = self.session.request(
                method=method,
                url=full_url,
                timeout=request_timeout,
                **kwargs,
            )

        except requests.exceptions.Timeout as e:
            raise RequestTimeoutError(
                message="Request timed out.",
                timeout_duration=float(request_timeout) if request_timeout else None,
            ) from e

        except requests.exceptions.RequestException as e:
            raise HakiAPIError(message=str(e)) from e

        # Rate limiting
        if response.status_code == 429:
            retry_after_str = response.headers.get("Retry-After")
            retry_after = None
            if retry_after_str:
                try:
                    retry_after = float(retry_after_str)
                except ValueError:
                    pass  # Ignore HTTP date formats; fallback to None

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

        # Client errors
        if 400 <= response.status_code < 500:
            raise ClientError(
                message=f"HTTP {response.status_code} Client Error",
                status_code=response.status_code,
                response=response,
            )

        # Server errors
        if response.status_code >= 500:
            raise ServerError(
                message=f"HTTP {response.status_code} Server Error",
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
