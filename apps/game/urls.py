"""URL patterns for the game app."""
from django.urls import path

from .fun_views import LoteriaGameView, MemoryHubView, MemoryMatchView, SilhouetteHubView, SilhouetteTowerView
from .views import (
    AIBattleCreateView,
    ActiveBattleListView,
    BattleActionView,
    BattleCreateView,
    BattleListView,
    BattleLogView,
    BattleView,
    HomeView,
    SpectatorView,
    SubstituteView,
    TeamSelectView,
    TutorialCompleteView,
    TutorialStarterSelectView,
    TutorialView,
)

app_name = "game"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("fun/silhouette/", SilhouetteHubView.as_view(), name="silhouette_hub"),
    path("fun/silhouette/<slug:tower_key>/", SilhouetteTowerView.as_view(), name="silhouette_tower"),
    path("fun/memory/", MemoryHubView.as_view(), name="memory_game"),
    path("fun/memory/<slug:board_key>/", MemoryMatchView.as_view(), name="memory_board"),
    path("fun/loteria/", LoteriaGameView.as_view(), name="loteria_game"),
    path("list/", BattleListView.as_view(), name="battle_list"),
    path("create/", BattleCreateView.as_view(), name="battle_create"),
    path("vs-ai/", AIBattleCreateView.as_view(), name="ai_battle_create"),
    path("<int:pk>/", BattleView.as_view(), name="battle_detail"),
    path("<int:pk>/action/", BattleActionView.as_view(), name="battle_action"),
    path("<int:pk>/substitute/", SubstituteView.as_view(), name="battle_substitute"),
    path("<int:pk>/log/", BattleLogView.as_view(), name="battle_log"),
    path("team/<int:battle_id>/", TeamSelectView.as_view(), name="team_select"),
    # Tutorial
    path("tutorial/", TutorialView.as_view(), name="tutorial"),
    path("tutorial/starter/", TutorialStarterSelectView.as_view(), name="tutorial_starter_select"),
    path("tutorial/complete/", TutorialCompleteView.as_view(), name="tutorial_complete"),
    # Spectator
    path("watch/", ActiveBattleListView.as_view(), name="spectate_list"),
    path("<int:pk>/watch/", SpectatorView.as_view(), name="spectate"),
]
