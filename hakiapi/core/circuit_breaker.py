from __future__ import annotations

import threading
from enum import Enum
from typing import Any

from .exceptions import HakiAPIError


class CircuitState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitOpenError(HakiAPIError):
    def __init__(
        self,
        message: str = "Circuit breaker is OPEN.",
        retry_after: float | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message=message, **kwargs)
        self.retry_after = retry_after


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        expected_exceptions: tuple[type[Exception], ...] = (HakiAPIError,),
    ) -> None:
        self.failure_threshold = max(1, failure_threshold)
        self.recovery_timeout = max(0.1, recovery_timeout)
        self.expected_exceptions = expected_exceptions

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._lock = threading.Lock()
