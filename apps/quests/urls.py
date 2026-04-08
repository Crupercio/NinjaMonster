"""URL patterns for the quests app."""
from django.urls import path

from .views import QuestClaimView, QuestListView

app_name = "quests"

urlpatterns = [
    path("", QuestListView.as_view(), name="quest_list"),
    path("<int:pk>/claim/", QuestClaimView.as_view(), name="quest_claim"),
]
