# HakiAPI - A modern, strongly-typed API client framework.

from importlib.metadata import PackageNotFoundError, version
from typing import Any

from .clients.github import GitHubClient
from .clients.gmail import GmailClient
from .clients.google_calendar import GoogleCalendarClient
from .core import auth, exceptions, paginator, retry
from .core.base_client import BaseAPIClient

try:
    from .core.async_base_client import AsyncBaseAPIClient  # noqa: F401

    _ASYNC_AVAILABLE = True
except ImportError:
    _ASYNC_AVAILABLE = False

try:
    __version__ = version("hakiapi")
except PackageNotFoundError:
    __version__ = "0.1.0"

__all__ = [
    "BaseAPIClient",
    "GitHubClient",
    "GmailClient",
    "GoogleCalendarClient",
    "__version__",
    "auth",
    "exceptions",
    "paginator",
    "retry",
]

if _ASYNC_AVAILABLE:
    __all__.append("AsyncBaseAPIClient")


def __getattr__(name: str) -> Any:
    if name == "AsyncBaseAPIClient":
        try:
            from .core.async_base_client import (
                AsyncBaseAPIClient as _AsyncBaseAPIClient,
            )

            return _AsyncBaseAPIClient
        except ImportError as e:
            raise ImportError(
                "AsyncBaseAPIClient requires the 'async' extra: "
                "pip install hakiapi[async]"
            ) from e
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
