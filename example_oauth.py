import os
import sys

from hakiapi.clients.google_calendar import GoogleCalendarClient
from hakiapi.core.oauth.google import GoogleOAuthFlow
from hakiapi.core.oauth.token_store import FileTokenStore

CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")

if not CLIENT_ID or not CLIENT_SECRET:
    print("❌ Error: Missing Google Cloud credentials.")
    sys.exit(1)

# 1. Configure the OAuth Flow
token_store = FileTokenStore("my_secure_token.json")

oauth_flow = GoogleOAuthFlow(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    scopes=["https://www.googleapis.com/auth/calendar.readonly"],
    store=token_store,
    redirect_port=8765, 
)

print("🚀 Booting up HakiAPI OAuth Engine...")
print("If you don't have a valid token, your browser will open now.\n")

# 2. FETCH THE TOKEN DIRECTLY! 
# This will force the browser to open, or load it from the JSON file.
oauth_token = oauth_flow.get_token()

print("✅ Token acquired! Initializing Client...")

# 3. Pass the raw access string directly into your existing client logic
with GoogleCalendarClient(token=oauth_token.access_token) as calendar_api:
    
    print("Fetching your next 5 upcoming events...\n")
    
    upcoming_events = calendar_api.events.upcoming(max_results=5)
    
    events_found = False
    for event in upcoming_events:
        events_found = True
        summary = event.get("summary", "Untitled Event")
        start_info = event.get("start", {})
        start_time = start_info.get("dateTime") or start_info.get("date", "All Day")
        
        print(f"📅 {summary}")
        print(f"   Starts: {start_time}\n")
        
    if not events_found:
        print("You have no upcoming events.")

print("✅ End-to-end OAuth test complete!")
