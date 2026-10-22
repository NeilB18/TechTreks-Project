import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

AGENT_TOKEN = "dev-agent-token"  # tripapi.settings default when DJANGO_DEBUG=1


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
    """'fake' | 'django' | 'http'. Callers must have the pytest-django `db` fixture active."""
    from agent.backend.fake.store import FakeBackend
    if kind == "fake":
        return FakeBackend()
    from trips.services import DjangoBackend
    if kind == "django":
        return DjangoBackend(seed=7)
    from django.test import Client

    from agent.backend.http import HttpBackend
    http = HttpBackend("http://testserver", token=AGENT_TOKEN, session=DjangoClientSession(Client()))
    http.state = DjangoBackend(seed=7)
    return http


@pytest.fixture(params=["fake", "django", "http"])
def any_backend(request, db):
    return make_backend(request.param)
