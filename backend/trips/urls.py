from django.urls import path

from trips import views

urlpatterns = [
    path("tools/<str:tool_name>", views.ToolView.as_view()),
    path("trips/<str:trip_id>/summary", views.TripSummaryView.as_view()),
    path("trips/<str:trip_id>/balances", views.TripBalancesView.as_view()),
    path("trips/<str:trip_id>", views.TripDetailView.as_view()),
]
