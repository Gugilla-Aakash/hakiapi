<div align="center">

# 🚀 HakiAPI

### Build production-grade Python API SDKs — not boilerplate.

Authentication · Retries · Pagination · Typed Exceptions · Session Management

[![PyPI](https://img.shields.io/pypi/v/hakiapi?style=for-the-badge)](https://pypi.org/project/hakiapi/)
[![Python](https://img.shields.io/pypi/pyversions/hakiapi?style=for-the-badge)](https://pypi.org/project/hakiapi/)
[![License](https://img.shields.io/github/license/Gugilla-Aakash/hakiapi?style=for-the-badge)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-214_passing-success?style=for-the-badge)](#testing)
[![Typing](https://img.shields.io/badge/typing-fully_typed-blue?style=for-the-badge)](#features)
[![Downloads](https://img.shields.io/pypi/dm/hakiapi?style=for-the-badge)](https://pypistats.org/packages/hakiapi)

**Stop rewriting authentication, retries, and pagination for every API client you build.**

[Installation](#installation) • [Quick Start](#quick-start) • [Features](#features) • [Architecture](#architecture) • [Create Your Own Client](#create-your-own-client) • [Roadmap](#roadmap)

</div>

---

## Why HakiAPI?

Every API client grows the same infrastructure, in the same order. You start with a simple HTTP call. Then you add authentication. Then retries. Then pagination. Then timeout and exception handling. Then session management. A month later, you've rebuilt the same plumbing you already wrote for the last five projects.

HakiAPI extracts all of that into one reusable core, so every client you build on top of it inherits production-ready behavior automatically. Instead of writing infrastructure, you write business logic.

### Without HakiAPI vs. with HakiAPI

| | Raw `requests` | HakiAPI |
|---|---|---|
| Retry on 429/500/502/503/504 | Write your own `urllib3.Retry` + `HTTPAdapter` wiring | Built into `BaseAPIClient` automatically |
| Auth (Bearer / API Key / HMAC) | Reimplement per project | 4 reusable `AuthBase` strategies, drop-in |
| Rate limits, timeouts, 4xx/5xx | Manually check `response.status_code` everywhere | Raised as typed, catchable exceptions |
| Pagination | Write a `while` loop per API's pagination style | Auto-detects Link-header and cursor/token pagination, iterated lazily |
| New service client | Copy-paste session + error-handling code | Subclass `BaseAPIClient`, define endpoints, done |

---

## ✨ Features

| Feature | Details |
|---|---|
| 🔐 Multiple auth strategies | `BearerTokenAuth`, `HeaderApiKeyAuth`, `QueryApiKeyAuth`, `HmacAuth` |
| 🔁 Automatic retries | Exponential backoff on `429/500/502/503/504`, mounted transparently on every session |
| 📄 Automatic pagination | Auto-detects Link-header (GitHub-style) and cursor/token (`meta.next_token`) pagination, lazily iterated with an optional `max_pages` safety valve |
| ⚠️ Typed exception hierarchy | `RateLimitError`, `AuthenticationError`, `ClientError`, `ServerError`, `RequestTimeoutError`, all rooted in `HakiAPIError` |
| 🌐 Persistent HTTP sessions | Connection pooling via `requests.Session`, closed automatically with `with` |
| 🧩 Extensible base client | Subclass `BaseAPIClient`, inherit everything above for free |
| 📦 Ready-to-use clients | GitHub, Gmail |
| 🧪 Fully tested | 214 tests, full coverage of core + clients |
| 🐍 Python 3.10+ | Fully type-hinted |

---

## Installation

```bash
pip install hakiapi
```

Requires **Python 3.10+**.

---

## Quick Start

### GitHub

```python
from hakiapi.clients.github import GitHubClient

with GitHubClient() as github:
    user = github.get_user("torvalds")
    print(f"{user['name']} — {user['public_repos']} public repos")
```

No authentication plumbing. No retry logic. No session handling. Just Python.

### Automatic pagination

Forget page numbers, `while` loops, and manually checking for a `next` page — HakiAPI follows Link headers, cursor pagination, and token pagination automatically, lazily:

```python
with GitHubClient() as github:
    for repo in github.get_all_user_repos("torvalds"):
        print(repo["name"])
```

### A full example

Aggregate every programming language used across a user's public repositories, entirely through the paginator:

```python
from hakiapi.clients.github import GitHubClient

with GitHubClient() as github:
    target_user = "Gugilla-Aakash"

    user_data = github.get_user(target_user)
    print(f"User: {user_data.get('name')}")
    print(f"Public Repos: {user_data.get('public_repos')}")

    lang_stats = github.get_aggregate_user_languages(target_user, params={"per_page": 5})

    total_bytes = sum(lang_stats.values())
    print("\nLanguage Breakdown (by byte allocation):")
    for lang, byte_count in sorted(lang_stats.items(), key=lambda i: i[1], reverse=True):
        percentage = (byte_count / total_bytes) * 100 if total_bytes else 0
        print(f"- {lang}: {byte_count} bytes ({percentage:.2f}%)")
```

*Output shape is illustrative — real numbers depend on the account queried.*

### Gmail

```python
from hakiapi.clients.gmail import GmailClient

with GmailClient(token="your-oauth-token") as gmail:
    for message in gmail.get_all_messages():
        print(message["id"])
```

Authentication, pagination, and retries — already handled.

---

## Exception Handling

Never check HTTP status codes manually again:

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

Every exception inherits from `HakiAPIError`, so you can catch broadly or narrowly — each carries `status_code` and the original `response` object.

```
HakiAPIError
├── ClientError                 (4xx)
│   ├── RateLimitError          (429, carries retry_after)
│   └── AuthenticationError     (401 / 403, carries auth_method)
├── ServerError                 (5xx)
└── RequestTimeoutError         (network-level timeout, no status code)
```

---

## Supported Authentication

| Strategy | Use case |
|---|---|
| `BearerTokenAuth` | Standard `Authorization: Bearer <token>` (GitHub, Gmail, most OAuth2 APIs) |
| `HeaderApiKeyAuth` | Custom header-based API keys (e.g. `X-API-Key: <key>`) |
| `QueryApiKeyAuth` | Query-string API keys, appended without dropping existing params |
| `HmacAuth` | HMAC-SHA256 request signing — signs method, path, timestamp, and body; sets the key, timestamp, and signature headers |

Every strategy is a reusable `AuthBase` instance — pass it once into `BaseAPIClient.__init__`, and every request is signed automatically.

---

## Automatic Retry

Retries happen transparently on `429`, `500`, `502`, `503`, and `504`, via `urllib3`'s `Retry` mounted on the session's `HTTPAdapter`:

- Exponential backoff
- Connection reuse across retries
- Timeout handling surfaced as `RequestTimeoutError`
- No configuration required for standard usage — override `total_retries`, `backoff_factor`, or `status_forcelist` if you need to

---

## Architecture

```
              GitHubClient, GmailClient, ...
                         │
                         ▼
                  BaseAPIClient
       ┌──────────────┬─────────┬──────────┐
       │              │         │          │
 Authentication     Retry   Pagination  Exceptions
  (auth.py)       (retry.py) (paginator.py) (exceptions.py)
                         │
                         ▼
                     requests
```

Every service client inherits production-ready infrastructure automatically — nothing to wire up per client.

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
```
{
    'time': '2026-07-19T10:00',
    'interval': 900, 
    'temperature': 30.6, 
    'windspeed': 13.9, 
    'winddirection': 271, 
    'is_day': 1, 
    'weathercode': 51
}
```

Authentication, retries, pagination, sessions, and exceptions are already included — you only write the endpoint logic.

---

## Project Structure

```
hakiapi/
├── core/
│   ├── auth.py            # BearerTokenAuth, HeaderApiKeyAuth, QueryApiKeyAuth, HmacAuth
│   ├── retry.py            # Exponential-backoff HTTPAdapter factory
│   ├── paginator.py        # Link-header + cursor/token pagination, lazily iterated
│   ├── base_client.py      # Session management, request lifecycle, error mapping
│   └── exceptions.py       # Typed exception hierarchy
│
└── clients/
    ├── github.py            # GitHubClient
    └── gmail.py             # GmailClient
```

---

## Design Principles

- Infrastructure should be written once.
- API clients should remain lightweight.
- Explicit is better than magical.
- Strong typing improves maintainability.
- Production readiness should be the default, not an afterthought.
- Developer experience matters as much as correctness.

---

## Testing

```bash
pip install hakiapi[dev]
pytest
```

- ✅ 214 tests passing
- ✅ Core framework covered (auth, retry, paginator, base client, exceptions)
- ✅ GitHub client covered
- ✅ Gmail client covered

---

## Roadmap

**Completed**
- [x] Base API framework (`BaseAPIClient`)
- [x] Authentication system (Bearer, Header, Query, HMAC)
- [x] Retry engine with exponential backoff
- [x] Automatic pagination (Link header + cursor/token)
- [x] Typed exception hierarchy
- [x] GitHub client
- [x] Gmail client

**Planned**
- [ ] Google Calendar client
- [ ] Stripe client
- [ ] Twitter/X client
- [ ] Async client (`httpx`-based)
- [ ] OAuth2 helpers
- [ ] Plugin system
- [ ] More service clients

---

## Contributing

Contributions are welcome — bug fixes, documentation, tests, or new clients. Please open an issue before proposing major changes so we can discuss the approach first.

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

### ⭐ If HakiAPI saved you from rewriting the same API client for the tenth time, consider giving it a star.

It helps more developers discover the project and motivates future development.

Built with ❤️ by **Gugilla Aakash**

</div>
