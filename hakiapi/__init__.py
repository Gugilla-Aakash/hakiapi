# HakiAPI - A modern, strongly-typed API client framework.

from .core.base_client import BaseAPIClient
from .clients.github import GitHubClient

from .core import exceptions
from .core import auth
from .core import retry
from .core import paginator

__all__ = [
    "BaseAPIClient",
    "GitHubClient",
    "exceptions",
    "auth",
    "retry",
    "paginator",
]
