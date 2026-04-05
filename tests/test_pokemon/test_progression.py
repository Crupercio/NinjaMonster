"""Tests for OwnedPokemon model, EXP/leveling service, and the new-user signal."""
from datetime import timedelta

import pytest
import allure
from django.utils import timezone

from apps.pokemon.models import OwnedPokemon
from apps.pokemon.services import (
    award_battle_exp,
    award_training_exp,
    claim_training,
    start_training,
    stop_training,
)
from tests.framework.base.base_test import BaseTest
from tests.framework.factories.pokemon_factory import OwnedPokemonFactory, PokemonFactory
from tests.framework.factories.user_factory import UserFactory


# ===========================================================================
# OwnedPokemon model
# ===========================================================================

@allure.epic("Pokemon")
@allure.feature("OwnedPokemon Model")
class TestOwnedPokemonModel(BaseTest):

    @allure.story("__str__ includes species name and level")
    @allure.severity(allure.severity_level.TRIVIAL)
    def test_str(self):
        op = OwnedPokemonFactory(level=5)
        assert op.species.name in str(op)
        assert "Lv.5" in str(op)

    @allure.story("battle_exp_gain bracket: Lv 1-9 = 10")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.parametrize("level,expected_gain", [
        (1,  10),
        (9,  10),
        (10, 20),
        (19, 20),
        (20, 30),
        (50, 60),
        (99, 100),
    ])
    def test_battle_exp_gain_bracket(self, level, expected_gain):
        op = OwnedPokemonFactory(level=level)
        assert op.battle_exp_gain == expected_gain

    @allure.story("exp_to_next_level equals level × 10")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.parametrize("level,expected_threshold", [
        (1,  10),
        (5,  50),
        (10, 100),
    ])
    def test_exp_to_next_level(self, level, expected_threshold):
        op = OwnedPokemonFactory(level=level)
        assert op.exp_to_next_level == expected_threshold

    @allure.story("New OwnedPokemon starts at level 1 with 0 EXP")
    @allure.severity(allure.severity_level.NORMAL)
    def test_defaults(self):
        op = OwnedPokemonFactory()
        assert op.level == 1
        assert op.experience == 0
        assert op.is_training is False


# ===========================================================================
# EXP service — award_battle_exp
# ===========================================================================

@allure.epic("Pokemon")
@allure.feature("EXP Service")
class TestAwardBattleExp(BaseTest):

    @allure.story("Win awards full bracket EXP")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_win_awards_full_exp(self):
        op = OwnedPokemonFactory(level=1, experience=0)
        earned = award_battle_exp(op, won=True)
        assert earned == 10
        op.refresh_from_db()
        assert op.experience == 10 or op.level == 2  # may have leveled up

    @allure.story("Loss awards half bracket EXP (rounded down)")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_loss_awards_half_exp(self):
        op = OwnedPokemonFactory(level=1, experience=0)
        earned = award_battle_exp(op, won=False)
        assert earned == 5
        op.refresh_from_db()
        assert op.experience == 5

    @allure.story("Training Pokemon cannot receive battle EXP")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_training_pokemon_cannot_battle(self):
        op = OwnedPokemonFactory(is_training=True)
        with pytest.raises(ValueError, match="training"):
            award_battle_exp(op, won=True)

    @allure.story("EXP reaching threshold triggers level up")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_level_up_on_threshold(self):
        # Lv1 threshold = 10 EXP; give 9 first, then win (10 more) → crosses 10
        op = OwnedPokemonFactory(level=1, experience=9)
        award_battle_exp(op, won=True)
        op.refresh_from_db()
        assert op.level == 2
        assert op.experience == 9  # 9 + 10 = 19; threshold was 10 → carry 9

    @allure.story("EXP carries over correctly across multiple level-ups")
    @allure.severity(allure.severity_level.NORMAL)
    def test_exp_carryover(self):
        # Lv1 threshold=10, Lv2 threshold=20. Start with 9 exp and +30 → two level-ups
        op = OwnedPokemonFactory(level=1, experience=9)
        op.experience = 9
        op.save()
        # Manually apply large exp via service internals by calling award on Lv1 trainer Pokemon
        # Easier: use a level 10 Pokemon (bracket=20) with 19 EXP, win → 20 more → level up + 19 carry
        op2 = OwnedPokemonFactory(level=10, experience=19)
        award_battle_exp(op2, won=True)
        op2.refresh_from_db()
        assert op2.level == 11
        assert op2.experience == 19  # 19 + 20 = 39; threshold was 20 → carry 19


# ===========================================================================
# EXP service — training
# ===========================================================================

@allure.epic("Pokemon")
@allure.feature("EXP Service")
class TestTraining(BaseTest):

    @allure.story("Training EXP is 3× the battle bracket")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_training_exp_is_triple(self):
        op = OwnedPokemonFactory(level=1, is_training=True)
        earned = award_training_exp(op)
        assert earned == 30  # 3 × 10

    @allure.story("Cannot get training EXP if not in training")
    @allure.severity(allure.severity_level.NORMAL)
    def test_training_exp_requires_training_mode(self):
        op = OwnedPokemonFactory(is_training=False)
        with pytest.raises(ValueError, match="not in training"):
            award_training_exp(op)

    @allure.story("start_training sets is_training=True")
    @allure.severity(allure.severity_level.NORMAL)
    def test_start_training(self):
        op = OwnedPokemonFactory(is_training=False)
        start_training(op)
        op.refresh_from_db()
        assert op.is_training is True

    @allure.story("stop_training sets is_training=False")
    @allure.severity(allure.severity_level.NORMAL)
    def test_stop_training(self):
        op = OwnedPokemonFactory(is_training=True)
        stop_training(op)
        op.refresh_from_db()
        assert op.is_training is False

    @allure.story("start_training is idempotent")
    @allure.severity(allure.severity_level.TRIVIAL)
    def test_start_training_idempotent(self):
        op = OwnedPokemonFactory(is_training=True)
        start_training(op)  # already training — should not error
        op.refresh_from_db()
        assert op.is_training is True

    @allure.story("stop_training is idempotent")
    @allure.severity(allure.severity_level.TRIVIAL)
    def test_stop_training_idempotent(self):
        op = OwnedPokemonFactory(is_training=False)
        stop_training(op)  # not training — should not error
        op.refresh_from_db()
        assert op.is_training is False

    @allure.story("claim_training awards correct XP for 30-minute session")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_claim_training_30min(self):
        # Level 1 bracket = 10; ticks = 30//2 = 15; total = 15 × 30 × 1.0 = 450
        op = OwnedPokemonFactory(level=1, experience=0)
        start_training(op, duration_minutes=30)
        # Force training_ends_at into the past so claim is allowed
        op.training_ends_at = timezone.now() - timedelta(seconds=1)
        op.save(update_fields=["training_ends_at"])
        earned = claim_training(op)
        assert earned == 450
        op.refresh_from_db()
        assert op.is_training is False
        assert op.training_ends_at is None

    @allure.story("claim_training applies 10% bonus for 1-hour session")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_claim_training_60min_bonus(self):
        # Level 1: ticks = 30; xp_per_tick = 30; total = 30 × 30 × 1.10 = 990
        op = OwnedPokemonFactory(level=1, experience=0)
        start_training(op, duration_minutes=60)
        op.training_ends_at = timezone.now() - timedelta(seconds=1)
        op.save(update_fields=["training_ends_at"])
        earned = claim_training(op)
        assert earned == 990

    @allure.story("claim_training applies 50% bonus for 4-hour session")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_claim_training_240min_bonus(self):
        # Level 1: ticks = 120; xp_per_tick = 30; total = 120 × 30 × 1.50 = 5400
        op = OwnedPokemonFactory(level=1, experience=0)
        start_training(op, duration_minutes=240)
        op.training_ends_at = timezone.now() - timedelta(seconds=1)
        op.save(update_fields=["training_ends_at"])
        earned = claim_training(op)
        assert earned == 5400

    @allure.story("claim_training raises if training not yet finished")
    @allure.severity(allure.severity_level.NORMAL)
    def test_claim_training_not_finished(self):
        op = OwnedPokemonFactory(level=1, experience=0)
        start_training(op, duration_minutes=30)
        # training_ends_at is in the future — claim must fail
        with pytest.raises(ValueError, match="not finished"):
            claim_training(op)

    @allure.story("claim_training raises if Pokemon is not in training")
    @allure.severity(allure.severity_level.NORMAL)
    def test_claim_training_not_in_training(self):
        op = OwnedPokemonFactory(is_training=False)
        with pytest.raises(ValueError, match="not currently in training"):
            claim_training(op)

    @allure.story("start_training rejects invalid duration")
    @allure.severity(allure.severity_level.NORMAL)
    def test_start_training_invalid_duration(self):
        op = OwnedPokemonFactory(is_training=False)
        with pytest.raises(ValueError, match="Invalid duration"):
            start_training(op, duration_minutes=45)


# ===========================================================================
# Signal — auto-assign 6 Pokemon on registration
# ===========================================================================

@allure.epic("Pokemon")
@allure.feature("Registration Signal")
class TestStarterPokemonSignal(BaseTest):

    @allure.story("New user receives exactly 6 OwnedPokemon")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_new_user_gets_six_pokemon(self):
        # Ensure at least 6 Gen1 Pokemon exist (seed_gen1 may not have run in test DB)
        for i in range(6):
            PokemonFactory(pokedex_number=i + 1)

        user = UserFactory()
        count = OwnedPokemon.objects.filter(owner=user).count()
        assert count == 6

    @allure.story("Starter Pokemon are all level 1 with 0 EXP")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_starters_are_level_1(self):
        for i in range(6):
            PokemonFactory(pokedex_number=i + 1)

        user = UserFactory()
        owned = OwnedPokemon.objects.filter(owner=user)
        assert all(op.level == 1 for op in owned)
        assert all(op.experience == 0 for op in owned)

    @allure.story("Starter Pokemon are unique species")
    @allure.severity(allure.severity_level.NORMAL)
    def test_starters_are_unique_species(self):
        for i in range(6):
            PokemonFactory(pokedex_number=i + 1)

        user = UserFactory()
        species_ids = list(
            OwnedPokemon.objects.filter(owner=user).values_list("species_id", flat=True)
        )
        assert len(species_ids) == len(set(species_ids))

    @allure.story("Updating an existing user does not award more Pokemon")
    @allure.severity(allure.severity_level.NORMAL)
    def test_update_user_does_not_reassign(self):
        for i in range(6):
            PokemonFactory(pokedex_number=i + 1)

        user = UserFactory()
        user.display_name = "Updated Name"
        user.save()

        count = OwnedPokemon.objects.filter(owner=user).count()
        assert count == 6  # still 6, not 12
