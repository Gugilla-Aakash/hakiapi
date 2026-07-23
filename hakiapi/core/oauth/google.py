from __future__ import annotations

import secrets
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import requests

from ..exceptions import HakiAPIError
from .token_store import OAuthToken, TokenStore

GOOGLE_AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"


class OAuthFlowError(HakiAPIError):
    """
    Raised when the interactive browser flow can't complete — the user
    denies consent, the redirect never arrives, or Google's token
    endpoint rejects the exchange.
    """

    pass


class _CallbackHandler(BaseHTTPRequestHandler):
    """
    One-shot handler for Google's redirect back to localhost.

    A fresh instance of this class is created per request by
    http.server, so results are stashed on `self.server` (the single
    HTTPServer instance) rather than on `self` — that's how the code
    makes it back out to `GoogleOAuthFlow`.
    """

    def do_GET(self) -> None:  # noqa: N802 — required name for http.server
        params = parse_qs(urlparse(self.path).query)

        self.server.oauth_result = {  # type: ignore[attr-defined]
            "code": params.get("code", [None])[0],
            "state": params.get("state", [None])[0],
            "error": params.get("error", [None])[0],
        }

        if self.server.oauth_result["error"]:  # type: ignore[attr-defined]
            body = (
                "<html><body><h1>Authorization failed</h1>"
                "<p>You can close this tab and return to your app.</p></body></html>"
            )
        else:
            body = (
                "<html><body><h1>Authorization complete</h1>"
                "<p>You can close this tab and return to your app.</p></body></html>"
            )

        encoded = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: Any) -> None:
        # Silence http.server's default per-request logging to stderr.
        pass


class GoogleOAuthFlow:
    """
    Drives Google's OAuth 2.0 Authorization Code flow end-to-end.

    Given a client_id/client_secret from Google Cloud, the scopes an
    app needs, and a TokenStore to persist the result, this builds the
    consent URL, opens it in the developer's browser, catches the
    redirect on localhost, exchanges the code for real tokens, and
    saves them.

    The `redirect_port` must match a "http://localhost:<port>/" entry
    registered as an authorized redirect URI for this client_id in the
    Google Cloud Console, or Google will refuse the redirect.
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        scopes: list[str],
        store: TokenStore,
        redirect_port: int = 8765,
        auth_uri: str = GOOGLE_AUTH_URI,
        token_uri: str = GOOGLE_TOKEN_URI,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.scopes = scopes
        self.store = store
        self.redirect_port = redirect_port
        self.redirect_uri = f"http://localhost:{redirect_port}/"
        self.auth_uri = auth_uri
        self.token_uri = token_uri

    def build_auth_url(self, state: str) -> str:
        """Construct the Google consent-screen URL for this flow."""
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.scopes),
            "access_type": "offline",  # request a refresh_token, not just an access_token
            "prompt": "consent",  # without this, repeat runs may not re-issue a refresh_token
            "state": state,
        }
        return f"{self.auth_uri}?{urlencode(params)}"

    def authorize(self, timeout: float = 120.0) -> OAuthToken:
        """
        Run the full interactive flow: open the browser, wait for the
        user to grant (or deny) consent, exchange the resulting code
        for tokens, persist them, and return the token.

        Raises OAuthFlowError if the user denies consent, nothing
        arrives within `timeout` seconds, the redirect's `state`
        doesn't match what was sent (a CSRF signal), or the token
        exchange itself fails.
        """
        state = secrets.token_urlsafe(24)
        auth_url = self.build_auth_url(state=state)

        webbrowser.open(auth_url)

        result = self._capture_redirect(timeout=timeout)

        if result["error"]:
            raise OAuthFlowError(f"Google denied authorization: {result['error']}")

        if not result["code"]:
            raise OAuthFlowError(
                "Google's redirect didn't include an authorization code."
            )

        if result["state"] != state:
            raise OAuthFlowError(
                "The 'state' on Google's redirect didn't match what was sent — "
                "aborting in case this is a forged redirect."
            )

        token = self.exchange_code_for_token(result["code"])
        self.store.save_token(token)
        return token

    def exchange_code_for_token(self, code: str) -> OAuthToken:
        """
        Trade a one-time authorization code for a real token set by
        calling Google's token endpoint directly. No browser involved —
        this is a plain server-to-server POST.
        """
        try:
            response = requests.post(
                self.token_uri,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": self.redirect_uri,
                },
                timeout=30,
            )
        except requests.RequestException as e:
            raise OAuthFlowError(f"Could not reach Google's token endpoint: {e}") from e

        if not response.ok:
            raise OAuthFlowError(
                f"Token exchange failed ({response.status_code}): {response.text}"
            )

        return self._token_from_payload(response.json())

    def _token_from_payload(self, payload: dict[str, Any]) -> OAuthToken:
        """Map a raw Google token-endpoint JSON payload onto our OAuthToken."""
        expires_in = payload.get("expires_in")
        expires_at = time.time() + expires_in if expires_in is not None else None

        granted_scope = payload.get("scope")
        scopes = granted_scope.split() if granted_scope else list(self.scopes)

        return OAuthToken(
            access_token=payload["access_token"],
            refresh_token=payload.get("refresh_token"),
            expires_at=expires_at,
            scopes=scopes,
        )

    def _capture_redirect(self, timeout: float) -> dict[str, str | None]:
        """
        Boot a local HTTP server for exactly one request, block until
        Google's redirect (or `timeout`) arrives, then shut down.
        """
        try:
            server = HTTPServer(("localhost", self.redirect_port), _CallbackHandler)
        except OSError as e:
            raise OAuthFlowError(
                f"Couldn't start the local server on port {self.redirect_port} "
                f"(is something else already using it?): {e}"
            ) from e

        server.timeout = timeout
        server.oauth_result = None  # type: ignore[attr-defined]

        try:
            server.handle_request()  # blocks for one request, or up to `timeout` seconds
        finally:
            server.server_close()

        result = server.oauth_result  # type: ignore[attr-defined]
        if result is None:
            raise OAuthFlowError(
                f"Timed out after {timeout:.0f}s waiting for Google's redirect. "
                "Did the consent screen get completed in the browser?"
            )

        return result

    def get_token(self, force: bool = False) -> OAuthToken:
        """
        Return a usable token, running the interactive browser flow
        only when nothing valid is already saved.

        This does not refresh an expired-but-refreshable token itself —
        that's a job for a dedicated refresh routine sitting alongside
        the TokenStore — it simply re-runs the full consent flow when
        the stored token (if any) is missing or expired.
        """
        if not force:
            existing = self.store.get_token()
            if existing is not None and not existing.is_expired:
                return existing

        return self.authorize()
