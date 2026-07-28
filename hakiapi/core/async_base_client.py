from typing import Any, TypeVar
import httpx
from .exceptions import HakiAPIError, RequestTimeoutError

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
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> Any:
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

        return response.json()
