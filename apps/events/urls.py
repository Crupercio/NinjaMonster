"""URL patterns for the seasonal events app."""
from django.urls import path

from . import views

app_name = "events"

urlpatterns = [
    path("", views.EventListView.as_view(), name="event_list"),
]
