from typing import Any, TypeVar
import httpx

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
        response = await self.client.request(
            method=method,
            url=endpoint.lstrip("/"),
            **kwargs,
        )

        return response.json()
