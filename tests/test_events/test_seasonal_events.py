"""
P4-2 — Seasonal Events Framework tests.

Covers:
- SeasonalEvent.is_running True for active event
- SeasonalEvent.is_running False for future event
- SeasonalEvent.is_running False for ended event
- SeasonalEvent.is_running False when is_active=False
- SeasonalEvent.status_label returns correct strings
- get_active_events() returns only running events
- get_upcoming_events() returns only future events
- apply_battle_win_bonus() awards BONUS_DUST to winner
- apply_battle_win_bonus() awards BONUS_RYO to winner
- apply_battle_win_bonus() DOUBLE_COMBO_DUST only fires for chain >= 3
- apply_battle_win_bonus() stacks multiple active events
- apply_battle_win_bonus() returns empty dict when no events active
- Event list page renders active events
- Event list page renders upcoming events
- Home page banner shows active events
"""
import allure
import pytest
from django.test import Client
from django.urls import reverse

from apps.events.models import EventBonusType
from apps.events.services import SeasonalEventService

from tests.framework.base.base_test import BaseTest
from tests.framework.factories.event_factory import SeasonalEventFactory
from tests.framework.factories.user_factory import UserFactory


def _make_fake_battle(max_combo_chain: int = 0):
    class _Fake:
        pk = 99999
    obj = _Fake()
    obj.max_combo_chain = max_combo_chain
    return obj


def _client(user) -> Client:
    user.set_password("pw")
    user.save(update_fields=["password"])
    c = Client()
    c.force_login(user)
    return c


@allure.epic("Events")
@allure.feature("Seasonal Event Model")
@pytest.mark.django_db
class TestSeasonalEventModel(BaseTest):

    @allure.story("is_running True for event within time window")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_is_running_true_for_active_event(self):
        event = SeasonalEventFactory(active=True)
        assert event.is_running is True

    @allure.story("is_running False for upcoming event")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_is_running_false_for_upcoming_event(self):
        event = SeasonalEventFactory(upcoming=True)
        assert event.is_running is False

    @allure.story("is_running False for ended event")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_is_running_false_for_ended_event(self):
        event = SeasonalEventFactory(ended=True)
        assert event.is_running is False

    @allure.story("is_running False when is_active=False regardless of dates")
    @allure.severity(allure.severity_level.NORMAL)
    def test_is_running_false_when_disabled(self):
        event = SeasonalEventFactory(active=True, is_active=False)
        assert event.is_running is False

    @allure.story("status_label returns 'active' for running event")
    @allure.severity(allure.severity_level.NORMAL)
    def test_status_label_active(self):
        event = SeasonalEventFactory(active=True)
        assert event.status_label == "active"

    @allure.story("status_label returns 'upcoming' for future event")
    @allure.severity(allure.severity_level.NORMAL)
    def test_status_label_upcoming(self):
        event = SeasonalEventFactory(upcoming=True)
        assert event.status_label == "upcoming"

    @allure.story("status_label returns 'ended' for past event")
    @allure.severity(allure.severity_level.NORMAL)
    def test_status_label_ended(self):
        event = SeasonalEventFactory(ended=True)
        assert event.status_label == "ended"


@allure.epic("Events")
@allure.feature("SeasonalEventService")
@pytest.mark.django_db
class TestSeasonalEventService(BaseTest):

    @allure.story("get_active_events returns only running events")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_get_active_events_returns_running_only(self):
        active = SeasonalEventFactory(active=True)
        SeasonalEventFactory(upcoming=True)
        SeasonalEventFactory(ended=True)
        svc = SeasonalEventService()
        result = list(svc.get_active_events())
        assert len(result) == 1
        assert result[0].pk == active.pk

    @allure.story("get_upcoming_events returns only future events")
    @allure.severity(allure.severity_level.NORMAL)
    def test_get_upcoming_events_returns_future_only(self):
        SeasonalEventFactory(active=True)
        upcoming = SeasonalEventFactory(upcoming=True)
        SeasonalEventFactory(ended=True)
        svc = SeasonalEventService()
        result = list(svc.get_upcoming_events())
        assert len(result) == 1
        assert result[0].pk == upcoming.pk

    @allure.story("apply_battle_win_bonus awards BONUS_DUST on win")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_apply_bonus_dust_awards_sticker_dust(self):
        user = UserFactory(sticker_dust=0)
        SeasonalEventFactory(active=True, event_type=EventBonusType.BONUS_DUST, bonus_value=80)
        svc = SeasonalEventService()
        summary = svc.apply_battle_win_bonus(user, _make_fake_battle())
        user.refresh_from_db()
        assert user.sticker_dust == 80
        assert summary["sticker_dust"] == 80

    @allure.story("apply_battle_win_bonus awards BONUS_RYO on win")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_apply_bonus_ryo_awards_ryo(self):
        user = UserFactory(ryo=0)
        SeasonalEventFactory(active=True, event_type=EventBonusType.BONUS_RYO, bonus_value=200)
        svc = SeasonalEventService()
        summary = svc.apply_battle_win_bonus(user, _make_fake_battle())
        user.refresh_from_db()
        assert user.ryo == 200
        assert summary["ryo"] == 200

    @allure.story("DOUBLE_COMBO_DUST fires only when chain >= 3")
    @allure.severity(allure.severity_level.NORMAL)
    def test_double_combo_dust_requires_chain_of_3(self):
        user = UserFactory(sticker_dust=0)
        SeasonalEventFactory(active=True, event_type=EventBonusType.DOUBLE_COMBO_DUST, bonus_value=100)
        svc = SeasonalEventService()
        # Chain of 2 — should not trigger
        summary_no_chain = svc.apply_battle_win_bonus(user, _make_fake_battle(max_combo_chain=2))
        user.refresh_from_db()
        assert user.sticker_dust == 0
        assert "sticker_dust" not in summary_no_chain

    @allure.story("DOUBLE_COMBO_DUST fires when chain >= 3")
    @allure.severity(allure.severity_level.NORMAL)
    def test_double_combo_dust_triggers_for_chain_of_3(self):
        user = UserFactory(sticker_dust=0)
        SeasonalEventFactory(active=True, event_type=EventBonusType.DOUBLE_COMBO_DUST, bonus_value=100)
        svc = SeasonalEventService()
        svc.apply_battle_win_bonus(user, _make_fake_battle(max_combo_chain=3))
        user.refresh_from_db()
        assert user.sticker_dust == 100

    @allure.story("Multiple active events stack their bonuses")
    @allure.severity(allure.severity_level.NORMAL)
    def test_multiple_events_stack(self):
        user = UserFactory(sticker_dust=0, ryo=0)
        SeasonalEventFactory(active=True, event_type=EventBonusType.BONUS_DUST, bonus_value=50)
        SeasonalEventFactory(active=True, event_type=EventBonusType.BONUS_RYO, bonus_value=150)
        svc = SeasonalEventService()
        summary = svc.apply_battle_win_bonus(user, _make_fake_battle())
        user.refresh_from_db()
        assert user.sticker_dust == 50
        assert user.ryo == 150
        assert summary == {"sticker_dust": 50, "ryo": 150}

    @allure.story("No active events returns empty dict")
    @allure.severity(allure.severity_level.NORMAL)
    def test_no_events_returns_empty_dict(self):
        user = UserFactory(sticker_dust=0)
        SeasonalEventFactory(ended=True)
        SeasonalEventFactory(upcoming=True)
        svc = SeasonalEventService()
        summary = svc.apply_battle_win_bonus(user, _make_fake_battle())
        assert summary == {}
        user.refresh_from_db()
        assert user.sticker_dust == 0


@allure.epic("Events")
@allure.feature("Event Pages")
@pytest.mark.django_db
class TestEventPages(BaseTest):

    @allure.story("Event list page renders active event name")
    @allure.severity(allure.severity_level.NORMAL)
    def test_event_list_renders_active_event(self):
        SeasonalEventFactory(active=True, name="Festival of Kizuna")
        user = UserFactory()
        response = _client(user).get(reverse("events:event_list"))
        assert response.status_code == 200
        assert "Festival of Kizuna" in response.content.decode()

    @allure.story("Event list page renders upcoming event")
    @allure.severity(allure.severity_level.NORMAL)
    def test_event_list_renders_upcoming_event(self):
        SeasonalEventFactory(upcoming=True, name="Chain Masters Cup")
        user = UserFactory()
        response = _client(user).get(reverse("events:event_list"))
        assert response.status_code == 200
        assert "Chain Masters Cup" in response.content.decode()

    @allure.story("Home page shows active event banner")
    @allure.severity(allure.severity_level.NORMAL)
    def test_home_page_shows_event_banner(self):
        SeasonalEventFactory(active=True, name="Ryo Rush Weekend")
        user = UserFactory()
        response = _client(user).get(reverse("game:home"))
        assert response.status_code == 200
        assert "Ryo Rush Weekend" in response.content.decode()

    @allure.story("Home page has no banner when no active events")
    @allure.severity(allure.severity_level.MINOR)
    def test_home_page_no_banner_without_events(self):
        SeasonalEventFactory(ended=True, name="Old Festival")
        user = UserFactory()
        response = _client(user).get(reverse("game:home"))
        content = response.content.decode()
        assert "Old Festival" not in content
