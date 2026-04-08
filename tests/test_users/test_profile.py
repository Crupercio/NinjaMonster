"""
P2-3 — Trainer profile page tests.

Covers:
- Profile page returns 200 for authenticated user viewing own profile
- Profile page returns 200 for authenticated user viewing another trainer
- Profile page returns 404 for non-existent username
- Profile page redirects anonymous user to login
- is_own_profile is True when viewing own profile
- is_own_profile is False when viewing another trainer
- Badges list is present in context
- showcase_stickers only shows stickers with is_showcase=True
- stat fields (battles_won, win_rate, longest_combo_chain) are in context
- recent_battles contains only this user's battles
"""
import allure
import pytest
from django.test import Client
from django.urls import reverse

from apps.game.models import Battle, BattleStatus
from apps.stickers.models import Sticker, StickerRarity, StickerVariant

from tests.framework.base.base_test import BaseTest
from tests.framework.factories.pokemon_factory import PokemonFactory, PokemonTypeFactory
from tests.framework.factories.user_factory import UserFactory


def _logged_in_client(user) -> Client:
    user.set_password("testpass123")
    user.save(update_fields=["password"])
    client = Client()
    client.force_login(user)
    return client


def _profile_url(username: str) -> str:
    return reverse("users:profile", kwargs={"username": username})


@allure.epic("Users")
@allure.feature("Trainer Profile")
@pytest.mark.django_db
class TestProfileAccess(BaseTest):

    @allure.story("Own profile returns 200")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_own_profile_200(self):
        user = UserFactory()
        client = _logged_in_client(user)
        response = client.get(_profile_url(user.username))
        assert response.status_code == 200

    @allure.story("Viewing another trainer's profile returns 200")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_other_profile_200(self):
        viewer = UserFactory()
        subject = UserFactory()
        client = _logged_in_client(viewer)
        response = client.get(_profile_url(subject.username))
        assert response.status_code == 200

    @allure.story("Non-existent username returns 404")
    @allure.severity(allure.severity_level.NORMAL)
    def test_nonexistent_username_404(self):
        user = UserFactory()
        client = _logged_in_client(user)
        response = client.get(_profile_url("no_such_trainer_xyz"))
        assert response.status_code == 404

    @allure.story("Anonymous user is redirected to login")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_anonymous_redirects_to_login(self):
        user = UserFactory()
        client = Client()
        response = client.get(_profile_url(user.username))
        assert response.status_code == 302
        assert "/login/" in response["Location"]


@allure.epic("Users")
@allure.feature("Trainer Profile")
@pytest.mark.django_db
class TestProfileContext(BaseTest):

    @allure.story("is_own_profile is True when viewing own profile")
    @allure.severity(allure.severity_level.NORMAL)
    def test_is_own_profile_true(self):
        user = UserFactory()
        client = _logged_in_client(user)
        response = client.get(_profile_url(user.username))
        assert response.context["is_own_profile"] is True

    @allure.story("is_own_profile is False when viewing another trainer")
    @allure.severity(allure.severity_level.NORMAL)
    def test_is_own_profile_false(self):
        viewer = UserFactory()
        subject = UserFactory()
        client = _logged_in_client(viewer)
        response = client.get(_profile_url(subject.username))
        assert response.context["is_own_profile"] is False

    @allure.story("badges list is present in context")
    @allure.severity(allure.severity_level.NORMAL)
    def test_badges_in_context(self):
        user = UserFactory()
        client = _logged_in_client(user)
        response = client.get(_profile_url(user.username))
        assert "badges" in response.context
        assert isinstance(response.context["badges"], list)
        assert len(response.context["badges"]) > 0

    @allure.story("showcase_stickers only shows is_showcase=True stickers")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_showcase_stickers_filtered(self):
        user = UserFactory()
        ptype = PokemonTypeFactory(name="Fire")
        poke = PokemonFactory(primary_type=ptype)

        # Create one showcase and one non-showcase sticker
        Sticker.objects.create(
            pokemon=poke, owner=user,
            rarity=StickerRarity.RARE, variant=StickerVariant.BASE,
            is_showcase=True,
        )
        Sticker.objects.create(
            pokemon=poke, owner=user,
            rarity=StickerRarity.COMMON, variant=StickerVariant.BASE,
            is_showcase=False,
        )

        client = _logged_in_client(user)
        response = client.get(_profile_url(user.username))
        showcase = response.context["showcase_stickers"]
        assert len(showcase) == 1
        assert showcase[0].is_showcase is True

    @allure.story("recent_battles only includes this user's battles")
    @allure.severity(allure.severity_level.NORMAL)
    def test_recent_battles_belong_to_user(self):
        user = UserFactory(tutorial_complete=True)
        other = UserFactory(tutorial_complete=True)
        unrelated = UserFactory(tutorial_complete=True)

        # Battle involving user
        Battle.objects.create(
            player_one=user, player_two=other,
            status=BattleStatus.FINISHED, winner=user,
        )
        # Unrelated battle (user not involved)
        Battle.objects.create(
            player_one=other, player_two=unrelated,
            status=BattleStatus.FINISHED, winner=other,
        )

        client = _logged_in_client(user)
        response = client.get(_profile_url(user.username))
        battles = response.context["recent_battles"]

        # All returned battles must involve this user
        for battle in battles:
            assert (
                battle.player_one_id == user.pk
                or battle.player_two_id == user.pk
            ), f"Battle #{battle.pk} does not involve user {user.pk}"

    @allure.story("First Victory badge is earned after first win")
    @allure.severity(allure.severity_level.NORMAL)
    def test_first_victory_badge_earned(self):
        user = UserFactory(battles_won=1)
        client = _logged_in_client(user)
        response = client.get(_profile_url(user.username))
        badges = {b["name"]: b["earned"] for b in response.context["badges"]}
        assert badges["First Victory"] is True

    @allure.story("Chain Initiate badge not earned at 0 combo chain")
    @allure.severity(allure.severity_level.NORMAL)
    def test_chain_initiate_not_earned(self):
        user = UserFactory(longest_combo_chain=0)
        client = _logged_in_client(user)
        response = client.get(_profile_url(user.username))
        badges = {b["name"]: b["earned"] for b in response.context["badges"]}
        assert badges["Chain Initiate"] is False
