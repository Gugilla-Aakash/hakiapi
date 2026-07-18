from typing import Any, Iterator, Optional
from ..core.base_client import BaseAPIClient
from ..core import auth


class GmailClient(BaseAPIClient):
    """
    Client for interacting with the Google Gmail API v1.
    Requires an OAuth 2.0 Bearer Token.
    """

    def __init__(self, token: str, **kwargs: Any) -> None:
        # Seamlessly pass the BearerAuth instance into the base engine
        kwargs["auth"] = auth.BearerTokenAuth(token)
        super().__init__(base_url="https://gmail.googleapis.com/gmail/v1/", **kwargs)

    def get_profile(self, user_id: str = "me", **kwargs: Any) -> dict[str, Any]:
        """Fetch the authenticated user's email profile."""
        return self.get(f"users/{user_id}/profile", **kwargs)

    def get_message(
        self, message_id: str, user_id: str = "me", **kwargs: Any
    ) -> dict[str, Any]:
        """Fetch the full payload of a specific email message by ID."""
        return self.get(f"users/{user_id}/messages/{message_id}", **kwargs)

    def get_messages_page(
        self, user_id: str = "me", page_token: Optional[str] = None, **kwargs: Any
    ) -> dict[str, Any]:
        """Fetch a single static page of message stubs."""
        params = kwargs.pop("params", {})
        if page_token:
            params["pageToken"] = page_token

        return self.get(f"users/{user_id}/messages", params=params, **kwargs)

    def get_all_messages(
        self, user_id: str = "me", **kwargs: Any
    ) -> Iterator[dict[str, Any]]:
        """
        Lazily yield every message by traversing the nextPageToken linked list.
        Memory-safe for inboxes with thousands of emails.
        """
        page_token: Optional[str] = None

        while True:
            response = self.get_messages_page(
                user_id=user_id, page_token=page_token, **kwargs
            )

            # Yield each message in the current block
            messages = response.get("messages", [])
            for msg in messages:
                yield msg

            # Grab the pointer to the next block of memory
            page_token = response.get("nextPageToken")

            # If the pointer is null, we have reached the end of the list
            if not page_token:
                break
