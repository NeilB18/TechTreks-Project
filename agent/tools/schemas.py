"""Qwen function-calling tool definitions (OpenAI format): the 20 backend tools
from specs.md plus send_message.

Schemas stick to plain JSON Schema (type, properties, required, items, enum,
description) because Model Studio's docs don't confirm anyOf/oneOf support.
Amounts are integer cents in the given currency. Person ids are the `id` values
in the injected trip summary. Keep inputs in sync with agent/backend/protocol.py
(tests/test_schemas.py checks this).
"""

CATEGORY = {"type": "string",
            "enum": ["LODGING", "TRANSPORT", "FOOD", "DRINKS", "ACTIVITIES", "OTHER", "SETTLEMENT"]}
CENTS = {"type": "integer", "minimum": 0,
         "description": "Integer cents (1/100 of the currency): $120 -> 12000, MX$1,800 -> 180000, $33.50 -> 3350"}
PERSON = {"type": "string", "description": "Person id from the trip summary"}
PEOPLE = {"type": "array", "items": PERSON}
CURRENCY = {"type": "string", "description": "ISO 4217 code, e.g. USD, MXN, EUR"}
TRIP_ID = {"type": "string"}
ISO_DATE = {"type": "string", "description": "ISO date, e.g. 2027-03-16"}


def _tool(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {"type": "function",
            "function": {"name": name, "description": description,
                         "parameters": {"type": "object", "properties": properties, "required": required}}}


SPLIT_FIELDS = {
    "split_with": {**PEOPLE, "description": "Equal split among these people. Leftover cents go to a random person in the split. People who opted out of this category are removed automatically and listed in auto_excluded."},
    "exact_amounts": {"type": "object", "additionalProperties": CENTS,
                      "description": "person_id -> cents in the expense currency. Must sum to amount. Use instead of split_with."},
    "exclude": {**PEOPLE, "description": "People to leave out of split_with for this expense only (e.g. 'everyone except Jake')."},
    "override_opt_outs": {**PEOPLE, "description": "Only after the person confirmed: include them even though they opted out of this category."},
}

BACKEND_TOOL_SCHEMAS = [
    # ------------------------------------------------------------- expenses
    _tool("log_expense",
          "Log a payment and split it. Call right away once payer, amount, currency and who it's for are clear; "
          "if who it's for is unclear, or the currency symbol is ambiguous, ask instead. The payer does not have to be in the split. "
          "Stores the original amount and the base-currency amount with the FX rate. Returns expense_id, splits (base-currency cents), auto_excluded, "
          "display (amounts to quote) and budget_warnings ({person_id: [warnings]}, private: DM each person their own).",
          {"trip_id": TRIP_ID, "paid_by": PERSON, "amount": {**CENTS, "description": "Total in `currency`, in cents: $120 -> 12000, MX$1,800 -> 180000"},
           "currency": CURRENCY, "description": {"type": "string"}, "category": CATEGORY,
           **SPLIT_FIELDS,
           "source_message": {"type": "string", "description": "The chat message this came from"}},
          ["trip_id", "paid_by", "amount", "currency", "description", "category"]),
    _tool("edit_expense",
          "Change an expense's amount, currency, category, description, payer or split. Any member can ask, "
          "but only call this after the payer has confirmed in chat. Returns budget_warnings like log_expense.",
          {"expense_id": {"type": "string"}, "requested_by": PERSON,
           "changes": {"type": "object", "properties": {
               "amount": CENTS, "currency": CURRENCY, "description": {"type": "string"}, "category": CATEGORY,
               "paid_by": PERSON, **SPLIT_FIELDS}}},
          ["expense_id", "requested_by", "changes"]),
    _tool("delete_expense",
          "Remove a wrongly logged expense. Any member can ask, but only call this after the payer has confirmed in chat.",
          {"expense_id": {"type": "string"}, "requested_by": PERSON},
          ["expense_id", "requested_by"]),
    _tool("record_refund",
          "Record money returned on an expense. Only the original payer reports refunds. It's a big change: "
          "show the per-person effect and get confirmation (and the leader's, if refunds_deletes is in leader_approval) before calling. "
          "Refund is shared in the same ratio as the original split. Returns payer_now_owes and budget_warnings.",
          {"expense_id": {"type": "string"}, "amount": CENTS, "currency": CURRENCY, "note": {"type": "string"}},
          ["expense_id", "amount", "currency"]),
    # ------------------------------------------------------ trip & members
    _tool("add_member", "Add someone to the trip.",
          {"trip_id": TRIP_ID, "chat_user_id": {"type": "string"}, "name": {"type": "string"},
           "payment_handle": {"type": "string", "description": "e.g. @name-venmo"}},
          ["trip_id", "chat_user_id", "name"]),
    _tool("remove_member",
          "Drop someone from the trip. Only after the person confirmed they're out (and the leader approved, if member_changes is in leader_approval). "
          "Past splits stay (they still owe); they come off future splits and activities. "
          "Returns budget_warnings for the remaining members (private: DM each person their own).",
          {"trip_id": TRIP_ID, "person_id": PERSON},
          ["trip_id", "person_id"]),
    _tool("update_trip",
          "Change trip settings. Changing destination, dates, status, base currency or group budget needs confirmation "
          "(the leader's, if trip_changes is in leader_approval). A date change returns activities now outside the trip; "
          "a group_budget change returns members_below_group_budget (ids only) so you can DM them and nudge the leader.",
          {"trip_id": TRIP_ID, "changes": {"type": "object", "properties": {
              "name": {"type": "string"}, "destination": {"type": "string"},
              "start_date": ISO_DATE, "end_date": ISO_DATE, "base_currency": CURRENCY,
              "status": {"type": "string", "enum": ["PLANNING", "BOOKED", "ACTIVE", "DONE"]},
              "target_break": {"type": "string"},
              "group_budget": {**CENTS, "description": "Per-person cents of the tier the leader locked in"},
              "leader_id": PERSON,
              "leader_approval": {"type": "array", "items": {"type": "string", "enum": [
                  "trip_changes", "member_changes", "itinerary_saves", "refunds_deletes"]}},
              "auto_log_mode": {"type": "string"}}}},
          ["trip_id", "changes"]),
    _tool("set_budget",
          "Set a person's private budget: total plus optional per-category limits. Budgets are private; only discuss them in that person's DM.",
          {"trip_id": TRIP_ID, "person_id": PERSON, "total": CENTS,
           "limits": {"type": "object", "additionalProperties": CENTS,
                      "description": "Category -> cents, e.g. {\"DRINKS\": 10000}"}},
          ["trip_id", "person_id", "total"]),
    _tool("set_exclusion",
          "Opt a person out of a whole category (e.g. not drinking -> DRINKS), or back in with remove=true. "
          "Per-expense exclusions go through `exclude` on log_expense instead.",
          {"trip_id": TRIP_ID, "person_id": PERSON, "category": CATEGORY,
           "remove": {"type": "boolean", "description": "true to opt back in"}},
          ["trip_id", "person_id", "category"]),
    # ------------------------------------------------------------ planning
    _tool("generate_itinerary",
          "Build a day-by-day itinerary draft from external travel APIs and return draft_id + days. Post the draft for the group. "
          "Only after the group confirms (the leader, if itinerary_saves is in leader_approval), call again with save_draft_id to save it as activities.",
          {"trip_id": TRIP_ID, "constraints": {"type": "string", "description": "Interests, pace, budget notes"},
           "save_draft_id": {"type": "string"}},
          ["trip_id"]),
    _tool("add_activity",
          "Add one activity, or edit one by passing activity_id.",
          {"trip_id": TRIP_ID, "activity_id": {"type": "string"}, "name": {"type": "string"},
           "location": {"type": "string"}, "start": {"type": "string", "description": "ISO date or datetime"},
           "end": {"type": "string"}, "est_cost_cents": CENTS,
           "cost_is_per_person": {"type": "boolean", "description": "false if est_cost_cents is the group total"},
           "attendees": PEOPLE, "important": {"type": "boolean"}, "booking_url": {"type": "string"},
           "expense_id": {"type": "string", "description": "Link to the expense once it's paid"}},
          ["trip_id"]),
    _tool("get_travel_tips",
          "Tier prices and travel tips from the group's average budget (the backend computes the average; individual budgets are never returned). "
          "First call with prices_only=true and multipliers [0.5, 0.75, 1, 1.25, 1.5, 2] to list the preset tiers. "
          "When someone picks a preset or a custom multiplier (e.g. 1.1), call with just that multiplier to get lodging, food, activities and money-saving tips. "
          "Returns missing_budgets: members who haven't set a budget yet.",
          {"trip_id": TRIP_ID, "destination": {"type": "string"},
           "multipliers": {"type": "array", "items": {"type": "number"},
                           "description": "Positive multipliers of the group average, e.g. [1.1]"},
           "prices_only": {"type": "boolean"},
           "interests": {"type": "array", "items": {"type": "string"}}},
          ["trip_id", "destination", "multipliers"]),
    _tool("create_poll", "Start a group vote (destination, dates, activities, tiers).",
          {"trip_id": TRIP_ID, "question": {"type": "string"},
           "options": {"type": "array", "items": {"type": "string"}, "minItems": 2},
           "closes_at": {"type": "string", "description": "ISO datetime"}},
          ["trip_id", "question", "options"]),
    _tool("vote_poll", "Record someone's vote from a chat reply.",
          {"poll_id": {"type": "string"}, "person_id": PERSON, "option": {"type": "string"}},
          ["poll_id", "person_id", "option"]),
    _tool("close_poll",
          "Close a poll and get the winner. Post the result, then ask before applying it with update_trip.",
          {"poll_id": {"type": "string"}},
          ["poll_id"]),
    _tool("create_reminder", "Schedule a reminder, e.g. 'pay the Airbnb by Friday'.",
          {"trip_id": TRIP_ID, "message": {"type": "string"},
           "due_at": {"type": "string", "description": "ISO datetime"},
           "audience": {**PEOPLE, "description": "Person ids, or [\"all\"] for everyone"}},
          ["trip_id", "message", "due_at", "audience"]),
    # ------------------------------------------------ money info & reads
    _tool("get_balances", "Who owes whom, pair by pair, with payment handles. Safe to share in the group.",
          {"trip_id": TRIP_ID}, ["trip_id"]),
    _tool("get_budget_status",
          "One person's budget: total, spent (their split shares, not what they paid), planned activity costs, remaining, and warnings. "
          "PRIVATE: anything from this result may only go to that person's DM, never the group. "
          "Use it when someone asks about their own budget. Expense tools already return budget_warnings, so there's no need to call this after each expense.",
          {"trip_id": TRIP_ID, "person_id": PERSON}, ["trip_id", "person_id"]),
    _tool("convert_currency", "Convert an amount between currencies.",
          {"amount": CENTS, "from": CURRENCY, "to": CURRENCY}, ["amount", "from", "to"]),
    _tool("get_trip",
          "Full trip state beyond the summary: every expense with splits and refunds, polls with votes, reminders, itinerary drafts. Never budgets.",
          {"trip_id": TRIP_ID}, ["trip_id"]),
]

# Handled by the runner / chat adapter, not the backend.
SEND_MESSAGE = _tool(
    "send_message",
    "The only way to talk. to=\"group\" posts in the group chat; to=<person_id> sends that person a private DM. "
    "Budget details (anyone's total, remaining, warnings, overspend advice) may only go to that person's own DM.",
    {"to": {"type": "string", "description": "\"group\" or a person id"},
     "text": {"type": "string"}},
    ["to", "text"])

ALL_TOOLS = BACKEND_TOOL_SCHEMAS + [SEND_MESSAGE]
