"""URL patterns for the ranked app."""
from django.urls import path

from .views import LeaderboardView, QueueJoinView, QueueLeaveView, QueueStatusView, RankedHomeView

app_name = "ranked"

urlpatterns = [
    path("", RankedHomeView.as_view(), name="home"),
    path("leaderboard/", LeaderboardView.as_view(), name="leaderboard"),
    path("queue/join/", QueueJoinView.as_view(), name="queue_join"),
    path("queue/leave/", QueueLeaveView.as_view(), name="queue_leave"),
    path("queue/status/", QueueStatusView.as_view(), name="queue_status"),
]
