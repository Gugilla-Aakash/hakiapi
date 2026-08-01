from __future__ import annotations

import time
import threading
from enum import Enum
from typing import Any, Callable, TypeVar

from .exceptions import HakiAPIError

T = TypeVar("T")


class CircuitState(Enum):
    CLOSED = "CLOSED"         # Normal operation: requests flow through
    OPEN = "OPEN"             # Failing fast: requests are blocked instantly
    HALF_OPEN = "HALF_OPEN"   # Testing recovery: a single trial request is allowed


class CircuitOpenError(HakiAPIError):
    """Raised when an API call is blocked because the circuit breaker is OPEN."""
    def __init__(self, message: str = "Circuit breaker is OPEN. Request blocked.", retry_after: float | None = None, **kwargs: Any) -> None:
        super().__init__(message=message, **kwargs)
        self.retry_after = retry_after


class CircuitBreaker:
    """
    Thread-safe implementation of the Circuit Breaker pattern.
    Protects downstream services from cascading failures and prevents resource exhaustion.
    """
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

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                # Check if recovery timeout has elapsed to transition to HALF_OPEN
                if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
            return self._state

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        """Decorator support for wrapping synchronous methods/functions."""
        def wrapper(*args: Any, **kwargs: Any) -> T:
            current_state = self.state

            if current_state == CircuitState.OPEN:
                remaining_cooldown = self.recovery_timeout - (time.monotonic() - self._last_failure_time)
                raise CircuitOpenError(
                    message=f"Circuit is OPEN. Fast-failing request for {func.__name__}.",
                    retry_after=max(0.0, remaining_cooldown),
                )

            try:
                result = func(*args, **kwargs)
                self._on_success()
                return result
            except self.expected_exceptions as e:
                self._on_failure()
                raise e

        return wrapper

    def _on_success(self) -> None:
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                # Recovery successful, close the circuit
                self._state = CircuitState.CLOSED
                self._failure_count = 0
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on normal success
                self._failure_count = 0

    def _on_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            if self._state == CircuitState.HALF_OPEN:
                # Trial request failed, reopen the circuit immediately
                self._state = CircuitState.OPEN
            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.failure_threshold:
                    self._state = CircuitState.OPEN
