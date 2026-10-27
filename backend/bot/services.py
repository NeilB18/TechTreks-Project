"""GroupMe callback -> agent -> replies.

GroupMe has no DM callbacks for bots, so every incoming event is a group message.
"""

import logging
import re

from django.conf import settings
from django.db import IntegrityError, transaction

from accounts.services import find_link_command, redeem
from agent.runner import ChatEvent, TripAgent
from bot import groupme
from bot.models import Conversation, GroupChat, ProcessedMessage
from trips.models import Person
from trips.services import DjangoBackend

log = logging.getLogger(__name__)
ERROR_REPLY = "Sorry, I hit a snag handling that. Try again in a minute?"


def make_agent(backend, trip_id: str, history: list[dict]):
    """The agent for one message. Tests replace this with a scripted agent."""
    return TripAgent(backend, trip_id, history=history)


def is_mention(text: str) -> bool:
    return re.search(rf"(^|\W){re.escape(settings.BOT_MENTION)}\b", text, re.I) is not None


def handle_callback(payload: dict) -> str:
    """Process one GroupMe callback. Returns what happened (for logs and tests)."""
    if payload.get("sender_type") != "user":
        return "ignored: not a user"
    message_id = str(payload.get("id") or "")
    if not message_id:
        return "ignored: no message id"
    chat = GroupChat.objects.select_related("trip").filter(group_id=str(payload.get("group_id"))).first()
    if chat is None:
        log.warning("Callback for unlinked GroupMe group %s", payload.get("group_id"))
        return "ignored: group not linked to a trip"
    try:
        with transaction.atomic():
            ProcessedMessage.objects.create(message_id=message_id)
    except IntegrityError:
        return "ignored: duplicate"

    text = payload.get("text") or ""
    mentioned = is_mention(text)
    if not mentioned and not settings.BOT_FORWARD_ALL:
        return "ignored: not mentioned"

    trip = chat.trip
    backend = DjangoBackend()
    person = _find_or_add_person(backend, trip.id, str(payload.get("user_id")), payload.get("name") or "")
    code = find_link_command(text) if mentioned else None
    if code:
        groupme.post_to_group(chat.bot_id, redeem(code, person))
        return "linked account"
    convo, _ = Conversation.objects.get_or_create(trip=trip)
    agent = make_agent(backend, trip.id, convo.history)
    event = ChatEvent(sender_id=person.person_id, text=text, channel="group", mentioned=mentioned,
                      chat_user_id=person.chat_user_id)
    try:
        result = agent.handle(event)
    except Exception:
        log.exception("Agent failed on message %s", message_id)
        groupme.post_to_group(chat.bot_id, ERROR_REPLY)
        return "error"
    convo.history = agent.history
    convo.save(update_fields=["history", "updated_at"])
    deliver(chat, result.outbox)
    return f"handled: {len(result.outbox)} message(s)"


def _find_or_add_person(backend: DjangoBackend, trip_id: str, user_id: str, name: str) -> Person:
    person = Person.objects.filter(trip_id=trip_id, chat_user_id=user_id).first()
    if person is None:
        backend.add_member(trip_id=trip_id, chat_user_id=user_id, name=name or f"Member {user_id}")
        person = Person.objects.get(trip_id=trip_id, chat_user_id=user_id)
    return person


def deliver(chat: GroupChat, outbox: list[dict]) -> None:
    """Group messages go to the group; anything addressed to a person goes privately, never the group."""
    people = {p.person_id: p for p in Person.objects.filter(trip=chat.trip)}
    for msg in outbox:
        if msg["to"] == "group":
            groupme.post_to_group(chat.bot_id, msg["text"])
        elif msg["to"] in people:
            groupme.send_dm(chat.trip, people[msg["to"]], msg["text"])
        else:
            log.error("Dropping message to unknown recipient %r", msg["to"])
