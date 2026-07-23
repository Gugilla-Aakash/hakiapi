"""
Handles the OAuth 2.0 token refresh lifecycle.
"""
import time
from typing import Any

import requests

from .google import GOOGLE_TOKEN_URI, OAuthFlowError
from .token_store import OAuthToken, TokenStore


def refresh_access_token(
    token: OAuthToken,
    client_id: str,
    client_secret: str,
    store: TokenStore,
    token_uri: str = GOOGLE_TOKEN_URI,
) -> OAuthToken:
    """
    Uses an existing refresh token to securely obtain a fresh access token
    from Google without requiring user interaction.

    If the refresh request fails due to an invalid or revoked grant, the
    underlying TokenStore is automatically wiped so the system can cleanly
    fall back to a full interactive authorization flow on the next attempt.
    """
    if not token.refresh_token:
        raise ValueError("Cannot refresh an OAuthToken that has no refresh_token.")

    try:
        response = requests.post(
            token_uri,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": token.refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=30,
        )
    except requests.RequestException as e:
        raise OAuthFlowError(
            f"Could not reach Google's token endpoint for refresh: {e}"
        ) from e

    if not response.ok:
        # wipe the useless token from the store so the framework forces a fresh login next time.
        store.delete_token()
        raise OAuthFlowError(
            f"Token refresh failed ({response.status_code}). Token revoked or expired. "
            f"Response: {response.text}"
        )

    payload: dict[str, Any] = response.json()

    new_refresh_token = payload.get("refresh_token", token.refresh_token)

    # Calculate the exact timestamp when this new access token will die
    expires_in = payload.get("expires_in")
    expires_at = time.time() + expires_in if expires_in is not None else None

    granted_scope = payload.get("scope")
    scopes = granted_scope.split() if granted_scope else list(token.scopes)

    # Reconstruct the validated token state
    new_token = OAuthToken(
        access_token=payload["access_token"],
        refresh_token=new_refresh_token,
        expires_at=expires_at,
        scopes=scopes,
    )

    # Persist the new state immediately so subsequent runs use the fresh token
    store.save_token(new_token)

    return new_token
