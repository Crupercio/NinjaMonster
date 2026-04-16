"""URL patterns for the expedition app."""
from django.urls import path

from .views import DrawEncounterAPI, ExpeditionHubView, ResolveEncounterAPI, StartExpeditionAPI

app_name = "expedition"

urlpatterns = [
    path("", ExpeditionHubView.as_view(), name="hub"),
    path("start/", StartExpeditionAPI.as_view(), name="start"),
    path("session/<int:session_id>/draw/", DrawEncounterAPI.as_view(), name="draw"),
    path("session/<int:session_id>/resolve/", ResolveEncounterAPI.as_view(), name="resolve"),
]
