import time
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest
import requests

# Adjust this import path if your oauth folder is not inside 'core'
from hakiapi.core.oauth.google import GoogleOAuthFlow, OAuthFlowError
from hakiapi.core.oauth.token_store import OAuthToken


@pytest.fixture
def mock_store() -> MagicMock:
    return MagicMock()


@pytest.fixture
def flow(mock_store: MagicMock) -> GoogleOAuthFlow:
    return GoogleOAuthFlow(
        client_id="fake-client-id",
        client_secret="fake-secret",
        scopes=["calendar.readonly"],
        store=mock_store,
        redirect_port=8765,
    )


# URL Building & Payload Mapping


class TestGoogleOAuthFlowOfflineLogic:
    def test_build_auth_url_contains_required_params(
        self, flow: GoogleOAuthFlow
    ) -> None:
        url = flow.build_auth_url(state="secure-state")

        parsed = urlparse(url)
        assert parsed.scheme == "https"
        assert parsed.netloc == "accounts.google.com"
        assert parsed.path == "/o/oauth2/v2/auth"

        params = parse_qs(parsed.query)
        assert params["client_id"][0] == "fake-client-id"
        assert params["redirect_uri"][0] == "http://localhost:8765/"
        assert params["response_type"][0] == "code"
        assert params["scope"][0] == "calendar.readonly"
        assert params["access_type"][0] == "offline"
        assert params["prompt"][0] == "consent"
        assert params["state"][0] == "secure-state"

    def test_token_from_payload_maps_correctly(self, flow: GoogleOAuthFlow) -> None:
        payload = {
            "access_token": "ya29.abc",
            "refresh_token": "1//def",
            "expires_in": 3599,
            "scope": "calendar.readonly gmail.readonly",
            "token_type": "Bearer",
        }

        now = time.time()
        token = flow._token_from_payload(payload)

        assert token.access_token == "ya29.abc"
        assert token.refresh_token == "1//def"
        assert token.scopes == ["calendar.readonly", "gmail.readonly"]
        # Allow a 1-second margin of error for the timestamp calculation
        assert token.expires_at is not None
        assert (now + 3598) < token.expires_at < (now + 3600)


# The Authorization Flow & HTTP Server


class TestGoogleOAuthFlowAuthorize:
    @patch("hakiapi.core.oauth.google.webbrowser.open")
    def test_authorize_success_flow(
        self,
        mock_webbrowser: MagicMock,
        flow: GoogleOAuthFlow,
        mock_store: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Mock the server capture returning a valid code and matching state
        mock_capture = MagicMock(
            return_value={"code": "auth-code-123", "state": "mock-state", "error": None}
        )
        monkeypatch.setattr(flow, "_capture_redirect", mock_capture)

        # Mock the random state generator so we know what to expect
        monkeypatch.setattr(
            "hakiapi.core.oauth.google.secrets.token_urlsafe", lambda _: "mock-state"
        )

        # Mock the final token exchange POST request
        expected_token = OAuthToken(access_token="final-access-token")
        mock_exchange = MagicMock(return_value=expected_token)
        monkeypatch.setattr(flow, "exchange_code_for_token", mock_exchange)

        result = flow.authorize()

        # Verifications
        mock_webbrowser.assert_called_once()
        mock_capture.assert_called_once()
        mock_exchange.assert_called_once_with("auth-code-123")

        # FIX: Call the assertion directly on the mock_store fixture
        mock_store.save_token.assert_called_once_with(expected_token)
        assert result == expected_token

    @patch("hakiapi.core.oauth.google.webbrowser.open")
    def test_authorize_raises_if_state_mismatches(
        self,
        mock_webbrowser: MagicMock,
        flow: GoogleOAuthFlow,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Simulate a forged redirect where the state doesn't match
        mock_capture = MagicMock(
            return_value={"code": "code", "state": "FORGED-STATE", "error": None}
        )
        monkeypatch.setattr(flow, "_capture_redirect", mock_capture)
        monkeypatch.setattr(
            "hakiapi.core.oauth.google.secrets.token_urlsafe", lambda _: "real-state"
        )

        with pytest.raises(OAuthFlowError, match="didn't match what was sent"):
            flow.authorize()

    @patch("hakiapi.core.oauth.google.webbrowser.open")
    def test_authorize_raises_on_google_error(
        self,
        mock_webbrowser: MagicMock,
        flow: GoogleOAuthFlow,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Simulate the user clicking "Cancel" on the Google consent screen
        mock_capture = MagicMock(
            return_value={"code": None, "state": "state", "error": "access_denied"}
        )
        monkeypatch.setattr(flow, "_capture_redirect", mock_capture)

        with pytest.raises(
            OAuthFlowError, match="Google denied authorization: access_denied"
        ):
            flow.authorize()


# The Token Exchange Request


class TestGoogleOAuthFlowExchange:
    @patch("hakiapi.core.oauth.google.requests.post")
    def test_exchange_code_for_token_success(
        self, mock_post: MagicMock, flow: GoogleOAuthFlow
    ) -> None:
        # Create a fake successful response
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "access_token": "new-token",
            "expires_in": 3600,
        }
        mock_post.return_value = mock_response

        token = flow.exchange_code_for_token("auth-code-123")

        assert token.access_token == "new-token"
        mock_post.assert_called_once()
        # Verify it passed the right data to Google
        post_kwargs = mock_post.call_args.kwargs
        assert post_kwargs["data"]["code"] == "auth-code-123"
        assert post_kwargs["data"]["grant_type"] == "authorization_code"

    @patch("hakiapi.core.oauth.google.requests.post")
    def test_exchange_code_for_token_http_error(
        self, mock_post: MagicMock, flow: GoogleOAuthFlow
    ) -> None:
        mock_post.side_effect = requests.RequestException("Network down")

        with pytest.raises(
            OAuthFlowError, match="Could not reach Google's token endpoint"
        ):
            flow.exchange_code_for_token("auth-code-123")

    @patch("hakiapi.core.oauth.google.requests.post")
    def test_exchange_code_for_token_invalid_grant(
        self, mock_post: MagicMock, flow: GoogleOAuthFlow
    ) -> None:
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 400
        mock_response.text = '{"error": "invalid_grant"}'
        mock_post.return_value = mock_response

        with pytest.raises(OAuthFlowError, match="Token exchange failed"):
            flow.exchange_code_for_token("auth-code-123")


# get_token (The Entrypoint)


class TestGoogleOAuthFlowGetToken:
    def test_get_token_returns_existing_valid_token(
        self, flow: GoogleOAuthFlow, mock_store: MagicMock
    ) -> None:
        # Create a valid token that expires far in the future
        valid_token = OAuthToken(access_token="valid", expires_at=time.time() + 3600)

        # FIX: Set the return value directly on the mock_store
        mock_store.get_token.return_value = valid_token

        result = flow.get_token()

        # Should return the existing token without calling authorize()
        assert result == valid_token
        mock_store.get_token.assert_called_once()

    def test_get_token_triggers_authorize_if_missing(
        self,
        flow: GoogleOAuthFlow,
        mock_store: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_store.get_token.return_value = None

        mock_authorize = MagicMock(return_value=OAuthToken(access_token="new"))
        monkeypatch.setattr(flow, "authorize", mock_authorize)

        result = flow.get_token()

        assert result.access_token == "new"
        mock_authorize.assert_called_once()

    def test_get_token_triggers_authorize_if_expired(
        self,
        flow: GoogleOAuthFlow,
        mock_store: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        expired_token = OAuthToken(access_token="expired", expires_at=time.time() - 100)

        mock_store.get_token.return_value = expired_token

        mock_authorize = MagicMock(return_value=OAuthToken(access_token="fresh"))
        monkeypatch.setattr(flow, "authorize", mock_authorize)

        result = flow.get_token()

        assert result.access_token == "fresh"
        mock_authorize.assert_called_once()

    def test_get_token_force_bypasses_store(
        self,
        flow: GoogleOAuthFlow,
        mock_store: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        valid_token = OAuthToken(access_token="valid", expires_at=time.time() + 3600)

        mock_store.get_token.return_value = valid_token

        mock_authorize = MagicMock(return_value=OAuthToken(access_token="forced-new"))
        monkeypatch.setattr(flow, "authorize", mock_authorize)

        result = flow.get_token(force=True)

        assert result.access_token == "forced-new"
        mock_authorize.assert_called_once()
