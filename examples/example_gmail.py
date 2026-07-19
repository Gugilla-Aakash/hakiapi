"""
Example usage of the HakiAPI Gmail Client with Resource-Based Routing.
"""

import os
import sys
from hakiapi import GmailClient, exceptions

# 1. Fetch the token from the OS environment securely
token = os.environ.get("GMAIL_OAUTH_TOKEN")

if not token:
    print("Error: GMAIL_OAUTH_TOKEN environment variable not found in the OS.")
    print("Please run: export GMAIL_OAUTH_TOKEN='your_token_here'")
    sys.exit(1)

# 2. Initialize the client securely using the context manager
try:
    with GmailClient(token=token) as gmail:
        print("Authenticating with Google...\n")

        # 3. Profile Resource
        profile = gmail.profile.get()
        print(f"✅ Connected as: {profile.get('emailAddress')}")

        # 4. Labels Resource
        print("\nFetching Mailbox Labels...")
        labels_response = gmail.labels.list()
        labels = labels_response.get("labels", [])
        print(f"Found {len(labels)} labels. Top 3:")
        for label in labels[:3]:
            print(f"  - {label.get('name')}")

        # 5. Messages Resource - Search & Pagination
        print("\nSearching for the 3 most recent unread messages...")
        # Using the new nested search and max_pages safety valve
        unread_messages = gmail.messages.search(query="is:unread", max_pages=1)

        for count, msg_stub in enumerate(unread_messages):
            if count >= 3:
                break

            msg_id = msg_stub.get("id")
            if not isinstance(msg_id, str):
                continue
            print(f"\n📥 Message ID: {msg_id}")

            # 6. Messages Resource - Get specific message payload
            full_msg = gmail.messages.get(message_id=msg_id)
            snippet = full_msg.get("snippet", "No snippet available.")
            print(f"   Snippet: {snippet[:75]}...")

except exceptions.HakiAPIError as e:
    print(f"\n❌ API Request failed: {e}")
