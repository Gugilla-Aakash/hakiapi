"""
Tests for the `create_retry_adapter` helper.

These tests verify that:
- A properly configured `HTTPAdapter` is returned.
- Default retry settings are used when no custom values are provided.
- Custom retry options are passed correctly to the underlying `Retry` object.
- `raise_on_status` is always disabled, since HakiAPI handles HTTP errors
  through its own exception classes.
- An empty `status_forcelist` is respected instead of being replaced with
  the default values.
"""

import pytest
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from hakiapi.core.retry import create_retry_adapter


DEFAULT_STATUS_FORCELIST = [429, 500, 502, 503, 504]


# Return type / basic shape


def test_returns_httpadapter_instance():
    adapter = create_retry_adapter()
    assert isinstance(adapter, HTTPAdapter)


def test_max_retries_is_retry_instance():
    adapter = create_retry_adapter()
    assert isinstance(adapter.max_retries, Retry)


# Defaults


def test_default_total_retries():
    adapter = create_retry_adapter()
    assert adapter.max_retries.total == 3


def test_default_backoff_factor():
    adapter = create_retry_adapter()
    assert adapter.max_retries.backoff_factor == 1.0


def test_default_status_forcelist():
    adapter = create_retry_adapter()
    assert adapter.max_retries.status_forcelist == DEFAULT_STATUS_FORCELIST


def test_default_allowed_methods_is_none():
    # None means "retry on all HTTP methods", i.e. no method filtering.
    adapter = create_retry_adapter()
    assert adapter.max_retries.allowed_methods is None


def test_raise_on_status_is_always_false():
    # HakiAPI defers error handling to its own exceptions, so urllib3
    # should never raise on its own for a forcelisted status.
    adapter = create_retry_adapter()
    assert adapter.max_retries.raise_on_status is False


# Custom overrides


def test_custom_total_retries():
    adapter = create_retry_adapter(total_retries=5)
    assert adapter.max_retries.total == 5


def test_custom_backoff_factor():
    adapter = create_retry_adapter(backoff_factor=2.5)
    assert adapter.max_retries.backoff_factor == 2.5


def test_custom_status_forcelist():
    custom_forcelist = [408, 500]
    adapter = create_retry_adapter(status_forcelist=custom_forcelist)
    assert adapter.max_retries.status_forcelist == custom_forcelist


def test_custom_allowed_methods():
    custom_methods = frozenset({"GET", "POST"})
    adapter = create_retry_adapter(allowed_methods=custom_methods)
    assert adapter.max_retries.allowed_methods == custom_methods


def test_raise_on_status_stays_false_with_custom_args():
    adapter = create_retry_adapter(total_retries=10, backoff_factor=0.1)
    assert adapter.max_retries.raise_on_status is False


# Edge cases


def test_empty_status_forcelist_is_not_replaced_with_hakiapi_default():
    # Passing an empty list is intentional. It shouldn't be replaced with the
    # default status_forcelist just because it's falsy. urllib3 will normalize
    # it to an empty set internally, which is the behavior we expect.
    adapter = create_retry_adapter(status_forcelist=[])
    assert not adapter.max_retries.status_forcelist
    assert set(adapter.max_retries.status_forcelist) != set(DEFAULT_STATUS_FORCELIST)


def test_status_forcelist_none_falls_back_to_default():
    adapter = create_retry_adapter(status_forcelist=None)
    assert adapter.max_retries.status_forcelist == DEFAULT_STATUS_FORCELIST


def test_zero_total_retries_is_respected():
    adapter = create_retry_adapter(total_retries=0)
    assert adapter.max_retries.total == 0


@pytest.mark.parametrize("total_retries", [1, 3, 5, 10])
def test_various_total_retries_values(total_retries):
    adapter = create_retry_adapter(total_retries=total_retries)
    assert adapter.max_retries.total == total_retries


@pytest.mark.parametrize("backoff_factor", [0.0, 0.5, 1.0, 3.2])
def test_various_backoff_factor_values(backoff_factor):
    adapter = create_retry_adapter(backoff_factor=backoff_factor)
    assert adapter.max_retries.backoff_factor == backoff_factor


# Independence between calls


def test_multiple_calls_return_independent_adapters():
    adapter_one = create_retry_adapter(total_retries=3)
    adapter_two = create_retry_adapter(total_retries=7)

    assert adapter_one.max_retries.total == 3
    assert adapter_two.max_retries.total == 7
    assert adapter_one is not adapter_two
    assert adapter_one.max_retries is not adapter_two.max_retries


def test_mutable_default_status_forcelist_not_shared_across_calls():
    adapter_one = create_retry_adapter()
    adapter_one.max_retries.status_forcelist = frozenset({999})

    adapter_two = create_retry_adapter()
    assert 999 not in adapter_two.max_retries.status_forcelist
