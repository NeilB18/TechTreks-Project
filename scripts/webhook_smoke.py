"""End-to-end smoke test of the GroupMe path on live Qwen, without GroupMe.

Runs Django in this process on a throwaway SQLite database and posts GroupMe-shaped callbacks to the real
webhook. The background worker handles them as in production, history is saved between callbacks, and
private messages are stored as notices. Only GroupMe's own API is replaced: group posts are captured.

    .venv/bin/python scripts/webhook_smoke.py            # prints a transcript
"""

import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]
DB = Path(tempfile.mkdtemp()) / "smoke.sqlite3"
SECRET = "smoke-secret"
os.environ.update(DJANGO_SETTINGS_MODULE="tripapi.settings", DATABASE_URL=f"sqlite:///{DB}",
                  GROUPME_CALLBACK_SECRET=SECRET, BOT_DM_MODE="store", BOT_INLINE="0", BOT_FORWARD_ALL="0")

import django  # noqa: E402

django.setup()

from django.core.management import call_command  # noqa: E402
from django.test import Client  # noqa: E402

from bot import groupme, worker  # noqa: E402
from bot.models import Conversation, PrivateNotice  # noqa: E402
from trips.models import Person  # noqa: E402

USERS = {"aarav": "1001", "priya": "1002", "jake": "1003", "mia": "1004"}
# (who, text, wait for the reply before the next one?)
SCRIPT = [
    ("priya", "omg so excited for miami", True),
    ("aarav", "@tripbot hey! I'm organizing our Miami trip, Mar 14-18. I'll be the trip leader", True),
    ("jake", "@tripbot hi, Jake here", True),
    ("mia", "@tripbot mia here!", True),
    ("priya", "@tripbot priya here too", True),
    ("aarav", "@tripbot airbnb is booked, $1,200, I paid, split with everyone", True),
    ("mia", "@tripbot set my budget to $600 total, max $80 on food", True),
    ("aarav", "@tripbot my venmo is @aarav-v", True),
    ("aarav", "@tripbot got $200 back on the airbnb, they gave us a discount", True),
    ("aarav", "@tripbot yes", True),
    # Two at once: the worker must handle them in order and keep both in the history.
    ("jake", "@tripbot dinner was $80, I paid, split with mia and me", False),
    ("mia", "@tripbot who owes who right now?", True),
]


class Captured:
    status_code = 200

    def raise_for_status(self):
        pass


def main() -> None:
    call_command("migrate", verbosity=0)
    call_command("link_group", "g-smoke", "bot-smoke", "smoke", "--name", "Miami (smoke test)", verbosity=0)
    posts: list[str] = []
    groupme.requests.post = lambda url, **kw: posts.append(kw["json"]["text"]) or Captured()
    client = Client(HTTP_HOST="localhost")
    seen_notices = 0
    for n, (who, text, wait) in enumerate(SCRIPT, 1):
        start = time.monotonic()
        before = len(posts)
        r = client.post(f"/groupme/callback/{SECRET}", content_type="application/json", data={
            "id": f"m{n}", "group_id": "g-smoke", "user_id": USERS[who], "name": who.title(),
            "text": text, "sender_type": "user", "attachments": []})
        print(f"\n[{n}] {who.title()}: {text}\n    webhook answered {r.status_code} {r.json()['outcome']} "
              f"in {time.monotonic() - start:.2f}s")
        if not wait:
            continue
        for q in list(worker._queues.values()):
            q.join()
        print(f"    (replies after {time.monotonic() - start:.0f}s)")
        for text_out in posts[before:]:
            print("    tripbot → group: " + text_out.replace("\n", "\n        "))
        notices = list(PrivateNotice.objects.filter(trip_id="smoke").order_by("created_at"))
        for notice in notices[seen_notices:]:
            print(f"    tripbot → private to {notice.person_id}: " + notice.text.replace("\n", "\n        "))
        seen_notices = len(notices)
    history = Conversation.objects.get(trip_id="smoke").history
    events = sum(1 for m in history if m["role"] == "user" and "<event>" in m["content"])
    print(f"\nMembers: {sorted(Person.objects.filter(trip_id='smoke').values_list('person_id', flat=True))}")
    print(f"History: {len(history)} messages, {events} chat turns, "
          f"{sum('<trip_state>' in m['content'] for m in history if m['role'] == 'user')} with trip state")


if __name__ == "__main__":
    main()
