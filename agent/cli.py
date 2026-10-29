"""Fake multi-person chat with the agent, backed by an in-memory TripEngine.

    python -m agent.cli                       # default seed (Example 7b's 8-person Miami trip)
    python -m agent.cli tests/scenarios/ex1_dropout.yaml

Type messages as `<person_id>: <text>` (every message is in the group chat).
Messages need "@tripbot" to count as a mention. Commands: /state, /balances,
/budget <person_id>, /quit.
"""

import json
import re
import sys

import yaml

from agent.backend.core.engine import TripEngine
from agent.runner import ChatEvent, TripAgent
from agent.scenarios import SCENARIO_DIR

LINE = re.compile(r"^(\w+)\s*:\s*(.+)$")


def main(argv: list[str]) -> None:
    path = argv[1] if len(argv) > 1 else SCENARIO_DIR / "ex7b_payer_outside_split.yaml"
    seed = yaml.safe_load(open(path))["seed"]
    backend = TripEngine()
    backend.load_seed(seed)
    trip_id = seed["trip"]["id"]
    agent = TripAgent(backend, trip_id)
    members = ", ".join(m["id"] for m in backend.summary(trip_id)["members"])
    print(f"Trip {trip_id!r} loaded from {path}. Members: {members}")
    print("Type `jake: @tripbot ...`. /state /balances /budget <id> /quit")
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not line:
            continue
        if line == "/quit":
            break
        if line == "/state":
            print(json.dumps(backend.get_trip(trip_id), indent=2, default=str))
            continue
        if line == "/balances":
            print(json.dumps(backend.get_balances(trip_id), indent=2))
            continue
        if line.startswith("/budget "):
            print(json.dumps(backend.get_budget_status(trip_id, line.split()[1]), indent=2))
            continue
        m = LINE.match(line)
        if not m:
            print("Format: <person_id>: <text>")
            continue
        sender, text = m.group(1).lower(), m.group(2)
        ev = ChatEvent(sender_id=sender, text=text, mentioned="@tripbot" in text.lower())
        result = agent.handle(ev)
        for c in result.tool_calls:
            if c.name != "send_message":
                status = f"ERROR {c.error}" if c.error else json.dumps(c.result, default=str)[:200]
                print(f"  [tool] {c.name}({json.dumps(c.input)}) -> {status}")
        for o in result.outbox:
            print(f"  tripbot: {o['text']}")
        if not result.outbox:
            print("  (tripbot stayed quiet)")


if __name__ == "__main__":
    main(sys.argv)
