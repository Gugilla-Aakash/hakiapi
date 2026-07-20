import datetime
from typing import Any, Iterator, Optional

from ..core.base_client import BaseAPIClient
from ..core import auth
from ..core.paginator import paginate


class CalendarsResource:
    """Handles operations related to the user's calendars."""

    def __init__(self, client: BaseAPIClient) -> None:
        self._client = client

    def list(
        self, max_pages: Optional[int] = None, **kwargs: Any
    ) -> Iterator[dict[str, Any]]:
        """List all calendars on the user's calendar list."""
        return paginate(
            client=self._client,
            endpoint="users/me/calendarList",
            max_pages=max_pages,
            **kwargs,
        )


class CalendarEventsResource:
    """Handles all read, write, and time-based search operations for events."""

    def __init__(self, client: BaseAPIClient) -> None:
        self._client = client

    def get(
        self, event_id: str, calendar_id: str = "primary", **kwargs: Any
    ) -> dict[str, Any]:
        """Fetch the full details of a specific event by ID."""
        return self._client.get(f"calendars/{calendar_id}/events/{event_id}", **kwargs)

    def list(
        self,
        calendar_id: str = "primary",
        max_pages: Optional[int] = None,
        **kwargs: Any,
    ) -> Iterator[dict[str, Any]]:
        """Lazily yield all events from a calendar."""
        return paginate(
            client=self._client,
            endpoint=f"calendars/{calendar_id}/events",
            max_pages=max_pages,
            **kwargs,
        )

    def today(
        self, calendar_id: str = "primary", **kwargs: Any
    ) -> Iterator[dict[str, Any]]:
        """Fetch all events happening between midnight today and midnight tomorrow (UTC)."""
        now = datetime.datetime.now(datetime.timezone.utc)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + datetime.timedelta(days=1)

        params = dict(kwargs.get("params", {}) or {})

        # Note:- Google Calendar requires ISO 8601 strings formatted with 'Z' for UTC
        params["timeMin"] = start_of_day.isoformat().replace("+00:00", "Z")
        params["timeMax"] = end_of_day.isoformat().replace("+00:00", "Z")
        params["singleEvents"] = (
            True  # Expands recurring events into individual instances
        )
        params["orderBy"] = "startTime"
        kwargs["params"] = params

        return self.list(calendar_id=calendar_id, **kwargs)

    def upcoming(
        self, calendar_id: str = "primary", max_results: int = 10, **kwargs: Any
    ) -> Iterator[dict[str, Any]]:
        """Fetch the next immediately upcoming events from right now."""
        now = datetime.datetime.now(datetime.timezone.utc)

        params = dict(kwargs.get("params", {}) or {})
        params["timeMin"] = now.isoformat().replace("+00:00", "Z")
        params["maxResults"] = max_results
        params["singleEvents"] = True
        params["orderBy"] = "startTime"
        kwargs["params"] = params

        # Pop max_pages from kwargs so it doesn't collide with our hardcoded max_pages=1
        kwargs.pop("max_pages", None)

        return self.list(calendar_id=calendar_id, max_pages=1, **kwargs)

    def create(
        self, payload: dict[str, Any], calendar_id: str = "primary", **kwargs: Any
    ) -> dict[str, Any]:
        """
        Create a new event.
        Requires 'start' and 'end' datetime payloads in the JSON body.
        """
        return self._client.post(
            f"calendars/{calendar_id}/events", json=payload, **kwargs
        )

    def delete(
        self, event_id: str, calendar_id: str = "primary", **kwargs: Any
    ) -> dict[str, Any]:
        """Delete an existing event."""
        # Note: Successful DELETE in Google APIs usually returns an empty 204 response
        return self._client.delete(
            f"calendars/{calendar_id}/events/{event_id}", **kwargs
        )


class GoogleCalendarClient(BaseAPIClient):
    """
    Client for interacting with the Google Calendar API v3.
    Requires an OAuth 2.0 Bearer Token with the appropriate scopes.
    """

    def __init__(self, token: str, **kwargs: Any) -> None:
        kwargs["auth"] = auth.BearerTokenAuth(token)
        super().__init__(base_url="https://www.googleapis.com/calendar/v3/", **kwargs)

        # Mount the nested resource endpoints
        self.calendars = CalendarsResource(self)
        self.events = CalendarEventsResource(self)
