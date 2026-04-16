"""
Phase 7 — Phase 6 mechanic integration tests (ComboChainEngine layer).

Covers:
  - SHIELDED absorbs hit, shield removed, second hit lands
  - HIDDEN excluded from _select_target
  - IMMUNE blocks status application
  - CHAIN_BREAKER halts combo chain
  - chase_condition restricts combo trigger to matching physical state
  - AIRBORNE → LAUNCHED auto-transition on damage
  - STATE_LOCKED prevents AIRBORNE → LAUNCHED transition
  - KNOCKBACK shifts grid position front→back
"""
import allure
import pytest

from apps.effects.constants import StatusCategory, StatusName
from apps.effects.engine import StatusEffectEngine
from apps.effects.models import StatusEffect
from apps.game.models import BattleLog, GridPosition, LogType
from apps.game.services import ComboChainEngine

from tests.framework.base.base_test import BaseTest
from tests.framework.factories.effects_factory import (
    ActiveStatusEffectFactory,
    StatusEffectFactory,
)
from tests.framework.factories.pokemon_factory import MoveFactory, PokemonTypeFactory
from tests.framework.helpers.battle_helpers import build_battle_pair, ensure_round

_engine = StatusEffectEngine()
_chain = ComboChainEngine()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_or_create_se(name: str, category: str) -> StatusEffect:
    se, _ = StatusEffect.objects.get_or_create(
        name=name,
        defaults={"category": category, "description": "test"},
    )
    return se


def _minimal_battle():
    """Return (battle, team1, team2, slot1, slot2, round_obj) with 6 slots each."""
    battle, team1, team2, slots1, slots2 = build_battle_pair()
    round_obj = ensure_round(battle, round_number=1)
    return battle, team1, team2, slots1, slots2, round_obj


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def normal_type():
    return PokemonTypeFactory(name="Normal")


@pytest.fixture()
def burn_status():
    return StatusEffectFactory(burned=True)


@pytest.fixture()
def airborne_se():
    return _get_or_create_se(StatusName.AIRBORNE, StatusCategory.PHYSICAL)


@pytest.fixture()
def launched_se():
    return _get_or_create_se(StatusName.LAUNCHED, StatusCategory.PHYSICAL)


@pytest.fixture()
def knockback_se():
    return _get_or_create_se(StatusName.KNOCKBACK, StatusCategory.PHYSICAL)


@pytest.fixture()
def shielded_se():
    return _get_or_create_se(StatusName.SHIELDED, StatusCategory.UTILITY)


@pytest.fixture()
def hidden_se():
    return _get_or_create_se(StatusName.HIDDEN, StatusCategory.UTILITY)


@pytest.fixture()
def immune_se():
    return _get_or_create_se(StatusName.IMMUNE, StatusCategory.UTILITY)


@pytest.fixture()
def chain_breaker_se():
    return _get_or_create_se(StatusName.CHAIN_BREAKER, StatusCategory.ADVANCED)


@pytest.fixture()
def state_locked_se():
    return _get_or_create_se(StatusName.STATE_LOCKED, StatusCategory.ADVANCED)


# ===========================================================================
# TestShielded
# ===========================================================================

@allure.epic("Battle")
@allure.feature("Phase 6 — Shield")
class TestShielded(BaseTest):

    @allure.story("SHIELDED absorbs one hit: damage = 0")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_shield_absorbs_hit_no_damage(self, normal_type, shielded_se):
        # Arrange
        battle, team1, team2, slots1, slots2, round_obj = _minimal_battle()
        attacker = slots1[0]
        target = slots2[0]
        initial_hp = target.current_hp

        move = MoveFactory(name="ShieldTest", move_type=normal_type, power=80)
        ActiveStatusEffectFactory(slot=target, status=shielded_se)

        # Act
        action = _chain._execute_move(
            round_obj=round_obj,
            attacker_slot=attacker,
            move=move,
            target_slot=target,
            chain_position=0,
            is_combo=False,
        )

        # Assert — zero damage, HP unchanged
        target.refresh_from_db()
        assert action.damage_dealt == 0
        assert target.current_hp == initial_hp

    @allure.story("SHIELDED is removed after absorbing a hit")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_shield_consumed_after_hit(self, normal_type, shielded_se):
        # Arrange
        battle, team1, team2, slots1, slots2, round_obj = _minimal_battle()
        attacker = slots1[0]
        target = slots2[0]
        move = MoveFactory(name="ConsumeShield", move_type=normal_type, power=60)
        ActiveStatusEffectFactory(slot=target, status=shielded_se)

        # Act
        _chain._execute_move(
            round_obj=round_obj,
            attacker_slot=attacker,
            move=move,
            target_slot=target,
            chain_position=0,
            is_combo=False,
        )

        # Assert
        assert not _engine.has_status(target, StatusName.SHIELDED)

    @allure.story("Second hit after shield consumed deals damage")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_second_hit_after_shield_deals_damage(self, normal_type, shielded_se):
        # Arrange
        battle, team1, team2, slots1, slots2, round_obj = _minimal_battle()
        attacker = slots1[0]
        target = slots2[0]
        move = MoveFactory(name="PostShield", move_type=normal_type, power=60)
        ActiveStatusEffectFactory(slot=target, status=shielded_se)

        # First hit — absorbed
        _chain._execute_move(
            round_obj=round_obj,
            attacker_slot=attacker,
            move=move,
            target_slot=target,
            chain_position=0,
            is_combo=False,
        )
        hp_after_shield = target.current_hp

        # Act — second hit (no shield)
        _chain._execute_move(
            round_obj=round_obj,
            attacker_slot=attacker,
            move=move,
            target_slot=target,
            chain_position=0,
            is_combo=False,
        )
        target.refresh_from_db()

        # Assert — HP decreased
        assert target.current_hp < hp_after_shield


# ===========================================================================
# TestHidden
# ===========================================================================

@allure.epic("Battle")
@allure.feature("Phase 6 — Hidden")
class TestHidden(BaseTest):

    @allure.story("HIDDEN slot is excluded from _select_target")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_hidden_slot_not_targeted(self, normal_type, hidden_se):
        # Arrange — 2-slot enemy team; first slot is HIDDEN
        battle, team1, team2, slots1, slots2, round_obj = _minimal_battle()
        move = MoveFactory(name="Target", move_type=normal_type, power=60)

        # Apply HIDDEN to ALL enemy slots to confirm None is returned when all hidden
        for s in slots2:
            ActiveStatusEffectFactory(slot=s, status=hidden_se)

        # Act
        target = _chain._select_target(team2, move)

        # Assert — no valid target
        assert target is None

    @allure.story("Non-hidden slot is selected when HIDDEN slot is present")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_non_hidden_slot_selected(self, normal_type, hidden_se):
        # Arrange — 6-slot team; all but last slot hidden
        battle, team1, team2, slots1, slots2, round_obj = _minimal_battle()
        move = MoveFactory(name="TargetVisible", move_type=normal_type, power=60)

        # Hide all front-row slots (positions 1-3 map to front row)
        # slots2 has positions 1-6; slots2[0..2] are front row
        for s in slots2[:5]:
            ActiveStatusEffectFactory(slot=s, status=hidden_se)

        # Act
        target = _chain._select_target(team2, move)

        # Assert — visible slot selected
        assert target is not None
        assert target.pk == slots2[5].pk


# ===========================================================================
# TestImmune
# ===========================================================================

@allure.epic("Battle")
@allure.feature("Phase 6 — Immune")
class TestImmune(BaseTest):

    @allure.story("IMMUNE prevents status application")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_immune_blocks_status(self, normal_type, immune_se, burn_status):
        # Arrange
        battle, team1, team2, slots1, slots2, round_obj = _minimal_battle()
        attacker = slots1[0]
        target = slots2[0]
        move = MoveFactory(
            name="BurnMove",
            move_type=normal_type,
            power=60,
            applies_status=burn_status,
        )
        ActiveStatusEffectFactory(slot=target, status=immune_se)

        # Act
        action = _chain._execute_move(
            round_obj=round_obj,
            attacker_slot=attacker,
            move=move,
            target_slot=target,
            chain_position=0,
            is_combo=False,
        )

        # Assert — no status applied, action records None
        assert action.status_applied is None
        assert not _engine.has_status(target, StatusName.BURNED)

    @allure.story("IMMUNE creates BattleLog immunity message")
    @allure.severity(allure.severity_level.NORMAL)
    def test_immune_logs_message(self, normal_type, immune_se, burn_status):
        # Arrange
        battle, team1, team2, slots1, slots2, round_obj = _minimal_battle()
        attacker = slots1[0]
        target = slots2[0]
        move = MoveFactory(
            name="BurnMoveLog",
            move_type=normal_type,
            power=60,
            applies_status=burn_status,
        )
        ActiveStatusEffectFactory(slot=target, status=immune_se)

        # Act
        _chain._execute_move(
            round_obj=round_obj,
            attacker_slot=attacker,
            move=move,
            target_slot=target,
            chain_position=0,
            is_combo=False,
        )

        # Assert — log entry contains "immune"
        immune_log = BattleLog.objects.filter(
            battle=battle,
            log_type=LogType.STATUS,
            message__icontains="immune",
        ).first()
        assert immune_log is not None


# ===========================================================================
# TestChainBreaker
# ===========================================================================

@allure.epic("Battle")
@allure.feature("Phase 6 — Chain Breaker")
class TestChainBreaker(BaseTest):

    @allure.story("CHAIN_BREAKER stops combo chain after hit on that target")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_chain_breaker_stops_chain(self, normal_type, chain_breaker_se):
        # Arrange — 3-link chain setup: move A applies burn, move B triggers on burn
        burn = StatusEffectFactory(burned=True)
        move_a = MoveFactory(
            name="ApplyBurnCB",
            move_type=normal_type,
            power=60,
            applies_status=burn,
            trigger_status=None,
        )
        move_b = MoveFactory(
            name="TriggerBurnCB",
            move_type=normal_type,
            power=60,
            applies_status=None,
            trigger_status=burn,
        )

        battle, team1, team2, slots1, slots2 = build_battle_pair(
            p1_moves=[move_a, move_b],
        )
        ensure_round(battle, round_number=1)
        attacker = slots1[0]
        target = slots2[0]

        # Apply CHAIN_BREAKER to target BEFORE the chain fires
        ActiveStatusEffectFactory(slot=target, status=chain_breaker_se)

        # Act — resolve full chain
        actions = _chain.resolve_combo_chain(
            battle=battle,
            attacker_slot=attacker,
            move=move_a,
            target_slot=target,
            round_number=1,
        )

        # Assert — chain stopped after first combo link.
        # Per spec: the hit on the CHAIN_BREAKER target still lands, then the chain halts.
        # action[0] = move_a (initial), action[1] = move_b (fired before chain is broken).
        # No further links beyond that.
        assert len(actions) == 2

    @allure.story("Hit still lands on CHAIN_BREAKER target before chain stops")
    @allure.severity(allure.severity_level.NORMAL)
    def test_chain_breaker_hit_still_deals_damage(self, normal_type, chain_breaker_se):
        # Arrange — a move with trigger_status already on target to ensure chain enters loop
        burn = StatusEffectFactory(burned=True)
        move_b = MoveFactory(
            name="TriggerBurnDmg",
            move_type=normal_type,
            power=60,
            applies_status=None,
            trigger_status=burn,
        )
        # Pre-apply burn to target so move_b fires immediately
        battle, team1, team2, slots1, slots2 = build_battle_pair(
            p1_moves=[move_b],
        )
        ensure_round(battle, round_number=1)
        attacker = slots1[0]
        target = slots2[0]
        initial_hp = target.current_hp

        # Pre-apply burn so the trigger condition is met
        ActiveStatusEffectFactory(slot=target, status=burn)
        ActiveStatusEffectFactory(slot=target, status=chain_breaker_se)

        # Act
        _chain.resolve_combo_chain(
            battle=battle,
            attacker_slot=attacker,
            move=move_b,
            target_slot=target,
            round_number=1,
        )

        # Assert — initial move dealt damage (target HP reduced)
        target.refresh_from_db()
        assert target.current_hp < initial_hp


# ===========================================================================
# TestChaseCondition
# ===========================================================================

@allure.epic("Battle")
@allure.feature("Phase 6 — Chase Condition")
class TestChaseCondition(BaseTest):

    @allure.story("Chase move with AIRBORNE condition fires when target is AIRBORNE")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_airborne_chase_fires_on_airborne_target(
        self, normal_type, airborne_se, burn_status
    ):
        # Arrange — move_a applies burn, move_b triggers on burn AND has AIRBORNE chase_condition
        move_a = MoveFactory(
            name="ApplyBurnAir",
            move_type=normal_type,
            power=60,
            applies_status=burn_status,
        )
        move_b = MoveFactory(
            name="AirChase",
            move_type=normal_type,
            power=60,
            trigger_status=burn_status,
            chase_condition=StatusName.AIRBORNE,
        )
        battle, team1, team2, slots1, slots2 = build_battle_pair(
            p1_moves=[move_a, move_b],
        )
        ensure_round(battle, round_number=1)
        attacker = slots1[0]
        target = slots2[0]

        # Put target in AIRBORNE state
        ActiveStatusEffectFactory(slot=target, status=airborne_se)

        # Act
        actions = _chain.resolve_combo_chain(
            battle=battle,
            attacker_slot=attacker,
            move=move_a,
            target_slot=target,
            round_number=1,
        )

        # Assert — chase fired (chain length > 1)
        assert len(actions) >= 2

    @allure.story("Chase move with AIRBORNE condition skipped when target is not AIRBORNE")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_airborne_chase_skipped_when_not_airborne(self, normal_type, burn_status):
        # Arrange — same setup, but target is NOT airborne (grounded by default)
        move_a = MoveFactory(
            name="ApplyBurnGnd",
            move_type=normal_type,
            power=60,
            applies_status=burn_status,
        )
        move_b = MoveFactory(
            name="AirChaseSkip",
            move_type=normal_type,
            power=60,
            trigger_status=burn_status,
            chase_condition=StatusName.AIRBORNE,
        )
        battle, team1, team2, slots1, slots2 = build_battle_pair(
            p1_moves=[move_a, move_b],
        )
        ensure_round(battle, round_number=1)
        attacker = slots1[0]
        target = slots2[0]

        # Target is grounded (no physical status applied)

        # Act
        actions = _chain.resolve_combo_chain(
            battle=battle,
            attacker_slot=attacker,
            move=move_a,
            target_slot=target,
            round_number=1,
        )

        # Assert — only initial move fired
        assert len(actions) == 1

    @allure.story("Chase move with GROUNDED condition fires when target is grounded")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_grounded_chase_fires_on_grounded_target(self, normal_type, burn_status):
        move_a = MoveFactory(
            name="ApplyBurnGrd",
            move_type=normal_type,
            power=60,
            applies_status=burn_status,
        )
        move_b = MoveFactory(
            name="GrdChase",
            move_type=normal_type,
            power=60,
            trigger_status=burn_status,
            chase_condition=StatusName.GROUNDED,
        )
        battle, team1, team2, slots1, slots2 = build_battle_pair(
            p1_moves=[move_a, move_b],
        )
        ensure_round(battle, round_number=1)
        attacker = slots1[0]
        target = slots2[0]

        # Target is grounded (implicit, no physical state)
        actions = _chain.resolve_combo_chain(
            battle=battle,
            attacker_slot=attacker,
            move=move_a,
            target_slot=target,
            round_number=1,
        )

        assert len(actions) >= 2

    @allure.story("Chase move with GROUNDED condition skipped when target is AIRBORNE")
    @allure.severity(allure.severity_level.NORMAL)
    def test_grounded_chase_skipped_when_airborne(
        self, normal_type, burn_status, airborne_se
    ):
        move_a = MoveFactory(
            name="ApplyBurnGrd2",
            move_type=normal_type,
            power=60,
            applies_status=burn_status,
        )
        move_b = MoveFactory(
            name="GrdChaseSkip",
            move_type=normal_type,
            power=60,
            trigger_status=burn_status,
            chase_condition=StatusName.GROUNDED,
        )
        battle, team1, team2, slots1, slots2 = build_battle_pair(
            p1_moves=[move_a, move_b],
        )
        ensure_round(battle, round_number=1)
        attacker = slots1[0]
        target = slots2[0]

        # Put target AIRBORNE — violates GROUNDED condition
        ActiveStatusEffectFactory(slot=target, status=airborne_se)

        actions = _chain.resolve_combo_chain(
            battle=battle,
            attacker_slot=attacker,
            move=move_a,
            target_slot=target,
            round_number=1,
        )

        assert len(actions) == 1

    @allure.story("Chase move with LAUNCHED condition fires when target is LAUNCHED")
    @allure.severity(allure.severity_level.NORMAL)
    def test_launched_chase_fires_on_launched_target(
        self, normal_type, burn_status, launched_se
    ):
        move_a = MoveFactory(
            name="ApplyBurnLnch",
            move_type=normal_type,
            power=60,
            applies_status=burn_status,
        )
        move_b = MoveFactory(
            name="LaunchChase",
            move_type=normal_type,
            power=60,
            trigger_status=burn_status,
            chase_condition=StatusName.LAUNCHED,
        )
        battle, team1, team2, slots1, slots2 = build_battle_pair(
            p1_moves=[move_a, move_b],
        )
        ensure_round(battle, round_number=1)
        attacker = slots1[0]
        target = slots2[0]

        ActiveStatusEffectFactory(slot=target, status=launched_se, remaining_turns=1)

        actions = _chain.resolve_combo_chain(
            battle=battle,
            attacker_slot=attacker,
            move=move_a,
            target_slot=target,
            round_number=1,
        )

        assert len(actions) >= 2


# ===========================================================================
# TestAirborneToLaunched
# ===========================================================================

@allure.epic("Battle")
@allure.feature("Phase 6 — Airborne Transition")
class TestAirborneToLaunched(BaseTest):

    @allure.story("Taking damage while AIRBORNE auto-transitions to LAUNCHED")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_airborne_becomes_launched_on_damage(self, normal_type, airborne_se):
        # Arrange
        battle, team1, team2, slots1, slots2, round_obj = _minimal_battle()
        # Create and load the LAUNCHED StatusEffect so the transition can fire
        _get_or_create_se(StatusName.LAUNCHED, StatusCategory.PHYSICAL)
        attacker = slots1[0]
        target = slots2[0]
        move = MoveFactory(name="HitAirborne", move_type=normal_type, power=60)
        ActiveStatusEffectFactory(slot=target, status=airborne_se)

        # Act
        _chain._execute_move(
            round_obj=round_obj,
            attacker_slot=attacker,
            move=move,
            target_slot=target,
            chain_position=0,
            is_combo=False,
        )

        # Assert
        assert not _engine.has_status(target, StatusName.AIRBORNE)
        assert _engine.has_status(target, StatusName.LAUNCHED)

    @allure.story("LAUNCHED BattleLog message created on transition")
    @allure.severity(allure.severity_level.NORMAL)
    def test_airborne_to_launched_logs_message(self, normal_type, airborne_se):
        # Arrange
        battle, team1, team2, slots1, slots2, round_obj = _minimal_battle()
        _get_or_create_se(StatusName.LAUNCHED, StatusCategory.PHYSICAL)
        attacker = slots1[0]
        target = slots2[0]
        move = MoveFactory(name="HitAirLog", move_type=normal_type, power=60)
        ActiveStatusEffectFactory(slot=target, status=airborne_se)

        # Act
        _chain._execute_move(
            round_obj=round_obj,
            attacker_slot=attacker,
            move=move,
            target_slot=target,
            chain_position=0,
            is_combo=False,
        )

        # Assert — "Launched" in logs
        launched_log = BattleLog.objects.filter(
            battle=battle,
            log_type=LogType.STATUS,
            message__icontains="Launched",
        ).first()
        assert launched_log is not None

    @allure.story("STATE_LOCKED prevents AIRBORNE → LAUNCHED transition")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_state_locked_prevents_transition(
        self, normal_type, airborne_se, state_locked_se
    ):
        # Arrange
        battle, team1, team2, slots1, slots2, round_obj = _minimal_battle()
        _get_or_create_se(StatusName.LAUNCHED, StatusCategory.PHYSICAL)
        attacker = slots1[0]
        target = slots2[0]
        move = MoveFactory(name="HitLocked", move_type=normal_type, power=60)
        ActiveStatusEffectFactory(slot=target, status=airborne_se)
        ActiveStatusEffectFactory(slot=target, status=state_locked_se, remaining_turns=2)

        # Act
        _chain._execute_move(
            round_obj=round_obj,
            attacker_slot=attacker,
            move=move,
            target_slot=target,
            chain_position=0,
            is_combo=False,
        )

        # Assert — AIRBORNE remains, LAUNCHED not applied
        assert _engine.has_status(target, StatusName.AIRBORNE)
        assert not _engine.has_status(target, StatusName.LAUNCHED)


# ===========================================================================
# TestKnockbackPosition
# ===========================================================================

@allure.epic("Battle")
@allure.feature("Phase 6 — Knockback")
class TestKnockbackPosition(BaseTest):

    @allure.story("KNOCKBACK moves FRONT_LEFT slot to BACK_LEFT")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_knockback_front_left_to_back_left(self, normal_type):
        # Arrange
        battle, team1, team2, slots1, slots2, round_obj = _minimal_battle()
        knockback_se = _get_or_create_se(StatusName.KNOCKBACK, StatusCategory.PHYSICAL)
        attacker = slots1[0]
        target = slots2[0]
        target.grid_position = GridPosition.FRONT_LEFT
        target.save(update_fields=["grid_position"])

        move = MoveFactory(
            name="KBLeft",
            move_type=normal_type,
            power=60,
            applies_status=knockback_se,
        )

        # Act
        _chain._execute_move(
            round_obj=round_obj,
            attacker_slot=attacker,
            move=move,
            target_slot=target,
            chain_position=0,
            is_combo=False,
        )

        # Assert
        target.refresh_from_db()
        assert target.grid_position == GridPosition.BACK_LEFT

    @allure.story("KNOCKBACK moves FRONT_RIGHT slot to BACK_RIGHT")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_knockback_front_right_to_back_right(self, normal_type):
        battle, team1, team2, slots1, slots2, round_obj = _minimal_battle()
        knockback_se = _get_or_create_se(StatusName.KNOCKBACK, StatusCategory.PHYSICAL)
        attacker = slots1[0]
        target = slots2[2]
        target.grid_position = GridPosition.FRONT_RIGHT
        target.save(update_fields=["grid_position"])

        move = MoveFactory(
            name="KBRight",
            move_type=normal_type,
            power=60,
            applies_status=knockback_se,
        )

        _chain._execute_move(
            round_obj=round_obj,
            attacker_slot=attacker,
            move=move,
            target_slot=target,
            chain_position=0,
            is_combo=False,
        )

        target.refresh_from_db()
        assert target.grid_position == GridPosition.BACK_RIGHT

    @allure.story("KNOCKBACK moves FRONT_CENTER slot to BACK_CENTER")
    @allure.severity(allure.severity_level.NORMAL)
    def test_knockback_front_center_to_back_center(self, normal_type):
        battle, team1, team2, slots1, slots2, round_obj = _minimal_battle()
        knockback_se = _get_or_create_se(StatusName.KNOCKBACK, StatusCategory.PHYSICAL)
        attacker = slots1[0]
        target = slots2[1]
        target.grid_position = GridPosition.FRONT_CENTER
        target.save(update_fields=["grid_position"])

        move = MoveFactory(
            name="KBCenter",
            move_type=normal_type,
            power=60,
            applies_status=knockback_se,
        )

        _chain._execute_move(
            round_obj=round_obj,
            attacker_slot=attacker,
            move=move,
            target_slot=target,
            chain_position=0,
            is_combo=False,
        )

        target.refresh_from_db()
        assert target.grid_position == GridPosition.BACK_CENTER

    @allure.story("KNOCKBACK on back-row slot leaves position unchanged")
    @allure.severity(allure.severity_level.NORMAL)
    def test_knockback_back_row_slot_unchanged(self, normal_type):
        battle, team1, team2, slots1, slots2, round_obj = _minimal_battle()
        knockback_se = _get_or_create_se(StatusName.KNOCKBACK, StatusCategory.PHYSICAL)
        attacker = slots1[0]
        target = slots2[3]
        target.grid_position = GridPosition.BACK_LEFT
        target.save(update_fields=["grid_position"])

        move = MoveFactory(
            name="KBBackRow",
            move_type=normal_type,
            power=60,
            applies_status=knockback_se,
        )

        _chain._execute_move(
            round_obj=round_obj,
            attacker_slot=attacker,
            move=move,
            target_slot=target,
            chain_position=0,
            is_combo=False,
        )

        target.refresh_from_db()
        assert target.grid_position == GridPosition.BACK_LEFT
