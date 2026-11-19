"""Add a trip from the site: GroupMe makes the group and the bot with the person's one-time token, and we
make the trip with them as its linked leader (backend/accounts/new_trip.py). GroupMe's API is faked."""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from accounts import new_trip
from bot import groupme
from bot.models import GroupChat
from trips.models import Person, Trip

TOKEN = "gm-token-123"


class _Resp:
    def __init__(self, status, body=None):
        self.status_code, self._body = status, body or {}

    def json(self):
        return self._body

    def raise_for_status(self):
        pass


@pytest.fixture
def gm(db, settings, monkeypatch):
    """Fake GroupMe. Records every call; `fail` makes one path answer 500."""
    settings.GROUPME_CLIENT_ID = "client-abc"
    settings.BACKEND_PUBLIC_URL = "https://bot.example"
    settings.GROUPME_CALLBACK_SECRET = "s3cret"
    settings.FRONTEND_URL = "https://site.example"
    state = {"calls": [], "posts": [], "fail": None}

    def request(method, url, json=None, headers=None, timeout=None):
        path = url.removeprefix(groupme.API)
        state["calls"].append((method, path, json, headers))
        if state["fail"] == path:
            return _Resp(500)
        return _Resp(200, {"response": {
            "/users/me": {"id": "9001", "name": "Romir Basu"},
            "/groups": {"id": "777", "share_url": "https://groupme.com/join_group/777/abc"},
            # The real API wraps the new bot (the docs don't show this): {"response": {"bot": {...}}}.
            "/bots": {"bot": {"bot_id": "bot-777", "group_id": "777", "name": "tripbot"}},
        }.get(path, {})})

    monkeypatch.setattr(new_trip.requests, "request", request)
    monkeypatch.setattr(groupme.requests, "post", lambda url, **kw: state["posts"].append(kw["json"]) or _Resp(200))
    return state


def signed_in():
    user = get_user_model().objects.create_user(username="romir", email="romir@example.com")
    client = Client()
    client.force_login(user)
    return client, user


def start(client, name="Cabo Spring Break"):
    return client.post("/api/me/new-trip", {"name": name}, content_type="application/json")


def test_add_a_trip_makes_the_group_the_bot_and_the_trip(gm):
    client, user = signed_in()
    r = start(client)
    assert r.status_code == 200 and r.json()["authorize_url"] == "https://oauth.groupme.com/oauth/authorize?client_id=client-abc"

    back = client.get(f"/accounts/groupme/callback?access_token={TOKEN}")
    trip = Trip.objects.get(name="Cabo Spring Break")
    assert back.status_code == 302 and back["Location"] == f"https://site.example/t/{trip.share_token}?new=1"

    # The group has a share link, and the bot calls this backend back with the secret.
    calls = {(m, p): body for m, p, body, _ in gm["calls"]}
    assert calls[("POST", "/groups")]["share"] is True and calls[("POST", "/groups")]["name"] == "Cabo Spring Break"
    assert calls[("POST", "/bots")]["bot"] == {"name": "tripbot", "group_id": "777",
                                               "callback_url": "https://bot.example/groupme/callback/s3cret"}
    # The token only ever travels in a header.
    assert all(h == {"X-Access-Token": TOKEN} and TOKEN not in p for _, p, _, h in gm["calls"])

    chat = GroupChat.objects.get(trip=trip)
    assert (chat.group_id, chat.bot_id, chat.join_url) == ("777", "bot-777", "https://groupme.com/join_group/777/abc")
    me = Person.objects.get(trip=trip)
    assert (me.name, me.chat_user_id, me.user, trip.leader_id) == ("Romir Basu", "9001", user, me.person_id)
    assert len(gm["posts"]) == 1 and trip.share_token in gm["posts"][0]["text"]  # the bot says hi

    # The trip shows up as yours, with the invite link.
    mine = client.get(f"/api/me/trips/{trip.id}").json()
    assert mine["group_join_url"] == "https://groupme.com/join_group/777/abc"
    assert mine["detail"]["trip"]["leader_id"] == me.person_id


def test_needs_sign_in_a_name_and_the_groupme_app(gm, settings):
    assert start(Client()).status_code == 401
    client, _ = signed_in()
    assert start(client, name="   ").status_code == 400
    assert start(client, name="x" * 61).status_code == 400
    settings.GROUPME_CLIENT_ID = ""
    assert start(client).status_code == 503


def test_callback_only_finishes_a_flow_you_started(gm):
    client, _ = signed_in()
    # No Add a trip started in this session: someone else's link with their token does nothing.
    r = client.get(f"/accounts/groupme/callback?access_token={TOKEN}")
    assert r["Location"] == "https://site.example/new?error=expired" and not gm["calls"]
    # Signed out.
    assert Client().get(f"/accounts/groupme/callback?access_token={TOKEN}")["Location"].endswith("error=signin")
    # Started, but they said no on GroupMe (no token): and it can't be finished later either.
    start(client)
    assert client.get("/accounts/groupme/callback")["Location"].endswith("error=cancelled")
    assert client.get(f"/accounts/groupme/callback?access_token={TOKEN}")["Location"].endswith("error=expired")
    assert not Trip.objects.exists()


def test_a_failed_bot_removes_the_group_and_saves_nothing(gm):
    client, _ = signed_in()
    start(client)
    gm["fail"] = "/bots"
    r = client.get(f"/accounts/groupme/callback?access_token={TOKEN}")
    assert r["Location"] == "https://site.example/new?error=groupme"
    assert ("POST", "/groups/777/destroy") in {(m, p) for m, p, _, _ in gm["calls"]}
    assert not Trip.objects.exists() and not GroupChat.objects.exists()


def test_the_bot_reply_works_in_either_shape(gm, monkeypatch):
    """The docs show the bot's fields directly; the API wraps them in "bot". Both make the trip."""
    real = new_trip._call
    monkeypatch.setattr(new_trip, "_call", lambda m, p, tok, body=None: {"bot_id": "bot-flat"} if p == "/bots" else real(m, p, tok, body))
    client, _ = signed_in()
    start(client)
    client.get(f"/accounts/groupme/callback?access_token={TOKEN}")
    assert GroupChat.objects.get().bot_id == "bot-flat"


def test_an_unexpected_error_goes_back_to_the_form_and_removes_the_group(gm, monkeypatch):
    def boom(*a, **kw):
        raise RuntimeError("database fell over")
    monkeypatch.setattr(new_trip.DjangoBackend, "add_member", boom)
    client, _ = signed_in()
    start(client)
    r = client.get(f"/accounts/groupme/callback?access_token={TOKEN}")
    assert r.status_code == 302 and r["Location"] == "https://site.example/new?error=groupme"  # not a bare 500
    assert ("POST", "/groups/777/destroy") in {(m, p) for m, p, _, _ in gm["calls"]}
    assert not Trip.objects.exists() and not GroupChat.objects.exists() and not gm["posts"]


def test_error_pages_have_the_site_look():
    from django.template.loader import render_to_string

    for page, words in (("500.html", "Something went wrong"), ("404.html", "Nothing here")):
        html = render_to_string(page)  # Django renders these with no request context
        assert words in html and "travelbot" in html and "<style>" in html and "Menu:" not in html


def test_access_tokens_never_reach_the_logs(caplog):
    """GroupMe puts the token in the callback's address; the request log must not print it."""
    import logging

    with caplog.at_level(logging.INFO, logger="django.server"):
        logging.getLogger("django.server").info('"%s" %s %s', f"GET /accounts/groupme/callback?access_token={TOKEN}&x=1 HTTP/1.1", "302", "0")
    with caplog.at_level(logging.INFO, logger="accounts"):
        logging.getLogger("accounts").warning("Add a trip failed for /cb?ACCESS_TOKEN=%s", TOKEN)
    assert TOKEN not in caplog.text
    assert "access_token=[hidden]&x=1" in caplog.text and "ACCESS_TOKEN=[hidden]" in caplog.text
