"""
Example usage of the HakiAPI Google Calendar Client with Resource-Based Routing.
"""

import os
import sys

# Import the client directly from the top-level facade
from hakiapi import GoogleCalendarClient, exceptions

# 1. Fetch the token from the OS environment securely
token = os.environ.get("GOOGLE_CALENDAR_TOKEN")

if not token:
    print("Error: GOOGLE_CALENDAR_TOKEN environment variable not found in the OS.")
    print("Please run: export GOOGLE_CALENDAR_TOKEN='your_token_here'")
    sys.exit(1)

# 2. Initialize the client securely using the context manager
try:
    with GoogleCalendarClient(token=token) as calendar_api:
        print("Authenticating with Google Calendar...\n")

        # 3. Calendars Resource - List available calendars
        print("Fetching your calendars...")
        # max_pages=1 is used as a safety valve to just grab the first page of calendars
        calendars_iterator = calendar_api.calendars.list(max_pages=1)

        print("Top 3 Calendars:")
        for count, cal in enumerate(calendars_iterator):
            if count >= 3:
                break
            # Google Calendar uses 'summary' for the display name
            print(f"  - {cal.get('summary')} (ID: {cal.get('id')})")

        # 4. Events Resource - Today's Events
        print("\nFetching today's events...")
        todays_events = calendar_api.events.today()

        events_found = False
        for event in todays_events:
            events_found = True
            summary = event.get("summary", "Untitled Event")

            # Google Calendar events have either 'dateTime' (specific time) or 'date' (all-day event)
            start_info = event.get("start", {})
            start_time = start_info.get("dateTime") or start_info.get(
                "date", "Unknown Time"
            )

            print(f"  📅 {summary}")
            print(f"     Starts: {start_time}")

        if not events_found:
            print("  No events scheduled for today! 🎉")

        # 5. Events Resource - Upcoming Events
        print("\nFetching your next 3 upcoming events...")
        # The client automatically caps max_pages=1 when max_results is provided
        upcoming_events = calendar_api.events.upcoming(max_results=3)

        for event in upcoming_events:
            summary = event.get("summary", "Untitled Event")
            event_id = event.get("id")

            if not isinstance(event_id, str):
                continue

            print(f"\n🔜 {summary}")
            print(f"   Event ID: {event_id}")

            # 6. Events Resource - Get specific event details
            # Just to demonstrate fetching a single event by its ID
            full_event = calendar_api.events.get(event_id=event_id)
            link = full_event.get("htmlLink", "No link available")
            print(f"   Link: {link}")

except exceptions.HakiAPIError as e:
    print(f"\n❌ API Request failed: {e}")
