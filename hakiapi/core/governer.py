import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass
class RateLimitState:
    remaining: int | float
    reset_timestamp: float


class PredictiveGovernor:
    def __init__(self, safety_margin: int = 1):
        self._registry: Dict[str, RateLimitState] = {}
        self._lock = threading.Lock()
        self.safety_margin = safety_margin

    def get_wait_time(self, host: str) -> float:
        with self._lock:
            state = self._registry.get(host)
            if not state:
                return 0.0

            if state.remaining > self.safety_margin:
                return 0.0

            now = time.time()
            if now >= state.reset_timestamp:
                state.remaining = float("inf")
                return 0.0

            return state.reset_timestamp - now

    def update_from_headers(self, host: str, headers: dict) -> None:
        """
        Post-request hook: Parses response headers and updates the registry.
        Supports GitHub-style (X-RateLimit-*) and IETF draft-style
        (RateLimit-*) headers, case-insensitively.
        """
        norm = {k.lower(): v for k, v in headers.items()}

        remaining, reset_ts = (
            self._parse_github(norm) or self._parse_ietf(norm) or (None, None)
        )

        if remaining is None or reset_ts is None:
            return  # No recognizable rate-limit headers; leave state untouched

        with self._lock:
            self._registry[host] = RateLimitState(
                remaining=remaining,
                reset_timestamp=reset_ts,
            )

    @staticmethod
    def _parse_github(headers: dict) -> Optional[Tuple[int, float]]:
        remaining = headers.get("x-ratelimit-remaining")
        reset = headers.get("x-ratelimit-reset")
        if remaining is None or reset is None:
            return None
        try:
            return int(remaining), float(reset)  # GitHub sends epoch seconds
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_ietf(headers: dict) -> Optional[Tuple[int, float]]:
        """
        Handles the IETF draft `RateLimit` / `RateLimit-Remaining` /
        `RateLimit-Reset` headers, where reset is delta-seconds, not epoch.
        """
        remaining = headers.get("ratelimit-remaining")
        reset = headers.get("ratelimit-reset")
        if remaining is None or reset is None:
            return None
        try:
            remaining_i = int(remaining)
            reset_delta = float(reset)
            return remaining_i, time.time() + reset_delta
        except (TypeError, ValueError):
            return None
