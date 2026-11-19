from django.conf import settings

SITE_NAME = "TravelBot"  # web/lib/site.ts


def site(request):
    """The site's name and address, for the sign-in pages Django draws itself (backend/templates)."""
    return {"SITE_NAME": SITE_NAME, "FRONTEND_URL": settings.FRONTEND_URL}
