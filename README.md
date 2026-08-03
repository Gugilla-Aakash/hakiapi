<div align="center">

# 🚀 HakiAPI

### Build production-grade Python API SDKs — not boilerplate.

Authentication · OAuth 2.0 · Retries · Circuit Breaker · Pagination · Typed Exceptions · Sync + Async

[![PyPI](https://img.shields.io/pypi/v/hakiapi?style=for-the-badge)](https://pypi.org/project/hakiapi/)
[![Python](https://img.shields.io/pypi/pyversions/hakiapi?style=for-the-badge)](https://pypi.org/project/hakiapi/)
[![License](https://img.shields.io/github/license/Gugilla-Aakash/hakiapi?style=for-the-badge)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-347_passing-success?style=for-the-badge)](#testing)
[![Typing](https://img.shields.io/badge/typing-fully_typed-blue?style=for-the-badge)](#features)
[![Async](https://img.shields.io/badge/async-httpx_powered-9cf?style=for-the-badge)](#async-client-core-async_base_clientpy)
[![Resilience](https://img.shields.io/badge/resilience-circuit_breaker-orange?style=for-the-badge)](#circuit-breaker-core-circuit_breakerpy)
[![Downloads](https://img.shields.io/pypi/dm/hakiapi?style=for-the-badge)](https://pypistats.org/packages/hakiapi)

**Stop rewriting authentication, retries, and pagination for every API client you build.**

[Installation](#installation) • [Quick Start](#quick-start) • [Features](#features) • [Core Concepts](#core-concepts) • [Circuit Breaker](#circuit-breaker-core-circuit_breakerpy) • [Async Client](#async-client-core-async_base_clientpy) • [Bundled Clients](#bundled-clients) • [Create Your Own Client](#create-your-own-client) • [Architecture](#architecture--project-structure) • [Roadmap](#roadmap)

</div>

---

## Why HakiAPI?

Every API client grows the same infrastructure, in the same order. You start with a simple HTTP call. Then you add authentication. Then retries. Then pagination. Then timeout and exception handling. A month later, you've rebuilt the same plumbing you already wrote for the last five projects.

HakiAPI extracts all of that into one reusable core (`BaseAPIClient`), so every client you build on top of it inherits the same battle-tested behavior automatically. Instead of writing infrastructure, you write endpoint logic.

### Raw `requests` vs. HakiAPI

| | Raw `requests` | HakiAPI |
|---|---|---|
| **OAuth 2.0 Flow** | Hand-roll the consent URL, spin up a redirect server, parse the callback yourself | `GoogleOAuthFlow` builds the consent URL, opens the browser, catches the redirect on `localhost`, verifies CSRF `state`, and exchanges the code for you |
| **Token Persistence** | Read/write a JSON file yourself and hope nothing corrupts it mid-write | `FileTokenStore` writes atomically (temp file + `os.replace`) with `0600` permissions |
| **Retry Logic** | Wire up your own `urllib3.Retry` + `HTTPAdapter` | Built into every `BaseAPIClient` session with exponential backoff on `429/500/502/503/504` |
| **Static Auth** | Reimplement Bearer/HMAC/API-key headers per project | 5 reusable `AuthBase` strategies, drop-in |
| **Error Handling** | Manually branch on `response.status_code` everywhere | Raised as a typed, catchable exception hierarchy carrying `status_code` and the original `response` |
| **Pagination** | Write a custom `while` loop per API's pagination style | `paginate()` auto-detects Link-header, `data`/`meta.next_token`, `messages`/`nextPageToken`, and `items`/`nextPageToken` styles, yielding lazily |
| **Async I/O** | Swap in `aiohttp`/`httpx` yourself and reimplement retries, timeouts, and status handling on top of it | `AsyncBaseAPIClient` is an `httpx`-backed mirror of `BaseAPIClient` — same retry engine, same typed exceptions, `async`/`await` throughout |
| **Cascading Failures** | A struggling downstream service keeps getting hammered by retries until your own app falls over with it | `CircuitBreaker` decorator trips OPEN after N consecutive failures, fails fast with `CircuitOpenError` during cooldown, then auto-probes recovery with a single trial call |

---

## ✨ Features

| Feature | Details |
|---|---|
| 🔐 **Interactive OAuth 2.0 Flow** | `GoogleOAuthFlow` drives Google's Authorization Code flow end-to-end: builds the consent URL, opens the system browser, boots a one-shot local `HTTPServer` to catch the redirect, validates the CSRF `state` token, and exchanges the code for tokens. |
| 🔁 **Manual Token Refresh** | `refresh_access_token()` exchanges a stored `refresh_token` for a new `access_token` without user interaction, and wipes the token store automatically if Google reports the grant as revoked. |
| 🗄️ **Atomic Token Vault** | `FileTokenStore` persists tokens to a local JSON file by writing to a temp file and swapping it in with `os.replace()`, so a crash mid-write can never leave a corrupted token file. The file is `chmod 0600`. |
| 🔐 **Multiple Auth Strategies** | `BearerTokenAuth`, `HeaderApiKeyAuth`, `QueryApiKeyAuth`, `HmacAuth` (SHA-256 request signing), and `OAuth2Auth` for wiring a `GoogleOAuthFlow` directly into a `requests.Session`. |
| 🔁 **Automatic Retries** | `create_retry_adapter()` mounts an `HTTPAdapter` with exponential backoff on `429/500/502/503/504` onto every `BaseAPIClient` session, deferring status handling to HakiAPI's own exceptions via `raise_on_status=False`. |
| 📄 **Smart Pagination** | `paginate()` auto-detects GitHub-style `Link` headers, Twitter-style `meta.next_token`, Gmail-style `messages` + `nextPageToken`, and Calendar-style `items` + `nextPageToken` — all as one lazy generator. |
| ⚠️ **Typed Exceptions** | `RateLimitError` (with `retry_after`), `AuthenticationError` (401/403), `ClientError` (4xx), `ServerError` (5xx), `RequestTimeoutError` — all inherit from `HakiAPIError`, which carries `status_code` and the original `response`. |
| ⚡ **Async Client** | `AsyncBaseAPIClient` is a fully `async`/`await`, `httpx`-powered counterpart to `BaseAPIClient` — same exponential backoff on `429/500/502/503/504`, the same typed exception hierarchy, `Retry-After` clamping, SSRF-safe URL/endpoint validation, and a max-response-size guard, so you don't lose any safety behavior by going async. |
| 🧯 **Circuit Breaker** | Thread-safe `CircuitBreaker` decorator implementing the classic `CLOSED → OPEN → HALF_OPEN` state machine. Fails fast with `CircuitOpenError` (carrying a `retry_after` cooldown) once `failure_threshold` consecutive failures are hit, then automatically allows a single trial request through after `recovery_timeout` seconds to probe for recovery. |
| 📦 **Ready-to-use Clients** | `GitHubClient` (REST + GraphQL), `GmailClient`, `GoogleCalendarClient` — out of the box. |

---

## Installation

```bash
pip install hakiapi
```

Requires **Python 3.10+**. Core dependencies are `requests>=2.32.0` and `urllib3>=1.26.0`.

`AsyncBaseAPIClient` is built on [`httpx`](https://www.python-httpx.org/), which isn't installed by default — add it if you want the async client:

```bash
pip install httpx
```

---

## Quick Start

### 1. Interactive OAuth 2.0 (Google Calendar)

`GoogleOAuthFlow.get_token()` checks the `TokenStore` first. If a valid, non-expired token is already saved, it's returned immediately. Otherwise it opens your browser, runs the full consent flow, and persists the result:

```python
import os
from dotenv import load_dotenv
from hakiapi.clients.google_calendar import GoogleCalendarClient
from hakiapi.core.oauth.google import GoogleOAuthFlow
from hakiapi.core.oauth.token_store import FileTokenStore

# Load variables from your .env file into os.environ
load_dotenv()

# 1. Set up the flow and the token vault
oauth_flow = GoogleOAuthFlow(
    client_id=os.environ["GOOGLE_CLIENT_ID"],
    client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
    scopes=["https://www.googleapis.com/auth/calendar.readonly"],
    store=FileTokenStore("my_secure_token.json"),
    redirect_port=8765,  # must match an authorized redirect URI in Google Cloud Console
)

# 2. get_token() returns the cached token if it's still valid,
#    otherwise it opens the browser and runs the full consent flow.
token = oauth_flow.get_token()

# 3. Initialize your client with the raw access token
with GoogleCalendarClient(token=token.access_token) as calendar:
    for event in calendar.events.upcoming(max_results=3):
        print(event.get("summary"))
```

> **Note:** `get_token()` does **not** silently refresh an expired token — it re-runs the interactive consent flow when the stored token is missing or expired. If you want silent, non-interactive refreshes using a saved `refresh_token`, call `refresh_access_token()` from `hakiapi.core.oauth.refresh` explicitly (see [OAuth 2.0](#oauth-20) below).

### 2. Automatic Pagination (GitHub)

Forget page numbers, `while` loops, and manually checking for a `next` page. `paginate()` follows Link headers automatically and yields lazily:

```python
from hakiapi.clients.github import GitHubClient

with GitHubClient() as github:
    # Lazily walks every page of the user's public repos
    for repo in github.get_all_user_repos("torvalds"):
        print(repo["name"])
```

### 3. Async Requests (`httpx`-based)

`AsyncBaseAPIClient` mirrors `BaseAPIClient` method-for-method, just with `async`/`await`:

```python
import asyncio
from hakiapi.core.async_base_client import AsyncBaseAPIClient

async def main():
    async with AsyncBaseAPIClient(base_url="https://api.github.com") as client:
        user = await client.get("/users/torvalds")
        print(user["name"])

asyncio.run(main())
```

---

## Core Concepts

### Exception Handling

Every exception raised by `BaseAPIClient._request()` inherits from `HakiAPIError`, carrying `status_code` and the original `response` object:

```python
from hakiapi.core.exceptions import AuthenticationError, RateLimitError, ServerError

try:
    github.get_user("torvalds")
except RateLimitError as e:
    print(f"Rate limited — retry after {e.retry_after}s")
except AuthenticationError:
    print("Invalid credentials.")
except ServerError:
    print("GitHub is currently unavailable.")
```

| Exception | Raised when | Extra attributes |
|---|---|---|
| `RateLimitError` | HTTP `429` | `retry_after` — parsed from the `Retry-After` header, if present |
| `AuthenticationError` | HTTP `401` / `403` | `auth_method` |
| `ClientError` | Any other `4xx` | — |
| `ServerError` | Any `5xx` | — |
| `RequestTimeoutError` | The request times out at the network level (no HTTP response was ever received) | `timeout_duration` |

### Authentication Strategies (`core/auth.py`)

All strategies implement `requests.auth.AuthBase`, so they drop straight into `BaseAPIClient(auth=...)`:

```python
from hakiapi.core.auth import BearerTokenAuth, HeaderApiKeyAuth, QueryApiKeyAuth, HmacAuth
```

- **`BearerTokenAuth(token)`** — sets `Authorization: Bearer <token>`.
- **`HeaderApiKeyAuth(header_name, api_key)`** — injects the key under a custom header.
- **`QueryApiKeyAuth(param_name, api_key)`** — appends the key as a query parameter, preserving any existing query string.
- **`HmacAuth(api_key, secret_key, ...)`** — signs each request with HMAC-SHA256 over `METHOD\nPATH\nTIMESTAMP\nBODY` (newline-delimited to prevent field-collision signature forgery), sending the key, timestamp, and signature as headers. Raises `TypeError` for streaming bodies, which aren't supported.
- **`OAuth2Auth(flow)`** — wraps any object exposing `get_token()` (like `GoogleOAuthFlow`) and injects a fresh `Authorization: Bearer` header on every request.

### Retry Engine (`core/retry.py`)

`create_retry_adapter()` builds an `HTTPAdapter` backed by `urllib3.util.Retry`:

- **3 retries by default**, with an exponential `backoff_factor` of `1.0`.
- Retries on `429, 500, 502, 503, 504` by default (configurable via `status_forcelist`).
- `raise_on_status=False` — `urllib3` never raises on its own; HakiAPI's typed exceptions handle the final failure.
- Mounted on both `http://` and `https://` for every `BaseAPIClient` session automatically.

### Circuit Breaker (`core/circuit_breaker.py`)

`CircuitBreaker` protects downstream services from cascading failures and stops a struggling API from being hammered by an ever-growing pile of retries. It's a thread-safe decorator you can drop onto any synchronous callable:

```python
from hakiapi.core.circuit_breaker import CircuitBreaker, CircuitOpenError
from hakiapi.core.exceptions import HakiAPIError

breaker = CircuitBreaker(
    failure_threshold=5,      # consecutive failures before the circuit opens
    recovery_timeout=30.0,    # seconds to wait before allowing a trial request
    expected_exceptions=(HakiAPIError,),  # exception types that count as failures
)

@breaker
def get_user(user_id: str):
    return github.get_user(user_id)

try:
    get_user("torvalds")
except CircuitOpenError as e:
    print(f"Downstream is unhealthy — retry in {e.retry_after:.1f}s")
```

It implements the classic three-state machine:

| State | Behavior |
|---|---|
| **`CLOSED`** | Normal operation. Requests pass through; a successful call resets the failure counter. |
| **`OPEN`** | Failing fast. Every call is blocked instantly with `CircuitOpenError` (no call is made to the wrapped function) until `recovery_timeout` seconds have elapsed. |
| **`HALF_OPEN`** | Testing recovery. Once the timeout elapses, a single trial request is allowed through — success closes the circuit and resets the counter, failure reopens it immediately and restarts the cooldown. |

- **Thread-safe.** All state transitions and counters are guarded by a single `threading.Lock`, so one `CircuitBreaker` instance can safely protect a callable shared across threads.
- **Lazy state evaluation.** The `OPEN → HALF_OPEN` transition happens the moment `state` is read (or a wrapped call is made) after `recovery_timeout` has elapsed — there's no background timer or polling thread.
- **`CircuitOpenError`** inherits from `HakiAPIError` and carries `retry_after` (seconds remaining in the cooldown, clamped to `>= 0`), so callers can back off intelligently instead of guessing.
- **Configurable failure scope.** `expected_exceptions` controls which exception types trip the breaker — defaults to `HakiAPIError`, so unrelated exceptions (e.g. a `ValueError` from bad input) pass straight through without affecting circuit state.
- **Self-clamping configuration.** `failure_threshold` is floored at `1` and `recovery_timeout` at `0.1` seconds, so a misconfigured `0` or negative value can't accidentally create a circuit that never opens or reopens instantly forever.

> **Note:** `CircuitBreaker` is currently a standalone utility — import it directly from `hakiapi.core.circuit_breaker` and wrap it around any client method (sync `BaseAPIClient` calls, a bundled client's methods, or your own functions) where you want fail-fast protection against a struggling dependency.

### Async Client (`core/async_base_client.py`)

`AsyncBaseAPIClient` is a ground-up, `httpx`-backed rewrite of `BaseAPIClient` for `asyncio` codebases — it is not a thin wrapper around the sync client. It re-implements the same guarantees natively on top of `httpx.AsyncClient` instead of `requests`:

```python
from hakiapi.core.async_base_client import AsyncBaseAPIClient

async with AsyncBaseAPIClient(
    base_url="https://api.example.com",
    timeout=10.0,
    max_retries=3,
    backoff_factor=0.5,
    max_response_bytes=10 * 1024 * 1024,
) as client:
    data = await client.get("/resource")
    created = await client.post("/resource", json={"name": "haki"})
```

- **Same retry engine, no `HTTPAdapter`.** Because `httpx` doesn't support mounting a `urllib3`-style adapter, retries are implemented directly in `_request()`: exponential backoff (`backoff_factor * 2**attempt` plus jitter) on `429/500/502/503/504`, and on `httpx.TimeoutException` / `httpx.RequestError` for network-level failures — up to `max_retries` attempts.
- **`Retry-After`-aware.** A `429` with a valid `Retry-After` header sleeps for exactly that long (clamped to 300s) instead of the backoff curve.
- **Same typed exception hierarchy.** `RateLimitError`, `AuthenticationError`, `ClientError`, `ServerError`, and `RequestTimeoutError` are raised from the exact same `hakiapi.core.exceptions` module the sync client uses — one `except` block works for both.
- **Same security posture.** `base_url` is validated to be `http(s)` with a real host at construction time; every `endpoint` passed to `get`/`post`/etc. is rejected if it's absolute or protocol-relative (blocks SSRF via a malicious or templated endpoint string); redirects are **not** followed automatically (`follow_redirects=False`).
- **Response-size guard.** Responses larger than `max_response_bytes` raise `HakiAPIError` before the body is handed back to you, checked against `Content-Length` when present.
- **Async context manager.** `async with AsyncBaseAPIClient(...) as client:` calls `client.close()` (which awaits `httpx.AsyncClient.aclose()`) on exit; `close()` is idempotent, so calling it more than once is safe.
- **`get`, `post`, `put`, `delete`, `patch`** all `await` through the same `_request()` pipeline as the sync client, and all accept `raw_response=True` to get the `httpx.Response` back instead of the parsed body.

> **Note:** `AsyncBaseAPIClient` currently lives in `hakiapi.core.async_base_client` as a standalone import — it isn't re-exported from the top-level `hakiapi` package yet, so import it directly as shown above.

### Smart Pagination (`core/paginator.py`)

`paginate(client, endpoint, max_pages=None, **kwargs)` is a generator that keeps requesting pages until it runs out, detecting the item list and the "next page" signal from the response shape:

| Response shape | Items key | Next-page signal |
|---|---|---|
| Raw JSON list | the list itself | `Link` response header (`rel="next"`) |
| `{"data": [...], "meta": {...}}` (Twitter/X-style) | `data` | `meta.next_token` |
| `{"messages": [...], "nextPageToken": ...}` (Gmail-style) | `messages` | `nextPageToken` |
| `{"items": [...], "nextPageToken": ...}` (Calendar-style) | `items` | `nextPageToken` |
| `{"resultSizeEstimate": 0}` (Gmail empty result) | — | stops cleanly, no error |

Any other shape raises `ValueError("Unexpected pagination response: ...")`. Pass `max_pages` to cap how many pages are fetched.

### OAuth 2.0 (`core/oauth/`)

The OAuth engine is split into three independent pieces:

- **`token_store.py`** — `OAuthToken` (a dataclass with `access_token`, `refresh_token`, `expires_at`, `scopes`, and an `is_expired` property with a 30-second leeway buffer) and the `TokenStore` abstract base class. `FileTokenStore` is the concrete implementation: it serializes tokens to JSON, writes atomically via a temp file + `os.replace()`, and sets `0600` permissions on the file.
- **`google.py`** — `GoogleOAuthFlow` drives the full interactive Authorization Code flow: builds the consent URL (`access_type=offline`, `prompt=consent` to force a refresh token on every run), opens it with `webbrowser.open()`, boots a one-shot `http.server.HTTPServer` on `localhost:<redirect_port>` to catch the redirect, validates the CSRF `state` parameter, and exchanges the authorization code for tokens via a direct POST to Google's token endpoint. Raises `OAuthFlowError` on denial, timeout, a `state` mismatch, or a failed exchange.
- **`refresh.py`** — `refresh_access_token(token, client_id, client_secret, store)` is a standalone function that exchanges a saved `refresh_token` for a new `access_token` without opening a browser. If Google rejects the refresh (revoked/invalid grant), it calls `store.delete_token()` so the next `get_token()` call cleanly falls back to the interactive flow.

These three pieces are intentionally decoupled — `GoogleOAuthFlow.get_token()` only checks expiry and re-runs the interactive flow if needed; wiring in silent refreshes via `refresh_access_token()` is left to the caller (or to `OAuth2Auth`, once you build that logic into your own `flow` object).

---

## Bundled Clients

### `GitHubClient` — REST + GraphQL

```python
from hakiapi.clients.github import GitHubClient

with GitHubClient(token="ghp_...") as gh:  # token is optional for public endpoints
    gh.get_user("torvalds")
    gh.search_users("location:hyderabad")
    gh.get_all_search_users("python")            # auto-paginated generator
    gh.get_user_repos("torvalds")                 # single page
    gh.get_all_user_repos("torvalds")              # auto-paginated generator
    gh.get_repo_languages("torvalds", "linux")
    gh.get_aggregate_user_languages("torvalds")    # sums languages across every repo
    gh.get_user_authored_activity("torvalds")      # recent authored PRs + issues
    gh.execute_graphql(query, variables={...})     # raises HakiAPIError on GraphQL-level errors
    gh.get_user_contributions("torvalds", from_date="2025-01-01T00:00:00Z")
```

`get_aggregate_user_languages()` walks every repository returned by `get_all_user_repos()` and silently skips any repo whose language lookup raises `HakiAPIError`, so one broken/empty repo doesn't fail the whole aggregation.

#### GraphQL Engine

`GitHubClient` isn't purely REST — it also ships a GraphQL execution layer on top of the same `BaseAPIClient` infrastructure, so GraphQL calls get the same retries, timeout handling, and auth as everything else.

```python
from hakiapi.clients.github import GitHubClient

with GitHubClient(token="ghp_...") as gh:
    data = gh.execute_graphql(
        """
        query($login: String!) {
            user(login: $login) {
                name
                bio
            }
        }
        """,
        variables={"login": "torvalds"},
    )
    print(data["user"]["name"])
```

- **`execute_graphql(query, variables=None, **kwargs)`** — the low-level engine. It `POST`s `{"query": ..., "variables": ...}` to GitHub's `/graphql` endpoint and unwraps the response. GraphQL is notorious for returning HTTP `200 OK` even when the query itself failed, with the real error buried in the response body — `execute_graphql` checks for an `"errors"` key in the payload and raises a `HakiAPIError` joining every message it finds, instead of letting a broken query silently return `None`. On success it returns just the `"data"` portion of the payload.
- **`get_user_contributions(username, from_date=None, to_date=None, **kwargs)`** — a ready-made query built on top of `execute_graphql`. It fetches a user's `contributionsCollection`: total contributions, commit contributions, issue contributions, and pull-request contributions, optionally scoped to a date range. `from_date`/`to_date` must be ISO 8601 strings (e.g. `"2025-01-01T00:00:00Z"`).

### `GmailClient` — resource-based routing

```python
from hakiapi import GmailClient

with GmailClient(token=access_token) as gmail:
    gmail.profile.get()                    # users/{id}/profile
    gmail.labels.list()                    # users/{id}/labels
    gmail.messages.get(message_id)         # a single message
    gmail.messages.list(max_pages=2)       # auto-paginated generator
    gmail.messages.search("is:unread")     # auto-paginated generator with a query
    gmail.messages.send({"raw": base64_rfc2822_string})
```

### `GoogleCalendarClient` — resource-based routing

```python
from hakiapi import GoogleCalendarClient

with GoogleCalendarClient(token=access_token) as cal:
    cal.calendars.list(max_pages=1)
    cal.events.get(event_id)
    cal.events.list(calendar_id="primary")
    cal.events.today()                       # midnight-to-midnight UTC, recurring events expanded
    cal.events.upcoming(max_results=5)        # next N events from now, single page
    cal.events.create({"summary": "...", "start": {...}, "end": {...}})
    cal.events.delete(event_id)
```

`today()` and `upcoming()` both auto-fill `timeMin`/`timeMax`, set `singleEvents=True` to expand recurring events, and sort by `startTime` — you only pass the calendar ID.

---

## Create Your Own Client

Subclass `BaseAPIClient`, point it at a base URL, and define your endpoints as plain methods. Authentication, retries, timeout handling, and typed exceptions are inherited automatically:

```python
from hakiapi import BaseAPIClient

class WeatherClient(BaseAPIClient):
    def __init__(self, **kwargs):
        super().__init__(base_url="https://api.open-meteo.com/v1", **kwargs)

    def get_weather(self, latitude: float, longitude: float):
        return self.get(
            "forecast",
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current_weather": True,
            },
        )

if __name__ == "__main__":
    # Hyderabad, Telangana, India
    with WeatherClient() as client:
        weather = client.get_weather(latitude=17.385, longitude=78.4867)
        print(weather["current_weather"])
```

`BaseAPIClient` exposes `get`, `post`, `put`, `patch`, and `delete`, all routed through `_request()`, which handles the retry-mounted session, timeout errors, status-code-to-exception mapping, and JSON/text response parsing (falling back to `response.text` if the body isn't valid JSON). Pass `raw_response=True` to get the raw `requests.Response` instead — this is what `paginate()` uses internally to read the `Link` header.

---

## Architecture & Project Structure

```text
hakiapi/
├── core/
│   ├── oauth/
│   │   ├── google.py         # GoogleOAuthFlow — interactive Authorization Code flow
│   │   ├── refresh.py        # refresh_access_token() — silent refresh via refresh_token
│   │   └── token_store.py    # OAuthToken, TokenStore (ABC), FileTokenStore
│   ├── auth.py                # BearerTokenAuth, HeaderApiKeyAuth, QueryApiKeyAuth, HmacAuth, OAuth2Auth
│   ├── retry.py                # create_retry_adapter() — exponential-backoff HTTPAdapter factory
│   ├── circuit_breaker.py      # CircuitBreaker — CLOSED/OPEN/HALF_OPEN fail-fast decorator
│   ├── paginator.py            # paginate() — Link-header + token-based pagination
│   ├── base_client.py          # BaseAPIClient — session, retries, exception mapping
│   ├── async_base_client.py    # AsyncBaseAPIClient — httpx-based async counterpart
│   └── exceptions.py           # HakiAPIError hierarchy
│
└── clients/
    ├── github.py               # GitHubClient — REST + GraphQL
    ├── gmail.py                # GmailClient — profile / labels / messages resources
    └── google_calendar.py      # GoogleCalendarClient — calendars / events resources
```

---

## Design Principles

* Infrastructure should be written once.
* API clients should remain lightweight.
* Explicit is better than magical.
* Strong typing improves maintainability.
* Production readiness should be the default, not an afterthought.
* Developer experience matters as much as correctness.

---

## Testing

```bash
pip install hakiapi[dev]
pytest
```

* ✅ **340+ tests passing**
* ✅ Core framework covered: `auth`, `retry`, `circuit_breaker`, `paginator`, `base_client`, `async_base_client`, `exceptions`
* ✅ `AsyncBaseAPIClient` covered end-to-end via `httpx.MockTransport` — success paths, retry/backoff, `Retry-After` handling, timeouts, SSRF/endpoint validation, response-size limits, and context-manager lifecycle
* ✅ `CircuitBreaker` covered end-to-end — state transitions (`CLOSED → OPEN → HALF_OPEN`), threshold clamping, `retry_after` calculation, success-resets-counter behavior, and unexpected-exception passthrough, with `time.monotonic` mocked for deterministic timing
* ✅ Full OAuth 2.0 engine covered: `google.py` (interactive flow) and `refresh.py` (silent refresh), fully mocked
* ✅ `FileTokenStore` atomic-write behavior covered
* ✅ `GitHubClient`, `GmailClient`, `GoogleCalendarClient` covered

---

## Roadmap

**Completed**

* [x] Base API framework (`BaseAPIClient`)
* [x] Authentication strategies (Bearer, Header API Key, Query API Key, HMAC, OAuth2)
* [x] Retry engine with exponential backoff
* [x] Automatic pagination (Link header, `data`/`meta`, `messages`/`items` + token styles)
* [x] Typed exception hierarchy
* [x] Interactive Google OAuth 2.0 flow (local redirect interceptor, CSRF-protected)
* [x] Atomic `FileTokenStore` and standalone silent-refresh routine
* [x] `GitHubClient`, `GmailClient`, `GoogleCalendarClient`
* [x] Async client (`AsyncBaseAPIClient`, `httpx`-based)
* [x] Circuit breaker (`CircuitBreaker`) for fail-fast protection against cascading failures

**Planned**

* [ ] Stripe client
* [ ] Twitter/X client
* [ ] Wire automatic silent refresh into `GoogleOAuthFlow.get_token()`
* [ ] Async versions of `GitHubClient` / `GmailClient` / `GoogleCalendarClient` on top of `AsyncBaseAPIClient`
* [ ] Top-level `hakiapi` export for `AsyncBaseAPIClient`
* [ ] Plugin system

---

## Contributing

Contributions are welcome — bug fixes, documentation, tests, or new clients. Please open an issue before proposing major changes so we can discuss the approach first.

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

### ⭐ If HakiAPI saved you from rewriting the same API client for the tenth time, consider giving it a star.

It helps more developers discover the project and motivates future development.

Built with ❤️ by **Gugilla Aakash**
