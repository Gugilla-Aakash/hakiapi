import hashlib
import hmac
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from requests.auth import AuthBase
from requests import PreparedRequest


class BearerTokenAuth(AuthBase):
    """Authenticate using a Bearer token."""

    def __init__(self, token: str) -> None:
        self.token = token

    def __call__(self, r: PreparedRequest) -> PreparedRequest:
        r.headers["Authorization"] = f"Bearer {self.token}"
        return r


class HeaderApiKeyAuth(AuthBase):
    """Authenticate using a custom API key header."""

    def __init__(self, header_name: str, api_key: str) -> None:
        self.header_name = header_name
        self.api_key = api_key

    def __call__(self, r: PreparedRequest) -> PreparedRequest:
        r.headers[self.header_name] = self.api_key
        return r


class QueryApiKeyAuth(AuthBase):
    """Authenticate by appending an API key as a query parameter."""

    def __init__(self, param_name: str, api_key: str) -> None:
        self.param_name = param_name
        self.api_key = api_key

    def __call__(self, r: PreparedRequest) -> PreparedRequest:
        if not r.url:
            return r

        parts = urlsplit(r.url)

        # Maintain as list of tuples to avoid dropping duplicate keys
        query_params = parse_qsl(parts.query, keep_blank_values=True)
        query_params.append((self.param_name, self.api_key))

        r.url = urlunsplit(
            (
                parts.scheme,
                parts.netloc,
                parts.path,
                urlencode(query_params),
                parts.fragment,
            )
        )

        return r


class HmacAuth(AuthBase):
    """
    Authenticate requests using HMAC-SHA256 signatures.

    The signature is generated from the HTTP method,
    request path, timestamp, and request body.
    """

    def __init__(
        self,
        api_key: str,
        secret_key: str,
        api_key_header: str = "X-API-Key",
        signature_header: str = "X-Signature",
        timestamp_header: str = "X-Timestamp",
    ) -> None:
        self.api_key = api_key
        self.secret_key = secret_key.encode()
        self.api_key_header = api_key_header
        self.signature_header = signature_header
        self.timestamp_header = timestamp_header

    def __call__(self, r: PreparedRequest) -> PreparedRequest:
        timestamp = str(int(time.time()))

        body = r.body

        if body is None:
            body_bytes = b""
        elif isinstance(body, bytes):
            body_bytes = body
        elif isinstance(body, str):
            body_bytes = body.encode()
        else:
            raise TypeError("Streaming request bodies are not supported.")

        if not r.method:
            raise ValueError("Cannot sign a request with no HTTP method set.")

        method = r.method.upper()
        path_url = getattr(r, "path_url", "/")

        message = b"\n".join(
            [
                method.encode(),
                path_url.encode(),
                timestamp.encode(),
                body_bytes,
            ]
        )

        signature = hmac.new(
            self.secret_key,
            message,
            hashlib.sha256,
        ).hexdigest()

        r.headers[self.api_key_header] = self.api_key
        r.headers[self.timestamp_header] = timestamp
        r.headers[self.signature_header] = signature

        return r
