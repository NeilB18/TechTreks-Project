"""Sending messages to GroupMe.

Group posts go through the bot API (https://dev.groupme.com/docs/v3#bots_post).
GroupMe bots can't send DMs, so private messages either go through the
direct-messages API with a user access token (BOT_DM_MODE=groupme; they come
from that account, e.g. a dedicated "tripbot" user), or are stored as
PrivateNotice rows for the trip page (BOT_DM_MODE=store, the default until the
DM spike confirms the first option works).
"""

import logging
import uuid

import requests
from django.conf import settings

from bot.models import PrivateNotice

log = logging.getLogger(__name__)
API = "https://api.groupme.com/v3"
MAX_LEN = 1000  # GroupMe's message length limit


def chunks(text: str, size: int = MAX_LEN) -> list[str]:
    """Split on line breaks where possible so long replies stay readable."""
    out, current = [], ""
    for line in text.splitlines(keepends=True):
        while len(line) > size:
            if current:
                out.append(current)
                current = ""
            out.append(line[:size])
            line = line[size:]
        if len(current) + len(line) > size:
            out.append(current)
            current = ""
        current += line
    if current:
        out.append(current)
    return [c.rstrip("\n") for c in out if c.strip()]


def post_to_group(bot_id: str, text: str) -> None:
    for part in chunks(text):
        resp = requests.post(f"{API}/bots/post", json={"bot_id": bot_id, "text": part}, timeout=15)
        resp.raise_for_status()


def send_dm(trip, person, text: str) -> str:
    """Deliver a private message. Returns "groupme" or "stored"."""
    if settings.BOT_DM_MODE == "groupme" and settings.GROUPME_ACCESS_TOKEN:
        for part in chunks(text):
            resp = requests.post(
                f"{API}/direct_messages", params={"token": settings.GROUPME_ACCESS_TOKEN},
                json={"direct_message": {"source_guid": str(uuid.uuid4()),
                                         "recipient_id": person.chat_user_id, "text": part}},
                timeout=15)
            resp.raise_for_status()
        return "groupme"
    PrivateNotice.objects.create(trip=trip, person_id=person.person_id, text=text)
    log.info("Stored private notice for %s on trip %s", person.person_id, trip.id)
    return "stored"
