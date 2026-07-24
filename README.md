<div align="center">

# 🚀 HakiAPI

### Build production-grade Python API SDKs — not boilerplate.

Authentication · Self-Healing OAuth 2.0 · Retries · Pagination · Typed Exceptions

[![PyPI](https://img.shields.io/pypi/v/hakiapi?style=for-the-badge)](https://pypi.org/project/hakiapi/)
[![Python](https://img.shields.io/pypi/pyversions/hakiapi?style=for-the-badge)](https://pypi.org/project/hakiapi/)
[![License](https://img.shields.io/github/license/Gugilla-Aakash/hakiapi?style=for-the-badge)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-280%2B_passing-success?style=for-the-badge)](#testing)
[![Typing](https://img.shields.io/badge/typing-fully_typed-blue?style=for-the-badge)](#features)
[![Downloads](https://img.shields.io/pypi/dm/hakiapi?style=for-the-badge)](https://pypistats.org/packages/hakiapi)

**Stop rewriting authentication, retries, and pagination for every API client you build.**

[Installation](#installation) • [Quick Start](#quick-start) • [Features](#features) • [Architecture](#architecture) • [Create Your Own Client](#create-your-own-client) • [Roadmap](#roadmap)

</div>

---

## Why HakiAPI?

Every API client grows the same infrastructure, in the same order. You start with a simple HTTP call. Then you add authentication. Then retries. Then pagination. Then timeout and exception handling. A month later, you've rebuilt the same plumbing you already wrote for the last five projects.

HakiAPI extracts all of that into one reusable core, so every client you build on top of it inherits enterprise-grade behavior automatically. Instead of writing infrastructure, you write business logic.

### Without HakiAPI vs. with HakiAPI

| | Raw `requests` | HakiAPI |
|---|---|---|
| **OAuth 2.0 Flow** | Copy-paste URLs, manually spin up servers, hand-roll refreshes | Fully automated local interceptor + atomic token vault + auto-refresh |
| **Retry Logic** | Write your own `urllib3.Retry` + `HTTPAdapter` wiring | Built into `BaseAPIClient` with exponential backoff on 429/50x |
| **Static Auth** | Reimplement Bearer/HMAC/API keys per project | 4 reusable `AuthBase` strategies, drop-in |
| **Error Handling** | Manually check `response.status_code` everywhere | Raised as statically-typed, catchable exceptions |
| **Pagination** | Write a custom `while` loop per API's pagination style | Auto-detects Link-header & cursor pagination, iterated lazily |

---

## ✨ Features

| Feature | Details |
|---|---|
| 🔄 **Self-Healing OAuth 2.0** | Interactive local server interceptor, CSRF-protected browser flow, and background token refreshing. |
| 🗄️ **Atomic Token Vault** | `FileTokenStore` guarantees zero state corruption during concurrent writes using secure temp-file swapping. |
| 🔐 **Multiple Auth Strategies** | `BearerTokenAuth`, `HeaderApiKeyAuth`, `QueryApiKeyAuth`, `HmacAuth`. |
| 🔁 **Automatic Retries** | Exponential backoff on `429/500/502/503/504`, mounted transparently on every session. |
| 📄 **Smart Pagination** | Auto-detects Link-header (GitHub-style) and cursor/token (`meta.next_token`) pagination. |
| ⚠️ **Typed Exceptions** | `RateLimitError`, `AuthenticationError`, `ClientError`, `ServerError`, `RequestTimeoutError`. |
| 📦 **Ready-to-use Clients** | GitHub, Gmail, GoogleCalendar out of the box. |

---

## Installation

```bash
pip install hakiapi

```

Requires **Python 3.10+**.

---

## Quick Start

### 1. The Full-Cycle OAuth 2.0 Engine (Google Calendar)

Stop forcing users to copy and paste authorization codes. HakiAPI handles the complete browser flow, securely saves the state to an atomic file vault, and **automatically refreshes expired tokens in the background.**

```python
import os
from hakiapi.clients.google_calendar import GoogleCalendarClient
from hakiapi.core.oauth import GoogleOAuthFlow, FileTokenStore

# 1. Set up the secure vault and flow logic
oauth_flow = GoogleOAuthFlow(
    client_id=os.environ.get("GOOGLE_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
    scopes=["https://www.googleapis.com/auth/calendar.readonly"],
    store=FileTokenStore("my_secure_token.json"),
    redirect_port=8765, 
)

# 2. .get_token() does the heavy lifting: 
# It loads the token if valid, silently refreshes if expired, 
# or opens the browser and spins up a local interceptor if missing!
token = oauth_flow.get_token()

# 3. Initialize your client
with GoogleCalendarClient(token=token.access_token) as calendar:
    for event in calendar.events.upcoming(max_results=3):
        print(event.get("summary"))

```

### 2. Automatic Pagination (GitHub)

Forget page numbers, `while` loops, and manually checking for a `next` page. HakiAPI follows Link headers and cursor pagination automatically, lazily yielding results:

```python
from hakiapi.clients.github import GitHubClient

with GitHubClient() as github:
    # Lazily iterates through every repository, handling all HTTP requests behind the scenes
    for repo in github.get_all_user_repos("torvalds"):
        print(repo["name"])

```

---

## Exception Handling

Never check HTTP status codes manually again. Every exception inherits from `HakiAPIError`, carrying the `status_code` and original `response` object.

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

---

## Architecture & Project Structure

HakiAPI is designed with strict separation of concerns. Every service client inherits production-ready infrastructure automatically.

```text
hakiapi/
├── core/
│   ├── oauth/               # The Self-Healing OAuth 2.0 Engine
│   │   ├── google.py        # Local server interceptor & CSRF protection
│   │   ├── token_store.py   # Atomic file vault for token persistence
│   │   └── refresh.py       # Background token refresh logic
│   ├── auth.py              # Static auth strategies (Bearer, HMAC, API Keys)
│   ├── retry.py             # Exponential-backoff HTTPAdapter factory
│   ├── paginator.py         # Link-header + cursor/token pagination
│   ├── base_client.py       # Request lifecycle & session management
│   └── exceptions.py        # Typed exception hierarchy
│
└── clients/
    ├── github.py            # GitHub API implementation
    ├── gmail.py             # Gmail API implementation
    └── google_calendar.py   # Google Calendar implementation

```

---

## Create Your Own Client

Creating a new SDK is intentionally simple: subclass `BaseAPIClient`, point it at a base URL, and define your endpoints as plain methods.

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

### Output

```json
{
    "time": "2026-07-24T22:00",
    "interval": 900, 
    "temperature": 30.6, 
    "windspeed": 13.9, 
    "winddirection": 271, 
    "is_day": 0, 
    "weathercode": 51
}

```

*Authentication, retries, pagination, sessions, and exceptions are entirely inherited — you only write the endpoint logic.*

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

* ✅ **280+ tests passing**
* ✅ Core framework covered (auth, retry, paginator, base client, exceptions)
* ✅ Full OAuth 2.0 engine mocked and covered
* ✅ Atomic file vault concurrency tested
* ✅ Client implementations covered

---

## Roadmap

**Completed**

* [x] Base API framework (`BaseAPIClient`)
* [x] Authentication system (Bearer, Header, Query, HMAC)
* [x] Retry engine with exponential backoff
* [x] Automatic pagination (Link header + cursor/token)
* [x] Typed exception hierarchy
* [x] Full-cycle OAuth 2.0 Engine (Local server, Vault, Auto-Refresh)
* [x] GitHub, Gmail, & Google Calendar clients

**Planned**

* [ ] Stripe client
* [ ] Twitter/X client
* [ ] Async client (`httpx`-based)
* [ ] Plugin system

---

## Contributing

Contributions are welcome — bug fixes, documentation, tests, or new clients. Please open an issue before proposing major changes so we can discuss the approach first.

---

## License

MIT License — see [LICENSE](https://www.google.com/search?q=LICENSE) for details.

---

### ⭐ If HakiAPI saved you from rewriting the same API client for the tenth time, consider giving it a star.

It helps more developers discover the project and motivates future development.

Built with ❤️ by **Gugilla Aakash**
