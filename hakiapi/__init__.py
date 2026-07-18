# HakiAPI - A modern, strongly-typed API client framework.

from .core.base_client import BaseAPIClient
from .clients.github import GitHubClient
from .clients.gmail import GmailClient

from .core import exceptions
from .core import auth
from .core import retry
from .core import paginator

__all__ = [
    "BaseAPIClient",
    "GitHubClient",
    "GmailClient",
    "exceptions",
    "auth",
    "retry",
    "paginator",
]
