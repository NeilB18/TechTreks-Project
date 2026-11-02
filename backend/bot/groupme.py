"""Sending messages to GroupMe.

Group posts go through the bot API (https://dev.groupme.com/docs/v3#bots_post).
GroupMe bots can't send DMs, and nothing the bot says is private (budgets are
shared with the trip), so every message goes to the group.
"""

import requests

API = "https://api.groupme.com/v3"
MAX_LEN = 1000  # GroupMe's message length limit


def chunks(text: str, size: int = MAX_LEN) -> list[str]:
    """Split on line breaks where possible so long replies stay readable."""
    out, current = [], ""
    for line in text.splitlines(keepends=True):
        while len(line) > size:
            if current:
                out.append(current)
                current = ""
            out.append(line[:size])
            line = line[size:]
        if len(current) + len(line) > size:
            out.append(current)
            current = ""
        current += line
    if current:
        out.append(current)
    return [c.rstrip("\n") for c in out if c.strip()]


def post_to_group(bot_id: str, text: str) -> None:
    for part in chunks(text):
        resp = requests.post(f"{API}/bots/post", json={"bot_id": bot_id, "text": part}, timeout=15)
        resp.raise_for_status()

