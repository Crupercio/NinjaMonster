"""Root URL configuration."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path

from apps.users import views as user_views


def health(_request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("health/", health, name="health"),
    path("", user_views.landing, name="landing"),
    path("dashboard/", user_views.dashboard, name="dashboard"),
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("accounts/", include("apps.users.urls", namespace="users")),
    path("pokemon/", include("apps.pokemon.urls", namespace="pokemon")),
    path("battle/", include("apps.game.urls", namespace="game")),
    path("stickers/", include("apps.stickers.urls", namespace="stickers")),
    path("quests/", include("apps.quests.urls", namespace="quests")),
    path("expedition/", include("apps.expedition.urls", namespace="expedition")),
    path("ranked/", include("apps.ranked.urls", namespace="ranked")),
    path("events/", include("apps.events.urls", namespace="events")),
    path("guilds/", include("apps.guilds.urls", namespace="guilds")),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
