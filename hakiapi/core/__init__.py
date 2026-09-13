from typing import Any

from . import auth, exceptions, oauth, paginator, retry
from .base_client import BaseAPIClient

try:
    from .async_base_client import AsyncBaseAPIClient  # noqa: F401

    _ASYNC_AVAILABLE = True
except ImportError:
    _ASYNC_AVAILABLE = False

__all__ = [
    "BaseAPIClient",
    "auth",
    "exceptions",
    "oauth",
    "paginator",
    "retry",
]

if _ASYNC_AVAILABLE:
    __all__.append("AsyncBaseAPIClient")


def __getattr__(name: str) -> Any:
    if name == "AsyncBaseAPIClient":
        try:
            from .async_base_client import AsyncBaseAPIClient as _AsyncBaseAPIClient

            return _AsyncBaseAPIClient
        except ImportError as e:
            raise ImportError(
                "AsyncBaseAPIClient requires the 'async' extra: "
                "pip install hakiapi[async]"
            ) from e
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
