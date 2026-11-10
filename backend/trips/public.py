"""What anyone with a trip's link (/t/<share_token>) may see: the overview and the itinerary.

No expenses, balances, budgets, group budget, payment handles or lodging: those are for
signed-in members of the trip (accounts/views.py, my_trip). Fields are listed, not
removed, so anything new added to get_trip stays private until it's put here on purpose.
"""

TRIP_FIELDS = ("id", "name", "status", "destination", "start_date", "end_date", "target_break",
               "base_currency", "leader_id")
MEMBER_FIELDS = ("id", "name", "active")
ACTIVITY_FIELDS = ("activity_id", "name", "location", "start", "end", "est_cost_cents", "cost_is_per_person",
                   "est_per_person_cents", "attendees", "important", "booking_url", "lat", "lon", "verified",
                   "maps_url", "kind", "from_idea")
IDEA_FIELDS = ("idea_id", "name", "kind", "location")


def _pick(d: dict, fields: tuple[str, ...]) -> dict:
    return {k: d[k] for k in fields if k in d}


def public_trip(detail: dict) -> dict:
    """Narrow get_trip's full view to the share-link view."""
    return {
        "trip": _pick(detail["trip"], TRIP_FIELDS),
        "members": [_pick(m, MEMBER_FIELDS) for m in detail["members"]],
        "activities": [_pick(a, ACTIVITY_FIELDS) for a in detail["activities"]],
        "ideas": [_pick(i, IDEA_FIELDS) for i in detail.get("ideas", [])],
    }
