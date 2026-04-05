"""URL patterns for the users app."""
from django.urls import path

from .views import DailyClaimView, RegisterView

app_name = "users"

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("daily-claim/", DailyClaimView.as_view(), name="daily_claim"),
]
