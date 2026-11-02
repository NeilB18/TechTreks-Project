"""GroupMe webhook -> scripted agent -> delivery, with GroupMe's HTTP API mocked (no network)."""

import io

import pytest
from django.core.management import call_command
from django.test import Client

from agent.runner import TurnResult
from bot import groupme, services, worker
from bot.models import Conversation, GroupChat
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
              {"to": "group", "text": "@Mia heads up: your food budget is almost used up."}]
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


def test_mention_runs_agent_and_posts_every_reply_in_the_group(bot):
    r = callback()
    assert r.status_code == 200 and r.json()["outcome"] == "handled: 2 message(s)"
    event = ScriptedAgent.calls[0]["event"]
    assert (event.sender_id, event.mentioned) == ("aarav", True)
    group_texts = [p["json"]["text"] for p in bot if p["url"].endswith("/bots/post")]
    assert group_texts == ["Logged 🍽️ Dinner, $120", "@Mia heads up: your food budget is almost used up."]


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
    assert ScriptedAgent.calls[0]["event"].chat_user_id == "333"  # lets people save their own payment handle


def test_history_persists_between_callbacks(bot):
    callback(msg_id="a")
    callback(msg_id="b", text="@tripbot yep")
    assert [c["history_len"] for c in ScriptedAgent.calls] == [0, 2]
    assert len(Conversation.objects.get(trip_id="miami").history) == 4


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


def test_send_due_reminders(bot):
    b = DjangoBackend()
    b.create_reminder(trip_id="miami", message="Pay the Airbnb", due_at="2020-01-01T09:00", audience="all")
    b.create_reminder(trip_id="miami", message="Bring ID", due_at="2020-01-01T09:00", audience=["mia"])
    b.create_reminder(trip_id="miami", message="Later", due_at="2999-01-01T09:00", audience="all")
    out = io.StringIO()
    call_command("send_due_reminders", stdout=out)
    assert "Sent 2" in out.getvalue()
    assert [p["json"]["text"] for p in bot] == ["⏰ Reminder: Pay the Airbnb", "⏰ Reminder for @Mia: Bring ID"]
    assert list(Reminder.objects.filter(sent=False).values_list("message", flat=True)) == ["Later"]


def test_link_group_creates_trip(db):
    out = io.StringIO()
    call_command("link_group", "g9", "bot-9", "cancun", "--name", "Cancún", stdout=out)
    chat = GroupChat.objects.get(group_id="g9")
    assert (chat.bot_id, chat.trip.name) == ("bot-9", "Cancún")


def test_webhook_queues_and_answers_at_once(bot, settings, monkeypatch):
    settings.BOT_INLINE = False
    queued = []
    monkeypatch.setattr(worker, "enqueue", queued.append)
    assert callback().json()["outcome"] == "queued"
    assert queued[0]["id"] == "m1" and not ScriptedAgent.calls


def test_worker_keeps_order_within_a_group_and_runs_groups_side_by_side(monkeypatch):
    import threading
    import time
    seen, started = [], {}
    release = threading.Event()

    def handle(payload):
        started[payload["id"]] = time.monotonic()
        if payload["id"] == "a1":
            release.wait(2)  # group a is busy; group b must not wait for it
        seen.append(payload["id"])
        return "handled"
    monkeypatch.setattr(worker, "handle_callback", handle)
    monkeypatch.setattr(worker, "_queues", {})
    for msg in [("a1", "ga"), ("a2", "ga"), ("b1", "gb")]:
        worker.enqueue({"id": msg[0], "group_id": msg[1]})
    deadline = time.monotonic() + 2
    while "b1" not in seen and time.monotonic() < deadline:
        time.sleep(0.01)
    assert "b1" in seen and "a2" not in seen  # b ran while a1 was still going; a2 waits its turn
    release.set()
    for q in worker._queues.values():
        q.join()
    assert seen.index("a1") < seen.index("a2")


def test_model_outage_gets_one_retry_before_the_apology(bot, monkeypatch, settings):
    import httpx2 as httpx
    from openai import APIConnectionError
    settings.BOT_INLINE = False  # the retry only waits in the background worker
    monkeypatch.setattr(services, "RETRY_AFTER_S", 0)
    attempts = []

    class Flaky:
        def __init__(self, history):
            self.history = list(history)

        def handle(self, event):
            attempts.append(len(self.history))
            if len(attempts) == 1:
                self.history.append({"role": "user", "content": "half a turn"})
                raise APIConnectionError(request=httpx.Request("POST", "https://qwen.example"))
            self.history += [{"role": "user", "content": event.text}]
            return TurnResult(outbox=[{"to": "group", "text": "Logged"}])
    monkeypatch.setattr(services, "make_agent", lambda backend, trip_id, history: Flaky(history))
    payload = {"id": "r1", "group_id": "g1", "user_id": "111", "name": "Aarav",
               "text": "@tripbot dinner $120", "sender_type": "user"}
    assert services.handle_callback(payload) == "handled: 1 message(s)"
    assert attempts == [0, 0]  # the retry starts from the saved history, not the failed half turn
    assert [p["json"]["text"] for p in bot] == ["Logged"]


def test_the_agent_gets_the_groups_local_time(bot, settings):
    settings.BOT_TIME_ZONE = "America/New_York"
    callback()
    event = ScriptedAgent.calls[0]["event"]
    from datetime import datetime
    from zoneinfo import ZoneInfo
    local = datetime.now(ZoneInfo("America/New_York")).replace(tzinfo=None)
    assert abs((datetime.fromisoformat(event.time) - local).total_seconds()) < 120


def test_reminders_use_local_time_and_one_failure_doesnt_block_the_rest(bot, monkeypatch):
    from bot.management.commands import send_due_reminders
    monkeypatch.setattr(send_due_reminders, "local_now", lambda: "2027-03-14T09:00")
    b = DjangoBackend()
    b.create_reminder(trip_id="miami", message="Boat at 9", due_at="2027-03-14T09:00", audience="all")
    b.create_reminder(trip_id="miami", message="Dinner at 9:30", due_at="2027-03-14T09:30", audience="all")
    b.create_reminder(trip_id="miami", message="Bring ID", due_at="2027-03-14T08:00", audience=["mia"])
    real_post = groupme.requests.post
    monkeypatch.setattr(groupme.requests, "post", lambda url, **kw: (_ for _ in ()).throw(RuntimeError("GroupMe down")))
    out = io.StringIO()
    call_command("send_due_reminders", stdout=out)
    assert "Sent 0" in out.getvalue()  # GroupMe was down, so both due reminders wait for the next run
    monkeypatch.setattr(groupme.requests, "post", real_post)
    call_command("send_due_reminders", stdout=out)
    # Retried; 9:30 isn't due yet.
    assert sorted(p["json"]["text"] for p in bot) == ["⏰ Reminder for @Mia: Bring ID", "⏰ Reminder: Boat at 9"]
