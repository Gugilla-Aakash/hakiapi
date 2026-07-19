from typing import Any, Iterator, Optional

from ..core.base_client import BaseAPIClient
from ..core import auth
from ..core.paginator import paginate


class GmailProfileResource:
    """Handles functions related to user Gmmail profile"""

    def __init__(self, client: BaseAPIClient) -> None:
        self._client = client

    def get(self, user_id: str = "me", **kwargs: Any) -> dict[str, Any]:
        return self._client.get(f"users/{user_id}/profile", **kwargs)


class GmailLabelsResource:
    """Handles funcntions related to Gmail index"""

    def __init__(self, client: BaseAPIClient) -> None:
        self._client = client

    """ Fetches all lables in user mailbox """

    def list(self, user_id: str = "me", **kwargs: Any) -> dict[str, Any]:
        return self._client.get(f"users/{user_id}/labels", **kwargs)


class GmailMessagesResource:
    """Handles Read, Write, and Search operations for messages"""

    def __init__(self, client: BaseAPIClient) -> None:
        self._client = client

    def get(
        self, message_id: str, user_id: str = "me", **kwargs: Any
    ) -> dict[str, Any]:
        """Fetch the full payload of a specific email message by ID."""
        return self._client.get(f"users/{user_id}/messages/{message_id}", **kwargs)

    def list(
        self, user_id: str = "me", max_pages: Optional[int] = None, **kwargs: Any
    ) -> Iterator[dict[str, Any]]:
        """Lazily yield messages using the central HakiAPI paginator."""

        # Let the core paginator handle all the heavy lifting!
        return paginate(
            client=self._client,
            endpoint=f"users/{user_id}/messages",
            max_pages=max_pages,
            **kwargs,
        )

    def search(
        self,
        query: str,
        user_id: str = "me",
        max_pages: Optional[int] = None,
        **kwargs: Any,
    ) -> Iterator[dict[str, Any]]:
        """Search for messages using standard Gmail query syntax (e.g., 'is:unread')"""

        params = dict(kwargs.get("params", {}) or {})
        params["q"] = query
        kwargs["params"] = params

        return self.list(user_id=user_id, max_pages=max_pages, **kwargs)

    def send(
        self, payload: dict[str, Any], user_id: str = "me", **kwargs: Any
    ) -> dict[str, Any]:
        """
        Send an email message.
        Note: The payload dict must contain a 'raw' key with a base64url encoded RFC 2822 string.
        """
        return self._client.post(
            f"users/{user_id}/messages/send", json=payload, **kwargs
        )


class GmailClient(BaseAPIClient):
    """
    Client for interacting with the Google Gmail API v1.
    Requires an OAuth 2.0 Bearer Token.
    """

    def __init__(self, token: str, **kwargs: Any) -> None:
        kwargs["auth"] = auth.BearerTokenAuth(token)
        super().__init__(base_url="https://gmail.googleapis.com/gmail/v1/", **kwargs)

        self.profile = GmailProfileResource(self)
        self.labels = GmailLabelsResource(self)
        self.messages = GmailMessagesResource(self)
