"""
Example usage of the HakiAPI Gmail Client.
"""

import os
import sys

# Import the client directly from the top-level facade
from hakiapi import GmailClient, exceptions

# Fetch the token from the OS environment securely
token = os.environ.get("GMAIL_OAUTH_TOKEN")

if not token:
    print("Error: GMAIL_OAUTH_TOKEN environment variable not found in the OS.")
    print("Please run: export GMAIL_OAUTH_TOKEN='your_token_here'")
    sys.exit(1)

# Initialize the client
client = GmailClient(token=token)

try:
    # Fetch the user's profile
    print("Authenticating with Google...")
    profile = client.get_profile()
    print(f"Success! Connected as: {profile.get('emailAddress')}")

    # Fetch the 3 most recent messages using your memory-safe generator
    print("\nFetching recent messages...")
    messages = client.get_all_messages()

    for count, msg in enumerate(messages):
        if count >= 3:
            break
        print(f"- Found Message ID: {msg.get('id')}")

except exceptions.HakiAPIError as e:
    print(f"API Request failed: {e}")
