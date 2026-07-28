from typing import Any, TypeVar
import httpx

from .exceptions import (
    AuthenticationError,
    ClientError,
    HakiAPIError,
    RateLimitError,
    RequestTimeoutError,
    ServerError,
)

T = TypeVar("T", bound="AsyncBaseAPIClient")


class AsyncBaseAPIClient:
    def __init__(
        self,
        base_url: str,
        auth: Any | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            auth=auth,
            timeout=self.timeout,
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def __aenter__(self: T) -> T:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    async def _request(
        self, method: str, endpoint: str, raw_response: bool = False, **kwargs: Any
    ) -> Any:
        # Safely extract timeout to pass to the exception engine if needed
        request_timeout = kwargs.pop("timeout", self.timeout)

        try:
            response = await self.client.request(
                method=method,
                url=endpoint.lstrip("/"),
                timeout=request_timeout,
                **kwargs,
            )

        except httpx.TimeoutException as e:
            raise RequestTimeoutError(
                message="Request timed out.",
                timeout_duration=float(request_timeout) if request_timeout else None,
            ) from e

        except httpx.RequestError as e:
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
