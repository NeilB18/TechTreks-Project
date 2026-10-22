from django.urls import path

from bot import views

urlpatterns = [
    path("callback/<str:secret>", views.groupme_callback),
]
