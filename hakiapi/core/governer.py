"""Backward-compatibility shim for the historic ``governer`` typo.

The module was renamed to :mod:`hakiapi.core.governor`. This shim keeps
``from hakiapi.core.governer import ...`` working while emitting a
``DeprecationWarning``. It will be removed in a future major release.
"""

from __future__ import annotations

import warnings

from .governor import PredictiveGovernor, RateLimitState  # noqa: F401

warnings.warn(
    "hakiapi.core.governer is deprecated (typo); use hakiapi.core.governor instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["PredictiveGovernor", "RateLimitState"]
