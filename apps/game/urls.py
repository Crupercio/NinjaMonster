"""URL patterns for the game app."""
from django.urls import path

from .views import (
    AIBattleCreateView,
    BattleActionView,
    BattleCreateView,
    BattleListView,
    BattleLogView,
    BattleView,
    HomeView,
    SubstituteView,
    TeamSelectView,
)

app_name = "game"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("list/", BattleListView.as_view(), name="battle_list"),
    path("create/", BattleCreateView.as_view(), name="battle_create"),
    path("vs-ai/", AIBattleCreateView.as_view(), name="ai_battle_create"),
    path("<int:pk>/", BattleView.as_view(), name="battle_detail"),
    path("<int:pk>/action/", BattleActionView.as_view(), name="battle_action"),
    path("<int:pk>/substitute/", SubstituteView.as_view(), name="battle_substitute"),
    path("<int:pk>/log/", BattleLogView.as_view(), name="battle_log"),
    path("team/<int:battle_id>/", TeamSelectView.as_view(), name="team_select"),
]
