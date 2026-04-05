"""Root URL configuration."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.users import views as user_views

urlpatterns = [
    path("", user_views.landing, name="landing"),
    path("dashboard/", user_views.dashboard, name="dashboard"),
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("accounts/", include("apps.users.urls", namespace="users")),
    path("pokemon/", include("apps.pokemon.urls", namespace="pokemon")),
    path("battle/", include("apps.game.urls", namespace="game")),
    path("stickers/", include("apps.stickers.urls", namespace="stickers")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
