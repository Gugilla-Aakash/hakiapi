"""
Tests for the custom exceptions used in HakiAPI.

These tests make sure that:
- Exception messages are formatted correctly, with or without a status code.
- The exception hierarchy stays intact, so catching broader exceptions
  (like ClientError or HakiAPIError) continues to work as expected.
- Extra attributes such as `retry_after` and `auth_method` are available,
  default to None, and can be assigned values.
- Common attributes like `status_code` and `response` are stored correctly
  across all exception types.
- Exception chaining (`raise ... from ...`) preserves the original cause,
  which is relied on by the request handling code.
"""

import pytest
from hakiapi.core.exceptions import (
    HakiAPIError,
    ClientError,
    ServerError,
    RateLimitError,
    AuthenticationError,
    RequestTimeoutError,
)


# __str__ formatting


def test_str_includes_status_code_when_present():
    err = HakiAPIError("Something broke", status_code=500)
    assert str(err) == "[500] Something broke"


def test_str_omits_status_code_when_absent():
    err = HakiAPIError("Something broke")
    assert str(err) == "Something broke"


def test_str_omits_status_code_when_explicitly_none():
    err = HakiAPIError("Something broke", status_code=None)
    assert str(err) == "Something broke"


def test_str_formatting_consistent_across_subclasses():
    assert str(ClientError("bad request", status_code=400)) == "[400] bad request"
    assert str(ServerError("boom", status_code=503)) == "[503] boom"
    assert str(RateLimitError("slow down", status_code=429)) == "[429] slow down"
    assert str(AuthenticationError("nope", status_code=401)) == "[401] nope"
    # FIXED: status_code removed from signature; using timeout_duration instead.
    assert str(RequestTimeoutError("too slow", timeout_duration=5.0)) == "too slow"


# Base attributes


def test_base_attributes_stored():
    fake_response = object()
    err = HakiAPIError("msg", status_code=418, response=fake_response)

    assert err.message == "msg"
    assert err.status_code == 418
    assert err.response is fake_response


def test_base_attributes_default_to_none():
    err = HakiAPIError("msg")

    assert err.status_code is None
    assert err.response is None


# Inheritance hierarchy -- callers rely on this for except-by-type


@pytest.mark.parametrize(
    "exc_class,expected_bases",
    [
        (ClientError, (HakiAPIError,)),
        (ServerError, (HakiAPIError,)),
        (RateLimitError, (ClientError, HakiAPIError)),
        (AuthenticationError, (ClientError, HakiAPIError)),
        (RequestTimeoutError, (HakiAPIError,)),
    ],
)
def test_inheritance_hierarchy(exc_class, expected_bases):
    for base in expected_bases:
        assert issubclass(exc_class, base)


def test_rate_limit_error_is_not_a_server_error():
    # Sanity check the hierarchy doesn't accidentally cross branches !!
    # a 429 is a client problem (too many requests), not a server one.
    assert not issubclass(RateLimitError, ServerError)


def test_authentication_error_is_not_a_server_error():
    assert not issubclass(AuthenticationError, ServerError)


def test_request_timeout_error_is_not_a_client_error():
    assert not issubclass(RequestTimeoutError, ClientError)


def test_all_exceptions_are_catchable_as_haki_api_error():
    for exc_class in (
        HakiAPIError,
        ClientError,
        ServerError,
        RateLimitError,
        AuthenticationError,
        RequestTimeoutError,
    ):
        with pytest.raises(HakiAPIError):
            raise exc_class("test message")


# Subclass-specific attributes


def test_rate_limit_error_retry_after_defaults_to_none():
    err = RateLimitError("slow down")
    assert err.retry_after is None


def test_rate_limit_error_retry_after_is_settable():
    err = RateLimitError("slow down", retry_after=30)
    assert err.retry_after == 30


def test_rate_limit_error_still_stores_base_attributes():
    err = RateLimitError("slow down", retry_after=30, status_code=429)
    assert err.status_code == 429
    assert err.retry_after == 30


def test_authentication_error_auth_method_defaults_to_none():
    err = AuthenticationError("nope")
    assert err.auth_method is None


def test_authentication_error_auth_method_is_settable():
    err = AuthenticationError("nope", auth_method="bearer")
    assert err.auth_method == "bearer"


# Exception chaining -- base_client.py relies on `raise ... from e`


def test_exception_chaining_preserves_cause():
    original = ValueError("root cause")

    try:
        try:
            raise original
        except ValueError as e:
            raise HakiAPIError("wrapped") from e
    except HakiAPIError as wrapped:
        assert wrapped.__cause__ is original
