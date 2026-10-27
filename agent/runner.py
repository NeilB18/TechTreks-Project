"""Qwen function-calling loop for one incoming chat message.

TripAgent keeps one conversation per trip (OpenAI chat format) and calls Qwen
through Model Studio's OpenAI-compatible endpoint.
"""

import json
import os
import re
from datetime import date, timedelta
from difflib import SequenceMatcher
from dataclasses import dataclass, field
from pathlib import Path

from openai import OpenAI

from agent import config
from agent.backend.protocol import Backend, ToolError, dispatch
from agent.enrich import enrich
from agent.tools.schemas import ALL_TOOLS

SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "system_prompt.md").read_text()
PAYER_CONFIRMS = {"edit_expense", "delete_expense", "record_refund"}
# update_trip fields that count as trip changes (specs.md); name, leader and settings are the group's own.
TRIP_CHANGE_FIELDS = {"destination", "start_date", "end_date", "base_currency", "status", "group_budget"}
# After these, the runner checks the budget of everyone affected (specs.md: after every expense,
# check everyone in the split). Done in code because the model sometimes skipped people.
BUDGET_CHECK_AFTER = {"log_expense", "edit_expense", "record_refund", "remove_member"}
# Budget tools whose numbers are private (spent amounts are just split shares, so they're not on the list).
CONFIRM_WORDS = re.compile(r"\b(confirm|yes)\b", re.I)
PRIVATE_BUDGET_TOOLS = {"set_budget", "get_budget_status"}
PRIVATE_KEYS = {"total", "total_cents", "remaining_cents", "remaining_after_planned_cents", "limit_cents"}
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
    chat_user_id: str | None = None  # the sender's GroupMe user id, when the chat adapter knows it
    private_page: str | None = None  # where private messages appear when they aren't real DMs (the trip page)


@dataclass
class ToolCall:
    name: str
    input: dict
    result: dict | None = None
    error: str | None = None
    by_runner: bool = False  # made by the runner itself (automatic budget checks), not the model


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
    return OpenAI(api_key=key, base_url=config.base_url(), timeout=config.REQUEST_TIMEOUT_S, max_retries=4)


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
        self.sender_id: str | None = None
        self.event: ChatEvent | None = None
        self.private_amounts: set[int] = set()  # budget numbers seen this turn; never in a group message

    def _event_text(self, ev: ChatEvent) -> str:
        state = self.backend.summary(self.trip_id)
        names = {m["id"]: m["name"] for m in state["members"]}
        lines = [f"channel: {ev.channel}",
                 f"sender: {names.get(ev.sender_id, ev.sender_id)} ({ev.sender_id})",
                 f"mentioned: {str(ev.mentioned).lower()}"]
        if ev.time:
            lines.append(f"time: {ev.time}")
            today = _day_of(ev.time)
            if today:
                # Live evals: "by Friday" became Mar 13, a Saturday. Spell the week out instead of trusting the
                # model's weekday arithmetic.
                lines.append("calendar: " + ", ".join(
                    f"{(today + timedelta(n)):%a} {(today + timedelta(n)).isoformat()}" + (" (today)" if n == 0 else "")
                    for n in range(8)))
        if ev.private_page:
            lines.append(f"private_page: {ev.private_page}")
        lines.append(f"message: {ev.text}")
        return (f"<trip_state>\n{json.dumps(state, sort_keys=True)}\n</trip_state>\n"
                f"<event>\n" + "\n".join(lines) + "\n</event>")

    def _call(self, thinking: bool | None = None):
        thinking = self.enable_thinking if thinking is None else thinking
        return self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, *self.history],
            tools=ALL_TOOLS,
            tool_choice="auto",
            parallel_tool_calls=True,
            extra_body={"enable_thinking": thinking,
                        **({"thinking_budget": config.THINKING_BUDGET}
                           if thinking and config.THINKING_BUDGET else {})},
        )

    def _payer_guard(self, name: str, args: dict) -> str | None:
        """Edits, deletes and refunds need the payer's OK (specs.md). Enforce it here instead of trusting
        the model: they only go through on a message from the payer, e.g. their "yes" to the question."""
        if name not in PAYER_CONFIRMS:
            return None
        expense = next((e for e in self.backend.get_trip(trip_id=self.trip_id)["expenses"]
                        if e["expense_id"] == args.get("expense_id")), None)
        if expense is None or expense["paid_by"] == self.sender_id:
            return None  # unknown ids are left to the backend's own error
        return (f"Only {expense['paid_by']} (who paid for {expense['description']}) can confirm this. "
                f"Nothing was changed. Ask them in the group, and do it once they reply yes.")

    def _leader_guard(self, name: str, args: dict) -> str | None:
        """Decisions the group routed to the leader only go through on a message from the leader. Live evals saw a
        dropout and a date change done on the requester's own say-so."""
        trip = self.backend.summary(self.trip_id)["trip"]
        leader, routed = trip.get("leader_id"), set(trip.get("leader_approval") or [])
        if not leader or self.sender_id == leader:
            return None
        needs = {"remove_member": "member_changes" in routed,
                 "update_trip": "trip_changes" in routed and bool(TRIP_CHANGE_FIELDS & set(args.get("changes") or {})),
                 "generate_itinerary": "itinerary_saves" in routed and bool(args.get("save_draft_id"))}
        if not needs.get(name):
            return None
        return (f"Not done: the group routed this to the leader ({leader}), so it only goes through on their message. "
                f"Ask {leader} in the group, and do it once they approve.")

    def _refund_guard(self, name: str) -> str | None:
        """Refunds are a big change (specs.md): the payer confirms the amount first, even when they're the
        one reporting it. So a refund only goes through if the bot's previous turn asked them to confirm."""
        if name != "record_refund" or self._asked_last_turn():
            return None
        return ("Not recorded yet: refunds need a confirmation first. Ask the payer to confirm the refund and "
                "what it means per person (\"Confirm?\"), then record it once they reply yes.")

    def _events(self) -> list[int]:
        """Where each incoming chat message starts in the history (the runner's own notes don't count)."""
        return [i for i, m in enumerate(self.history) if m["role"] == "user" and "<event>" in (m["content"] or "")]

    def _trim_history(self) -> None:
        """Keep the last HISTORY_TURNS messages (each with its tool calls), and drop the <trip_state> from all
        but the newest: the current state is all the model needs, and old copies only cost tokens."""
        events = self._events()
        if len(events) > config.HISTORY_TURNS:
            self.history = self.history[events[-config.HISTORY_TURNS]:]
            events = self._events()
        for i in events[:-1]:
            content = self.history[i]["content"]
            if content.startswith("<trip_state>"):
                self.history[i] = {**self.history[i], "content": content[content.index("<event>"):]}

    def _asked_last_turn(self) -> bool:
        events = self._events()
        if len(events) < 2:
            return False
        last_turn = self.history[events[-2]:events[-1]]
        sent = {m["tool_call_id"] for m in last_turn if m["role"] == "tool" and m["content"] == '{"sent": true}'}
        for m in last_turn:
            for tc in m.get("tool_calls") or []:
                if tc["function"]["name"] != "send_message" or tc["id"] not in sent:
                    continue
                try:
                    args = json.loads(tc["function"]["arguments"] or "{}")
                except ValueError:
                    continue
                text = args.get("text") or ""
                # "Confirm?", or no question mark: "Confirm and I'll log it", "reply yes".
                if args.get("to") in ("group", self.sender_id) and ("?" in text or CONFIRM_WORDS.search(text)):
                    return True
        return False

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
            if to == "group" and self.event and self.event.channel == "group" and not self.event.mentioned \
                    and not any(c.name not in ("send_message",) and not c.by_runner for c in result.tool_calls[:-1]):
                # Nobody asked: small talk gets no reply. Real alerts come with a tool call (a check or change).
                call.error = ("You weren't @mentioned and haven't checked or changed anything, so this is small talk: "
                              "don't reply. End the turn.")
                return f"Error: {call.error}"
            used_tools = any(c.name != "send_message" and not c.by_runner for c in result.tool_calls[:-1])
            if to not in ("group", self.sender_id) and not used_tools:
                # Live: while asking the payer to confirm a refund, the no-thinking follow-up DM'd everyone in
                # the split (one DM garbled). Private news for others always follows a check or a change.
                call.error = ("Not sent: nothing was checked or changed this turn, so there's no private news for "
                              f"{to}. Ask or answer in the group (or the sender's DM), and DM others only after "
                              "something is confirmed and done.")
                return f"Error: {call.error}"
            leaked = to == "group" and _mentions_amount(text or "", self.private_amounts)
            if leaked:
                # Live run: someone set their budget in the group and the reply repeated it there.
                call.error = (f"Not sent: this group message contains a private budget number ({leaked}). Budgets "
                              "only go to the person's DM. In the group, say at most \"sent you a DM 🔒\".")
                return f"Error: {call.error}"
            if any(m["to"] == to and SequenceMatcher(None, m["text"], text or "").ratio() > 0.8 for m in result.outbox):
                # The no-thinking follow-up sometimes re-sends what it just sent, slightly reworded.
                call.error = f"Not sent: you already sent {to} nearly the same message this turn. End the turn."
                return f"Error: {call.error}"
            members = {m["id"] for m in self.backend.summary(self.trip_id)["members"]}
            if not text or (to != "group" and to not in members):
                call.error = f"`to` must be \"group\" or one of {sorted(members)}"
                return f"Error: {call.error}"
            result.outbox.append({"to": to, "text": text})
            call.result = {"sent": True}
            return json.dumps(call.result)
        if name == "set_payment_handle":
            return self._set_payment_handle(args, call)
        if name == "add_member":
            # The chat adapter adds people when they first @mention the bot. The model never sees chat ids, so a
            # call from it invents one (live: "mia here!" made a second Mia).
            call.error = ("People are added automatically the first time they @mention you, so everyone who has "
                          "messaged you is already in trip_state members. Nothing was changed. If someone's missing, "
                          "ask them to say hi with @tripbot.")
            return f"Error: {call.error}"
        blocked = self._payer_guard(name, args) or self._leader_guard(name, args) or self._refund_guard(name)
        if blocked:
            call.error = blocked
            return f"Error: {blocked}"
        try:
            call.result = dispatch(self.backend, name, args)
        except ToolError as e:
            call.error = str(e)
            return f"Error: {e}"
        if name in PRIVATE_BUDGET_TOOLS:
            self.private_amounts |= _private_amounts({"args": args, "result": call.result})
        summary = self.backend.summary(self.trip_id)
        enrich(call.result, args, summary)
        if name in BUDGET_CHECK_AFTER:
            self._attach_budget_warnings(name, call.result, summary, result)
        if name == "record_refund":
            self._attach_paid_back(call.result, summary)
        return json.dumps(call.result, default=str)

    def _set_payment_handle(self, args: dict, call: ToolCall) -> str:
        """Saved through add_member, which updates the member with this chat user id. Keyed on the sender's
        chat id, so people can only change their own handle."""
        handle = (args.get("handle") or "").strip()
        chat_id = self.event.chat_user_id if self.event else None
        if not handle or not chat_id:
            call.error = ("Can't save a handle here: it only works for the sender, from the group chat." if handle
                          else "`handle` is required")
            return f"Error: {call.error}"
        try:
            call.result = dispatch(self.backend, "add_member",
                                   {"trip_id": self.trip_id, "chat_user_id": chat_id, "name": "", "payment_handle": handle})
        except ToolError as e:
            call.error = str(e)
            return f"Error: {e}"
        call.result = {"saved": True, "person_id": call.result.get("person_id"), "handle": handle}
        return json.dumps(call.result)

    def _attach_paid_back(self, out: dict, summary: dict) -> None:
        """People who already paid the payer back have money coming back now; the model must DM them."""
        payer = out.get("payer")
        senders = sorted({e["paid_by"] for e in self.backend.get_trip(trip_id=self.trip_id)["expenses"]
                          if e["category"] == "SETTLEMENT" and payer in (e.get("shares") or {})})
        if senders:
            names = {m["id"]: m["name"] for m in summary["members"]}
            out["already_paid_back"] = senders
            out["next_step"] = (f"{', '.join(names.get(s, s) for s in senders)} already paid {names.get(payer, payer)} back, "
                                "so their money changes now: after get_balances, DM each of them who will pay them "
                                "(or who they pay) and how much, from the settle-up lines.")

    def _attach_budget_warnings(self, name: str, out: dict, summary: dict, result: TurnResult) -> None:
        """Check everyone affected and add `budget_warnings` ({person_id: [warnings]}, private)."""
        if name == "remove_member":
            people = [m["id"] for m in summary["members"] if m["active"]]
        else:
            people = list(out.get("shares") or out.get("per_person") or (out.get("expense") or {}).get("shares") or {})
        warnings = {}
        for pid in people:  # everyone affected, as specs.md asks; people without a budget just return no warnings
            args = {"trip_id": self.trip_id, "person_id": pid}
            check = ToolCall(name="get_budget_status", input=args, by_runner=True)
            result.tool_calls.append(check)
            try:
                check.result = dispatch(self.backend, "get_budget_status", args)
            except ToolError as e:
                check.error = str(e)
                continue
            if check.result.get("warnings"):
                warnings[pid] = check.result["warnings"]
        out["budget_warnings"] = warnings
        out["next_step"] = (
            f"Budgets were checked automatically. DM each person in budget_warnings ({', '.join(warnings)}) "
            "about their own warning; never mention it in the group." if warnings
            else "Budgets were checked automatically: no warnings, so don't mention budgets.")

    def handle(self, event: ChatEvent) -> TurnResult:
        result = TurnResult()
        self.sender_id = event.sender_id
        self.event = event
        self.private_amounts = set()
        self.history.append({"role": "user", "content": self._event_text(event)})
        self._trim_history()
        nudged = False
        fast = False
        for _ in range(config.MAX_TOOL_ROUNDS):
            resp = self._call(thinking=False if fast else None)
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
            # Messages are usually the last step, so the next call only needs to say "done" or send
            # any remaining DMs: no thinking needed for that.
            fast = config.FAST_FOLLOWUP and all(tc.function.name == "send_message" for tc in tool_calls)
        else:
            result.stop_reason = "max_tool_rounds"
        return result


def _private_amounts(obj, key: str | None = None) -> set[int]:
    """Budget totals, limits and what's left, in cents, anywhere in a budget tool's args or result."""
    if isinstance(obj, dict):
        out = set()
        for k, v in obj.items():
            # set_budget's `limits` maps category -> cents, so its values count as limits.
            out |= _private_amounts(v, "limit_cents" if k == "limits" else k)
        return out
    if isinstance(obj, list):
        return set().union(*(_private_amounts(v, key) for v in obj)) if obj else set()
    if isinstance(obj, int) and not isinstance(obj, bool) and obj > 0 and key in PRIVATE_KEYS:
        return {obj}
    return set()


def _mentions_amount(text: str, amounts: set[int]) -> str | None:
    """The first of these amounts written in the text as dollars ("$600", "$1,200", "$80.50"), if any."""
    for cents in sorted(amounts, reverse=True):
        dollars = f"{cents // 100:,}".replace(",", ",?")
        frac = rf"\.{cents % 100:02d}" if cents % 100 else r"(?:\.00)?"
        if re.search(rf"\$\s?{dollars}{frac}(?![\d,]*\d)", text):
            return f"${cents / 100:,.2f}".removesuffix(".00")
    return None


def _day_of(time_text: str) -> date | None:
    """The date at the start of an event time like "2027-03-10T12:00 (Wednesday)"."""
    try:
        return date.fromisoformat(time_text[:10])
    except ValueError:
        return None
