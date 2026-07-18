<div align="center">

# HakiAPI

### Build resilient Python API clients — not boilerplate.

A modern, typed, extensible framework for building production-ready API SDKs with automatic authentication, retries, pagination, and consistent error handling.

[![PyPI](https://img.shields.io/pypi/v/hakiapi)](https://pypi.org/project/hakiapi/)
[![Python](https://img.shields.io/pypi/pyversions/hakiapi)](https://pypi.org/project/hakiapi/)
[![License](https://img.shields.io/github/license/Gugilla-Aakash/hakiapi)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-190%2B%20passing-brightgreen)](#testing)

[Installation](#installation) • [Quick Example](#quick-example) • [Features](#features) • [Architecture](#architecture) • [Roadmap](#roadmap)

</div>

---

## Why HakiAPI?

Every API client eventually implements the same things:

- Authentication
- Retry logic
- Pagination
- Session management
- Exception handling

HakiAPI provides these once, correctly, so you can focus on your API instead of rebuilding infrastructure.

---

## Installation

```bash
pip install hakiapi
```

---

## Quick Example

```python
from hakiapi.clients.github import GitHubClient

github = GitHubClient()
user = github.get_user("torvalds")
print(user["login"])
```

**Automatic pagination** — no page counting, no manual `while` loops:

```python
for repo in github.get_all_user_repos("torvalds"):
    print(repo["name"])
```

**Automatic retries and errors** — failures surface as typed exceptions you can actually catch:

```python
from hakiapi.core.exceptions import RateLimitError, ServerError

try:
    user = github.get_user("torvalds")
except RateLimitError:
    print("Rate limited — back off and retry later")
except ServerError:
    print("GitHub is having issues, not your code")
```

No page counting.
No retry handling.
No authentication plumbing.
Just Python.

---

## Features

| | |
|---|---|
| 🔐 **Multiple auth strategies** | Bearer Token, API Key (Header), API Key (Query), HMAC |
| 🔁 **Automatic retries** | Configurable backoff that preserves typed exceptions instead of swallowing failures |
| 📄 **Automatic pagination** | Auto-detects GitHub-style Link headers *and* cursor/token APIs, iterated lazily |
| ⚠️ **Rich exception hierarchy** | `RateLimitError`, `ServerError`, and more — catch exactly what you expect |
| 🧱 **Extensible `BaseAPIClient`** | Subclass it once, inherit auth/retry/pagination for free |
| 📦 **Ready-to-use service clients** | GitHub, Gmail included out of the box |

---

## Architecture

```
            GitHubClient,GmailClient
                       │
                       ▼
                BaseAPIClient
      ┌──────────────┬─────────┬──────────┐
      │              │         │          │
Authentication     Retry   Pagination  Exceptions
```

Each service client is a thin layer over `BaseAPIClient` — define your endpoints, and authentication, retries, and pagination come along automatically.

---

## Project Structure

```
hakiapi/
├── core/
│   ├── auth.py
│   ├── retry.py
│   ├── paginator.py
│   ├── base_client.py
│   └── exceptions.py
│
└── clients/
    ├── github.py
    ├── gmail.py
```

---

## Testing

```bash
pytest
```

- ✔ 210+ tests
- ✔ Full client coverage (GitHub, Gmail)
- ✔ Full core framework coverage (auth, retry, paginator, base client)

---

## Roadmap

- [x] Base API framework
- [x] Retry engine
- [x] Authentication system
- [x] Automatic pagination
- [x] GitHub client
- [x] Gmail client
- [ ] Stripe client
- [ ] Twitter client
- [ ] Async client
- [ ] More API clients

---

## Contributing

Pull requests are welcome. Please open an issue before proposing major changes so we can discuss the approach first.

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

Built with ❤️ by **Gugilla Aakash**

If HakiAPI helps your project, consider giving it a ⭐

</div>
