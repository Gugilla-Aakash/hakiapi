from typing import Any, Iterator
from urllib.parse import parse_qsl, urlparse

from .base_client import BaseAPIClient


def paginate(
    client: BaseAPIClient, endpoint: str, max_pages: int | None = None, **kwargs: Any
) -> Iterator[Any]:
    """
    Fetches all pages from APIs that use different pagination methods,
    figuring out which one to use based on the response.

    Supported pagination styles:
    1. Link header (GitHub)
    2. Token-based "data/meta" (Twitter/X)
    3. Token-based "messages/nextPageToken" (Google/Gmail)
    """

    raw_params = kwargs.pop("params", None) or {}
    if isinstance(raw_params, dict):
        params = list(raw_params.items())
    else:
        params = list(raw_params)

    pages_fetched = 0

    while endpoint:
        if max_pages is not None and pages_fetched >= max_pages:
            break

        response = client._request(
            "GET",
            endpoint,
            raw_response=True,
            params=params or None,
            **kwargs,
        )

        pages_fetched += 1
        data = response.json()

        # Detect GitHub (list), Twitter ("data"), Gmail ("messages"),
        # or Calendar/Drive-style ("items")
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            if isinstance(data.get("data"), list):
                items = data["data"]
            elif isinstance(data.get("messages"), list):
                items = data["messages"]
            elif isinstance(data.get("items"), list):
                items = data["items"]
            else:
                raise ValueError(
                    "Paginator expected a list response, or a dict with a "
                    "'data', 'messages', or 'items' list."
                )
        else:
            raise ValueError("Unexpected response format.")

        for item in items:
            yield item

        # 1. GitHub-style (Link header)
        if "next" in response.links:
            next_url = response.links["next"]["url"]
            parsed = urlparse(next_url)
            endpoint = parsed.path.lstrip("/")
            params = parse_qsl(parsed.query) if parsed.query else []
            continue

        # 2. Twitter-style (meta.next_token)
        twitter_token = (
            data.get("meta", {}).get("next_token") if isinstance(data, dict) else None
        )
        if twitter_token:
            params = [(k, v) for k, v in params if k != "pagination_token"]
            params.append(("pagination_token", twitter_token))
            continue

        # 3. Google-style (nextPageToken)
        google_token = data.get("nextPageToken") if isinstance(data, dict) else None
        if google_token:
            params = [(k, v) for k, v in params if k != "pageToken"]
            params.append(("pageToken", google_token))
            continue

        break
