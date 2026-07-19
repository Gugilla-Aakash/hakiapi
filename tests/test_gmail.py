"""
Tests for GmailClient and its resource classes.
"""

from unittest.mock import MagicMock, patch

import pytest

from hakiapi.clients.gmail import (
    GmailClient,
    GmailLabelsResource,
    GmailMessagesResource,
    GmailProfileResource,
)
from hakiapi.core.auth import BearerTokenAuth


# Fixtures


@pytest.fixture
def mock_client() -> MagicMock:
    """A stand-in for BaseAPIClient."""
    return MagicMock()


# GmailProfileResource


class TestGmailProfileResource:
    def test_get_default_user(self, mock_client: MagicMock) -> None:
        resource = GmailProfileResource(mock_client)
        mock_client.get.return_value = {"emailAddress": "me@example.com"}

        result = resource.get()

        mock_client.get.assert_called_once_with("users/me/profile")
        assert result == {"emailAddress": "me@example.com"}

    def test_get_explicit_user(self, mock_client: MagicMock) -> None:
        resource = GmailProfileResource(mock_client)
        resource.get(user_id="someone@example.com")

        mock_client.get.assert_called_once_with("users/someone@example.com/profile")


# GmailLabelsResource


class TestGmailLabelsResource:
    def test_list_calls_correct_endpoint(self, mock_client: MagicMock) -> None:
        resource = GmailLabelsResource(mock_client)
        mock_client.get.return_value = {"labels": [{"id": "INBOX"}]}

        result = resource.list()

        mock_client.get.assert_called_once_with("users/me/labels")
        assert result == {"labels": [{"id": "INBOX"}]}


# GmailMessagesResource.get


class TestGmailMessagesGet:
    def test_get_message_by_id(self, mock_client: MagicMock) -> None:
        resource = GmailMessagesResource(mock_client)
        mock_client.get.return_value = {"id": "abc123"}

        result = resource.get("abc123")

        mock_client.get.assert_called_once_with("users/me/messages/abc123")
        assert result == {"id": "abc123"}


# GmailMessagesResource Pagination & Search


class TestGmailMessagesPaginationAndSearch:
    @patch("hakiapi.clients.gmail.paginate")
    def test_list_delegates_to_paginator(
        self, mock_paginate: MagicMock, mock_client: MagicMock
    ) -> None:
        resource = GmailMessagesResource(mock_client)
        mock_paginate.return_value = iter([{"id": "1"}, {"id": "2"}])

        messages = list(resource.list(user_id="someone", max_pages=5, timeout=10))

        assert messages == [{"id": "1"}, {"id": "2"}]
        mock_paginate.assert_called_once_with(
            client=mock_client,
            endpoint="users/someone/messages",
            max_pages=5,
            timeout=10,
        )

    @patch("hakiapi.clients.gmail.paginate")
    def test_search_injects_query_and_delegates(
        self, mock_paginate: MagicMock, mock_client: MagicMock
    ) -> None:
        resource = GmailMessagesResource(mock_client)
        mock_paginate.return_value = iter([{"id": "A"}])

        messages = list(resource.search("is:unread", user_id="me", max_pages=2))

        assert messages == [{"id": "A"}]
        mock_paginate.assert_called_once_with(
            client=mock_client,
            endpoint="users/me/messages",
            max_pages=2,
            params={"q": "is:unread"},
        )

    @patch("hakiapi.clients.gmail.paginate")
    def test_search_preserves_existing_params(
        self, mock_paginate: MagicMock, mock_client: MagicMock
    ) -> None:
        resource = GmailMessagesResource(mock_client)

        list(resource.search("label:INBOX", params={"includeSpamTrash": True}))

        mock_paginate.assert_called_once_with(
            client=mock_client,
            endpoint="users/me/messages",
            max_pages=None,
            params={"q": "label:INBOX", "includeSpamTrash": True},
        )

    @patch("hakiapi.clients.gmail.paginate")
    def test_search_does_not_mutate_caller_params(
        self, mock_paginate: MagicMock, mock_client: MagicMock
    ) -> None:
        resource = GmailMessagesResource(mock_client)
        caller_params = {"maxResults": 10}

        list(resource.search("is:unread", params=caller_params))

        assert caller_params == {"maxResults": 10}
        assert "q" not in caller_params


# GmailMessagesResource.send


class TestGmailMessagesSend:
    def test_send_posts_payload(self, mock_client: MagicMock) -> None:
        resource = GmailMessagesResource(mock_client)
        payload = {"raw": "base64url_encoded"}
        mock_client.post.return_value = {"id": "sent123"}

        result = resource.send(payload)

        mock_client.post.assert_called_once_with("users/me/messages/send", json=payload)
        assert result == {"id": "sent123"}

    def test_send_with_explicit_user(self, mock_client: MagicMock) -> None:
        resource = GmailMessagesResource(mock_client)
        payload = {"raw": "abc"}

        resource.send(payload, user_id="someone@example.com")

        mock_client.post.assert_called_once_with(
            "users/someone@example.com/messages/send", json=payload
        )


# GmailClient wiring


class TestGmailClientWiring:
    def test_mounts_resources(self) -> None:
        client = GmailClient(token="fake-token")

        assert isinstance(client.profile, GmailProfileResource)
        assert isinstance(client.labels, GmailLabelsResource)
        assert isinstance(client.messages, GmailMessagesResource)

    def test_base_url_is_gmail_v1(self) -> None:
        client = GmailClient(token="fake-token")
        assert client.base_url == "https://gmail.googleapis.com/gmail/v1"

    def test_uses_bearer_token_auth(self) -> None:
        client = GmailClient(token="fake-token")
        assert isinstance(getattr(client.session, "auth", None), BearerTokenAuth)
