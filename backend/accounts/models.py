from django.conf import settings
from django.db import models


class LinkCode(models.Model):
    """A short code shown to a signed-in user. Posting "@tripbot link <code>" in the
    group chat proves which GroupMe account is theirs, without needing DMs."""
    code = models.CharField(max_length=8, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="link_codes")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
