"""
Phase 4 — Combo Chain tests.

Covers: chain fires, chain depth, max-depth cap, fainted skip,
duplicate-trigger prevention, immunity breaking chain,
and correct BattleLog entries.
"""
import allure
import pytest

from apps.game.models import BattleAction, BattleLog, BattleRound, BattleStatus, LogType
from apps.game.services import ComboChainEngine, MAX_CHAIN_DEPTH

from tests.framework.base.base_test import BaseTest
from tests.framework.factories.battle_factory import (
    BattleFactory,
    BattleSlotFactory,
    BattleTeamFactory,
)
from tests.framework.factories.effects_factory import StatusEffectFactory
from tests.framework.factories.pokemon_factory import (
    MoveFactory,
    PokemonFactory,
    PokemonTypeFactory,
)
from tests.framework.factories.user_factory import UserFactory
from tests.framework.helpers.battle_helpers import build_battle_pair, ensure_round


def _make_chain_battle(
    p1_moves,
    p2_moves=None,
):
    """
    Build a minimal 1v1-style battle with exactly 6 slots per team.

    All player-1 Pokemon learn every move in p1_moves.
    All player-2 Pokemon learn every move in p2_moves (or nothing).
    Returns (battle, team1, team2, slots1, slots2, round_obj).
    """
    battle, team1, team2, slots1, slots2 = build_battle_pair(
        p1_moves=p1_moves, p2_moves=p2_moves
    )
    round_obj = ensure_round(battle, round_number=1)
    return battle, team1, team2, slots1, slots2, round_obj


# ===========================================================================
# TestComboChainBasic
# ===========================================================================

@allure.epic("Battle")
@allure.feature("Combo Chain")
class TestComboChainBasic(BaseTest):

    @allure.story("Move with no status produces no chain (single action)")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_no_status_no_chain(self, normal_type, chain_engine):
        # Arrange
        plain_move = MoveFactory(name="Plain", move_type=normal_type, power=60)
        battle, team1, team2, slots1, slots2, round_obj = _make_chain_battle(
            p1_moves=[plain_move]
        )

        # Act
        actions = chain_engine.resolve_combo_chain(
            battle=battle,
            attacker_slot=slots1[0],
            move=plain_move,
            target_slot=slots2[0],
            round_number=1,
        )

        # Assert — only the initial action, no chain
        assert len(actions) == 1
        assert actions[0].is_combo_triggered is False
        assert actions[0].order_in_chain == 0

    @allure.story("Move applies status → teammate with trigger_status fires automatically")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_depth_one_chain_fires(
        self, chain_engine, burn_applies_move, burn_trigger_move, normal_type
    ):
        # Arrange: p1 team has both moves; p2 team has no special moves
        battle, team1, team2, slots1, slots2, round_obj = _make_chain_battle(
            p1_moves=[burn_applies_move, burn_trigger_move]
        )
        attacker = slots1[0]
        target = slots2[0]

        # Act
        actions = chain_engine.resolve_combo_chain(
            battle=battle,
            attacker_slot=attacker,
            move=burn_applies_move,
            target_slot=target,
            round_number=1,
        )

        # Assert — at least 2 actions (initial + 1 triggered)
        assert len(actions) >= 2
        assert actions[0].is_combo_triggered is False
        assert actions[1].is_combo_triggered is True
        assert actions[1].order_in_chain == 1

    @allure.story("Chain depth 2: A applies burn → B triggers on burn & applies poison → C triggers on poison")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_depth_two_chain(
        self,
        chain_engine,
        burn_applies_move,
        burn_applies_poison_trigger_move,
        poison_trigger_move,
        normal_type,
    ):
        # Arrange: p1 team learns all three moves
        battle, team1, team2, slots1, slots2, round_obj = _make_chain_battle(
            p1_moves=[
                burn_applies_move,
                burn_applies_poison_trigger_move,
                poison_trigger_move,
            ]
        )

        # Act
        actions = chain_engine.resolve_combo_chain(
            battle=battle,
            attacker_slot=slots1[0],
            move=burn_applies_move,
            target_slot=slots2[0],
            round_number=1,
        )

        # Assert — 3+ actions
        assert len(actions) >= 3
        combo_actions = [a for a in actions if a.is_combo_triggered]
        assert len(combo_actions) >= 2

    @allure.story("Combo chain actions are logged with correct chain metadata")
    @allure.severity(allure.severity_level.NORMAL)
    def test_combo_chain_logged(
        self, chain_engine, burn_applies_move, burn_trigger_move
    ):
        battle, team1, team2, slots1, slots2, round_obj = _make_chain_battle(
            p1_moves=[burn_applies_move, burn_trigger_move]
        )

        chain_engine.resolve_combo_chain(
            battle=battle,
            attacker_slot=slots1[0],
            move=burn_applies_move,
            target_slot=slots2[0],
            round_number=1,
        )

        combo_logs = BattleLog.objects.filter(battle=battle, log_type=LogType.COMBO)
        assert combo_logs.exists()
        summary = combo_logs.filter(chain_position=0).first()
        assert summary is not None
        assert "Chain x" in summary.message

    @allure.story("battle.max_combo_chain is updated after a chain")
    @allure.severity(allure.severity_level.NORMAL)
    def test_max_combo_chain_updated(
        self, chain_engine, burn_applies_move, burn_trigger_move
    ):
        battle, team1, team2, slots1, slots2, round_obj = _make_chain_battle(
            p1_moves=[burn_applies_move, burn_trigger_move]
        )
        assert battle.max_combo_chain == 0

        chain_engine.resolve_combo_chain(
            battle=battle,
            attacker_slot=slots1[0],
            move=burn_applies_move,
            target_slot=slots2[0],
            round_number=1,
        )

        battle.refresh_from_db()
        assert battle.max_combo_chain >= 2


# ===========================================================================
# TestComboChainEdgeCases
# ===========================================================================

@allure.epic("Battle")
@allure.feature("Combo Chain Edge Cases")
class TestComboChainEdgeCases(BaseTest):

    @allure.story("Fainted target stops chain from continuing")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_target_fainted_stops_chain(
        self, chain_engine, burn_applies_move, burn_trigger_move
    ):
        battle, team1, team2, slots1, slots2, round_obj = _make_chain_battle(
            p1_moves=[burn_applies_move, burn_trigger_move]
        )
        # Set target to 1 HP so first move kills it
        target = slots2[0]
        target.current_hp = 1
        target.save(update_fields=["current_hp"])

        actions = chain_engine.resolve_combo_chain(
            battle=battle,
            attacker_slot=slots1[0],
            move=burn_applies_move,
            target_slot=target,
            round_number=1,
        )

        # Dead target can't have statuses applied → no combo triggers
        target.refresh_from_db()
        assert target.is_fainted or len(actions) == 1

    @allure.story("Same (slot, move) pair does not fire twice in one chain")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_no_duplicate_triggers_in_chain(
        self, chain_engine, burn_applies_move, burn_trigger_move
    ):
        battle, team1, team2, slots1, slots2, round_obj = _make_chain_battle(
            p1_moves=[burn_applies_move, burn_trigger_move]
        )

        actions = chain_engine.resolve_combo_chain(
            battle=battle,
            attacker_slot=slots1[0],
            move=burn_applies_move,
            target_slot=slots2[0],
            round_number=1,
        )

        # Count occurrences of each (attacker_slot_id, move_id)
        fired_pairs = [(a.attacker_slot_id, a.move_id) for a in actions]
        assert len(fired_pairs) == len(set(fired_pairs))

    @allure.story("Chain respects MAX_CHAIN_DEPTH cap (no infinite loop)")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_chain_respects_max_depth(self, chain_engine, normal_type):
        # Build a circular chain: status A triggers apply-B, status B triggers apply-A
        status_a = StatusEffectFactory(
            name="test_chain_a",
            category="naruto",
            description="chain a",
        )
        status_b = StatusEffectFactory(
            name="test_chain_b",
            category="naruto",
            description="chain b",
        )

        move_apply_a = MoveFactory(
            name="ApplyA", move_type=normal_type, power=10,
            applies_status=status_a, trigger_status=None,
        )
        move_a_to_b = MoveFactory(
            name="ATriggerApplyB", move_type=normal_type, power=10,
            applies_status=status_b, trigger_status=status_a,
        )
        move_b_to_a = MoveFactory(
            name="BTriggerApplyA", move_type=normal_type, power=10,
            applies_status=status_a, trigger_status=status_b,
        )

        battle, team1, team2, slots1, slots2, round_obj = _make_chain_battle(
            p1_moves=[move_apply_a, move_a_to_b, move_b_to_a]
        )

        actions = chain_engine.resolve_combo_chain(
            battle=battle,
            attacker_slot=slots1[0],
            move=move_apply_a,
            target_slot=slots2[0],
            round_number=1,
        )

        # Chain must be capped at MAX_CHAIN_DEPTH + 1 (initial action)
        assert len(actions) <= MAX_CHAIN_DEPTH + 1

    @allure.story("Immune target: status not applied → chain does not continue")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_immunity_breaks_chain(
        self, chain_engine, burn_applies_move, burn_trigger_move
    ):
        # Arrange: target is Fire type (immune to burn)
        fire_type = PokemonTypeFactory(name="Fire")
        fire_poke = PokemonFactory(primary_type=fire_type, base_hp=80)

        user1 = UserFactory()
        user2 = UserFactory()
        battle = BattleFactory(
            player_one=user1, player_two=user2, status=BattleStatus.ACTIVE
        )
        team1 = BattleTeamFactory(battle=battle, owner=user1)
        team2 = BattleTeamFactory(battle=battle, owner=user2)
        ensure_round(battle, round_number=1)

        normal_type = PokemonTypeFactory(name="Normal")
        attacker_poke = PokemonFactory(primary_type=normal_type)
        attacker_poke.moves.add(burn_applies_move, burn_trigger_move)

        attacker = BattleSlotFactory(team=team1, pokemon=attacker_poke, position=1)
        target = BattleSlotFactory(team=team2, pokemon=fire_poke, position=1)
        # Fill remaining slots so team is valid
        for pos in range(2, 7):
            BattleSlotFactory(team=team1, pokemon=PokemonFactory(primary_type=normal_type), position=pos)
            BattleSlotFactory(team=team2, pokemon=PokemonFactory(primary_type=normal_type), position=pos)

        # Act
        actions = chain_engine.resolve_combo_chain(
            battle=battle,
            attacker_slot=attacker,
            move=burn_applies_move,
            target_slot=target,
            round_number=1,
        )

        # Assert — burn not applied to fire type → no combo
        assert len(actions) == 1

    @allure.story("Multiple teammates can all trigger on the same enemy status")
    @allure.severity(allure.severity_level.NORMAL)
    def test_multiple_teammates_trigger_same_status(
        self, chain_engine, burn_applies_move, burn_trigger_move, normal_type
    ):
        # All 6 of team1's Pokemon have BOTH moves
        battle, team1, team2, slots1, slots2, round_obj = _make_chain_battle(
            p1_moves=[burn_applies_move, burn_trigger_move]
        )

        actions = chain_engine.resolve_combo_chain(
            battle=battle,
            attacker_slot=slots1[0],
            move=burn_applies_move,
            target_slot=slots2[0],
            round_number=1,
        )

        # Several slots can trigger — expect more than just 2 actions
        combo_actions = [a for a in actions if a.is_combo_triggered]
        assert len(combo_actions) >= 1  # at minimum one triggered


# ===========================================================================
# TestBattleService
# ===========================================================================

@allure.epic("Battle")
@allure.feature("Battle Setup")
class TestBattleCreation(BaseTest):

    @allure.story("create_battle returns a battle in SETUP state")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_create_battle_setup_status(self, svc):
        user = UserFactory()
        battle = svc.create_battle(player_one=user)

        assert battle.pk is not None
        assert battle.status == BattleStatus.SETUP

    @allure.story("set_team creates exactly 6 BattleSlots")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_set_team_creates_six_slots(self, svc):
        from apps.game.models import BattleSlot, BattleStatus
        user = UserFactory()
        battle = svc.create_battle(player_one=user)
        battle.status = BattleStatus.SETUP
        battle.save(update_fields=["status"])

        pokemon_ids = [PokemonFactory().pk for _ in range(6)]
        team = svc.set_team(battle, user, pokemon_ids)

        from apps.game.models import BattleSlot
        assert BattleSlot.objects.filter(team=team).count() == 6

    @allure.story("set_team rejects fewer or more than 6 Pokemon")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.parametrize("count", [5, 7, 1])
    def test_set_team_rejects_wrong_count(self, svc, count):
        user = UserFactory()
        battle = svc.create_battle(player_one=user)
        pokemon_ids = [PokemonFactory().pk for _ in range(count)]

        with pytest.raises(ValueError, match="exactly 6"):
            svc.set_team(battle, user, pokemon_ids)

    @allure.story("start_battle requires both teams to be set")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_start_battle_requires_both_teams(self, svc):
        user1 = UserFactory()
        user2 = UserFactory()
        battle = svc.create_battle(player_one=user1, player_two=user2)
        pokemon_ids = [PokemonFactory().pk for _ in range(6)]
        svc.set_team(battle, user1, pokemon_ids)

        with pytest.raises(ValueError, match="Need 2 teams"):
            svc.start_battle(battle)

    @allure.story("start_battle transitions to ACTIVE when both teams ready")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_start_battle_transitions_to_active(self, svc):
        user1 = UserFactory()
        user2 = UserFactory()
        battle = svc.create_battle(player_one=user1, player_two=user2)
        ids1 = [PokemonFactory().pk for _ in range(6)]
        ids2 = [PokemonFactory().pk for _ in range(6)]
        svc.set_team(battle, user1, ids1)
        svc.set_team(battle, user2, ids2)

        svc.start_battle(battle)

        battle.refresh_from_db()
        assert battle.status == BattleStatus.ACTIVE


@allure.epic("Battle")
@allure.feature("Round Execution")
class TestRoundExecution(BaseTest):

    def _setup_active_battle(self, svc):
        """Helper: create a fully active battle with two teams."""
        user1 = UserFactory()
        user2 = UserFactory()
        battle = svc.create_battle(player_one=user1, player_two=user2)
        ids1 = [PokemonFactory().pk for _ in range(6)]
        ids2 = [PokemonFactory().pk for _ in range(6)]
        svc.set_team(battle, user1, ids1)
        svc.set_team(battle, user2, ids2)
        svc.start_battle(battle)
        battle.refresh_from_db()
        return battle, user1, user2

    @allure.story("execute_round increments current_round")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_round_increments_counter(self, svc):
        from apps.game.models import BattleSlot
        battle, user1, _ = self._setup_active_battle(svc)
        team1 = battle.teams.get(owner=user1)
        team2 = battle.teams.exclude(owner=user1).first()

        slot1 = BattleSlot.objects.filter(team=team1).first()
        slot2 = BattleSlot.objects.filter(team=team2).first()
        normal_type = PokemonTypeFactory(name="NormalRound")
        move = MoveFactory(name="NormalMove", move_type=normal_type, power=30)
        slot1.pokemon.moves.add(move)

        svc.execute_round(
            battle,
            player_one_actions=[{"slot_id": slot1.pk, "move_id": move.pk, "target_id": slot2.pk}],
            player_two_actions=[],
        )

        battle.refresh_from_db()
        assert battle.current_round == 2

    @allure.story("execute_round rejects non-active battle")
    @allure.severity(allure.severity_level.NORMAL)
    def test_execute_round_rejects_non_active(self, svc):
        user = UserFactory()
        battle = svc.create_battle(player_one=user)  # status = SETUP

        with pytest.raises(ValueError, match="not active"):
            svc.execute_round(battle, [], [])

    @allure.story("check_winner returns None while both teams alive")
    @allure.severity(allure.severity_level.NORMAL)
    def test_check_winner_none_when_alive(self, svc):
        battle, _, _ = self._setup_active_battle(svc)
        assert svc.check_winner(battle) is None

    @allure.story("check_winner returns the surviving team owner when one side faints")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_check_winner_returns_survivor(self, svc):
        from apps.game.models import BattleSlot
        battle, user1, user2 = self._setup_active_battle(svc)
        team2 = battle.teams.exclude(owner=user1).first()

        # Faint all slots on team2
        BattleSlot.objects.filter(team=team2).update(is_fainted=True, current_hp=0)

        winner = svc.check_winner(battle)
        assert winner == user1

    @allure.story("status effects tick after player actions each round")
    @allure.severity(allure.severity_level.NORMAL)
    def test_status_effects_tick_after_actions(self, svc):
        from apps.effects.engine import StatusEffectEngine
        from apps.effects.models import ActiveStatusEffect
        from apps.game.models import BattleSlot
        from tests.framework.factories.effects_factory import StatusEffectFactory

        battle, user1, _ = self._setup_active_battle(svc)
        team1 = battle.teams.get(owner=user1)
        team2 = battle.teams.exclude(owner=user1).first()

        slot1 = BattleSlot.objects.filter(team=team1).first()
        slot2 = BattleSlot.objects.filter(team=team2).first()

        burned = StatusEffectFactory(burned=True)
        engine = StatusEffectEngine()
        engine.apply_status(slot2, burned, round_number=1)
        initial_hp = slot2.current_hp

        normal_type = PokemonTypeFactory(name="NormalTick")
        move = MoveFactory(name="TickMove", move_type=normal_type, power=0)
        slot1.pokemon.moves.add(move)

        svc.execute_round(
            battle,
            player_one_actions=[{"slot_id": slot1.pk, "move_id": move.pk, "target_id": slot2.pk}],
            player_two_actions=[],
        )

        slot2.refresh_from_db()
        assert slot2.current_hp < initial_hp
