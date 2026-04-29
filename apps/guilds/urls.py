"""URL patterns for the guilds app."""
from django.urls import path

from . import views

app_name = "guilds"

urlpatterns = [
    path("", views.GuildListView.as_view(), name="list"),
    path("create/", views.GuildCreateView.as_view(), name="create"),
    path("leave/", views.GuildLeaveView.as_view(), name="leave"),
    path("<int:pk>/", views.GuildDetailView.as_view(), name="detail"),
    path("<int:pk>/album/", views.GuildAlbumView.as_view(), name="album"),
    path("<int:pk>/join/", views.GuildJoinView.as_view(), name="join"),
    path("<int:pk>/donate/", views.GuildDonateStickerView.as_view(), name="donate"),
    path("<int:pk>/quests/claim/", views.GuildClaimQuestView.as_view(), name="claim_quest"),
    path("<int:pk>/kick/<int:user_pk>/", views.GuildKickView.as_view(), name="kick"),
    path("<int:pk>/promote/<int:user_pk>/", views.GuildPromoteView.as_view(), name="promote"),
    path("<int:pk>/demote/<int:user_pk>/", views.GuildDemoteView.as_view(), name="demote"),
]
