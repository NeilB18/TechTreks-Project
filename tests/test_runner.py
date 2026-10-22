"""The runner's tool loop, with a scripted stand-in for the Qwen client (no API calls)."""

import json
from types import SimpleNamespace as NS

from agent.runner import ChatEvent, TripAgent
from agent.scenarios import load_scenarios, make_backend


def tool_call(id, name, args):
    return NS(id=id, type="function",
              function=NS(name=name, arguments=args if isinstance(args, str) else json.dumps(args)))


def response(finish_reason, content=None, *tool_calls):
    msg = NS(content=content, tool_calls=list(tool_calls) or None)
    return NS(choices=[NS(message=msg, finish_reason=finish_reason)],
              usage=NS(model_dump=lambda: {"prompt_tokens": 1, "completion_tokens": 1}))


class ScriptedClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []
        self.chat = NS(completions=NS(create=self.create))

    def create(self, **kw):
        self.requests.append({**kw, "messages": list(kw["messages"])})
        return self.responses.pop(0)


def test_tool_loop_runs_tools_and_delivers_messages():
    scn = next(s for s in load_scenarios() if s["example"] == "4a")
    backend = make_backend(scn)
    client = ScriptedClient([
        response("tool_calls", "Logging it.",
                 tool_call("t1", "log_expense", {
                     "trip_id": "miami", "paid_by": "mia", "amount": 12000, "currency": "USD",
                     "description": "Dinner", "category": "FOOD", "split_with": ["aarav", "mia"]}),
                 tool_call("t2", "send_message", {"to": "nobody", "text": "hi"}),
                 tool_call("t3", "get_balances", "{not json")),
        response("tool_calls", None,
                 tool_call("t4", "send_message", {"to": "group", "text": "Logged $60 each"})),
        response("stop", ""),
    ])
    agent = TripAgent(backend, "miami", client=client)
    r = agent.handle(ChatEvent(sender_id="mia", text="@tripbot dinner $120 split with everyone except Jake"))

    assert [c.name for c in r.tool_calls] == ["log_expense", "send_message", "get_balances", "send_message"]
    assert r.tool_calls[1].error  # bad recipient goes back to the model as an error
    assert "Invalid JSON" in r.tool_calls[2].error
    assert r.outbox == [{"to": "group", "text": "Logged $60 each"}]
    assert r.stray_text == ["Logging it."]
    assert len(backend.trips["miami"].expenses) == 1

    first = client.requests[0]
    assert first["model"] == "qwen3.8-flash"
    assert first["extra_body"] == {"enable_thinking": True}
    assert first["tool_choice"] == "auto"  # thinking mode rejects "required"/object
    assert first["messages"][0]["role"] == "system"
    assert "<trip_state>" in first["messages"][1]["content"]
    second = client.requests[1]["messages"]
    assert second[2]["tool_calls"][0]["id"] == "t1"
    assert [m["tool_call_id"] for m in second[3:6]] == ["t1", "t2", "t3"]
    assert second[4]["content"].startswith("Error:")


def test_history_carries_across_turns():
    scn = next(s for s in load_scenarios() if s["example"] == "9")
    client = ScriptedClient([response("stop", ""), response("stop", "")])
    agent = TripAgent(make_backend(scn), "miami", client=client)
    agent.handle(ChatEvent(sender_id="aarav", text="@tripbot got $150 back"))
    before = list(agent.history)
    agent.handle(ChatEvent(sender_id="aarav", text="@tripbot yep"))
    assert agent.history[:len(before)] == before
    assert len(client.requests[1]["messages"]) == 4  # system + user + assistant + user


def test_undelivered_text_gets_one_reminder():
    scn = next(s for s in load_scenarios() if s["example"] == "4a")
    client = ScriptedClient([
        response("stop", "Logged! $60 each."),
        response("tool_calls", None, tool_call("t1", "send_message", {"to": "group", "text": "Logged! $60 each."})),
        response("stop", "done"),
    ])
    agent = TripAgent(make_backend(scn), "miami", client=client)
    r = agent.handle(ChatEvent(sender_id="mia", text="@tripbot dinner"))
    assert r.outbox == [{"to": "group", "text": "Logged! $60 each."}]
    assert len(client.requests) == 3  # reminded once, never twice
    assert client.requests[1]["messages"][-1]["content"].startswith("[runner]")
