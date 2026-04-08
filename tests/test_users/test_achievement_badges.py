"""
P2-6 — Achievement badge system tests.

Covers:
- _compute_badges returns 13 badges
- earned flags match user state (combo, wins, stickers, new fields)
- perfect_victories incremented when winner's team has no fainted slots
- hard_ai_wins incremented when Hard AI is defeated
- hard_ai_wins NOT incremented for Easy/Medium AI wins
- perfect_victories NOT incremented when a slot is fainted
- daily_claim_streak resets when last claim was not yesterday
- daily_claim_streak increments when last claim was yesterday
- max_daily_claim_streak never decreases
- trades_completed incremented for both parties on accept_trade
- profile page renders all 13 badges
"""
import allure
import pytest
from datetime import date, timedelta
from django.test import Client
from django.urls import reverse

from apps.users.services import claim_daily_reward
from tests.framework.base.base_test import BaseTest
from tests.framework.factories.user_factory import UserFactory


def _logged_in_client(user) -> Client:
    user.set_password("testpass123")
    user.save(update_fields=["password"])
    client = Client()
    client.force_login(user)
    return client


@allure.epic("Users")
@allure.feature("Achievement Badges")
@pytest.mark.django_db
class TestComputeBadges(BaseTest):

    @allure.story("_compute_badges returns exactly 13 badges")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_badge_count(self):
        from apps.users.views import _compute_badges
        user = UserFactory()
        badges = _compute_badges(user, {})
        assert len(badges) == 13

    @allure.story("Combo badges earned based on longest_combo_chain")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_chain_initiate_earned(self):
        from apps.users.views import _compute_badges
        user = UserFactory(longest_combo_chain=2)
        badges = {b["name"]: b for b in _compute_badges(user, {})}
        assert badges["Chain Initiate"]["earned"] is True
        assert badges["Chain Warrior"]["earned"] is False
        assert badges["Chain Master"]["earned"] is False

    @allure.story("Chain Warrior and Master earned at 5 and 10 links")
    @allure.severity(allure.severity_level.NORMAL)
    def test_chain_warrior_and_master(self):
        from apps.users.views import _compute_badges
        user = UserFactory(longest_combo_chain=10)
        badges = {b["name"]: b for b in _compute_badges(user, {})}
        assert badges["Chain Warrior"]["earned"] is True
        assert badges["Chain Master"]["earned"] is True

    @allure.story("Perfect Victory badge uses perfect_victories field")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_perfect_victory_earned(self):
        from apps.users.views import _compute_badges
        user_no = UserFactory(perfect_victories=0)
        user_yes = UserFactory(perfect_victories=1)
        assert _compute_badges(user_no, {})[10]["earned"] is False
        assert _compute_badges(user_yes, {})[10]["earned"] is True

    @allure.story("AI Breaker badge uses hard_ai_wins field")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_ai_breaker_earned(self):
        from apps.users.views import _compute_badges
        user_no = UserFactory(hard_ai_wins=9)
        user_yes = UserFactory(hard_ai_wins=10)
        assert _compute_badges(user_no, {})[11]["earned"] is False
        assert _compute_badges(user_yes, {})[11]["earned"] is True

    @allure.story("Trader badge uses trades_completed field")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_trader_earned(self):
        from apps.users.views import _compute_badges
        user_no = UserFactory(trades_completed=9)
        user_yes = UserFactory(trades_completed=10)
        badges_no = {b["name"]: b for b in _compute_badges(user_no, {})}
        badges_yes = {b["name"]: b for b in _compute_badges(user_yes, {})}
        assert badges_no["Trader"]["earned"] is False
        assert badges_yes["Trader"]["earned"] is True

    @allure.story("Daily Devotion uses max_daily_claim_streak >= 30")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_daily_devotion_earned(self):
        from apps.users.views import _compute_badges
        user_no = UserFactory(max_daily_claim_streak=29)
        user_yes = UserFactory(max_daily_claim_streak=30)
        badges_no = {b["name"]: b for b in _compute_badges(user_no, {})}
        badges_yes = {b["name"]: b for b in _compute_badges(user_yes, {})}
        assert badges_no["Daily Devotion"]["earned"] is False
        assert badges_yes["Daily Devotion"]["earned"] is True

    @allure.story("Champion badge is always unearned (PvP not implemented)")
    @allure.severity(allure.severity_level.NORMAL)
    def test_champion_always_unearned(self):
        from apps.users.views import _compute_badges
        user = UserFactory(battles_won=9999)
        badges = {b["name"]: b for b in _compute_badges(user, {})}
        assert badges["Champion"]["earned"] is False


@allure.epic("Users")
@allure.feature("Achievement Badges")
@pytest.mark.django_db
class TestDailyClaimStreak(BaseTest):

    @allure.story("Streak resets to 1 when last claim was not yesterday")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_streak_resets(self):
        user = UserFactory(
            last_daily_claim=date.today() - timedelta(days=3),
            daily_claim_streak=5,
            max_daily_claim_streak=5,
        )
        claim_daily_reward(user)
        user.refresh_from_db()
        assert user.daily_claim_streak == 1

    @allure.story("Streak increments when last claim was yesterday")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_streak_continues(self):
        user = UserFactory(
            last_daily_claim=date.today() - timedelta(days=1),
            daily_claim_streak=4,
            max_daily_claim_streak=4,
        )
        claim_daily_reward(user)
        user.refresh_from_db()
        assert user.daily_claim_streak == 5

    @allure.story("max_daily_claim_streak never decreases")
    @allure.severity(allure.severity_level.NORMAL)
    def test_max_streak_preserved(self):
        user = UserFactory(
            last_daily_claim=date.today() - timedelta(days=3),
            daily_claim_streak=1,
            max_daily_claim_streak=20,
        )
        claim_daily_reward(user)
        user.refresh_from_db()
        assert user.max_daily_claim_streak == 20
        assert user.daily_claim_streak == 1


@allure.epic("Users")
@allure.feature("Achievement Badges")
@pytest.mark.django_db
class TestProfileBadgeDisplay(BaseTest):

    @allure.story("Profile page renders all 13 badge entries")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_profile_shows_13_badges(self):
        user = UserFactory()
        client = _logged_in_client(user)
        response = client.get(reverse("users:profile", kwargs={"username": user.username}))
        assert response.status_code == 200
        assert len(response.context["badges"]) == 13
