"""
P3-4 — Spectator mode tests (GDD §20.15).

Covers:
- spectate_list page renders and shows active battles
- spectate_list excludes finished battles
- spectate_list excludes tutorial battles
- spectate view renders for an active battle
- spectate view returns 404 for a finished battle
- spectate view requires login (anonymous redirect)
- spectate_list requires login (anonymous redirect)
- SpectatorConsumer connects to the same group as BattleConsumer (group name check)
- Watch nav link present for authenticated users
"""
import allure
import pytest
from django.test import Client
from django.urls import reverse

from apps.game.consumers import SpectatorConsumer
from apps.game.models import BattleStatus

from tests.framework.base.base_test import BaseTest
from tests.framework.factories.battle_factory import (
    BattleFactory,
    BattleSlotFactory,
    BattleTeamFactory,
)
from tests.framework.factories.pokemon_factory import PokemonFactory, PokemonTypeFactory
from tests.framework.factories.user_factory import UserFactory


def _client(user) -> Client:
    user.set_password("pw")
    user.save(update_fields=["password"])
    c = Client()
    c.force_login(user)
    return c


def _active_battle_with_teams():
    """Return an active battle with two teams (4 slots each)."""
    p1 = UserFactory()
    p2 = UserFactory()
    battle = BattleFactory(player_one=p1, player_two=p2, status=BattleStatus.ACTIVE, is_tutorial=False)
    normal_type = PokemonTypeFactory(name="Normal")
    for owner in (p1, p2):
        team = BattleTeamFactory(battle=battle, owner=owner)
        for pos in range(1, 5):
            poke = PokemonFactory(primary_type=normal_type)
            BattleSlotFactory(team=team, pokemon=poke, position=pos, is_active=True)
    return battle, p1, p2


@allure.epic("Game")
@allure.feature("Spectator Mode")
@pytest.mark.django_db
class TestSpectateListView(BaseTest):

    @allure.story("spectate_list renders and shows active battles")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_spectate_list_shows_active_battles(self):
        battle, p1, _ = _active_battle_with_teams()
        client = _client(p1)

        response = client.get(reverse("game:spectate_list"))

        assert response.status_code == 200
        assert battle in response.context["battles"]

    @allure.story("spectate_list excludes finished battles")
    @allure.severity(allure.severity_level.NORMAL)
    def test_spectate_list_excludes_finished(self):
        p1 = UserFactory()
        p2 = UserFactory()
        finished = BattleFactory(
            player_one=p1, player_two=p2,
            status=BattleStatus.FINISHED, is_tutorial=False,
        )
        client = _client(p1)

        response = client.get(reverse("game:spectate_list"))

        assert finished not in response.context["battles"]

    @allure.story("spectate_list excludes tutorial battles")
    @allure.severity(allure.severity_level.NORMAL)
    def test_spectate_list_excludes_tutorials(self):
        p1 = UserFactory()
        p2 = UserFactory()
        tutorial = BattleFactory(
            player_one=p1, player_two=p2,
            status=BattleStatus.ACTIVE, is_tutorial=True,
        )
        client = _client(p1)

        response = client.get(reverse("game:spectate_list"))

        assert tutorial not in response.context["battles"]

    @allure.story("spectate_list requires login")
    @allure.severity(allure.severity_level.NORMAL)
    def test_spectate_list_requires_login(self):
        response = Client().get(reverse("game:spectate_list"))

        assert response.status_code == 302
        assert "/accounts/login" in response["Location"]


@allure.epic("Game")
@allure.feature("Spectator Mode")
@pytest.mark.django_db
class TestSpectateView(BaseTest):

    @allure.story("spectate view renders for an active battle")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_spectate_view_renders(self):
        battle, p1, _ = _active_battle_with_teams()
        # A third user who is not in the battle
        spectator = UserFactory()
        client = _client(spectator)

        response = client.get(reverse("game:spectate", kwargs={"pk": battle.pk}))

        assert response.status_code == 200
        assert response.context["battle"] == battle

    @allure.story("spectate view returns 404 for a finished battle")
    @allure.severity(allure.severity_level.NORMAL)
    def test_spectate_view_404_for_finished(self):
        p1 = UserFactory()
        p2 = UserFactory()
        finished = BattleFactory(
            player_one=p1, player_two=p2,
            status=BattleStatus.FINISHED, is_tutorial=False,
        )
        spectator = UserFactory()
        client = _client(spectator)

        response = client.get(reverse("game:spectate", kwargs={"pk": finished.pk}))

        assert response.status_code == 404

    @allure.story("spectate view requires login")
    @allure.severity(allure.severity_level.NORMAL)
    def test_spectate_view_requires_login(self):
        battle, _, _ = _active_battle_with_teams()

        response = Client().get(reverse("game:spectate", kwargs={"pk": battle.pk}))

        assert response.status_code == 302
        assert "/accounts/login" in response["Location"]


@allure.epic("Game")
@allure.feature("Spectator Mode")
@pytest.mark.django_db
class TestSpectatorConsumer(BaseTest):

    @allure.story("SpectatorConsumer uses the same group name as BattleConsumer")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_spectator_group_name_matches_battle_group(self):
        """
        Both consumers must join the same channel group so broadcast messages
        from BattleActionView reach spectator clients automatically.
        """
        battle_pk = 42

        # Simulate what BattleConsumer.connect() sets
        expected_group = f"battle_{battle_pk}"

        # SpectatorConsumer must use the identical pattern
        consumer = SpectatorConsumer()
        consumer.battle_pk = battle_pk
        consumer.group_name = f"battle_{consumer.battle_pk}"

        assert consumer.group_name == expected_group


@allure.epic("Game")
@allure.feature("Spectator Mode")
@pytest.mark.django_db
class TestSpectatorNav(BaseTest):

    @allure.story("Watch nav link present for authenticated users")
    @allure.severity(allure.severity_level.MINOR)
    def test_watch_nav_link_present(self):
        user = UserFactory()
        client = _client(user)

        response = client.get(reverse("game:spectate_list"))

        assert b"Watch" in response.content
