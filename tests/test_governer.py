"""Tests for the deprecated ``hakiapi.core.governer`` typo shim."""

import importlib
import sys

import pytest


def test_governer_shim_emits_deprecation_and_reexports() -> None:
    sys.modules.pop("hakiapi.core.governer", None)
    with pytest.warns(DeprecationWarning, match="governer is deprecated"):
        import hakiapi.core.governer as shim

        importlib.reload(shim)

    from hakiapi.core.governor import PredictiveGovernor, RateLimitState

    assert shim.PredictiveGovernor is PredictiveGovernor
    assert shim.RateLimitState is RateLimitState
    assert set(shim.__all__) == {"PredictiveGovernor", "RateLimitState"}
