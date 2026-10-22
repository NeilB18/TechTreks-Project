from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("trips.urls")),
    path("groupme/", include("bot.urls")),
    path("accounts/", include("allauth.urls")),
    path("api/me/", include("accounts.urls")),
]
