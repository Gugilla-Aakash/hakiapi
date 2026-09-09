from __future__ import annotations

import time

from hakiapi.core.governer import PredictiveGovernor, RateLimitState


class TestPredictiveGovernor:
    def test_governor_allows_request_when_no_state_exists(self):
        governor = PredictiveGovernor(safety_margin=1)
        assert governor.get_wait_time("api.example.com") == 0.0

    def test_governor_allows_request_when_remaining_is_above_margin(self):
        governor = PredictiveGovernor(safety_margin=5)
        governor._registry["api.example.com"] = RateLimitState(
            remaining=10, reset_timestamp=time.time() + 60
        )
        assert governor.get_wait_time("api.example.com") == 0.0

    def test_governor_calculates_wait_time_when_quota_exhausted(self):
        governor = PredictiveGovernor(safety_margin=1)
        future_reset = time.time() + 15.0
        governor._registry["api.example.com"] = RateLimitState(
            remaining=0, reset_timestamp=future_reset
        )

        wait_time = governor.get_wait_time("api.example.com")
        # Should be approximately 15 seconds (allowing a tiny execution delta)
        assert 14.0 <= wait_time <= 15.0

    def test_governor_resets_quota_if_timestamp_has_passed(self):
        governor = PredictiveGovernor(safety_margin=1)
        past_reset = time.time() - 5.0  # Reset was 5 seconds ago
        governor._registry["api.example.com"] = RateLimitState(
            remaining=0, reset_timestamp=past_reset
        )

        # Should detect that reset time passed, clear block, and return 0.0
        assert governor.get_wait_time("api.example.com") == 0.0
        assert governor._registry["api.example.com"].remaining == float("inf")


class TestHeaderParsing:
    def test_parses_github_style_headers(self):
        governor = PredictiveGovernor()
        headers = {
            "X-RateLimit-Limit": "5000",
            "X-RateLimit-Remaining": "42",
            "X-RateLimit-Reset": "1800000000",
        }

        governor.update_from_headers("api.github.com", headers)
        state = governor._registry.get("api.github.com")

        assert state is not None
        assert state.remaining == 42
        assert state.reset_timestamp == 1800000000.0

    def test_parses_ietf_style_headers(self):
        governor = PredictiveGovernor()
        headers = {
            "RateLimit-Limit": "100",
            "RateLimit-Remaining": "0",
            "RateLimit-Reset": "30",  # 30 seconds delta
        }

        before_time = time.time()
        governor.update_from_headers("api.ietf.org", headers)
        after_time = time.time()

        state = governor._registry.get("api.ietf.org")
        assert state is not None
        assert state.remaining == 0
        # Reset timestamp should be roughly now + 30 seconds
        assert (before_time + 30.0) <= state.reset_timestamp <= (after_time + 30.0)

    def test_ignores_unrecognized_headers(self):
        governor = PredictiveGovernor()
        headers = {"Content-Type": "application/json"}

        governor.update_from_headers("api.example.com", headers)
        assert "api.example.com" not in governor._registry
