import json
import sys
from pathlib import Path

import pytest
from django.conf import settings as django_settings

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Whatever the API checks: the dev default, or the real token when .env sets AGENT_API_TOKEN
AGENT_TOKEN = django_settings.AGENT_API_TOKEN


@pytest.fixture(autouse=True)
def _bot_inline(settings):
    """Webhook tests check the outcome in the response, so the agent runs inside the request."""
    settings.BOT_INLINE = True


def pytest_addoption(parser):
    parser.addoption("--repeat", type=int, default=1,
                     help="Run each live scenario N times to catch flaky behavior")


class DjangoClientSession:
    """Lets HttpBackend talk to Django's test client instead of a real server."""

    def __init__(self, client):
        self.client = client

    def post(self, url, json=None, headers=None, timeout=None):
        return self.client.post(url.removeprefix("http://testserver"), data=_dumps(json),
                                content_type="application/json", headers=headers)

    def get(self, url, headers=None, timeout=None):
        return self.client.get(url.removeprefix("http://testserver"), headers=headers)


def _dumps(obj):
    return json.dumps(obj)


def make_backend(kind: str):
    """'memory' | 'django' | 'http'. Callers must have the pytest-django `db` fixture active."""
    from agent.backend.core.engine import TripEngine
    if kind == "memory":
        return TripEngine()
    from trips.services import DjangoBackend
    if kind == "django":
        return DjangoBackend()
    from django.test import Client

    from agent.backend.http import HttpBackend
    http = HttpBackend("http://testserver", token=AGENT_TOKEN, session=DjangoClientSession(Client()))
    http.state = DjangoBackend()
    return http


@pytest.fixture(params=["memory", "django", "http"])
def any_backend(request, db):
    return make_backend(request.param)


@pytest.fixture(autouse=True)
def no_live_travel(monkeypatch):
    """Tests never call Google Places or SerpAPI, even if keys are in .env."""
    monkeypatch.delenv("GOOGLE_PLACES_API_KEY", raising=False)
    monkeypatch.delenv("SERPAPI_KEY", raising=False)
