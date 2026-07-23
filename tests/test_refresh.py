"""
Tests for the OAuth 2.0 refresh flow.
"""

import time
from unittest.mock import MagicMock, patch

import pytest
import requests

# Adjust this import path if your oauth folder is not inside 'core'
from hakiapi.core.oauth.google import OAuthFlowError
from hakiapi.core.oauth.refresh import refresh_access_token
from hakiapi.core.oauth.token_store import OAuthToken


@pytest.fixture
def mock_store() -> MagicMock:
    return MagicMock()


@pytest.fixture
def expired_token() -> OAuthToken:
    """A standard token that has expired but possesses a refresh_token."""
    return OAuthToken(
        access_token="old-access-token",
        refresh_token="old-refresh-token",
        expires_at=time.time() - 3600,  # Expired an hour ago
        scopes=["calendar.readonly", "gmail.readonly"],
    )


# Pre-Flight Validation


class TestRefreshValidation:
    def test_missing_refresh_token_raises_value_error(
        self, mock_store: MagicMock
    ) -> None:
        token_without_refresh = OAuthToken(access_token="only-access")

        with pytest.raises(
            ValueError, match="Cannot refresh an OAuthToken that has no refresh_token"
        ):
            refresh_access_token(
                token=token_without_refresh,
                client_id="client-id",
                client_secret="client-secret",
                store=mock_store,
            )


# Network & Rejection Handling


class TestRefreshErrorHandling:
    @patch("hakiapi.core.oauth.refresh.requests.post")
    def test_network_failure_raises_oauth_error(
        self, mock_post: MagicMock, expired_token: OAuthToken, mock_store: MagicMock
    ) -> None:
        mock_post.side_effect = requests.RequestException("DNS resolution failed")

        with pytest.raises(
            OAuthFlowError, match="Could not reach Google's token endpoint for refresh"
        ):
            refresh_access_token(expired_token, "client-id", "secret", mock_store)

    @patch("hakiapi.core.oauth.refresh.requests.post")
    def test_rejected_token_wipes_store_and_raises(
        self, mock_post: MagicMock, expired_token: OAuthToken, mock_store: MagicMock
    ) -> None:
        # Simulate Google rejecting the refresh token (e.g., user revoked access)
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 400
        mock_response.text = '{"error": "invalid_grant"}'
        mock_post.return_value = mock_response

        with pytest.raises(OAuthFlowError, match="Token refresh failed"):
            refresh_access_token(expired_token, "client-id", "secret", mock_store)

        mock_store.delete_token.assert_called_once()
        mock_store.save_token.assert_not_called()


# Successful Token Exchange & Fallbacks


class TestRefreshSuccess:
    @patch("hakiapi.core.oauth.refresh.requests.post")
    def test_success_with_new_refresh_token_and_scopes(
        self, mock_post: MagicMock, expired_token: OAuthToken, mock_store: MagicMock
    ) -> None:
        # Simulate a full payload where Google gives us a brand new refresh token
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "access_token": "brand-new-access",
            "refresh_token": "brand-new-refresh",
            "expires_in": 3600,
            "scope": "calendar.readonly gmail.readonly openid",
        }
        mock_post.return_value = mock_response

        now = time.time()
        new_token = refresh_access_token(
            expired_token, "client-id", "secret", mock_store
        )

        # Verify POST payload sent to Google
        mock_post.assert_called_once()
        post_data = mock_post.call_args.kwargs["data"]
        assert post_data["refresh_token"] == "old-refresh-token"
        assert post_data["grant_type"] == "refresh_token"

        # Verify the new token state
        assert new_token.access_token == "brand-new-access"
        assert new_token.refresh_token == "brand-new-refresh"
        assert new_token.scopes == ["calendar.readonly", "gmail.readonly", "openid"]
        assert new_token.expires_at is not None
        assert (now + 3595) < new_token.expires_at < (now + 3605)

        # Verify the new state was immediately persisted
        mock_store.save_token.assert_called_once_with(new_token)

    @patch("hakiapi.core.oauth.refresh.requests.post")
    def test_success_falls_back_to_old_refresh_token_and_scopes(
        self, mock_post: MagicMock, expired_token: OAuthToken, mock_store: MagicMock
    ) -> None:
        # Simulate a sparse payload where Google omits the refresh_token and scope
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "access_token": "brand-new-access",
            "expires_in": 3600,
        }
        mock_post.return_value = mock_response

        new_token = refresh_access_token(
            expired_token, "client-id", "secret", mock_store
        )

        # Verify the fallback magic worked
        assert new_token.access_token == "brand-new-access"
        assert new_token.refresh_token == "old-refresh-token"
        assert new_token.scopes == ["calendar.readonly", "gmail.readonly"]

        mock_store.save_token.assert_called_once_with(new_token)
