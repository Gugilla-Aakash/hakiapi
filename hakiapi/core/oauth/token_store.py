from __future__ import annotations

import json
import os
import tempfile
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class OAuthToken:
    """
    Represents the current OAuth 2.0 token state.

    `expires_at` is stored as a Unix timestamp (seconds) so the expiration time
    is always absolute, even after the token is serialized or read from disk.
    """

    access_token: str
    refresh_token: str | None = None
    expires_at: float | None = None
    scopes: list[str] = field(default_factory=list)

    @property
    def is_expired(self) -> bool:
        """
        Returns True if the token has expired or will expire soon.

        If `expires_at` is missing, the token is assumed to never expire. A small
        buffer is applied to refresh the token before it reaches its expiration time.
        """
        if self.expires_at is None:
            return False
        leeway_seconds = 30
        return time.time() >= (self.expires_at - leeway_seconds)

    def to_dict(self) -> dict[str, Any]:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
            "scopes": list(self.scopes),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OAuthToken:
        if not isinstance(data, dict):
            raise ValueError("Token data must be a dictionary object.")

        try:
            access_token = data["access_token"]
        except KeyError as e:
            raise ValueError(
                "Token data is missing required 'access_token' field."
            ) from e

        if not isinstance(access_token, str):
            raise ValueError("Required 'access_token' field must be a string.")

        return cls(
            access_token=access_token,
            refresh_token=data.get("refresh_token"),
            expires_at=data.get("expires_at"),
            scopes=list(data.get("scopes") or []),
        )


class TokenStore(ABC):
    """
    Abstract interface for storing and retrieving an OAuth token.

    Implementations decide where the token is stored, such as a file,
    database, or secrets manager. Other parts of the application only
    interact with this interface, making it easy to change the storage
    backend without affecting the rest of the code.
    """

    @abstractmethod
    def get_token(self) -> OAuthToken | None:
        """Return the stored token, or None if no token has been saved yet."""
        raise NotImplementedError

    @abstractmethod
    def save_token(self, token: OAuthToken) -> None:
        """Persist the given token, overwriting any previously stored token."""
        raise NotImplementedError

    @abstractmethod
    def delete_token(self) -> None:
        """Remove the stored token, if any. Must be safe to call when none exists."""
        raise NotImplementedError


class FileTokenStore(TokenStore):
    """
    Stores the OAuth token in a local JSON file.

    Updates are written atomically by writing to a temporary file first and
    then replacing the original file. The token file is created with 0600
    permissions since it contains sensitive credentials.
    """

    def __init__(self, path: str | Path = "token.json") -> None:
        self.path = Path(path)

    def get_token(self) -> OAuthToken | None:
        if not self.path.exists():
            return None

        try:
            raw = self.path.read_text(encoding="utf-8")
        except OSError as e:
            raise OSError(f"Failed to read token file at {self.path}: {e}") from e

        if not raw.strip():
            return None

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"Token file at {self.path} is not valid JSON.") from e

        return OAuthToken.from_dict(data)

    def save_token(self, token: OAuthToken) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

        fd, tmp_path = tempfile.mkstemp(
            dir=self.path.parent,
            prefix=f".{self.path.name}.",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(token.to_dict(), f, indent=2)

            os.chmod(tmp_path, 0o600)
            os.replace(tmp_path, self.path)
        except BaseException:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise

    def delete_token(self) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass
