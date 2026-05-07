"""URL patterns for the users app."""
from django.urls import path

from .views import AchievementsView, ArcadeDailyChallengeClaim, ArcadeDailyChallengeProgressAPI, BuyCandyAPI, DailyClaimView, GuideAdvanceAPI, RegisterView, TrainerProfileView

app_name = "users"

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("daily-claim/", DailyClaimView.as_view(), name="daily_claim"),
    path("profile/<str:username>/", TrainerProfileView.as_view(), name="profile"),
    path("buy-candy/", BuyCandyAPI.as_view(), name="buy_candy"),
    path("arcade-challenge/progress/", ArcadeDailyChallengeProgressAPI.as_view(), name="arcade_challenge_progress"),
    path("arcade-challenge/claim/", ArcadeDailyChallengeClaim.as_view(), name="arcade_challenge_claim"),
    path("achievements/", AchievementsView.as_view(), name="achievements"),
    path("guide/advance/", GuideAdvanceAPI.as_view(), name="guide_advance"),
]
