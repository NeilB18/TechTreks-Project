from django.urls import path

from accounts import views

# Mounted at /api/me/
urlpatterns = [
    path("", views.me),
    path("link-code", views.link_code),
    path("trips/<str:trip_id>", views.my_trip),
    path("trips/<str:trip_id>/budget", views.my_budget),
    path("trips/<str:trip_id>/theme", views.my_trip_theme),
    path("trips/<str:trip_id>/payments", views.my_payment),
]
