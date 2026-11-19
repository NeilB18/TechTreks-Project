"""Add a trip from the site: a new GroupMe group with @tripbot in it, and a trip it talks to.

The flow (views.new_trip, then views.groupme_connected):
1. A signed-in person types the trip's name. We remember it in their session and send them to
   GroupMe to let TravelBot act for them once (GroupMe's OAuth: oauth.groupme.com/oauth/authorize).
2. GroupMe sends them back with an access token. With it we read who they are, make the group
   (with a share link, so friends can join), and add the bot to it, pointing at this backend.
3. We make the trip, link the group and bot to it, and add them as its first member and leader,
   linked to their sign-in. The bot says hi in the group.

The token is only used for those few calls and is never saved (team decision, Oct 29, 2026).
"""

import logging
import re
import secrets

import requests
from django.conf import settings
from django.db import transaction

from bot import groupme
from bot.models import GroupChat
from trips.models import Person, Trip
from trips.services import DjangoBackend

log = logging.getLogger(__name__)

AUTHORIZE_URL = "https://oauth.groupme.com/oauth/authorize"
MAX_NAME = 60


class GroupMeError(Exception):
    """GroupMe said no, or couldn't be reached. Nothing on our side was saved."""


def clean_name(name) -> str | None:
    if not isinstance(name, str):
        return None
    name = " ".join(name.split())
    return name if 0 < len(name) <= MAX_NAME else None


def authorize_url() -> str | None:
    """Where to send the person to let TravelBot make the group. None if the GroupMe app isn't set up."""
    if not settings.GROUPME_CLIENT_ID:
        return None
    return f"{AUTHORIZE_URL}?client_id={settings.GROUPME_CLIENT_ID}"


def bot_callback_url() -> str | None:
    if not (settings.BACKEND_PUBLIC_URL and settings.GROUPME_CALLBACK_SECRET):
        return None
    return f"{settings.BACKEND_PUBLIC_URL}/groupme/callback/{settings.GROUPME_CALLBACK_SECRET}"


def _call(method: str, path: str, token: str, body: dict | None = None) -> dict:
    """One GroupMe API call with the person's token (in a header, never the URL)."""
    try:
        resp = requests.request(method, f"{groupme.API}{path}", json=body, timeout=15,
                                headers={"X-Access-Token": token})
    except requests.RequestException as e:
        raise GroupMeError(f"couldn't reach GroupMe ({type(e).__name__})") from None
    if resp.status_code >= 400:
        raise GroupMeError(f"GroupMe {method} {path} -> {resp.status_code}")
    return (resp.json() or {}).get("response") or {}


def _trip_id(name: str) -> str:
    """Readable and unique: "cabo-spring-break-3f9a1c"."""
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "trip"
    while True:
        trip_id = f"{base}-{secrets.token_hex(3)}"
        if not Trip.objects.filter(id=trip_id).exists():
            return trip_id


def create_trip_with_group(user, name: str, token: str) -> Trip:
    """Make the GroupMe group and its bot with the person's token, then the trip. Returns the trip."""
    callback = bot_callback_url()
    if callback is None:
        raise GroupMeError("BACKEND_PUBLIC_URL or GROUPME_CALLBACK_SECRET isn't set")
    me = _call("GET", "/users/me", token)
    group = _call("POST", "/groups", token, {
        "name": name, "share": True,
        "description": f"Planned with {settings.BOT_MENTION}: the plan, who paid, and who owes who."})
    try:
        bot = _call("POST", "/bots", token, {"bot": {
            "name": settings.BOT_MENTION.lstrip("@"), "group_id": str(group["id"]), "callback_url": callback}})
    except GroupMeError:
        # Don't leave an empty group behind that nobody asked for.
        try:
            _call("POST", f"/groups/{group['id']}/destroy", token)
        except GroupMeError:
            log.warning("Couldn't remove GroupMe group %s after the bot failed", group.get("id"))
        raise

    with transaction.atomic():
        trip = Trip.objects.create(id=_trip_id(name), name=name)
        GroupChat.objects.create(group_id=str(group["id"]), bot_id=str(bot["bot_id"]), trip=trip,
                                 join_url=group.get("share_url") or "")
        person_id = DjangoBackend().add_member(trip_id=trip.id, chat_user_id=str(me["id"]),
                                               name=me.get("name") or "Trip leader")["person_id"]
        Person.objects.filter(trip=trip, person_id=person_id).update(user=user)
        Trip.objects.filter(id=trip.id).update(leader_id=person_id)
    trip.refresh_from_db()

    page = f"{settings.FRONTEND_URL}/t/{trip.share_token}"
    try:
        groupme.post_to_group(str(bot["bot_id"]), (
            f"Hi! I'm {settings.BOT_MENTION}. Tell me what you spend (\"{settings.BOT_MENTION} I paid $60 for "
            f"dinner\") and I'll split it, keep the plan, and watch budgets. Everyone's added the first time they "
            f"{settings.BOT_MENTION}. Trip page: {page}"))
    except requests.RequestException:
        log.warning("Couldn't post the welcome message for trip %s", trip.id)
    return trip
