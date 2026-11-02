"""API for the signed-in person (session cookie from Google sign-in).

"My budget" is the budget of the trip member linked to the signed-in account (budgets are
shared with the trip, but the page shows your own first). People who aren't linked to a member
of the trip get 403, and anonymous requests get 401.
"""

from functools import wraps

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from accounts.services import new_code
from trips.models import Person
from trips.services import DjangoBackend


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
        "people": [{"trip_id": p.trip_id, "trip_name": p.trip.name, "person_id": p.person_id, "name": p.name}
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
def my_budget(request, trip_id: str):
    person = Person.objects.filter(trip_id=trip_id, user=request.user).first()
    if person is None:
        return JsonResponse({"error": "You're not linked to a member of this trip"}, status=403)
    status = DjangoBackend().get_budget_status(trip_id=trip_id, person_id=person.person_id)
    return JsonResponse({"person_id": person.person_id, "name": person.name, "budget": status})
