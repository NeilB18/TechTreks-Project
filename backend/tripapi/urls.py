from django.contrib import admin
from django.urls import include, path

from accounts.views import groupme_connected

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("trips.urls")),
    path("groupme/", include("bot.urls")),
    # Add a trip: GroupMe sends people back here (accounts/new_trip.py). Before allauth's /accounts/ routes.
    path("accounts/groupme/callback", groupme_connected),
    path("accounts/", include("allauth.urls")),
    path("api/me/", include("accounts.urls")),
]
