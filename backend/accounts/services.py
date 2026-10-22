"""Linking a Google sign-in to a trip member.

1. The signed-in user asks for a code (POST /api/me/link-code).
2. They post "@tripbot link <code>" in their trip's group chat.
3. The bot sees which GroupMe user posted it and links that trip member to the
   account that created the code.

Only the code's owner sees the code, and only the real GroupMe user can post as
themselves, so this works without DMs. Codes are single-use and expire.
"""

import re
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from accounts.models import LinkCode
from trips.models import Person

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O or 1/I
LINK_COMMAND = re.compile(r"\blink\s+([A-Za-z0-9]{6})\b", re.I)


def new_code(user) -> LinkCode:
    LinkCode.objects.filter(user=user, used_at__isnull=True).delete()
    while True:
        code = "".join(secrets.choice(ALPHABET) for _ in range(6))
        if not LinkCode.objects.filter(code=code).exists():
            break
    return LinkCode.objects.create(
        code=code, user=user,
        expires_at=timezone.now() + timedelta(minutes=settings.LINK_CODE_MINUTES))


def find_link_command(text: str) -> str | None:
    match = LINK_COMMAND.search(text)
    return match.group(1).upper() if match else None


def redeem(code: str, person: Person) -> str:
    """Link `person` (who posted the code) to the code's owner. Returns a group-safe reply."""
    with transaction.atomic():
        link = (LinkCode.objects.select_for_update()
                .filter(code=code.upper(), used_at__isnull=True, expires_at__gt=timezone.now()).first())
        if link is None:
            return "That link code didn't work. It may have expired, so grab a new one from the trip page."
        link.used_at = timezone.now()
        link.save(update_fields=["used_at"])
        person.user = link.user
        person.save(update_fields=["user"])
    return f"✅ {person.name}, your trip page is linked. Your budget shows there, only for you."
