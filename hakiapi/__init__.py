# HakiAPI - A modern, strongly-typed API client framework.

from importlib.metadata import PackageNotFoundError, version

from .clients.github import GitHubClient
from .clients.gmail import GmailClient
from .clients.google_calendar import GoogleCalendarClient
from .core import auth, exceptions, paginator, retry
from .core.base_client import BaseAPIClient

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
