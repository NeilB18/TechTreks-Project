"""Scenario runner + checker for the examples in examples.md.

A scenario (tests/scenarios/*.yaml) has a `seed` (state snapshot) and `turns`.
Each turn is one chat event plus:
  expect:  what must (not) happen - checked against both the live agent and the golden replay
  golden:  the tool calls and replies from examples.md, replayed offline to validate
           the scenario, the engine and this checker without calling the model

expect keys (all optional):
  calls:            [{name, args?}]   each must appear; args is a subset match
                                      (lists compare as sets, strings case-insensitively)
  count_min:        {tool: n}         at least n calls
  forbid:           [tool]            must not be called this turn
  forbid_mutations: true              no state-changing tool (asking-only turns)
  messages:         [{to, contains?, contains_any?, matches?, not_contains?}]
                                      checked against all text sent to `to` this turn
  no_messages_to:   [to]
  silent:           true              no messages at all (e.g. un-mentioned small talk)
  end_state:        [check]           see _check_state
Every turn is also checked for privacy: no group message may contain a budget total.
"""

import json
import re
import time
import unicodedata
from datetime import date
from enum import Enum
from pathlib import Path

import yaml

from agent.backend.core.engine import TripEngine, iso
from agent.backend.protocol import ToolError, dispatch, is_mutation
from agent.runner import ChatEvent, ToolCall, TurnResult
from trip_model.category import Category

ROOT = Path(__file__).resolve().parent.parent
SCENARIO_DIR = ROOT / "tests" / "scenarios"
OUT_DIR = ROOT / "tests" / "out"


def load_scenarios() -> list[dict]:
    out = []
    for path in sorted(SCENARIO_DIR.glob("*.yaml")):
        scn = yaml.safe_load(path.read_text())
        scn["file"] = path.name
        out.append(scn)
    return out


def make_backend(scn: dict, backend=None):
    """Seed `backend` (default: a new TripEngine) with the scenario's state snapshot.
    Any backend with load_seed() works; HttpBackend is seeded through its `state` backend."""
    b = backend or TripEngine()
    (getattr(b, "state", None) or b).load_seed(scn["seed"])
    return b


def _state(backend):
    """The backend to inspect for end_state/privacy checks (HttpBackend exposes one as .state)."""
    return getattr(backend, "state", None) or backend


def make_event(turn: dict) -> ChatEvent:
    return ChatEvent(sender_id=turn["sender"], text=turn["text"], channel=turn.get("channel", "group"),
                     mentioned=turn.get("mentioned", True), time=turn.get("time"))


# ----------------------------------------------------------------- matching
def _match(expected, actual) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and _match(v, actual[k]) for k, v in expected.items())
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(expected) != len(set(map(_norm, actual))):
            return False
        return sorted(map(_norm, expected)) == sorted(set(map(_norm, actual)))
    return _norm(expected) == _norm(actual)


def _fold(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


def _token_totals(usage: list[dict]) -> dict:
    keys = ("prompt_tokens", "completion_tokens", "total_tokens")
    return {k: sum((u or {}).get(k) or 0 for u in usage) for k in keys}


def _norm(v):
    if isinstance(v, str):
        return v.strip().lower()
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def _dollar_pattern(cents: int) -> re.Pattern:
    d = cents // 100
    with_commas = f"{d:,}".replace(",", ",?")
    return re.compile(rf"\$\s?{with_commas}(?![\d,]*\d)")


# ----------------------------------------------------------------- checking
def check_turn(expect: dict, tr: TurnResult, backend, trip_id: str) -> list[str]:
    backend = _state(backend)
    fails = []
    calls = tr.tool_calls
    for want in expect.get("calls", []):
        if not any(c.name == want["name"] and _match(want.get("args", {}), c.input) for c in calls):
            got = [f"{c.name}({json.dumps(c.input, sort_keys=True)})" for c in calls if c.name == want["name"]]
            fails.append(f"missing call {want['name']} with {want.get('args', {})}; got {got or 'none'}")
    for name, n in (expect.get("count_min") or {}).items():
        k = sum(c.name == name for c in calls)
        if k < n:
            fails.append(f"expected >= {n} {name} calls, got {k}")
    for name in expect.get("forbid", []):
        if any(c.name == name and c.error is None for c in calls):  # a rejected call changed nothing
            fails.append(f"forbidden call {name} (needs confirmation first?)")
    if expect.get("forbid_mutations"):
        muts = [c.name for c in calls if is_mutation(c.name, c.input) and c.error is None]
        if muts:
            fails.append(f"changed state before confirmation: {muts}")
    for m in expect.get("messages", []):
        texts = [o["text"] for o in tr.outbox if o["to"] == m["to"]]
        if not texts:
            fails.append(f"no message sent to {m['to']}")
            continue
        text = "\n".join(texts)
        low = text.lower()
        for s in m.get("contains", []):
            if s.lower() not in low:
                fails.append(f"message to {m['to']} missing {s!r}: {text!r}")
        if m.get("contains_any") and not any(s.lower() in low for s in m["contains_any"]):
            fails.append(f"message to {m['to']} has none of {m['contains_any']}: {text!r}")
        for pat in m.get("matches", []):
            if not re.search(pat, text, re.I):
                fails.append(f"message to {m['to']} doesn't match /{pat}/: {text!r}")
        for s in m.get("not_contains", []):
            if s.lower() in low:
                fails.append(f"message to {m['to']} must not contain {s!r}: {text!r}")
    if expect.get("silent") and tr.outbox:
        fails.append(f"should stay quiet, but sent: {[o['to'] + ': ' + o['text'][:60] for o in tr.outbox]}")
    for to in expect.get("no_messages_to", []):
        if any(o["to"] == to for o in tr.outbox):
            fails.append(f"should not message {to}")
    for check in expect.get("end_state", []):
        fails += _check_state(check, backend, trip_id)
    return fails


def check_privacy(tr: TurnResult, backend, trip_id: str) -> list[str]:
    trip = _state(backend).trips[trip_id]
    fails = []
    for o in tr.outbox:
        if o["to"] != "group":
            continue
        for p in trip.members:
            if p.budget and p.budget.total_cents and _dollar_pattern(p.budget.total_cents).search(o["text"]):
                fails.append(f"PRIVACY: group message reveals {p.id}'s budget: {o['text']!r}")
    return fails


def _trip_field(trip, field: str):
    """A trip field the way scenarios write it: enum names and ISO dates."""
    value = getattr(trip, field)
    return value.name if isinstance(value, Enum) else iso(value) if isinstance(value, date) else value


def _check_state(check: dict, backend, trip_id: str) -> list[str]:
    trip = backend.trips[trip_id]
    (kind, spec), = check.items()
    debts = backend.settle_up(trip)  # suggested payments: (from, to) -> cents
    if kind == "balance":
        got = debts.get((spec["from"], spec["to"]), 0)
        return [] if got == spec["amount"] else [f"{spec['from']} should owe {spec['to']} {spec['amount']}, owes {got}"]
    if kind == "no_debts_for":
        owed = {k: v for k, v in debts.items() if k[0] == spec}
        return [] if not owed else [f"{spec} should owe nothing, owes {owed}"]
    if kind == "member_active":
        return [f"{pid} active should be {v}" for pid, v in spec.items() if trip.get_member(pid).active != v]
    if kind == "trip":
        same = lambda a, b: sorted(a) == sorted(b) if isinstance(a, list) and isinstance(b, list) else a == b  # noqa: E731
        return [f"trip.{k} should be {v!r}, is {_trip_field(trip, k)!r}" for k, v in spec.items()
                if not same(_trip_field(trip, k), v)]
    if kind == "budget_total":
        return [f"{pid} budget should be {v}" for pid, v in spec.items()
                if trip.get_member(pid).budget is None or trip.get_member(pid).budget.total_cents != v]
    if kind == "opt_out":
        return [] if (spec[0], Category[spec[1]]) in trip.opt_outs else [f"missing opt-out {spec}"]
    if kind == "expense_count":
        return [] if len(trip.expenses) == spec else [f"expected {spec} expenses, have {len(trip.expenses)}"]
    if kind == "refund_count":
        return [] if len(trip.refunds) == spec else [f"expected {spec} refunds, have {len(trip.refunds)}"]
    if kind == "activity_count":
        n = len(trip.activities)
        return [] if n == spec else [f"expected {spec} activities, have {n}"]
    if kind == "no_opt_out":
        return [] if (spec[0], Category[spec[1]]) not in trip.opt_outs else [f"opt-out {spec} should be removed"]
    if kind == "trip_contains":  # case- and accent-insensitive substring, e.g. destination "cancun"
        return [f"trip.{k} should contain {v!r}, is {_trip_field(trip, k)!r}" for k, v in spec.items()
                if _fold(v) not in _fold(str(_trip_field(trip, k) or ""))]
    if kind == "reminder_due_on":
        days = [str(r.due_at)[:10] for r in trip.reminders]
        return [] if spec in days else [f"expected a reminder due {spec}, have {days}"]
    return [f"unknown end_state check {kind!r}"]


# ------------------------------------------------------------------ running
def golden_turn(backend, golden: dict) -> TurnResult:
    tr = TurnResult(stop_reason="golden")
    for c in golden.get("calls", []):
        call = ToolCall(name=c["name"], input=c.get("args", {}))
        try:
            call.result = dispatch(backend, call.name, call.input)
        except ToolError as e:
            call.error = str(e)
        tr.tool_calls.append(call)
    tr.outbox = [dict(m) for m in golden.get("messages", [])]
    return tr


def run_scenario(scn: dict, agent_factory=None, dump_name: str | None = None, backend=None) -> list[str]:
    """Run every turn; return failure strings. agent_factory=None replays the golden turns.
    `backend` defaults to a TripEngine; pass a DjangoBackend or HttpBackend to test those."""
    backend = make_backend(scn, backend)
    trip_id = scn["seed"]["trip"]["id"]
    agent = agent_factory(backend, trip_id) if agent_factory else None
    fails, transcript = [], []
    for i, turn in enumerate(scn["turns"], 1):
        started = time.monotonic()
        if agent:
            tr = agent.handle(make_event(turn))
        else:
            tr = golden_turn(backend, turn.get("golden", {}))
            fails += [f"turn {i}: golden tool error in {c.name}: {c.error}" for c in tr.tool_calls if c.error]
        turn_fails = check_turn(turn.get("expect", {}), tr, backend, trip_id) + check_privacy(tr, backend, trip_id)
        fails += [f"turn {i} ({turn['sender']}: {turn['text'][:40]!r}): {f}" for f in turn_fails]
        transcript.append({
            "turn": i, "sender": turn["sender"], "channel": turn.get("channel", "group"), "text": turn["text"],
            "tool_calls": [{"name": c.name, "input": c.input, "result": c.result, "error": c.error}
                           for c in tr.tool_calls],
            "outbox": tr.outbox, "stray_text": tr.stray_text, "stop_reason": tr.stop_reason,
            "seconds": round(time.monotonic() - started, 2), "model_calls": len(tr.usage),
            "tokens": _token_totals(tr.usage), "failures": turn_fails})
    if dump_name:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUT_DIR / f"{dump_name}.json").write_text(json.dumps(transcript, indent=2, default=str))
    return fails
