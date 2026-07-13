from typing import Any


class HakiAPIError(Exception):
    """Base exception for all Haki API errors."""

    def __init__(
        self, message: str, status_code: int | None = None, response: Any | None = None
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response = response

    def __str__(self) -> str:
        if self.status_code:
            return f"[{self.status_code}] {self.message}"
        return self.message


class ClientError(HakiAPIError):
    """Raised when the API returns a 4xx status code."""

    pass


class ServerError(HakiAPIError):
    """Raised when the API returns a 5xx status code."""

    pass


class RateLimitError(ClientError):
    """Raised for HTTP 429 Too Many Requests."""

    def __init__(
        self,
        message: str,
        retry_after: int | float | None = None,
        status_code: int | None = 429,
        response: Any | None = None,
    ) -> None:
        super().__init__(message, status_code=status_code, response=response)
        self.retry_after = retry_after


class AuthenticationError(ClientError):
    """Raised for HTTP 401 Unauthorized and 403 Forbidden."""

    def __init__(
        self,
        message: str,
        auth_method: str | None = None,
        status_code: int | None = None,
        response: Any | None = None,
    ) -> None:
        super().__init__(message, status_code=status_code, response=response)
        self.auth_method = auth_method


class RequestTimeoutError(HakiAPIError):
    """
    Raised when a request times out at the network level.
    Inherits directly from base, as timeouts lack HTTP status codes.
    """

    def __init__(self, message: str, timeout_duration: float | None = None) -> None:
        # Status code and response are explicitly None for network timeouts
        super().__init__(message, status_code=None, response=None)
        self.timeout_duration = timeout_duration
