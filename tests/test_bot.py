"""GroupMe webhook -> scripted agent -> delivery, with GroupMe's HTTP API mocked (no network)."""

import io

import pytest
from django.core.management import call_command
from django.test import Client, override_settings

from agent.runner import TurnResult
from bot import groupme, services
from bot.models import Conversation, GroupChat, PrivateNotice
from trips.models import Person, Reminder
from trips.services import DjangoBackend

SECRET = "s3cret"
URL = f"/groupme/callback/{SECRET}"


class ScriptedAgent:
    """Stands in for TripAgent: records the event and history, returns a fixed outbox."""
    calls = []

    def __init__(self, backend, trip_id, history, outbox):
        self.history = list(history)
        self.outbox = outbox
        self.trip_id = trip_id

    def handle(self, event):
        ScriptedAgent.calls.append({"event": event, "history_len": len(self.history)})
        self.history += [{"role": "user", "content": event.text}, {"role": "assistant", "content": "ok"}]
        return TurnResult(outbox=self.outbox)


@pytest.fixture
def bot(db, monkeypatch, settings):
    settings.GROUPME_CALLBACK_SECRET = SECRET
    settings.BOT_DM_MODE = "store"
    DjangoBackend().load_seed({
        "trip": {"id": "miami", "name": "Miami", "leader": "aarav"},
        "members": [{"id": "aarav", "name": "Aarav", "chat_user_id": "111"},
                    {"id": "mia", "name": "Mia", "chat_user_id": "222"}],
    })
    GroupChat.objects.create(group_id="g1", bot_id="bot-1", trip_id="miami")
    posts = []
    monkeypatch.setattr(groupme.requests, "post",
                        lambda url, **kw: posts.append({"url": url, **kw}) or _Ok())
    outbox = [{"to": "group", "text": "Logged 🍽️ Dinner, $120"},
              {"to": "mia", "text": "Heads up: your food budget is almost used up."}]
    ScriptedAgent.calls = []
    monkeypatch.setattr(services, "make_agent",
                        lambda backend, trip_id, history: ScriptedAgent(backend, trip_id, history, outbox))
    return posts


class _Ok:
    status_code = 200

    def raise_for_status(self):
        pass


def callback(msg_id="m1", text="@tripbot dinner was $120", user_id="111", name="Aarav", sender_type="user",
             group_id="g1"):
    return Client().post(URL, data={"id": msg_id, "group_id": group_id, "user_id": user_id, "name": name,
                                    "text": text, "sender_type": sender_type, "attachments": []},
                         content_type="application/json")


def test_mention_runs_agent_and_keeps_dms_out_of_the_group(bot):
    r = callback()
    assert r.status_code == 200 and r.json()["outcome"] == "handled: 2 message(s)"
    event = ScriptedAgent.calls[0]["event"]
    assert (event.sender_id, event.channel, event.mentioned) == ("aarav", "group", True)
    group_texts = [p["json"]["text"] for p in bot if p["url"].endswith("/bots/post")]
    assert group_texts == ["Logged 🍽️ Dinner, $120"]
    assert all("budget" not in t for t in group_texts)
    notice = PrivateNotice.objects.get()
    assert (notice.person_id, notice.text) == ("mia", "Heads up: your food budget is almost used up.")


def test_ignores_bots_system_unmentioned_and_duplicates(bot):
    assert callback(sender_type="bot").json()["outcome"] == "ignored: not a user"
    assert callback(msg_id="m2", sender_type="system").json()["outcome"] == "ignored: not a user"
    assert callback(msg_id="m3", text="anyone up for tacos").json()["outcome"] == "ignored: not mentioned"
    assert callback(msg_id="m4", text="email me at x@tripbotland.com").json()["outcome"] == "ignored: not mentioned"
    assert callback(msg_id="m5").json()["outcome"].startswith("handled")
    assert callback(msg_id="m5").json()["outcome"] == "ignored: duplicate"
    assert callback(msg_id="m6", group_id="other").json()["outcome"] == "ignored: group not linked to a trip"
    assert len(ScriptedAgent.calls) == 1


def test_forward_all_sends_unmentioned_messages(bot, settings):
    settings.BOT_FORWARD_ALL = True
    callback(text="dinner was $120, I paid")
    assert ScriptedAgent.calls[0]["event"].mentioned is False


def test_wrong_secret_is_404(bot):
    assert Client().post("/groupme/callback/nope", data={}, content_type="application/json").status_code == 404


def test_unknown_sender_is_added_to_the_trip(bot):
    callback(user_id="333", name="Jake Lee")
    jake = Person.objects.get(trip_id="miami", chat_user_id="333")
    assert jake.name == "Jake Lee"
    assert ScriptedAgent.calls[0]["event"].sender_id == jake.person_id


def test_history_persists_between_callbacks(bot):
    callback(msg_id="a")
    callback(msg_id="b", text="@tripbot yep")
    assert [c["history_len"] for c in ScriptedAgent.calls] == [0, 2]
    assert len(Conversation.objects.get(trip_id="miami").history) == 4


def test_groupme_dm_mode_uses_direct_messages_api(bot, settings):
    settings.BOT_DM_MODE = "groupme"
    settings.GROUPME_ACCESS_TOKEN = "user-token"
    callback()
    dm = next(p for p in bot if p["url"].endswith("/direct_messages"))
    assert dm["json"]["direct_message"]["recipient_id"] == "222"
    assert dm["params"] == {"token": "user-token"}
    assert not PrivateNotice.objects.exists()


def test_agent_error_posts_apology(bot, monkeypatch):
    class Broken:
        history = []

        def handle(self, event):
            raise RuntimeError("model down")
    monkeypatch.setattr(services, "make_agent", lambda *a: Broken())
    assert callback().json()["outcome"] == "error"
    assert bot[-1]["json"]["text"] == services.ERROR_REPLY


def test_long_messages_are_split():
    parts = groupme.chunks("line\n" * 400)
    assert all(len(p) <= groupme.MAX_LEN for p in parts) and len(parts) == 2
    assert groupme.chunks("x" * 2500) == ["x" * 1000, "x" * 1000, "x" * 500]


@override_settings(BOT_DM_MODE="store")
def test_send_due_reminders(bot):
    b = DjangoBackend()
    b.create_reminder(trip_id="miami", message="Pay the Airbnb", due_at="2020-01-01T09:00", audience="all")
    b.create_reminder(trip_id="miami", message="Bring ID", due_at="2020-01-01T09:00", audience=["mia"])
    b.create_reminder(trip_id="miami", message="Later", due_at="2999-01-01T09:00", audience="all")
    out = io.StringIO()
    call_command("send_due_reminders", stdout=out)
    assert "Sent 2" in out.getvalue()
    assert [p["json"]["text"] for p in bot] == ["⏰ Reminder: Pay the Airbnb"]
    assert PrivateNotice.objects.get().text == "⏰ Reminder: Bring ID"
    assert list(Reminder.objects.filter(sent=False).values_list("message", flat=True)) == ["Later"]


def test_link_group_creates_trip(db):
    out = io.StringIO()
    call_command("link_group", "g9", "bot-9", "cancun", "--name", "Cancún", stdout=out)
    chat = GroupChat.objects.get(group_id="g9")
    assert (chat.bot_id, chat.trip.name) == ("bot-9", "Cancún")
