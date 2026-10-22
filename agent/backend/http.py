"""HttpBackend: the Backend protocol over the Django API (backend/trips/views.py).

    backend = HttpBackend("http://localhost:8000", token=os.environ["AGENT_API_TOKEN"])

The server validates arguments and returns 400 {"error": ...} for a ToolError,
which is re-raised here so the runner treats both backends the same.
"""

import requests

from agent.backend.protocol import BACKEND_TOOLS, ToolError


class HttpBackend:
    def __init__(self, base_url: str, token: str, session=None, timeout: float = 30):
        self.base_url = base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {token}"}
        self.session = session or requests.Session()
        self.timeout = timeout
        self.state = None  # tests may attach a DjangoBackend here for the scenario checker

    def _handle(self, resp) -> dict:
        data = resp.json()
        if resp.status_code == 200:
            return data
        if resp.status_code in (400, 404):
            raise ToolError(data.get("error", f"HTTP {resp.status_code}"))
        raise RuntimeError(f"Backend error {resp.status_code}: {data}")

    def call(self, name: str, args: dict) -> dict:
        resp = self.session.post(f"{self.base_url}/api/tools/{name}", json=args,
                                 headers=self.headers, timeout=self.timeout)
        return self._handle(resp)

    def summary(self, trip_id: str) -> dict:
        resp = self.session.get(f"{self.base_url}/api/trips/{trip_id}/summary",
                                headers=self.headers, timeout=self.timeout)
        return self._handle(resp)


def _tool(name: str):
    def method(self, **kwargs):  # the server checks the arguments
        return self.call(name, kwargs)
    method.__name__ = name
    return method


for _name in BACKEND_TOOLS:
    setattr(HttpBackend, _name, _tool(_name))
