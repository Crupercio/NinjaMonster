"""Tests for BattleAIService — all three difficulty levels."""
import allure
import pytest

from apps.game.ai import BattleAIService
from apps.game.models import AIDifficulty, Battle
from apps.game.services import BattleService

from tests.framework.base.base_test import BaseTest
from tests.framework.factories.pokemon_factory import MoveFactory, PokemonFactory, PokemonTypeFactory
from tests.framework.factories.user_factory import UserFactory

_svc = BattleService()
_ai = BattleAIService()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_ai_battle(difficulty: str = "medium") -> tuple[Battle, object]:
    """
    Create a full AI battle (player team + AI team) in ACTIVE status,
    returning (battle, ai_user).  Every Pokemon has at least one move so
    the AI can always generate actions.
    """
    normal_type = PokemonTypeFactory(name="Normal")
    default_move = MoveFactory(name="Tackle", move_type=normal_type, power=40)

    player = UserFactory()
    ai_user = _ai.get_or_create_ai_user()

    battle = _svc.create_battle(
        player_one=player,
        player_two=ai_user,
        is_ai_battle=True,
        ai_difficulty=difficulty,
    )

    def _poke_with_move():
        p = PokemonFactory(primary_type=normal_type)
        p.moves.add(default_move)
        return p

    player_pokemon = [_poke_with_move() for _ in range(6)]
    _svc.set_team(battle, player, [p.pk for p in player_pokemon])

    ai_pokemon = [_poke_with_move() for _ in range(6)]
    _svc.set_team(battle, ai_user, [p.pk for p in ai_pokemon])

    _svc.start_battle(battle)
    battle.refresh_from_db()
    return battle, ai_user


# ===========================================================================
# AI system user
# ===========================================================================

@allure.epic("AI")
@allure.feature("AI System User")
class TestAISystemUser(BaseTest):

    @allure.story("get_or_create_ai_user creates a stable singleton")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_ai_user_singleton(self):
        u1 = _ai.get_or_create_ai_user()
        u2 = _ai.get_or_create_ai_user()
        assert u1.pk == u2.pk
        assert u1.username == "__ai_trainer__"

    @allure.story("AI user has unusable password")
    @allure.severity(allure.severity_level.NORMAL)
    def test_ai_user_has_unusable_password(self):
        ai_user = _ai.get_or_create_ai_user()
        assert not ai_user.has_usable_password()


# ===========================================================================
# AI team building
# ===========================================================================

@allure.epic("AI")
@allure.feature("AI Team Building")
class TestAITeamBuilding(BaseTest):

    @allure.story("build_ai_team_pokemon_ids returns exactly 6 unique PKs")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_build_ai_team_returns_6(self):
        # Need at least 6 Pokemon in the DB
        PokemonFactory.create_batch(6)
        ids = _ai.build_ai_team_pokemon_ids()
        assert len(ids) == 6
        assert len(set(ids)) == 6  # all unique

    @allure.story("build_ai_team_pokemon_ids raises if fewer than 6 Pokemon exist")
    @allure.severity(allure.severity_level.NORMAL)
    def test_build_ai_team_too_few_pokemon(self):
        # Blank DB — only create 3
        from apps.pokemon.models import Pokemon
        Pokemon.objects.all().delete()
        PokemonFactory.create_batch(3)
        with pytest.raises(ValueError, match="Not enough Pokemon"):
            _ai.build_ai_team_pokemon_ids()


# ===========================================================================
# Easy difficulty
# ===========================================================================

@allure.epic("AI")
@allure.feature("Easy AI")
class TestEasyAI(BaseTest):

    @allure.story("Easy AI generates one action per non-fainted slot")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_easy_generates_actions(self):
        battle, ai_user = _build_ai_battle(difficulty="easy")
        actions = _ai.get_ai_actions(battle)
        # 6 AI slots, all alive
        assert len(actions) == 6

    @allure.story("Easy AI actions all reference valid slot / move / target IDs")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_easy_action_ids_are_valid(self):
        from apps.game.models import BattleSlot
        from apps.pokemon.models import Move

        battle, ai_user = _build_ai_battle(difficulty="easy")
        ai_team = battle.teams.filter(owner=ai_user).first()
        player_team = battle.teams.exclude(owner=ai_user).first()

        ai_slot_ids = set(ai_team.slots.values_list("pk", flat=True))
        player_slot_ids = set(player_team.slots.values_list("pk", flat=True))

        actions = _ai.get_ai_actions(battle)
        for a in actions:
            assert a["slot_id"] in ai_slot_ids
            assert a["target_id"] in player_slot_ids
            assert Move.objects.filter(pk=a["move_id"]).exists()

    @allure.story("Easy AI skips fainted slots")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_easy_skips_fainted_slots(self):
        battle, ai_user = _build_ai_battle(difficulty="easy")
        ai_team = battle.teams.filter(owner=ai_user).first()

        # Faint 2 AI slots
        fainted = list(ai_team.slots.all()[:2])
        for slot in fainted:
            slot.is_fainted = True
            slot.save(update_fields=["is_fainted"])

        actions = _ai.get_ai_actions(battle)
        assert len(actions) == 4  # 6 - 2 fainted

    @allure.story("Easy AI never targets a fainted player Pokemon")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_easy_never_targets_fainted(self):
        battle, ai_user = _build_ai_battle(difficulty="easy")
        player_team = battle.teams.exclude(owner=ai_user).first()

        # Faint 5 of 6 player slots, leave 1 alive
        alive_slot = player_team.slots.first()
        for slot in player_team.slots.exclude(pk=alive_slot.pk):
            slot.is_fainted = True
            slot.save(update_fields=["is_fainted"])

        actions = _ai.get_ai_actions(battle)
        for a in actions:
            assert a["target_id"] == alive_slot.pk


# ===========================================================================
# Medium difficulty
# ===========================================================================

@allure.epic("AI")
@allure.feature("Medium AI")
class TestMediumAI(BaseTest):

    @allure.story("Medium AI generates one action per non-fainted slot")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_medium_generates_actions(self):
        battle, _ = _build_ai_battle(difficulty="medium")
        actions = _ai.get_ai_actions(battle)
        assert len(actions) == 6

    @allure.story("Medium AI prefers status-applying moves on clean targets")
    @allure.severity(allure.severity_level.NORMAL)
    def test_medium_prefers_status_moves(self):
        """When one move applies a status and others are neutral, medium AI picks the status move."""
        from tests.framework.factories.effects_factory import StatusEffectFactory

        normal_type = PokemonTypeFactory(name="Normal")
        burn = StatusEffectFactory(burned=True)

        # Move A: power 60, applies burn
        move_a = MoveFactory(name="BurnMove", move_type=normal_type, power=60, applies_status=burn)
        # Move B: power 60, no status
        move_b = MoveFactory(name="PlainMove", move_type=normal_type, power=60, applies_status=None)

        player = UserFactory()
        ai_user = _ai.get_or_create_ai_user()

        battle = _svc.create_battle(
            player_one=player, player_two=ai_user,
            is_ai_battle=True, ai_difficulty="medium",
        )

        # Give AI team pokemon with both moves
        poke = PokemonFactory(primary_type=normal_type)
        poke.moves.add(move_a, move_b)
        ai_pokemon = [poke] + [PokemonFactory(primary_type=normal_type) for _ in range(5)]
        _svc.set_team(battle, ai_user, [p.pk for p in ai_pokemon])

        player_pokemon = [PokemonFactory(primary_type=normal_type) for _ in range(6)]
        _svc.set_team(battle, player, [p.pk for p in player_pokemon])
        _svc.start_battle(battle)
        battle.refresh_from_db()

        # Run 10 times — medium AI should pick BurnMove for slot 1 most of the time
        # (score 60+20 vs 60+rand(0-3)); burn_move has deterministic advantage
        picked_burn = 0
        for _ in range(20):
            actions = _ai.get_ai_actions(battle)
            first = next(
                a for a in actions
                if a["slot_id"] == battle.teams.filter(owner=ai_user)
                                              .first().slots.first().pk
            )
            if first["move_id"] == move_a.pk:
                picked_burn += 1
        # Should pick burn move at least 60% of 20 trials
        assert picked_burn >= 12


# ===========================================================================
# Hard difficulty
# ===========================================================================

@allure.epic("AI")
@allure.feature("Hard AI")
class TestHardAI(BaseTest):

    @allure.story("Hard AI generates one action per non-fainted slot")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_hard_generates_actions(self):
        battle, _ = _build_ai_battle(difficulty="hard")
        actions = _ai.get_ai_actions(battle)
        assert len(actions) == 6

    @allure.story("Hard AI targets lowest-HP player Pokemon")
    @allure.severity(allure.severity_level.NORMAL)
    def test_hard_targets_lowest_hp(self):
        battle, ai_user = _build_ai_battle(difficulty="hard")
        player_team = battle.teams.exclude(owner=ai_user).first()

        # Set one slot to critically low HP
        weak_slot = player_team.slots.all()[2]
        weak_slot.current_hp = 1
        weak_slot.save(update_fields=["current_hp"])

        actions = _ai.get_ai_actions(battle)
        # All hard AI actions should target the weakest slot
        for a in actions:
            assert a["target_id"] == weak_slot.pk

    @allure.story("Hard AI action IDs are all valid")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_hard_action_ids_valid(self):
        from apps.pokemon.models import Move

        battle, ai_user = _build_ai_battle(difficulty="hard")
        ai_team = battle.teams.filter(owner=ai_user).first()
        player_team = battle.teams.exclude(owner=ai_user).first()

        ai_slot_ids = set(ai_team.slots.values_list("pk", flat=True))
        player_slot_ids = set(player_team.slots.values_list("pk", flat=True))

        actions = _ai.get_ai_actions(battle)
        for a in actions:
            assert a["slot_id"] in ai_slot_ids
            assert a["target_id"] in player_slot_ids
            assert Move.objects.filter(pk=a["move_id"]).exists()

    @allure.story("Hard AI battle model stores correct difficulty and is_ai_battle flag")
    @allure.severity(allure.severity_level.NORMAL)
    def test_hard_battle_model_flags(self):
        battle, _ = _build_ai_battle(difficulty="hard")
        battle.refresh_from_db()
        assert battle.is_ai_battle is True
        assert battle.ai_difficulty == AIDifficulty.HARD


# ===========================================================================
# Full round execution with AI
# ===========================================================================

@allure.epic("AI")
@allure.feature("AI Round Execution")
class TestAIRoundExecution(BaseTest):

    @allure.story("Execute one full round against AI without errors")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_full_round_executes(self):
        battle, ai_user = _build_ai_battle(difficulty="medium")
        player_team = battle.teams.exclude(owner=ai_user).first()

        # Build player actions: each slot attacks the first AI target
        ai_team = battle.teams.filter(owner=ai_user).first()
        first_ai_slot = ai_team.slots.first()

        player_actions = []
        for slot in player_team.slots.all():
            move = slot.pokemon.moves.first()
            if move:
                player_actions.append({
                    "slot_id": slot.pk,
                    "move_id": move.pk,
                    "target_id": first_ai_slot.pk,
                })

        ai_actions = _ai.get_ai_actions(battle)
        round_obj = _svc.execute_round(battle, player_actions, ai_actions)

        assert round_obj is not None
        battle.refresh_from_db()
        # Round should have advanced (or battle ended)
        assert battle.current_round >= 1
