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

    1. Link header pagination (used by APIs like GitHub)
    - Looks for a `next` link in the HTTP `Link` header.
    - Each response is expected to be a JSON list.

    2. Token-based pagination (used by APIs like Twitter/X API v2)
    - Reads `meta.next_token` from the response body.
    - Requests the next page by sending the same endpoint with the
     updated `pagination_token` query parameter.
    - Responses are expected to look like:
     {"data": [...], "meta": {"next_token": "..."}}

    If a `next` link is available, it takes priority. Otherwise, the
    paginator checks for a `next_token`. If neither is found, there are
    no more pages to fetch.
    """

    # Extract initial params and ensure they are a list of tuples
    # to prevent dropping duplicate keys.
    raw_params = kwargs.pop("params", None) or {}
    if isinstance(raw_params, dict):
        params = list(raw_params.items())
    else:
        params = list(raw_params)

    pages_fetched = 0

    while endpoint:
        # Safety valve: Prevent infinite loops caused by API routing bugs
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

        if isinstance(data, list):
            items = data
        elif isinstance(data, dict) and isinstance(data.get("data"), list):
            items = data["data"]
        else:
            raise ValueError(
                "Paginator expected a list response, or a dict with a "
                "'data' list (e.g. {'data': [...]})."
            )

        for item in items:
            yield item

        # RFC 5988 Link header (GitHub-style)
        if "next" in response.links:
            next_url = response.links["next"]["url"]
            parsed = urlparse(next_url)

            # Strictly extract only the path to prevent query string duplication
            # in requests, and completely bypass brittle base_url prefix matching.
            endpoint = parsed.path.lstrip("/")
            params = parse_qsl(parsed.query) if parsed.query else []
            continue

        # cursor/token pagination (Twitter-style)
        next_token = (
            data.get("meta", {}).get("next_token") if isinstance(data, dict) else None
        )

        if next_token:
            # Filters out the old pagination_token tuple, then append the new one
            params = [(k, v) for k, v in params if k != "pagination_token"]
            params.append(("pagination_token", next_token))
            continue

        break
