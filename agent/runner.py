"""Qwen function-calling loop for one incoming chat message.

TripAgent keeps one conversation per trip (OpenAI chat format) and calls Qwen
through Model Studio's OpenAI-compatible endpoint.
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from openai import OpenAI

from agent import config
from agent.backend.protocol import Backend, ToolError, dispatch
from agent.tools.schemas import ALL_TOOLS

SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "system_prompt.md").read_text()
UNDELIVERED_NOTE = (
    "[runner] Your last text was not delivered: nobody sees text outside send_message. "
    "If it was meant for someone, send it now with send_message (to \"group\", or a person id for "
    "anything private like budgets). If it wasn't meant to be sent, reply with nothing."
)


@dataclass
class ChatEvent:
    sender_id: str
    text: str
    channel: str = "group"  # "group" | "dm"
    mentioned: bool = True
    time: str | None = None


@dataclass
class ToolCall:
    name: str
    input: dict
    result: dict | None = None
    error: str | None = None


@dataclass
class TurnResult:
    tool_calls: list[ToolCall] = field(default_factory=list)
    outbox: list[dict] = field(default_factory=list)  # {"to": "group" | person_id, "text": ...}
    stray_text: list[str] = field(default_factory=list)  # text outside send_message (not delivered)
    stop_reason: str | None = None
    usage: list[dict] = field(default_factory=list)


def make_client() -> OpenAI:
    key = os.environ.get(config.API_KEY_ENV)
    if not key:
        raise RuntimeError(f"Set {config.API_KEY_ENV} to your Model Studio API key")
    # A stuck request otherwise waits 10 minutes; fail fast and let the client retry.
    return OpenAI(api_key=key, base_url=config.base_url(), timeout=config.REQUEST_TIMEOUT_S, max_retries=2)


class TripAgent:
    def __init__(self, backend: Backend, trip_id: str, client: OpenAI | None = None,
                 model: str = config.MODEL, enable_thinking: bool = config.ENABLE_THINKING,
                 history: list[dict] | None = None):
        self.backend = backend
        self.trip_id = trip_id
        self.client = client or make_client()
        self.model = model
        self.enable_thinking = enable_thinking
        # Plain JSON-serializable dicts, so the bot can store and reload them between webhooks.
        self.history: list[dict] = list(history or [])

    def _event_text(self, ev: ChatEvent) -> str:
        state = self.backend.summary(self.trip_id)
        names = {m["id"]: m["name"] for m in state["members"]}
        lines = [f"channel: {ev.channel}",
                 f"sender: {names.get(ev.sender_id, ev.sender_id)} ({ev.sender_id})",
                 f"mentioned: {str(ev.mentioned).lower()}"]
        if ev.time:
            lines.append(f"time: {ev.time}")
        lines.append(f"message: {ev.text}")
        return (f"<trip_state>\n{json.dumps(state, sort_keys=True)}\n</trip_state>\n"
                f"<event>\n" + "\n".join(lines) + "\n</event>")

    def _call(self):
        return self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, *self.history],
            tools=ALL_TOOLS,
            tool_choice="auto",
            parallel_tool_calls=True,
            extra_body={"enable_thinking": self.enable_thinking},
        )

    def _run_tool(self, name: str, raw_args: str, result: TurnResult) -> str:
        try:
            args = json.loads(raw_args or "{}")
            if not isinstance(args, dict):
                raise ValueError("arguments must be a JSON object")
        except ValueError as e:
            result.tool_calls.append(ToolCall(name=name, input={"_raw": raw_args}, error=f"Invalid JSON: {e}"))
            return f"Error: arguments were not valid JSON ({e}). Call {name} again with a JSON object."
        call = ToolCall(name=name, input=args)
        result.tool_calls.append(call)
        if name == "send_message":
            to, text = args.get("to"), args.get("text")
            members = {m["id"] for m in self.backend.summary(self.trip_id)["members"]}
            if not text or (to != "group" and to not in members):
                call.error = f"`to` must be \"group\" or one of {sorted(members)}"
                return f"Error: {call.error}"
            result.outbox.append({"to": to, "text": text})
            call.result = {"sent": True}
            return json.dumps(call.result)
        try:
            call.result = dispatch(self.backend, name, args)
            return json.dumps(call.result, default=str)
        except ToolError as e:
            call.error = str(e)
            return f"Error: {e}"

    def handle(self, event: ChatEvent) -> TurnResult:
        result = TurnResult()
        self.history.append({"role": "user", "content": self._event_text(event)})
        nudged = False
        for _ in range(config.MAX_TOOL_ROUNDS):
            resp = self._call()
            if resp.usage:
                result.usage.append(resp.usage.model_dump())
            choice = resp.choices[0]
            msg = choice.message
            result.stop_reason = choice.finish_reason
            tool_calls = msg.tool_calls or []
            assistant = {"role": "assistant", "content": msg.content or ""}
            if tool_calls:
                assistant["tool_calls"] = [
                    {"id": tc.id, "type": "function",
                     "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in tool_calls]
            self.history.append(assistant)
            if msg.content and msg.content.strip():
                result.stray_text.append(msg.content)
            if not tool_calls:
                # Text written outside send_message is never delivered. Rather than guessing who it
                # was for (it might be private), remind the model once to send it properly.
                if msg.content and msg.content.strip() and not nudged and not result.outbox:
                    nudged = True
                    self.history.append({"role": "user", "content": UNDELIVERED_NOTE})
                    continue
                break
            for tc in tool_calls:
                content = self._run_tool(tc.function.name, tc.function.arguments, result)
                self.history.append({"role": "tool", "tool_call_id": tc.id, "content": content})
        else:
            result.stop_reason = "max_tool_rounds"
        return result
