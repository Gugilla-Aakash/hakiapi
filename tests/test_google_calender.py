"""
Tests for GoogleCalendarClient and its resource classes.
"""

import datetime
from typing import Any
from unittest.mock import MagicMock

import pytest

from hakiapi.clients.google_calendar import (
    CalendarEventsResource,
    CalendarsResource,
    GoogleCalendarClient,
)

# Fixtures


@pytest.fixture
def mock_client() -> MagicMock:
    return MagicMock()


def fake_paginate_capture(
    monkeypatch: pytest.MonkeyPatch, module_path: str
) -> MagicMock:
    """
    Patches `paginate` where it's looked up (inside hakiapi.clients.google_calendar),
    and makes it return an empty iterator by default so callers can just
    inspect the call args without needing a real generator to drain.
    """
    mock = MagicMock(return_value=iter([]))
    monkeypatch.setattr(module_path, mock)
    return mock


# CalendarsResource.list


class TestCalendarsResourceList:
    def test_calls_paginate_with_correct_endpoint(
        self, mock_client: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_paginate = fake_paginate_capture(
            monkeypatch, "hakiapi.clients.google_calendar.paginate"
        )
        resource = CalendarsResource(mock_client)

        list(resource.list())

        mock_paginate.assert_called_once_with(
            client=mock_client, endpoint="users/me/calendarList", max_pages=None
        )

    def test_forwards_max_pages(
        self, mock_client: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_paginate = fake_paginate_capture(
            monkeypatch, "hakiapi.clients.google_calendar.paginate"
        )
        resource = CalendarsResource(mock_client)

        list(resource.list(max_pages=5))

        assert mock_paginate.call_args.kwargs["max_pages"] == 5

    def test_forwards_extra_kwargs(
        self, mock_client: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_paginate = fake_paginate_capture(
            monkeypatch, "hakiapi.clients.google_calendar.paginate"
        )
        resource = CalendarsResource(mock_client)

        list(resource.list(params={"minAccessRole": "writer"}, timeout=5))

        assert mock_paginate.call_args.kwargs["params"] == {"minAccessRole": "writer"}
        assert mock_paginate.call_args.kwargs["timeout"] == 5

    def test_yields_items_from_paginate(
        self, mock_client: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "hakiapi.clients.google_calendar.paginate",
            MagicMock(return_value=iter([{"id": "cal1"}, {"id": "cal2"}])),
        )
        resource = CalendarsResource(mock_client)

        result = list(resource.list())

        assert result == [{"id": "cal1"}, {"id": "cal2"}]


# CalendarEventsResource.get / create / delete


class TestCalendarEventsResourceCrud:
    def test_get_default_calendar(self, mock_client: MagicMock) -> None:
        resource = CalendarEventsResource(mock_client)
        mock_client.get.return_value = {"id": "evt1"}

        result = resource.get("evt1")

        mock_client.get.assert_called_once_with("calendars/primary/events/evt1")
        assert result == {"id": "evt1"}

    def test_get_explicit_calendar(self, mock_client: MagicMock) -> None:
        resource = CalendarEventsResource(mock_client)

        resource.get("evt1", calendar_id="work@example.com")

        mock_client.get.assert_called_once_with(
            "calendars/work@example.com/events/evt1"
        )

    def test_create_posts_payload(self, mock_client: MagicMock) -> None:
        resource = CalendarEventsResource(mock_client)
        payload = {
            "summary": "Standup",
            "start": {"dateTime": "2026-07-21T09:00:00Z"},
            "end": {"dateTime": "2026-07-21T09:15:00Z"},
        }
        mock_client.post.return_value = {"id": "evt2", **payload}

        result = resource.create(payload)

        mock_client.post.assert_called_once_with(
            "calendars/primary/events", json=payload
        )
        assert result["id"] == "evt2"

    def test_create_with_explicit_calendar(self, mock_client: MagicMock) -> None:
        resource = CalendarEventsResource(mock_client)
        payload = {"summary": "1:1"}

        resource.create(payload, calendar_id="work@example.com")

        mock_client.post.assert_called_once_with(
            "calendars/work@example.com/events", json=payload
        )

    def test_delete_default_calendar(self, mock_client: MagicMock) -> None:
        resource = CalendarEventsResource(mock_client)
        mock_client.delete.return_value = {}

        resource.delete("evt1")

        mock_client.delete.assert_called_once_with("calendars/primary/events/evt1")

    def test_delete_explicit_calendar(self, mock_client: MagicMock) -> None:
        resource = CalendarEventsResource(mock_client)

        resource.delete("evt1", calendar_id="work@example.com")

        mock_client.delete.assert_called_once_with(
            "calendars/work@example.com/events/evt1"
        )


# CalendarEventsResource.list


class TestCalendarEventsResourceList:
    def test_calls_paginate_with_correct_endpoint(
        self, mock_client: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_paginate = fake_paginate_capture(
            monkeypatch, "hakiapi.clients.google_calendar.paginate"
        )
        resource = CalendarEventsResource(mock_client)

        list(resource.list())

        mock_paginate.assert_called_once_with(
            client=mock_client, endpoint="calendars/primary/events", max_pages=None
        )

    def test_endpoint_uses_explicit_calendar_id(
        self, mock_client: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_paginate = fake_paginate_capture(
            monkeypatch, "hakiapi.clients.google_calendar.paginate"
        )
        resource = CalendarEventsResource(mock_client)

        list(resource.list(calendar_id="work@example.com"))

        assert (
            mock_paginate.call_args.kwargs["endpoint"]
            == "calendars/work@example.com/events"
        )

    def test_forwards_max_pages_and_params(
        self, mock_client: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_paginate = fake_paginate_capture(
            monkeypatch, "hakiapi.clients.google_calendar.paginate"
        )
        resource = CalendarEventsResource(mock_client)

        list(resource.list(max_pages=2, params={"q": "standup"}))

        assert mock_paginate.call_args.kwargs["max_pages"] == 2
        assert mock_paginate.call_args.kwargs["params"] == {"q": "standup"}


# CalendarEventsResource.today

FIXED_NOW = datetime.datetime(2026, 7, 20, 15, 30, 45, tzinfo=datetime.timezone.utc)


class _FixedDatetime(datetime.datetime):
    """Lets us pin datetime.datetime.now() without freezegun as a dependency."""

    @classmethod
    def now(cls, tz=None):  # type: ignore[override]
        return FIXED_NOW


class TestCalendarEventsResourceToday:
    def test_time_window_is_midnight_to_midnight_utc(
        self, mock_client: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_paginate = fake_paginate_capture(
            monkeypatch, "hakiapi.clients.google_calendar.paginate"
        )
        monkeypatch.setattr(
            "hakiapi.clients.google_calendar.datetime.datetime", _FixedDatetime
        )
        resource = CalendarEventsResource(mock_client)

        list(resource.today())

        params = mock_paginate.call_args.kwargs["params"]
        assert params["timeMin"] == "2026-07-20T00:00:00Z"
        assert params["timeMax"] == "2026-07-21T00:00:00Z"

    def test_sets_single_events_and_order_by(
        self, mock_client: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_paginate = fake_paginate_capture(
            monkeypatch, "hakiapi.clients.google_calendar.paginate"
        )
        monkeypatch.setattr(
            "hakiapi.clients.google_calendar.datetime.datetime", _FixedDatetime
        )
        resource = CalendarEventsResource(mock_client)

        list(resource.today())

        params = mock_paginate.call_args.kwargs["params"]
        assert params["singleEvents"] is True
        assert params["orderBy"] == "startTime"

    def test_uses_correct_endpoint_and_default_calendar(
        self, mock_client: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_paginate = fake_paginate_capture(
            monkeypatch, "hakiapi.clients.google_calendar.paginate"
        )
        monkeypatch.setattr(
            "hakiapi.clients.google_calendar.datetime.datetime", _FixedDatetime
        )
        resource = CalendarEventsResource(mock_client)

        list(resource.today())

        assert mock_paginate.call_args.kwargs["endpoint"] == "calendars/primary/events"

    def test_respects_explicit_calendar_id(
        self, mock_client: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_paginate = fake_paginate_capture(
            monkeypatch, "hakiapi.clients.google_calendar.paginate"
        )
        monkeypatch.setattr(
            "hakiapi.clients.google_calendar.datetime.datetime", _FixedDatetime
        )
        resource = CalendarEventsResource(mock_client)

        list(resource.today(calendar_id="work@example.com"))

        assert (
            mock_paginate.call_args.kwargs["endpoint"]
            == "calendars/work@example.com/events"
        )

    def test_does_not_mutate_callers_params_dict(
        self, mock_client: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_paginate_capture(monkeypatch, "hakiapi.clients.google_calendar.paginate")
        monkeypatch.setattr(
            "hakiapi.clients.google_calendar.datetime.datetime", _FixedDatetime
        )
        resource = CalendarEventsResource(mock_client)

        caller_params = {"q": "standup"}
        list(resource.today(params=caller_params))

        # today() must not have added timeMin/timeMax/etc into the caller's own dict
        assert caller_params == {"q": "standup"}

    def test_preserves_existing_params(
        self, mock_client: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_paginate = fake_paginate_capture(
            monkeypatch, "hakiapi.clients.google_calendar.paginate"
        )
        monkeypatch.setattr(
            "hakiapi.clients.google_calendar.datetime.datetime", _FixedDatetime
        )
        resource = CalendarEventsResource(mock_client)

        list(resource.today(params={"q": "standup"}))

        params = mock_paginate.call_args.kwargs["params"]
        assert params["q"] == "standup"
        assert params["timeMin"] == "2026-07-20T00:00:00Z"

    def test_no_max_pages_by_default(
        self, mock_client: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_paginate = fake_paginate_capture(
            monkeypatch, "hakiapi.clients.google_calendar.paginate"
        )
        monkeypatch.setattr(
            "hakiapi.clients.google_calendar.datetime.datetime", _FixedDatetime
        )
        resource = CalendarEventsResource(mock_client)

        list(resource.today())

        assert mock_paginate.call_args.kwargs["max_pages"] is None


# CalendarEventsResource.upcoming


class TestCalendarEventsResourceUpcoming:
    def test_sets_time_min_to_now(
        self, mock_client: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_paginate = fake_paginate_capture(
            monkeypatch, "hakiapi.clients.google_calendar.paginate"
        )
        monkeypatch.setattr(
            "hakiapi.clients.google_calendar.datetime.datetime", _FixedDatetime
        )
        resource = CalendarEventsResource(mock_client)

        list(resource.upcoming())

        params = mock_paginate.call_args.kwargs["params"]
        assert params["timeMin"] == "2026-07-20T15:30:45Z"

    def test_default_max_results_is_ten(
        self, mock_client: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_paginate = fake_paginate_capture(
            monkeypatch, "hakiapi.clients.google_calendar.paginate"
        )
        monkeypatch.setattr(
            "hakiapi.clients.google_calendar.datetime.datetime", _FixedDatetime
        )
        resource = CalendarEventsResource(mock_client)

        list(resource.upcoming())

        assert mock_paginate.call_args.kwargs["params"]["maxResults"] == 10

    def test_custom_max_results_forwarded_as_query_param(
        self, mock_client: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_paginate = fake_paginate_capture(
            monkeypatch, "hakiapi.clients.google_calendar.paginate"
        )
        monkeypatch.setattr(
            "hakiapi.clients.google_calendar.datetime.datetime", _FixedDatetime
        )
        resource = CalendarEventsResource(mock_client)

        list(resource.upcoming(max_results=3))

        assert mock_paginate.call_args.kwargs["params"]["maxResults"] == 3

    def test_forces_max_pages_to_one(
        self, mock_client: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_paginate = fake_paginate_capture(
            monkeypatch, "hakiapi.clients.google_calendar.paginate"
        )
        monkeypatch.setattr(
            "hakiapi.clients.google_calendar.datetime.datetime", _FixedDatetime
        )
        resource = CalendarEventsResource(mock_client)

        list(resource.upcoming())

        assert mock_paginate.call_args.kwargs["max_pages"] == 1

    def test_passing_max_pages_explicitly_is_safely_ignored(
        self, mock_client: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Since upcoming() hardcodes max_pages=1 to rely on maxResults capping,
        if a caller erroneously passes max_pages=5, it should be safely discarded
        to prevent a TypeError collision, and default back to 1.
        """
        mock_paginate = fake_paginate_capture(
            monkeypatch, "hakiapi.clients.google_calendar.paginate"
        )
        monkeypatch.setattr(
            "hakiapi.clients.google_calendar.datetime.datetime", _FixedDatetime
        )
        resource = CalendarEventsResource(mock_client)

        # This will no longer raise a TypeError!
        list(resource.upcoming(max_pages=5))

        assert mock_paginate.call_args.kwargs["max_pages"] == 1

    def test_sets_single_events_and_order_by(
        self, mock_client: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_paginate = fake_paginate_capture(
            monkeypatch, "hakiapi.clients.google_calendar.paginate"
        )
        monkeypatch.setattr(
            "hakiapi.clients.google_calendar.datetime.datetime", _FixedDatetime
        )
        resource = CalendarEventsResource(mock_client)

        list(resource.upcoming())

        params = mock_paginate.call_args.kwargs["params"]
        assert params["singleEvents"] is True
        assert params["orderBy"] == "startTime"

    def test_does_not_mutate_callers_params_dict(
        self, mock_client: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_paginate_capture(monkeypatch, "hakiapi.clients.google_calendar.paginate")
        monkeypatch.setattr(
            "hakiapi.clients.google_calendar.datetime.datetime", _FixedDatetime
        )
        resource = CalendarEventsResource(mock_client)

        caller_params = {"q": "standup"}
        list(resource.upcoming(params=caller_params))

        assert caller_params == {"q": "standup"}

    def test_respects_explicit_calendar_id(
        self, mock_client: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_paginate = fake_paginate_capture(
            monkeypatch, "hakiapi.clients.google_calendar.paginate"
        )
        monkeypatch.setattr(
            "hakiapi.clients.google_calendar.datetime.datetime", _FixedDatetime
        )
        resource = CalendarEventsResource(mock_client)

        list(resource.upcoming(calendar_id="work@example.com"))

        assert (
            mock_paginate.call_args.kwargs["endpoint"]
            == "calendars/work@example.com/events"
        )


# GoogleCalendarClient wiring


class TestGoogleCalendarClientWiring:
    def test_mounts_resources(self) -> None:
        client = GoogleCalendarClient(token="fake-token")

        assert isinstance(client.calendars, CalendarsResource)
        assert isinstance(client.events, CalendarEventsResource)

    def test_base_url_is_calendar_v3(self) -> None:
        client = GoogleCalendarClient(token="fake-token")

        # Fixed: BaseAPIClient safely strips the trailing slash
        assert client.base_url == "https://www.googleapis.com/calendar/v3"


# Integration-style: full round trip through the real paginate(), proving
# the 'items' response shape (Google Calendar/Drive-style) is now handled.


class FakeResponse:
    def __init__(self, json_data: Any, links: dict | None = None) -> None:
        self._json_data = json_data
        self.links = links or {}

    def json(self) -> Any:
        return self._json_data


class TestGoogleCalendarPaginationIntegration:
    def test_events_list_handles_items_shaped_response(
        self, mock_client: MagicMock
    ) -> None:
        mock_client._request.return_value = FakeResponse(
            {"kind": "calendar#events", "items": [{"id": "evt1"}, {"id": "evt2"}]}
        )
        resource = CalendarEventsResource(mock_client)

        events = list(resource.list())

        assert events == [{"id": "evt1"}, {"id": "evt2"}]

    def test_calendars_list_handles_items_shaped_response_with_pagetoken(
        self, mock_client: MagicMock
    ) -> None:
        mock_client._request.side_effect = [
            FakeResponse({"items": [{"id": "cal1"}], "nextPageToken": "TOK"}),
            FakeResponse({"items": [{"id": "cal2"}]}),
        ]
        resource = CalendarsResource(mock_client)

        calendars = list(resource.list())

        assert calendars == [{"id": "cal1"}, {"id": "cal2"}]
        assert mock_client._request.call_count == 2
