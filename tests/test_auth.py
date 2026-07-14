"""
Test suite for auth.py

Covers BearerTokenAuth, HeaderApiKeyAuth, QueryApiKeyAuth, and HmacAuth.
Checks all the edge cases.
"""

import hashlib
import hmac
import time
from urllib.parse import parse_qsl, urlsplit

import pytest
from requests import PreparedRequest, Request

from hakiapi.core.auth import (
    BearerTokenAuth,
    HeaderApiKeyAuth,
    QueryApiKeyAuth,
    HmacAuth,
)


# Helpers


def make_request(
    method: str = "GET",
    url: str = "https://api.example.com/v1/resource",
    body=None,
    headers=None,
) -> PreparedRequest:
    """Build a real PreparedRequest so path_url, headers, etc. behave normally."""
    req = Request(method=method, url=url, data=body, headers=headers or {})
    return req.prepare()


# BearerTokenAuth


class TestBearerTokenAuth:
    def test_sets_authorization_header(self):
        r = make_request()
        auth = BearerTokenAuth("my-token")
        result = auth(r)
        assert result.headers["Authorization"] == "Bearer my-token"

    def test_returns_same_request_object(self):
        r = make_request()
        auth = BearerTokenAuth("tok")
        assert auth(r) is r

    def test_overwrites_existing_authorization_header(self):
        r = make_request(headers={"Authorization": "Basic old"})
        auth = BearerTokenAuth("new-token")
        result = auth(r)
        assert result.headers["Authorization"] == "Bearer new-token"

    def test_empty_token(self):
        r = make_request()
        auth = BearerTokenAuth("")
        result = auth(r)
        assert result.headers["Authorization"] == "Bearer "

    def test_token_with_special_characters(self):
        r = make_request()
        token = "abc.def-ghi_123~xyz"
        auth = BearerTokenAuth(token)
        result = auth(r)
        assert result.headers["Authorization"] == f"Bearer {token}"


# HeaderApiKeyAuth


class TestHeaderApiKeyAuth:
    def test_sets_custom_header(self):
        r = make_request()
        auth = HeaderApiKeyAuth("X-Api-Key", "secret123")
        result = auth(r)
        assert result.headers["X-Api-Key"] == "secret123"

    def test_different_header_names(self):
        r = make_request()
        auth = HeaderApiKeyAuth("X-Custom-Auth", "key-value")
        result = auth(r)
        assert result.headers["X-Custom-Auth"] == "key-value"

    def test_does_not_touch_authorization_header(self):
        r = make_request()
        auth = HeaderApiKeyAuth("X-Api-Key", "secret123")
        result = auth(r)
        assert "Authorization" not in result.headers

    def test_overwrites_existing_same_named_header(self):
        r = make_request(headers={"X-Api-Key": "old"})
        auth = HeaderApiKeyAuth("X-Api-Key", "new")
        result = auth(r)
        assert result.headers["X-Api-Key"] == "new"

    def test_returns_same_request_object(self):
        r = make_request()
        auth = HeaderApiKeyAuth("X-Api-Key", "k")
        assert auth(r) is r


# QueryApiKeyAuth


class TestQueryApiKeyAuth:
    def test_appends_param_to_url_without_query(self):
        r = make_request(url="https://api.example.com/v1/resource")
        auth = QueryApiKeyAuth("api_key", "abc123")
        result = auth(r)
        assert isinstance(result.url, str)
        parts = urlsplit(result.url)
        assert dict(parse_qsl(parts.query))["api_key"] == "abc123"

    def test_preserves_existing_query_params(self):
        r = make_request(url="https://api.example.com/v1/resource?foo=bar")
        auth = QueryApiKeyAuth("api_key", "abc123")
        result = auth(r)
        assert isinstance(result.url, str)
        params = dict(parse_qsl(urlsplit(result.url).query))
        assert params["foo"] == "bar"
        assert params["api_key"] == "abc123"

    def test_preserves_duplicate_keys(self):
        r = make_request(url="https://api.example.com/v1/resource?tag=a&tag=b")
        auth = QueryApiKeyAuth("api_key", "abc123")
        result = auth(r)
        assert isinstance(result.url, str)
        pairs = parse_qsl(urlsplit(result.url).query)
        tag_values = [v for k, v in pairs if k == "tag"]
        assert tag_values == ["a", "b"]

    def test_preserves_path_and_scheme_and_netloc(self):
        r = make_request(url="https://api.example.com/v1/resource")
        auth = QueryApiKeyAuth("api_key", "abc123")
        result = auth(r)
        assert isinstance(result.url, str)
        parts = urlsplit(result.url)
        assert parts.scheme == "https"
        assert parts.netloc == "api.example.com"
        assert parts.path == "/v1/resource"

    def test_preserves_fragment(self):
        r = make_request(url="https://api.example.com/v1/resource#section")
        auth = QueryApiKeyAuth("api_key", "abc123")
        result = auth(r)
        assert isinstance(result.url, str)
        assert urlsplit(result.url).fragment == "section"

    def test_url_encodes_special_characters_in_key(self):
        r = make_request(url="https://api.example.com/v1/resource")
        auth = QueryApiKeyAuth("api_key", "a b+c/d")
        result = auth(r)
        assert isinstance(result.url, str)
        params = dict(parse_qsl(urlsplit(result.url).query))
        assert params["api_key"] == "a b+c/d"

    def test_returns_request_unchanged_if_url_missing(self):
        r = make_request()
        r.url = None
        auth = QueryApiKeyAuth("api_key", "abc123")
        result = auth(r)
        assert result.url is None

    def test_appending_same_param_name_creates_duplicate(self):
        r = make_request(url="https://api.example.com/v1/resource?api_key=old")
        auth = QueryApiKeyAuth("api_key", "new")
        result = auth(r)
        assert isinstance(result.url, str)
        pairs = parse_qsl(urlsplit(result.url).query)
        values = [v for k, v in pairs if k == "api_key"]
        assert values == ["old", "new"]


# HmacAuth


class TestHmacAuth:
    def _expected_signature(self, secret, method, path_url, timestamp, body_bytes):
        message = b"\n".join(
            [method.encode(), path_url.encode(), timestamp.encode(), body_bytes]
        )
        return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()

    def test_sets_all_three_headers(self):
        r = make_request()
        auth = HmacAuth("key123", "secret")
        result = auth(r)
        assert "X-API-Key" in result.headers
        assert "X-Timestamp" in result.headers
        assert "X-Signature" in result.headers

    def test_api_key_header_value(self):
        r = make_request()
        auth = HmacAuth("key123", "secret")
        result = auth(r)
        assert result.headers["X-API-Key"] == "key123"

    def test_custom_header_names(self):
        r = make_request()
        auth = HmacAuth(
            "key123",
            "secret",
            api_key_header="Api-Key",
            signature_header="Signature",
            timestamp_header="Ts",
        )
        result = auth(r)
        assert "Api-Key" in result.headers
        assert "Signature" in result.headers
        assert "Ts" in result.headers

    def test_timestamp_is_current_unix_time(self):
        before = int(time.time())
        r = make_request()
        auth = HmacAuth("key123", "secret")
        result = auth(r)
        after = int(time.time())
        ts = int(result.headers["X-Timestamp"])
        assert before <= ts <= after

    def test_signature_matches_expected_for_get_no_body(self):
        r = make_request(method="GET", url="https://api.example.com/v1/resource")
        auth = HmacAuth("key123", "secret")
        result = auth(r)

        expected = self._expected_signature(
            "secret",
            "GET",
            result.path_url,
            result.headers["X-Timestamp"],
            b"",
        )
        assert result.headers["X-Signature"] == expected

    def test_signature_matches_expected_for_post_with_body(self):
        r = make_request(
            method="POST",
            url="https://api.example.com/v1/resource",
            body="hello world",
        )
        auth = HmacAuth("key123", "secret")
        result = auth(r)

        body_bytes = result.body
        if isinstance(body_bytes, str):
            body_bytes = body_bytes.encode()

        assert body_bytes is not None

        expected = self._expected_signature(
            "secret",
            "POST",
            result.path_url,
            result.headers["X-Timestamp"],
            body_bytes,
        )
        assert result.headers["X-Signature"] == expected

    def test_different_secrets_produce_different_signatures(self):
        r1 = make_request()
        r2 = make_request()
        sig1 = HmacAuth("key", "secret1")(r1).headers["X-Signature"]
        sig2 = HmacAuth("key", "secret2")(r2).headers["X-Signature"]
        assert sig1 != sig2

    def test_method_is_uppercased(self):
        r = make_request(method="get")
        auth = HmacAuth("key123", "secret")
        result = auth(r)
        expected = self._expected_signature(
            "secret", "GET", result.path_url, result.headers["X-Timestamp"], b""
        )
        assert result.headers["X-Signature"] == expected

    def test_raises_on_missing_method(self):
        r = make_request()
        r.method = None
        auth = HmacAuth("key123", "secret")
        with pytest.raises(ValueError):
            auth(r)

    def test_raises_typeerror_on_streamed_body(self):
        r = make_request()

        class FakeStream:
            pass

        r.body = FakeStream()  # type: ignore
        auth = HmacAuth("key123", "secret")
        with pytest.raises(TypeError):
            auth(r)

    def test_bytes_body_used_directly(self):
        r = make_request(method="POST", url="https://api.example.com/v1/resource")
        r.body = b"raw-bytes-body"
        auth = HmacAuth("key123", "secret")
        result = auth(r)

        expected = self._expected_signature(
            "secret",
            "POST",
            result.path_url,
            result.headers["X-Timestamp"],
            b"raw-bytes-body",
        )
        assert result.headers["X-Signature"] == expected

    def test_none_body_treated_as_empty_bytes(self):
        r = make_request(method="GET", url="https://api.example.com/v1/resource")
        r.body = None
        auth = HmacAuth("key123", "secret")
        result = auth(r)

        expected = self._expected_signature(
            "secret", "GET", result.path_url, result.headers["X-Timestamp"], b""
        )
        assert result.headers["X-Signature"] == expected

    def test_query_string_included_via_path_url(self):
        r = make_request(url="https://api.example.com/v1/resource?foo=bar")
        auth = HmacAuth("key123", "secret")
        result = auth(r)
        assert "?foo=bar" in result.path_url

        expected = self._expected_signature(
            "secret", "GET", result.path_url, result.headers["X-Timestamp"], b""
        )
        assert result.headers["X-Signature"] == expected

    def test_signature_is_hex_sha256_length(self):
        r = make_request()
        auth = HmacAuth("key123", "secret")
        result = auth(r)
        assert len(result.headers["X-Signature"]) == 64
        int(result.headers["X-Signature"], 16)

    def test_delimiter_prevents_field_collision(self):
        r1 = make_request(method="GET", url="https://api.example.com/1")

        auth1 = HmacAuth("key123", "secret")
        result1 = auth1(r1)
        fixed_ts = result1.headers["X-Timestamp"]

        sig_direct = self._expected_signature("secret", "GET", "/1", fixed_ts, b"")
        sig_collision_attempt = self._expected_signature(
            "secret", "GET1", "/", fixed_ts, b""
        )
        assert sig_direct != sig_collision_attempt
