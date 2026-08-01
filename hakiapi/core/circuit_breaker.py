from enum import Enum
from typing import Any

from .exceptions import HakiAPIError


class CircuitState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitOpenError(HakiAPIError):
    """Raised when requests are blocked because the circuit is open."""

    def __init__(
        self,
        message: str = "Circuit breaker is OPEN.",
        retry_after: float | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message=message, **kwargs)
        self.retry_after = retry_after
