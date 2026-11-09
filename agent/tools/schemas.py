"""Qwen function-calling tool definitions (OpenAI format): the 26 backend tools
from specs.md plus send_message.

Schemas stick to plain JSON Schema (type, properties, required, items, enum,
description) because Model Studio's docs don't confirm anyOf/oneOf support.
Amounts are integer cents in the given currency. Person ids are the `id` values
in the injected trip summary. Keep inputs in sync with agent/backend/protocol.py
(tests/test_schemas.py checks this). Category and status names come from trip_model/.
"""

from trip_model.category import Category
from trip_model.trip_status import TripStatus

# Spending categories. SETTLEMENT (paybacks) is only created by record_payback.
CATEGORY = {"type": "string", "enum": [c.name for c in Category if c != Category.SETTLEMENT]}
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
    "split_with": {**PEOPLE, "description": "Equal split among these people. Leftover cents go to people in id order. People who opted out of this category are removed automatically and listed in auto_excluded."},
    "exact_amounts": {"type": "object", "additionalProperties": CENTS,
                      "description": "person_id -> cents in the expense currency. Must sum to amount. Use instead of split_with."},
    "percentages": {"type": "object", "additionalProperties": {"type": "number", "minimum": 0},
                    "description": "person_id -> percent of this expense, e.g. {\"aarav\": 40, \"jake\": 30, \"mia\": 30}. Must sum to 100. Use instead of split_with."},
    "exclude": {**PEOPLE, "description": "People to leave out of split_with for this expense only (e.g. 'everyone except Jake')."},
    "override_opt_outs": {**PEOPLE, "description": "Only after the person confirmed: include them even though they opted out of this category."},
}

BACKEND_TOOL_SCHEMAS = [
    # ------------------------------------------------------------- expenses
    _tool("log_expense",
          "Log a payment and split it. Call right away once payer, amount, currency and who it's for are clear; "
          "if who it's for is unclear, or the currency symbol is ambiguous, ask instead. The payer does not have to be in the split. "
          "Stores the original amount and the base-currency amount with the FX rate. Pass exactly one of split_with, exact_amounts or percentages. "
          "Returns expense_id, shares (what each person owes for it, base-currency cents; use these in confirmations), "
          "splits (net change per person: + is owed, - owes; sums to 0) and auto_excluded, plus display (chat-ready amounts) and "
          "budget_warnings ({person_id: [warnings]}: @mention each person with theirs in the group). Paybacks go through record_payback instead.",
          {"trip_id": TRIP_ID, "paid_by": PERSON, "amount": {**CENTS, "description": "Total in `currency`, in cents"},
           "currency": CURRENCY, "description": {"type": "string"}, "category": CATEGORY,
           **SPLIT_FIELDS,
           "source_message": {"type": "string", "description": "The chat message this came from"}},
          ["trip_id", "paid_by", "amount", "currency", "description", "category"]),
    _tool("edit_expense",
          "Change an expense's amount, currency, category, description, payer or split. Any member can ask, "
          "but only call this after the payer has confirmed in chat.",
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
          "Refund is shared in the same ratio as the original split.",
          {"expense_id": {"type": "string"}, "amount": CENTS, "currency": CURRENCY, "note": {"type": "string"}},
          ["expense_id", "amount", "currency"]),
    _tool("record_payback",
          "Record that someone paid someone back outside the app (Venmo, Zelle, cash). Only call once the payment really happened: "
          "the sender says they paid, or the receiver confirms. Lowers what they owe; it's not spending and doesn't count toward budgets.",
          {"trip_id": TRIP_ID, "from_person": PERSON, "to_person": PERSON,
           "amount": {**CENTS, "description": "Amount paid in `currency`, in cents"}, "currency": CURRENCY},
          ["trip_id", "from_person", "to_person", "amount", "currency"]),
    # ------------------------------------------------------ trip & members
    _tool("add_member", "Add someone to the trip.",
          {"trip_id": TRIP_ID, "chat_user_id": {"type": "string"}, "name": {"type": "string"},
           "payment_handle": {"type": "string", "description": "e.g. @name-venmo"}},
          ["trip_id", "chat_user_id", "name"]),
    _tool("remove_member",
          "Drop someone from the trip. Only after the person confirmed they're out (and the leader approved, if member_changes is in leader_approval). "
          "Past splits stay (they still owe); they come off future splits and activities.",
          {"trip_id": TRIP_ID, "person_id": PERSON},
          ["trip_id", "person_id"]),
    _tool("update_trip",
          "Change trip settings. Changing destination, dates, status, base currency or group budget needs confirmation "
          "(the leader's, if trip_changes is in leader_approval). A date change returns activities now outside the trip; "
          "a group_budget change returns members_below_group_budget so you can tell the group who's below it.",
          {"trip_id": TRIP_ID, "changes": {"type": "object", "properties": {
              "name": {"type": "string"}, "destination": {"type": "string"},
              "start_date": ISO_DATE, "end_date": ISO_DATE, "base_currency": CURRENCY,
              "status": {"type": "string", "enum": [s.name for s in TripStatus]},
              "target_break": {"type": "string"},
              "group_budget": {**CENTS, "description": "Per-person cents of the tier the leader locked in"},
              "leader_id": PERSON,
              "leader_approval": {"type": "array", "items": {"type": "string", "enum": [
                  "trip_changes", "member_changes", "itinerary_saves", "refunds_deletes"]}},
              "auto_log_mode": {"type": "string"},
              "lodging": {"type": "string", "description": "Where the group is staying: a hotel name or street address. "
                          "It's looked up on the map; if it can't be found nothing is saved, so ask for the address. "
                          "Empty string clears it. No confirmation needed."},
              "home_city": {"type": "string", "description": "Where the group flies from (a city), for flight links "
                            "when picking a destination. Ask once if it's missing. No confirmation needed."},
              "planning_notes": {"type": "string", "description": "The group's interests and pace for planning, "
                                 "e.g. \"chill mornings, big on food, one night out\". No confirmation needed."}}}},
          ["trip_id", "changes"]),
    _tool("set_budget",
          "Set a person's budget for this trip: total plus optional per-category limits. Everyone on the trip can see budgets.",
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
          "Draft only the days someone asked for (days is required: if they didn't say which days, ask first). The group's ideas "
          "go in first, then the stops you suggest to fill what's left; plans already on those days keep their slots. Each stop is "
          "checked on OpenStreetMap and put into a free slot (morning, lunch, afternoon, dinner, night), grouped by area and respecting "
          "opening hours when known. Returns draft_id, days, ideas_used, not_found (stops the map couldn't find: offer a swap) and "
          "skipped (over the limit). A new draft replaces the old one. Post the draft for the group. "
          "Only after the group confirms (the leader, if itinerary_saves is in leader_approval), call again with save_draft_id to save it as activities.",
          {"trip_id": TRIP_ID,
           "days": {"type": "array", "items": ISO_DATE, "description": "The dates to plan, only the ones asked for"},
           "places": {"type": "array", "maxItems": 15,
                      "description": "Real, well-known places in the destination to fill the days after the group's ideas, up to 3 a day in all",
                      "items": {"type": "object", "additionalProperties": False, "required": ["name", "kind"],
                                "properties": {"name": {"type": "string", "description": "The place's real name, e.g. \"Versailles Restaurant\""},
                                               "kind": {"type": "string", "enum": ["food", "activity", "night"]},
                                               "est_cost_cents": {**CENTS, "description": "Your estimate per person"}}}},
           "use_ideas": {"type": "boolean", "description": "false to leave the ideas list out of this draft"},
           "constraints": {"type": "string", "description": "Interests, pace, budget notes"},
           "save_draft_id": {"type": "string"}},
          ["trip_id"]),
    _tool("add_activity",
          "Add one activity, or edit one by passing activity_id (with day and no start, it moves to a free slot of its kind that day; "
          "updated: false means that day is full). For a place, pass kind: it's checked on the map, and with day "
          "(and no start) it goes in the first free slot of its kind that day. If the day has no free slot of that kind, or the "
          "place is closed then, nothing is saved (created: false): ask for a time, another day, or the ideas list. "
          "Pass idea_id to put an idea from the ideas list on a day; it leaves the list.",
          {"trip_id": TRIP_ID, "activity_id": {"type": "string"}, "name": {"type": "string"},
           "kind": {"type": "string", "enum": ["food", "activity", "night"],
                    "description": "For places only; leave out for things like flights or check-in"},
           "day": {**ISO_DATE, "description": "The date; the slot is picked for you"},
           "idea_id": {"type": "string", "description": "An idea from the ideas list"},
           "location": {"type": "string"}, "start": {"type": "string", "description": "ISO date or datetime"},
           "end": {"type": "string"}, "est_cost_cents": CENTS,
           "cost_is_per_person": {"type": "boolean", "description": "false if est_cost_cents is the group total"},
           "attendees": PEOPLE, "important": {"type": "boolean"}, "booking_url": {"type": "string"},
           "expense_id": {"type": "string", "description": "Link to the expense once it's paid"}},
          ["trip_id"]),
    _tool("remove_activity",
          "Remove a saved activity. Small change: do it and confirm, unless it's linked to an expense or marked important, "
          "then ask the group first. One that came from the ideas list goes back on it (back_on_ideas). A linked expense stays logged.",
          {"trip_id": TRIP_ID, "activity_id": {"type": "string"}},
          ["trip_id", "activity_id"]),
    _tool("edit_draft",
          "One change to an unsaved itinerary draft, without rebuilding it: drop a stop, swap a stop for another place (it keeps "
          "that slot if it fits, otherwise a free slot of its kind that day), move a stop to another day, or add a place to a day. "
          "The draft keeps its draft_id. Returns the whole draft; changed: false means nothing changed (day_full or closed_then), so ask.",
          {"trip_id": TRIP_ID, "draft_id": {"type": "string"},
           "action": {"type": "string", "enum": ["drop", "swap", "move", "add"]},
           "stop": {"type": "string", "description": "The name of the stop in the draft (drop, swap, move)"},
           "place": {"type": "object", "additionalProperties": False, "required": ["name", "kind"],
                     "description": "The new place (swap, add): a real place in the destination",
                     "properties": {"name": {"type": "string"},
                                    "kind": {"type": "string", "enum": ["food", "activity", "night"]},
                                    "est_cost_cents": {**CENTS, "description": "Your estimate per person"}}},
           "day": {**ISO_DATE, "description": "The day to move it to (move) or put it on (add)"}},
          ["trip_id", "draft_id", "action"]),
    _tool("compare_destinations",
          "Compare 2 to 5 destinations you suggest for the trip. Each is checked on the map and against everyone's budget, "
          "with a Google Flights link from home_city (ask where they fly from first if it's missing). est_cost_cents is your "
          "estimate per person for the whole trip WITHOUT flights (lodging, food, activities); est_flight_cents is a separate "
          "round-trip estimate per person, which varies a lot. Returns who each one is a stretch for. Then offer a poll.",
          {"trip_id": TRIP_ID,
           "places": {"type": "array", "minItems": 2, "maxItems": 5,
                      "items": {"type": "object", "additionalProperties": False, "required": ["name", "est_cost_cents"],
                                "properties": {"name": {"type": "string", "description": "A real city or area, e.g. \"Cancún\""},
                                               "est_cost_cents": {**CENTS, "description": "Per person for the trip, without flights"},
                                               "est_flight_cents": {**CENTS, "description": "Round-trip flight per person from home_city"}}}}},
          ["trip_id", "places"]),
    _tool("find_nearby",
          "The closest places of a kind to where the group is staying (lodging in trip_state), or to `near`. Returns up to 5, "
          "closest first, each with distance, walk time, listed hours and a Maps link: use those as given. OpenStreetMap has no "
          "ratings, so say \"closest\", not \"best\", and only mention places from the results. If there's no lodging it errors: "
          "ask where they're staying. Empty results: offer to look farther.",
          {"trip_id": TRIP_ID,
           "what": {"type": "string", "description": "A short word or two: pizza, coffee, tacos, bar, pharmacy, grocery, atm"},
           "near": {"type": "string", "description": "A place someone named instead of the lodging, e.g. \"Wynwood Walls\""},
           "radius_m": {"type": "integer", "minimum": 100, "maximum": 5000,
                        "description": "How far to look in meters; default 1600 (about a mile). Only when they ask for farther or closer."}},
          ["trip_id", "what"]),
    _tool("save_idea",
          "The ideas list: places the group wants to do but hasn't put on a day. Save one when someone asks you to add a place "
          "without a day, or remove one (remove=true with idea_id or name; anyone on the trip can). Each idea is checked on the map; "
          "not_found means it couldn't be found, so say so. Up to 20 ideas. Itinerary drafts use ideas first.",
          {"trip_id": TRIP_ID, "name": {"type": "string", "description": "The place's real name"},
           "kind": {"type": "string", "enum": ["food", "activity", "night"]},
           "est_cost_cents": {**CENTS, "description": "Your estimate per person, if you have one"},
           "idea_id": {"type": "string", "description": "To remove an idea"},
           "remove": {"type": "boolean"},
           "suggested_by": {**PERSON, "description": "Filled in for you: the person who asked"}},
          ["trip_id"]),
    _tool("get_travel_tips",
          "Tier prices and travel tips from the group's average budget. Also returns each member's total in `budgets`. "
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
    _tool("get_balances",
          "Each person's net balance (+ is owed, - owes) and suggested_payments: the fewest-ish payments that settle everyone up, "
          "netted across the group, with the receiver's payment handle. Someone may be told to pay a person other than the one who paid for their stuff. "
          "Safe to share in the group.",
          {"trip_id": TRIP_ID}, ["trip_id"]),
    _tool("get_budget_status",
          "One person's budget: total, spent (their split shares, not what they paid), planned activity costs, remaining, and warnings. "
          "Warnings come from category limits only (under 10% of a limit left, counting planned activities). "
          "Budgets are shared with the trip, so this can go in the group. "
          "Use it when someone asks how a budget is doing. After expenses, refunds and dropouts the runner already "
          "checks everyone affected and adds budget_warnings to the result.",
          {"trip_id": TRIP_ID, "person_id": PERSON}, ["trip_id", "person_id"]),
    _tool("convert_currency", "Convert an amount between currencies.",
          {"amount": CENTS, "from": CURRENCY, "to": CURRENCY}, ["amount", "from", "to"]),
    _tool("get_trip",
          "Full trip state beyond the summary: every expense with shares, splits and refunds, polls with votes, reminders, itinerary drafts, the ideas list with map details, and everyone's budget (total and category limits).",
          {"trip_id": TRIP_ID}, ["trip_id"]),
]

# Handled by the runner / chat adapter, not the backend.
SEND_MESSAGE = _tool(
    "send_message",
    "The only way to talk: posts in the group chat. Tag people with @Name when a message is for them.",
    {"text": {"type": "string"}},
    ["text"])

SET_PAYMENT_HANDLE = _tool(
    "set_payment_handle",
    "Save the sender's own payment handle (Venmo, Zelle, Cash App), shown in settle-up lines. Only for the person "
    "who sent the message; nobody can set someone else's.",
    {"handle": {"type": "string", "description": "e.g. @mia-venmo, or \"Zelle: 555-0100\""}},
    ["handle"])

ALL_TOOLS = BACKEND_TOOL_SCHEMAS + [SET_PAYMENT_HANDLE, SEND_MESSAGE]
