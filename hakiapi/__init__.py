# HakiAPI - A modern, strongly-typed API client framework.

from .core.base_client import BaseAPIClient
from .clients.github import GitHubClient
from .clients.gmail import GmailClient
from .clients.google_calendar import GoogleCalendarClient
from importlib.metadata import PackageNotFoundError, version
from .core import exceptions
from .core import auth
from .core import retry
from .core import paginator

try:
    __version__ = version("hakiapi")
except PackageNotFoundError:
    __version__ = "0.1.0"

__all__ = [
    "BaseAPIClient",
    "GitHubClient",
    "GmailClient",
    "GoogleCalendarClient",
    "exceptions",
    "auth",
    "retry",
    "paginator",
    "__version__",
]
