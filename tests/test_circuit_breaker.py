# tests/test_circuit_breaker.py

from unittest.mock import patch

import pytest

from hakiapi.core.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
)
from hakiapi.core.exceptions import HakiAPIError


class DummyError(HakiAPIError):
    pass


def test_initial_state_is_closed():
    cb = CircuitBreaker()

    assert cb.state == CircuitState.CLOSED
    assert cb._failure_count == 0


def test_successful_call_returns_value():
    cb = CircuitBreaker()

    @cb
    def func():
        return 42

    assert func() == 42
    assert cb.state == CircuitState.CLOSED
    assert cb._failure_count == 0


def test_failure_increments_failure_count():
    cb = CircuitBreaker(failure_threshold=5)

    @cb
    def func():
        raise DummyError("boom")

    with pytest.raises(DummyError):
        func()

    assert cb._failure_count == 1
    assert cb.state == CircuitState.CLOSED


def test_circuit_opens_after_threshold():
    cb = CircuitBreaker(failure_threshold=2)

    @cb
    def func():
        raise DummyError("error")

    with pytest.raises(DummyError):
        func()

    with pytest.raises(DummyError):
        func()

    assert cb.state == CircuitState.OPEN


def test_open_circuit_blocks_calls():
    cb = CircuitBreaker(failure_threshold=1)

    @cb
    def func():
        raise DummyError("error")

    with pytest.raises(DummyError):
        func()

    with pytest.raises(CircuitOpenError):
        func()


def test_retry_after_is_non_negative():
    cb = CircuitBreaker(
        failure_threshold=1,
        recovery_timeout=10,
    )

    @cb
    def func():
        raise DummyError("error")

    with pytest.raises(DummyError):
        func()

    with pytest.raises(CircuitOpenError) as exc:
        func()

    # 1. Assert it's not None (satisfies Pyright)
    assert exc.value.retry_after is not None

    # 2. Now safely check if it's >= 0
    assert exc.value.retry_after >= 0


def test_half_open_after_timeout():
    cb = CircuitBreaker(
        failure_threshold=1,
        recovery_timeout=10,
    )

    with patch("hakiapi.core.circuit_breaker.time.monotonic") as mono:
        mono.return_value = 0

        @cb
        def func():
            raise DummyError("error")

        with pytest.raises(DummyError):
            func()

        mono.return_value = 11

        assert cb.state == CircuitState.HALF_OPEN


def test_half_open_success_closes_circuit():
    cb = CircuitBreaker(
        failure_threshold=1,
        recovery_timeout=10,
    )

    with patch("hakiapi.core.circuit_breaker.time.monotonic") as mono:
        mono.return_value = 0

        @cb
        def fail():
            raise DummyError("error")

        with pytest.raises(DummyError):
            fail()

        mono.return_value = 11

        @cb
        def success():
            return "ok"

        assert success() == "ok"

        assert cb.state == CircuitState.CLOSED
        assert cb._failure_count == 0


def test_half_open_failure_reopens():
    cb = CircuitBreaker(
        failure_threshold=1,
        recovery_timeout=10,
    )

    with patch("hakiapi.core.circuit_breaker.time.monotonic") as mono:
        mono.return_value = 0

        @cb
        def func():
            raise DummyError("error")

        with pytest.raises(DummyError):
            func()

        mono.return_value = 11

        with pytest.raises(DummyError):
            func()

        assert cb.state == CircuitState.OPEN


def test_success_resets_failure_counter():
    cb = CircuitBreaker(failure_threshold=5)

    @cb
    def fail():
        raise DummyError("error")

    @cb
    def success():
        return True

    with pytest.raises(DummyError):
        fail()

    assert cb._failure_count == 1

    success()

    assert cb._failure_count == 0


def test_unexpected_exception_not_counted():
    cb = CircuitBreaker(
        failure_threshold=2,
        expected_exceptions=(DummyError,),
    )

    @cb
    def func():
        raise ValueError()

    with pytest.raises(ValueError):
        func()

    assert cb._failure_count == 0
    assert cb.state == CircuitState.CLOSED


@pytest.mark.parametrize("threshold", [0, -1, -10])
def test_threshold_is_clamped(threshold):
    cb = CircuitBreaker(failure_threshold=threshold)

    assert cb.failure_threshold == 1


@pytest.mark.parametrize("timeout", [0, -5, -100])
def test_timeout_is_clamped(timeout):
    cb = CircuitBreaker(recovery_timeout=timeout)

    assert cb.recovery_timeout == 0.1


def test_multiple_success_calls_keep_closed():
    cb = CircuitBreaker()

    @cb
    def func():
        return 1

    for _ in range(20):
        assert func() == 1

    assert cb.state == CircuitState.CLOSED


def test_circuit_open_error_contains_retry_after():
    err = CircuitOpenError(
        retry_after=12.5,
    )

    assert err.retry_after == 12.5
