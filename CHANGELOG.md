# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Coverage hardening for README/profile checks, OAuth redirect handler,
  and the `governer` deprecation shim.

## [2.1.6] - 2026-09-21

### Added
- Quality pipeline (`.github/workflows/ci.yml`): 4 jobs — Ruff check + format,
  pytest matrix `3.10–3.14`, mypy type check, Bandit + pip-audit security scan.
- PyPI classifiers for Python `3.11–3.14`, MIT license, and typing.

### Fixed
- 27 Ruff violations (moderate set `E,F,I,UP,B,SIM`, line-length 88): E501
  reflows, SIM105 `contextlib.suppress`, B011 `pytest.raises`.
- 2 Bandit false positives suppressed with justification: `B311` retry
  jitter, `B105` public OAuth endpoint.

### Changed
- `pytest` now enforces coverage gate `>=85%` (370 tests, 86.94%).
- `mypy` runs on `hakiapi` (`warn_return_any=false` for `Any`-returning
  request helpers).
- Dev extra now includes `pytest-cov`, `mypy`, `bandit[toml]`, `pip-audit`.

## [2.1.5] - 2026-09-01

### Changed
- Renamed `hakiapi.core.governer` (typo) to `hakiapi.core.governor`.
  Old path still works via `DeprecationWarning` shim.

[2.1.6]: https://github.com/Gugilla-Aakash/hakiapi/compare/v2.1.5...v2.1.6
[2.1.5]: https://github.com/Gugilla-Aakash/hakiapi/releases/tag/v2.1.5
