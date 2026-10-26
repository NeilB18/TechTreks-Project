"""Tool schemas match the backend contract and stick to schema keywords Qwen documents."""

import inspect
import json

from agent.backend.fake.store import FakeBackend
from agent.backend.protocol import BACKEND_TOOLS
from agent.tools.schemas import ALL_TOOLS, BACKEND_TOOL_SCHEMAS


def test_one_schema_per_backend_tool():
    names = [t["function"]["name"] for t in BACKEND_TOOL_SCHEMAS]
    assert len(names) == len(set(names)) == 21
    assert set(names) == set(BACKEND_TOOLS)
    assert ALL_TOOLS[-1]["function"]["name"] == "send_message"
    assert all(t["type"] == "function" for t in ALL_TOOLS)


def test_schema_params_match_fake_backend():
    for tool in BACKEND_TOOL_SCHEMAS:
        fn_schema = tool["function"]
        fn = getattr(FakeBackend, fn_schema["name"])
        params = inspect.signature(fn).parameters
        props = fn_schema["parameters"]["properties"]
        if any(p.kind is p.VAR_KEYWORD for p in params.values()):
            continue  # convert_currency takes "from" via **kw
        assert set(props) == set(params) - {"self"}, fn_schema["name"]
        required = {n for n, p in params.items() if n != "self" and p.default is p.empty}
        assert set(fn_schema["parameters"]["required"]) == required, fn_schema["name"]


def test_no_undocumented_schema_keywords():
    text = json.dumps(ALL_TOOLS)
    for kw in ("anyOf", "oneOf", "allOf", "exclusiveMinimum", "$ref"):
        assert kw not in text, kw
