"""
Unit tests for GmailClient.

Strategy: mock `GmailClient.get()` and `GmailClient.get_messages_page()`
directly rather than the underlying HTTP layer. GmailClient inherits its
actual request machinery from BaseAPIClient, which should already have its
own dedicated test suite — these tests only need to verify GmailClient's
own logic: endpoint construction, parameter handling, and the pagination
generator in get_all_messages().

"""

from unittest.mock import patch

import pytest

from hakiapi.clients.gmail import GmailClient
from hakiapi.core.auth import BearerTokenAuth


@pytest.fixture
def client() -> GmailClient:
    """Provides a reusable GmailClient instance with a dummy token."""
    return GmailClient(token="fake-token")


class TestInit:
    def test_sets_correct_base_url(self, client: GmailClient) -> None:
        # BaseAPIClient automatically strips trailing slashes to normalize URLs
        assert client.base_url == "https://gmail.googleapis.com/gmail/v1"

    def test_configures_bearer_token_auth(self) -> None:
        client = GmailClient(token="my-secret-token")
        # Auth is bound directly to the underlying requests.Session object
        assert isinstance(getattr(client.session, "auth", None), BearerTokenAuth)

    def test_forwards_extra_kwargs_to_base_client(self) -> None:
        client = GmailClient(token="tok", timeout=30)
        assert getattr(client, "timeout", None) == 30


class TestGetProfile:
    def test_default_user_id(self, client: GmailClient) -> None:
        with patch.object(
            client, "get", return_value={"emailAddress": "me@example.com"}
        ) as mock_get:
            result = client.get_profile()

        mock_get.assert_called_once_with("users/me/profile")
        assert result == {"emailAddress": "me@example.com"}

    def test_custom_user_id(self, client: GmailClient) -> None:
        with patch.object(client, "get", return_value={}) as mock_get:
            client.get_profile(user_id="someone@example.com")

        mock_get.assert_called_once_with("users/someone@example.com/profile")

    def test_forwards_extra_kwargs(self, client: GmailClient) -> None:
        with patch.object(client, "get", return_value={}) as mock_get:
            client.get_profile(timeout=5)

        mock_get.assert_called_once_with("users/me/profile", timeout=5)


class TestGetMessage:
    def test_builds_correct_endpoint(self, client: GmailClient) -> None:
        with patch.object(client, "get", return_value={"id": "abc123"}) as mock_get:
            result = client.get_message("abc123")

        mock_get.assert_called_once_with("users/me/messages/abc123")
        assert result == {"id": "abc123"}

    def test_custom_user_id(self, client: GmailClient) -> None:
        with patch.object(client, "get", return_value={}) as mock_get:
            client.get_message("abc123", user_id="other@example.com")

        mock_get.assert_called_once_with("users/other@example.com/messages/abc123")

    def test_forwards_extra_kwargs(self, client: GmailClient) -> None:
        with patch.object(client, "get", return_value={}) as mock_get:
            client.get_message("abc123", format="full")

        mock_get.assert_called_once_with("users/me/messages/abc123", format="full")


class TestGetMessagesPage:
    def test_no_page_token(self, client: GmailClient) -> None:
        with patch.object(client, "get", return_value={"messages": []}) as mock_get:
            client.get_messages_page()

        mock_get.assert_called_once_with("users/me/messages", params={})

    def test_with_page_token(self, client: GmailClient) -> None:
        with patch.object(client, "get", return_value={"messages": []}) as mock_get:
            client.get_messages_page(page_token="TOKEN123")

        mock_get.assert_called_once_with(
            "users/me/messages", params={"pageToken": "TOKEN123"}
        )

    def test_preserves_existing_params(self, client: GmailClient) -> None:
        with patch.object(client, "get", return_value={"messages": []}) as mock_get:
            client.get_messages_page(page_token="TOKEN123", params={"q": "is:unread"})

        mock_get.assert_called_once_with(
            "users/me/messages",
            params={"q": "is:unread", "pageToken": "TOKEN123"},
        )

    def test_custom_user_id(self, client: GmailClient) -> None:
        with patch.object(client, "get", return_value={"messages": []}) as mock_get:
            client.get_messages_page(user_id="other@example.com")

        mock_get.assert_called_once_with("users/other@example.com/messages", params={})


class TestGetAllMessages:
    def test_yields_messages_from_single_page(self, client: GmailClient) -> None:
        response = {"messages": [{"id": "1"}, {"id": "2"}]}
        with patch.object(
            client, "get_messages_page", return_value=response
        ) as mock_page:
            results = list(client.get_all_messages())

        assert results == [{"id": "1"}, {"id": "2"}]
        mock_page.assert_called_once_with(user_id="me", page_token=None)

    def test_follows_pagination_across_multiple_pages(
        self, client: GmailClient
    ) -> None:
        page_1 = {"messages": [{"id": "1"}], "nextPageToken": "PAGE2"}
        page_2 = {"messages": [{"id": "2"}], "nextPageToken": "PAGE3"}
        page_3 = {"messages": [{"id": "3"}]}  # no nextPageToken -> stop

        with patch.object(
            client, "get_messages_page", side_effect=[page_1, page_2, page_3]
        ) as mock_page:
            results = list(client.get_all_messages())

        assert results == [{"id": "1"}, {"id": "2"}, {"id": "3"}]
        assert mock_page.call_count == 3
        mock_page.assert_any_call(user_id="me", page_token=None)
        mock_page.assert_any_call(user_id="me", page_token="PAGE2")
        mock_page.assert_any_call(user_id="me", page_token="PAGE3")

    def test_stops_when_next_page_token_missing(self, client: GmailClient) -> None:
        with patch.object(
            client, "get_messages_page", return_value={"messages": [{"id": "1"}]}
        ) as mock_page:
            results = list(client.get_all_messages())

        assert results == [{"id": "1"}]
        mock_page.assert_called_once()

    def test_handles_empty_inbox(self, client: GmailClient) -> None:
        with patch.object(
            client, "get_messages_page", return_value={"messages": []}
        ) as mock_page:
            results = list(client.get_all_messages())

        assert results == []
        mock_page.assert_called_once()

    def test_handles_missing_messages_key(self, client: GmailClient) -> None:
        # Defensive: API could theoretically omit "messages" on an empty inbox
        with patch.object(client, "get_messages_page", return_value={}) as mock_page:
            results = list(client.get_all_messages())

        assert results == []
        # Consume the variable to prove the internal HTTP layer was called
        mock_page.assert_called_once()

    def test_is_lazy_and_lets_caller_control_fetch_timing(
        self, client: GmailClient
    ) -> None:
        page_1 = {"messages": [{"id": "1"}], "nextPageToken": "PAGE2"}
        page_2 = {"messages": [{"id": "2"}]}

        with patch.object(
            client, "get_messages_page", side_effect=[page_1, page_2]
        ) as mock_page:
            gen = client.get_all_messages()
            assert mock_page.call_count == 0  # nothing fetched until iteration starts

            assert next(gen) == {"id": "1"}
            assert mock_page.call_count == 1

            assert next(gen) == {"id": "2"}
            assert mock_page.call_count == 2

            with pytest.raises(StopIteration):
                next(gen)

    def test_forwards_extra_kwargs_to_each_page(self, client: GmailClient) -> None:
        with patch.object(
            client, "get_messages_page", return_value={"messages": []}
        ) as mock_page:
            list(client.get_all_messages(user_id="me", q="is:unread"))

        mock_page.assert_called_once_with(user_id="me", page_token=None, q="is:unread")
