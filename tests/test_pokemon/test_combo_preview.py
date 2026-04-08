"""
P2-4 — Combo chain preview in team builder tests.

Covers:
- _build_combo_preview returns empty list when no OwnedPokemon
- _build_combo_preview returns empty list when no moves are assigned
- _build_combo_preview detects a single chain link (A applies status → B triggers)
- _build_combo_preview detects multiple links when several pairs exist
- _build_combo_preview skips pokemon with incomplete move slots
- _build_combo_preview does NOT link a pokemon to itself
- TeamView context includes 'combo_links' key
- TeamView combo_links shows link when team has a valid chain pair
"""
import allure
import pytest
from django.test import Client
from django.urls import reverse

from apps.pokemon.views import _build_combo_preview

from tests.framework.base.base_test import BaseTest
from tests.framework.factories.effects_factory import StatusEffectFactory
from tests.framework.factories.pokemon_factory import (
    MoveFactory,
    OwnedPokemonFactory,
    PokemonTypeFactory,
)
from tests.framework.factories.user_factory import UserFactory


def _logged_in_client(user) -> Client:
    user.set_password("testpass123")
    user.save(update_fields=["password"])
    c = Client()
    c.force_login(user)
    return c


def _make_chain_pair(ptype=None):
    """Return (applier_op, trigger_op, burn_status) with all 4 move slots assigned."""
    if ptype is None:
        ptype = PokemonTypeFactory(name="Fire")
    burn_status = StatusEffectFactory(burned=True)

    # Use auto-sequenced names (no hardcoding) to avoid unique constraint conflicts
    std_base = MoveFactory(move_type=ptype, applies_status=None, trigger_status=None)
    sp_base = MoveFactory(move_type=ptype, applies_status=None, trigger_status=None)
    sup_base = MoveFactory(move_type=ptype, applies_status=None, trigger_status=None)
    chase_inert = MoveFactory(move_type=ptype, applies_status=None, trigger_status=None)

    burn_applier = MoveFactory(move_type=ptype, applies_status=burn_status, trigger_status=None)
    burn_chaser = MoveFactory(move_type=ptype, applies_status=None, trigger_status=burn_status)

    # applier pokemon: standard applies burn, chase/special/support are inert
    applier_op = OwnedPokemonFactory(
        move_standard=burn_applier,
        move_chase=chase_inert,
        move_special=sp_base,
        move_support=sup_base,
    )
    # trigger pokemon: chase triggers on burn, others inert
    trigger_op = OwnedPokemonFactory(
        move_standard=std_base,
        move_chase=burn_chaser,
        move_special=sp_base,
        move_support=sup_base,
    )
    return applier_op, trigger_op, burn_status


@allure.epic("Team Builder")
@allure.feature("Combo Chain Preview")
@pytest.mark.django_db
class TestBuildComboPreview(BaseTest):

    @allure.story("Returns empty list for empty team")
    @allure.severity(allure.severity_level.NORMAL)
    def test_empty_list_no_pokemon(self):
        assert _build_combo_preview([]) == []

    @allure.story("Returns empty list when no moves assigned")
    @allure.severity(allure.severity_level.NORMAL)
    def test_empty_list_no_moves(self):
        op = OwnedPokemonFactory(
            move_standard=None, move_chase=None,
            move_special=None, move_support=None,
        )
        assert _build_combo_preview([op]) == []

    @allure.story("Detects a single chain link")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_detects_one_link(self):
        applier, trigger, burn = _make_chain_pair()
        links = _build_combo_preview([applier, trigger])

        assert len(links) == 1
        link = links[0]
        assert link["from_name"] == applier.species.name
        assert link["to_name"] == trigger.species.name
        assert link["status_name"] == burn.name

    @allure.story("Does NOT link pokemon to itself")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_no_self_link(self):
        ptype = PokemonTypeFactory(name="Normal")
        burn_status = StatusEffectFactory(burned=True)
        # Pokemon with both apply AND chase-trigger on same status
        applier = MoveFactory(name="Apply", move_type=ptype, applies_status=burn_status)
        chaser = MoveFactory(name="Chase", move_type=ptype, trigger_status=burn_status)
        inert = MoveFactory(name="Inert", move_type=ptype)
        op = OwnedPokemonFactory(
            move_standard=applier, move_chase=chaser,
            move_special=inert, move_support=inert,
        )
        links = _build_combo_preview([op])
        assert links == []

    @allure.story("Skips pokemon with incomplete move slots")
    @allure.severity(allure.severity_level.NORMAL)
    def test_skips_incomplete_slots(self):
        applier, trigger, _ = _make_chain_pair()
        # Break trigger's chase slot
        trigger.move_chase = None
        trigger.save(update_fields=["move_chase"])
        trigger.refresh_from_db()
        # Re-fetch so the in-memory obj reflects the DB
        from apps.pokemon.models import OwnedPokemon
        trigger_fresh = OwnedPokemon.objects.select_related(
            "move_standard__applies_status",
            "move_chase__trigger_status",
            "move_special__applies_status",
            "move_support__applies_status",
        ).get(pk=trigger.pk)

        links = _build_combo_preview([applier, trigger_fresh])
        assert links == []

    @allure.story("Detects multiple links when several pairs exist")
    @allure.severity(allure.severity_level.NORMAL)
    def test_detects_multiple_links(self):
        ptype = PokemonTypeFactory(name="Water")
        applier1, trigger1, _ = _make_chain_pair(ptype)
        applier2, trigger2, _ = _make_chain_pair(ptype)

        links = _build_combo_preview([applier1, trigger1, applier2, trigger2])
        # Each pair contributes ≥1 link
        assert len(links) >= 2


@allure.epic("Team Builder")
@allure.feature("Combo Chain Preview")
@pytest.mark.django_db
class TestTeamViewComboLinks(BaseTest):

    @allure.story("TeamView context includes combo_links key")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_team_view_has_combo_links(self):
        user = UserFactory(tutorial_complete=True)
        client = _logged_in_client(user)
        response = client.get(reverse("pokemon:team"))
        assert response.status_code == 200
        assert "combo_links" in response.context

    @allure.story("combo_links shows link when team has valid chain pair")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_team_view_shows_chain_link(self):
        user = UserFactory(tutorial_complete=True)
        applier, trigger, burn = _make_chain_pair()
        applier.owner = user
        applier.save(update_fields=["owner"])
        trigger.owner = user
        trigger.save(update_fields=["owner"])

        from apps.pokemon.models import Team, TeamSlot
        team, _ = Team.objects.get_or_create(owner=user)
        TeamSlot.objects.create(team=team, pokemon=applier, position=1)
        TeamSlot.objects.create(team=team, pokemon=trigger, position=2)

        client = _logged_in_client(user)
        response = client.get(reverse("pokemon:team"))
        links = response.context["combo_links"]
        assert len(links) >= 1
        assert any(lk["status_name"] == burn.name for lk in links)
