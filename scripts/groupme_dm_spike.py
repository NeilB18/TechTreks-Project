"""Check whether we can send private budget messages through GroupMe.

GroupMe bots can only post in their group. Private messages have to go through
the direct-messages API with a *user* access token, so they appear to come from
that user account (e.g. a dedicated "tripbot" GroupMe account), not the bot.

Run it with the token of the account that would send DMs (dev.groupme.com ->
"Access Token" at the top right), and the GroupMe user id of a teammate who
agreed to get a test DM:

    GROUPME_ACCESS_TOKEN=... .venv/bin/python scripts/groupme_dm_spike.py <recipient_user_id>

Then tell Romir: did the DM arrive, and who did it look like it came from?
"""

import os
import sys
import uuid

import requests

API = "https://api.groupme.com/v3"


def main() -> None:
    token = os.environ.get("GROUPME_ACCESS_TOKEN")
    if not token or len(sys.argv) != 2:
        sys.exit(__doc__)
    recipient = sys.argv[1]
    me = requests.get(f"{API}/users/me", params={"token": token}, timeout=15)
    me.raise_for_status()
    sender = me.json()["response"]
    print(f"Sending as GroupMe user {sender['name']} (id {sender['id']})")
    resp = requests.post(
        f"{API}/direct_messages", params={"token": token}, timeout=15,
        json={"direct_message": {"source_guid": str(uuid.uuid4()), "recipient_id": recipient,
                                 "text": "tripbot DM test: budget messages would arrive here privately."}})
    print(f"HTTP {resp.status_code}: {resp.text[:300]}")
    if resp.ok:
        print("Sent. Check the recipient's GroupMe DMs. If it arrived, set BOT_DM_MODE=groupme.")
    else:
        print("Failed. Keep BOT_DM_MODE=store (private notices on the trip page).")


if __name__ == "__main__":
    main()
