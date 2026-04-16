"""URL patterns for the users app."""
from django.urls import path

from .views import BuyCandyAPI, DailyClaimView, RegisterView, TrainerProfileView

app_name = "users"

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("daily-claim/", DailyClaimView.as_view(), name="daily_claim"),
    path("profile/<str:username>/", TrainerProfileView.as_view(), name="profile"),
    path("buy-candy/", BuyCandyAPI.as_view(), name="buy_candy"),
]
