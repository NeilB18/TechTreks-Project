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
    scn = next(s for s in load_scenarios() if s.get("example") == "4a")
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

    model_calls = [c for c in r.tool_calls if not c.by_runner]  # the runner also checks budgets after log_expense
    assert [c.name for c in model_calls] == ["log_expense", "send_message", "get_balances", "send_message"]
    assert model_calls[1].error  # bad recipient goes back to the model as an error
    assert "Invalid JSON" in model_calls[2].error
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
    scn = next(s for s in load_scenarios() if s.get("example") == "9")
    client = ScriptedClient([response("stop", ""), response("stop", "")])
    agent = TripAgent(make_backend(scn), "miami", client=client)
    agent.handle(ChatEvent(sender_id="aarav", text="@tripbot got $150 back"))
    before = list(agent.history)
    agent.handle(ChatEvent(sender_id="aarav", text="@tripbot yep"))
    assert agent.history[1:len(before)] == before[1:]
    sent = client.requests[1]["messages"]
    assert len(sent) == 4  # system + user + assistant + user
    # Only the newest message carries the trip state; the earlier one keeps just its event.
    assert sent[1]["content"].startswith("<event>") and "$150 back" in sent[1]["content"]
    assert sent[3]["content"].startswith("<trip_state>")


def test_history_keeps_only_the_last_turns(monkeypatch):
    from agent import config
    monkeypatch.setattr(config, "HISTORY_TURNS", 3)
    client = ScriptedClient([response("stop", "") for _ in range(5)])
    agent = TripAgent(engine(), "miami", client=client)
    for n in range(5):
        agent.handle(ChatEvent(sender_id="jake", text=f"@tripbot message {n}"))
    events = [m["content"] for m in agent.history if m["role"] == "user"]
    assert len(events) == 3 and "message 2" in events[0] and "message 4" in events[-1]
    assert sum("<trip_state>" in e for e in events) == 1


def test_undelivered_text_gets_one_reminder():
    scn = next(s for s in load_scenarios() if s.get("example") == "4a")
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


DINNER_TRIP = {
    "trip": {"id": "miami", "name": "Miami", "base_currency": "USD", "leader": "aarav"},
    "members": [{"id": "aarav", "name": "Aarav", "handle": "@aarav-venmo"},
                {"id": "jake", "name": "Jake", "handle": "@jake-venmo"},
                {"id": "mia", "name": "Mia", "handle": "@mia-venmo"}],
    "budgets": {"mia": {"total": 90000, "limits": {"FOOD": 15000}}},
    "expenses": [{"id": "e1", "paid_by": "aarav", "amount": 12000, "description": "Dinner", "category": "FOOD",
                  "split_with": ["aarav", "jake", "mia"]}],
}


def engine():
    from agent.backend.core.engine import TripEngine
    b = TripEngine()
    b.load_seed(DINNER_TRIP)
    return b


def test_edits_deletes_refunds_need_a_message_from_the_payer():
    backend = engine()
    edit = {"expense_id": "e1", "requested_by": "jake", "changes": {"amount": 15000}}
    client = ScriptedClient([
        response("tool_calls", None, tool_call("t1", "edit_expense", edit)), response("stop", ""),
        response("tool_calls", None, tool_call("t2", "edit_expense", edit)), response("stop", ""),
    ])
    agent = TripAgent(backend, "miami", client=client)
    r = agent.handle(ChatEvent(sender_id="jake", text="@tripbot dinner was $150"))
    assert "Only aarav" in r.tool_calls[0].error
    assert backend.trips["miami"].expenses[0].amount_cents == 12000  # unchanged
    r = agent.handle(ChatEvent(sender_id="aarav", text="@tripbot yep"))
    assert r.tool_calls[0].error is None
    assert backend.trips["miami"].expenses[0].amount_cents == 15000


def test_results_get_chat_ready_amounts_and_automatic_budget_checks():
    backend = engine()
    tacos = {"trip_id": "miami", "paid_by": "jake", "amount": 33000, "currency": "USD", "description": "Tacos",
             "category": "FOOD", "split_with": ["aarav", "jake", "mia"]}
    client = ScriptedClient([
        response("tool_calls", None, tool_call("t1", "log_expense", tacos),
                 tool_call("t2", "get_balances", {"trip_id": "miami"})),
        response("stop", ""),
    ])
    r = TripAgent(backend, "miami", client=client).handle(ChatEvent(sender_id="jake", text="@tripbot tacos $330"))
    logged = r.tool_calls[0].result
    assert logged["display"]["amount"] == "$330" and logged["display"]["shares"]["mia"] == "$110"
    assert logged["display"]["pay_to"] == "Jake (@jake-venmo)"
    # Everyone in the split is checked; only Mia has a budget: $40 dinner + $110 tacos uses her whole $150 food limit.
    checks = [c for c in r.tool_calls if c.by_runner]
    assert sorted(c.input["person_id"] for c in checks) == ["aarav", "jake", "mia"]
    assert list(logged["budget_warnings"]) == ["mia"] and "mia" in logged["next_step"]
    balances = next(c for c in r.tool_calls if c.name == "get_balances").result
    assert all(line.count(" pays ") == 1 for line in balances["lines"])
    assert any(line.startswith("Aarav pays Jake") and line.endswith("@jake-venmo") for line in balances["lines"])


def test_unmentioned_small_talk_cant_be_answered():
    client = ScriptedClient([
        response("tool_calls", None, tool_call("t1", "send_message", {"to": "group", "text": "😂 so fun"})),
        response("stop", ""),
    ])
    r = TripAgent(engine(), "miami", client=client).handle(
        ChatEvent(sender_id="jake", text="lol that boat was fun", mentioned=False))
    assert r.outbox == [] and "small talk" in r.tool_calls[0].error


def test_refund_tells_the_model_who_already_paid_back():
    backend = engine()
    backend.record_payback(trip_id="miami", from_person="jake", to_person="aarav", amount=4000, currency="USD")
    refund = {"expense_id": "e1", "amount": 6000, "currency": "USD"}
    client = ScriptedClient([
        response("tool_calls", None, tool_call("t0", "send_message", {"to": "group", "text": "$60 refund on Dinner? Confirm?"})),
        response("stop", ""),
        response("tool_calls", None, tool_call("t1", "record_refund", refund)), response("stop", ""),
    ])
    agent = TripAgent(backend, "miami", client=client)
    agent.handle(ChatEvent(sender_id="aarav", text="@tripbot got $60 back on dinner"))
    r = agent.handle(ChatEvent(sender_id="aarav", text="@tripbot yes"))
    out = r.tool_calls[0].result
    assert out["already_paid_back"] == ["jake"] and "Jake already paid Aarav back" in out["next_step"]


def test_refund_waits_for_a_confirmation_even_from_the_payer():
    backend = engine()
    refund = {"expense_id": "e1", "amount": 6000, "currency": "USD"}
    client = ScriptedClient([
        response("tool_calls", None, tool_call("t1", "record_refund", refund)),
        response("tool_calls", None, tool_call("t2", "send_message", {"to": "group", "text": "$60 back on Dinner. Confirm?"})),
        response("stop", ""),
        response("tool_calls", None, tool_call("t3", "record_refund", refund)), response("stop", ""),
    ])
    agent = TripAgent(backend, "miami", client=client)
    r = agent.handle(ChatEvent(sender_id="aarav", text="@tripbot got $60 back on dinner"))
    assert "confirmation first" in r.tool_calls[0].error
    assert not backend.trips["miami"].refunds
    r = agent.handle(ChatEvent(sender_id="aarav", text="@tripbot yep"))
    assert r.tool_calls[0].error is None and len(backend.trips["miami"].refunds) == 1


def test_call_after_messages_runs_without_thinking():
    client = ScriptedClient([
        response("tool_calls", None, tool_call("t1", "get_balances", {"trip_id": "miami"})),
        response("tool_calls", None, tool_call("t2", "send_message", {"to": "group", "text": "All square"})),
        response("tool_calls", None, tool_call("t3", "send_message", {"to": "mia", "text": "psst"})),
        response("stop", ""),
    ])
    r = TripAgent(engine(), "miami", client=client).handle(ChatEvent(sender_id="jake", text="@tripbot balances?"))
    assert [m["to"] for m in r.outbox] == ["group", "mia"]  # the follow-up can still send DMs
    thinking = [req["extra_body"]["enable_thinking"] for req in client.requests]
    assert thinking == [True, True, False, False]


def test_group_reply_cant_repeat_a_budget_set_in_the_group():
    budget = {"trip_id": "miami", "person_id": "mia", "total": 60000, "limits": {"FOOD": 8000}}
    client = ScriptedClient([
        response("tool_calls", None, tool_call("t1", "set_budget", budget)),
        response("tool_calls", None,
                 tool_call("t2", "send_message", {"to": "group", "text": "Saved: $600 total, $80 on food"}),
                 tool_call("t3", "send_message", {"to": "mia", "text": "Saved: $600 total, $80 on food"})),
        response("tool_calls", None, tool_call("t4", "send_message", {"to": "group", "text": "Sent you a DM, Mia 🔒"})),
        response("stop", ""),
    ])
    r = TripAgent(engine(), "miami", client=client).handle(
        ChatEvent(sender_id="mia", text="@tripbot set my budget to $600, max $80 on food"))
    assert "private budget number ($600)" in r.tool_calls[1].error
    assert r.outbox == [{"to": "mia", "text": "Saved: $600 total, $80 on food"},
                        {"to": "group", "text": "Sent you a DM, Mia 🔒"}]


def test_people_can_save_their_own_payment_handle_only():
    from agent.backend.core.engine import TripEngine
    backend = TripEngine()
    backend.load_seed({"trip": {"id": "miami", "name": "Miami"},
                       "members": [{"id": "mia", "name": "Mia", "chat_user_id": "222"},
                                   {"id": "jake", "name": "Jake", "chat_user_id": "333"}]})
    client = ScriptedClient([
        response("tool_calls", None, tool_call("t1", "set_payment_handle", {"handle": "@mia-v"})), response("stop", ""),
        response("tool_calls", None, tool_call("t2", "set_payment_handle", {"handle": "@nope"})), response("stop", ""),
    ])
    agent = TripAgent(backend, "miami", client=client)
    r = agent.handle(ChatEvent(sender_id="mia", text="@tripbot my venmo is @mia-v", chat_user_id="222"))
    assert r.tool_calls[0].result == {"saved": True, "person_id": "mia", "handle": "@mia-v"}
    r = agent.handle(ChatEvent(sender_id="jake", text="@tripbot set mia's venmo to @nope"))  # no chat id known
    assert r.tool_calls[0].error
    members = {m["id"]: m for m in backend.summary("miami")["members"]}
    assert members["mia"]["handle"] == "@mia-v" and members["mia"]["name"] == "Mia" and not members["jake"]["handle"]


def test_model_cant_add_members_with_made_up_chat_ids():
    backend = engine()
    client = ScriptedClient([
        response("tool_calls", None, tool_call("t1", "add_member", {"trip_id": "miami", "chat_user_id": "mia", "name": "Mia"})),
        response("stop", ""),
    ])
    r = TripAgent(backend, "miami", client=client).handle(ChatEvent(sender_id="mia", text="@tripbot mia here!"))
    assert "added automatically" in r.tool_calls[0].error
    assert [m["id"] for m in backend.summary("miami")["members"]].count("mia") == 1
    assert len(backend.summary("miami")["members"]) == 3


def test_decisions_routed_to_the_leader_need_the_leaders_message():
    from agent.backend.core.engine import TripEngine
    backend = TripEngine()
    backend.load_seed({**DINNER_TRIP, "trip": {**DINNER_TRIP["trip"], "start_date": "2027-03-14", "end_date": "2027-03-18",
                                              "leader_approval": ["member_changes", "trip_changes"]}})
    dates = {"trip_id": "miami", "changes": {"start_date": "2027-03-16", "end_date": "2027-03-20"}}
    client = ScriptedClient([
        response("tool_calls", None, tool_call("t1", "update_trip", dates),
                 tool_call("t2", "remove_member", {"trip_id": "miami", "person_id": "mia"}),
                 tool_call("t3", "update_trip", {"trip_id": "miami", "changes": {"name": "Miami 2027"}})),
        response("stop", ""),
        response("tool_calls", None, tool_call("t4", "update_trip", dates)), response("stop", ""),
    ])
    agent = TripAgent(backend, "miami", client=client)
    r = agent.handle(ChatEvent(sender_id="mia", text="@tripbot push it to the 16th, and I'm out"))
    assert "routed this to the leader (aarav)" in r.tool_calls[0].error
    assert "routed this to the leader" in r.tool_calls[1].error
    assert r.tool_calls[2].error is None  # renaming isn't a trip change
    trip = backend.summary("miami")["trip"]
    assert trip["start_date"] == "2027-03-14" and len(backend.summary("miami")["members"]) == 3
    r = agent.handle(ChatEvent(sender_id="aarav", text="@tripbot approved"))
    assert r.tool_calls[0].error is None and backend.summary("miami")["trip"]["start_date"] == "2027-03-16"


def test_refund_confirmation_can_be_asked_without_a_question_mark():
    client = ScriptedClient([
        response("tool_calls", None,
                 tool_call("t1", "send_message", {"to": "group", "text": "$60 back on Dinner, $20 each. Confirm and I'll log it."})),
        response("stop", ""),
        response("tool_calls", None, tool_call("t2", "record_refund", {"expense_id": "e1", "amount": 6000, "currency": "USD"})),
        response("stop", ""),
    ])
    agent = TripAgent(engine(), "miami", client=client)
    agent.handle(ChatEvent(sender_id="aarav", text="@tripbot got $60 back on dinner"))
    r = agent.handle(ChatEvent(sender_id="aarav", text="@tripbot yep"))
    assert r.tool_calls[0].error is None


def test_no_dms_to_others_on_a_turn_that_checked_or_changed_nothing():
    client = ScriptedClient([
        response("tool_calls", None,
                 tool_call("t1", "send_message", {"to": "group", "text": "$60 back on Dinner? Confirm?"})),
        response("tool_calls", None,
                 tool_call("t2", "send_message", {"to": "jake", "text": "Heads up: you'd get $20 back"}),
                 tool_call("t3", "send_message", {"to": "aarav", "text": "Just to you: confirm in the group"})),
        response("stop", ""),
    ])
    r = TripAgent(engine(), "miami", client=client).handle(ChatEvent(sender_id="aarav", text="@tripbot got $60 back"))
    assert "no private news for jake" in r.tool_calls[1].error
    assert [m["to"] for m in r.outbox] == ["group", "aarav"]  # the sender's own DM is fine
