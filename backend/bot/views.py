import hmac
import json
import logging

from django.conf import settings
from django.http import Http404, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from bot import worker
from bot.services import handle_callback

log = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def groupme_callback(request, secret: str):
    """GroupMe posts every group message here. The secret in the URL is the only
    thing GroupMe can send to prove the call is real, so a wrong one is a 404."""
    expected = settings.GROUPME_CALLBACK_SECRET
    if not expected or not hmac.compare_digest(secret, expected):
        raise Http404
    try:
        payload = json.loads(request.body)
    except ValueError:
        return JsonResponse({"error": "invalid JSON"}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"error": "invalid payload"}, status=400)
    if not settings.BOT_INLINE:
        worker.enqueue(payload)  # answer GroupMe now; the reply follows in 10–25 s
        return JsonResponse({"ok": True, "outcome": "queued"})
    outcome = handle_callback(payload)
    log.info("GroupMe message %s: %s", payload.get("id"), outcome)
    return JsonResponse({"ok": True, "outcome": outcome})
