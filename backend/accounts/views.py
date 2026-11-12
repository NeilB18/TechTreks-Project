"""API for the signed-in person (session cookie from Google sign-in).

"My budget" is the budget of the trip member linked to the signed-in account (budgets are
shared with the trip, but the page shows your own first). People who aren't linked to a member
of the trip get 403, and anonymous requests get 401.
"""

import json
import logging
from functools import wraps

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from accounts.services import new_code
from agent.backend.core.rules import fmt_usd
from agent.backend.protocol import ToolError
from bot import groupme
from bot.models import GroupChat
from trips.models import Budget, Person, Trip
from trips.services import DjangoBackend

log = logging.getLogger(__name__)


def login_required_json(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Sign in first", "login_url": "/accounts/google/login/"}, status=401)
        return view(request, *args, **kwargs)
    return wrapper


@require_GET
@ensure_csrf_cookie
def me(request):
    """Who's signed in and which trip members they're linked to. Also sets the CSRF cookie."""
    if not request.user.is_authenticated:
        return JsonResponse({"signed_in": False, "login_url": "/accounts/google/login/"})
    people = Person.objects.filter(user=request.user).select_related("trip")
    return JsonResponse({
        "signed_in": True,
        "email": request.user.email,
        "people": [{"trip_id": p.trip_id, "trip_name": p.trip.name, "share_token": p.trip.share_token,
                    "person_id": p.person_id, "name": p.name}
                   for p in people],
    })


@require_POST
@login_required_json
def link_code(request):
    code = new_code(request.user)
    return JsonResponse({
        "code": code.code,
        "expires_at": code.expires_at.isoformat(),
        "instructions": f"Post \"{settings.BOT_MENTION} link {code.code}\" in your trip's group chat "
                        f"within {settings.LINK_CODE_MINUTES} minutes.",
    })


@require_GET
@login_required_json
def my_trip(request, trip_id: str):
    """The money side of the trip page: the full trip, balances, your own budget, and everyone's
    (budgets are shared with the trip; the page shows yours first).

    Only for a signed-in account linked to a member of this trip. Anyone with the link sees
    the rest through the public view (trips/public.py).
    """
    person = Person.objects.filter(trip_id=trip_id, user=request.user).first()
    if person is None:
        return JsonResponse({"error": "You're not linked to a member of this trip"}, status=403)
    backend = DjangoBackend()
    return JsonResponse({
        "person_id": person.person_id,
        "detail": backend.get_trip(trip_id=trip_id),
        "balances": backend.get_balances(trip_id=trip_id),
        "budget": backend.get_budget_status(trip_id=trip_id, person_id=person.person_id),
        "budgets": backend.budget_overview(trip_id=trip_id),
    })


@require_http_methods(["GET", "POST"])
@login_required_json
def my_budget(request, trip_id: str):
    """GET: your budget. POST {"total_cents"}: change your own total (only yours). Category limits stay
    as they are (set_budget replaces them, so the current ones go back in), and the bot posts one line."""
    person = Person.objects.filter(trip_id=trip_id, user=request.user).first()
    if person is None:
        return JsonResponse({"error": "You're not linked to a member of this trip"}, status=403)
    backend = DjangoBackend()
    if request.method == "POST":
        total = _body(request).get("total_cents")
        if not isinstance(total, int) or isinstance(total, bool) or not 0 < total <= MAX_CENTS:
            return JsonResponse({"error": "total_cents must be a whole number of cents above 0"}, status=400)
        current = Budget.objects.filter(person=person).first()
        if current is None or current.total_cents != total:
            backend.set_budget(trip_id=trip_id, person_id=person.person_id, total=total,
                               limits=dict(current.limits) if current else None)
            _post_to_group(trip_id, f"{person.name}'s budget is now {fmt_usd(total)}.")
    status = backend.get_budget_status(trip_id=trip_id, person_id=person.person_id)
    return JsonResponse({"person_id": person.person_id, "name": person.name, "budget": status})


@require_POST
@login_required_json
def my_payment(request, trip_id: str):
    """Mark a payment you sent as sent: POST {"to", "amount_cents", "request_id"}. Only the payer marks it,
    for no more than they owe that person right now. The same request_id twice records it once (a double tap)."""
    person = Person.objects.filter(trip_id=trip_id, user=request.user).first()
    if person is None:
        return JsonResponse({"error": "You're not linked to a member of this trip"}, status=403)
    body = _body(request)
    to, amount, request_id = body.get("to"), body.get("amount_cents"), body.get("request_id")
    if not isinstance(request_id, str) or not 0 < len(request_id) <= 64:
        return JsonResponse({"error": "request_id is required"}, status=400)
    if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
        return JsonResponse({"error": "amount_cents must be a whole number of cents above 0"}, status=400)
    receiver = Person.objects.filter(trip_id=trip_id, person_id=to, active=True).exclude(pk=person.pk).first()
    if receiver is None:
        return JsonResponse({"error": "Pick someone else on this trip"}, status=400)
    key = f"payment:{request.user.pk}:{request_id}"
    done = cache.get(key)
    if done:
        return JsonResponse(done)

    backend = DjangoBackend()
    owed = sum(p["amount_cents"] for p in backend.get_balances(trip_id=trip_id)["suggested_payments"]
               if p["from"] == person.person_id and p["to"] == receiver.person_id)
    if amount > owed:
        return JsonResponse({"error": f"You owe {receiver.name} {fmt_usd(owed)} right now", "owed_cents": owed},
                            status=400)
    if not cache.add(key, {"pending": True}, PAYMENT_KEY_SECONDS):  # a second tap already in flight
        return JsonResponse({"pending": True})
    trip = Trip.objects.get(id=trip_id)
    out = backend.record_payback(trip_id=trip_id, from_person=person.person_id, to_person=receiver.person_id,
                                 amount=amount, currency=trip.base_currency)
    cache.set(key, out, PAYMENT_KEY_SECONDS)
    _post_to_group(trip_id, f"{person.name} sent {receiver.name} {fmt_usd(amount)}.")
    return JsonResponse(out)


MAX_CENTS = 100_000_000  # $1,000,000: a typo guard
PAYMENT_KEY_SECONDS = 600


def _body(request) -> dict:
    try:
        data = json.loads(request.body or b"{}")
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _post_to_group(trip_id: str, text: str) -> None:
    """One short line in the trip's group chat, written here (no AI). The change is already saved,
    so if GroupMe fails it stands anyway; trips without a linked group skip the post."""
    chat = GroupChat.objects.filter(trip_id=trip_id).first()
    if chat is None:
        return
    try:
        groupme.post_to_group(chat.bot_id, text)
    except Exception:
        log.exception("Couldn't post %r to trip %s's group", text, trip_id)


@require_POST
@login_required_json
def my_trip_theme(request, trip_id: str):
    """A member picks the trip page's look. Only how the page looks: no leader approval, no group post."""
    person = Person.objects.filter(trip_id=trip_id, user=request.user).first()
    if person is None:
        return JsonResponse({"error": "You're not linked to a member of this trip"}, status=403)
    try:
        theme = json.loads(request.body or b"{}").get("theme")
        return JsonResponse(DjangoBackend().set_theme(trip_id, theme))
    except (ValueError, AttributeError):
        return JsonResponse({"error": "Send {\"theme\": ...} as JSON"}, status=400)
    except ToolError as e:
        return JsonResponse({"error": str(e)}, status=400)
