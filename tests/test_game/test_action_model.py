"""
Phase 7 — Action model tests (Naruto Online style).

Covers:
  - standard move auto-fires every round (no player selection needed)
  - mystery fires when mystery toggle is True, skipped when False
  - mystery blocked by ACUPUNCTURED → falls back to standard
  - mystery blocked by TAUNTED → falls back to standard
"""
import allure
import pytest

from apps.effects.constants import StatusCategory, StatusName
from apps.effects.models import StatusEffect
from apps.game.services import BattleService
from apps.pokemon.models import MoveSlotType

from tests.framework.base.base_test import BaseTest
from tests.framework.factories.effects_factory import ActiveStatusEffectFactory
from tests.framework.factories.pokemon_factory import MoveFactory, PokemonTypeFactory
from tests.framework.helpers.battle_helpers import build_battle_pair

_svc = BattleService()


def _get_or_create_se(name: str, category: str) -> StatusEffect:
    se, _ = StatusEffect.objects.get_or_create(
        name=name,
        defaults={"category": category, "description": "test"},
    )
    return se


def _normal_type():
    return PokemonTypeFactory(name="Normal")


# ===========================================================================
# TestStandardAutoFires
# ===========================================================================

@allure.epic("Battle")
@allure.feature("Phase 1 — Action Model")
class TestStandardAutoFires(BaseTest):
    """Standard move auto-fires every round, regardless of mystery toggle."""

    @allure.story("Standard move selected when use_mystery=False")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_standard_fires_when_mystery_not_toggled(self):
        # Arrange
        nt = _normal_type()
        standard_move = MoveFactory(
            name="StdAutoFire", move_type=nt, power=60,
            slot_type=MoveSlotType.STANDARD,
        )
        mystery_move = MoveFactory(
            name="MysAutoFire", move_type=nt, power=80,
            slot_type=MoveSlotType.MYSTERY,
        )
        battle, team1, team2, slots1, slots2 = build_battle_pair(
            p1_moves=[standard_move, mystery_move],
        )
        attacker = slots1[0]

        # Act
        actions = _svc.prepare_player_actions(
            battle, team1, {attacker.pk: {"use_mystery": False}}
        )

        # Assert — action uses the standard move
        slot_action = next((a for a in actions if a["slot_id"] == attacker.pk), None)
        assert slot_action is not None
        assert slot_action["move_id"] == standard_move.pk

    @allure.story("Standard move selected when slot not in submission (implicit default)")
    @allure.severity(allure.severity_level.NORMAL)
    def test_standard_fires_with_empty_submission(self):
        # Arrange
        nt = _normal_type()
        standard_move = MoveFactory(
            name="StdEmptySub", move_type=nt, power=60,
            slot_type=MoveSlotType.STANDARD,
        )
        battle, team1, team2, slots1, slots2 = build_battle_pair(
            p1_moves=[standard_move],
        )
        attacker = slots1[0]

        # Act — empty submission dict, slot not listed
        actions = _svc.prepare_player_actions(battle, team1, {})

        # Assert
        slot_action = next((a for a in actions if a["slot_id"] == attacker.pk), None)
        assert slot_action is not None
        assert slot_action["move_id"] == standard_move.pk

    @allure.story("All six active slots produce an action when none submit mystery toggle")
    @allure.severity(allure.severity_level.NORMAL)
    def test_all_slots_get_actions_by_default(self):
        # Arrange
        nt = _normal_type()
        standard_move = MoveFactory(
            name="StdAllSlots", move_type=nt, power=60,
            slot_type=MoveSlotType.STANDARD,
        )
        battle, team1, team2, slots1, slots2 = build_battle_pair(
            p1_moves=[standard_move],
        )

        # Act
        actions = _svc.prepare_player_actions(battle, team1, {})

        # Assert — one action per active slot (6 by default)
        assert len(actions) == 6


# ===========================================================================
# TestMysteryToggle
# ===========================================================================

@allure.epic("Battle")
@allure.feature("Phase 1 — Action Model")
class TestMysteryToggle(BaseTest):
    """Mystery move fires when toggle is True; falls back to standard when False."""

    @allure.story("Mystery move selected when use_mystery=True and move available")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_mystery_fires_when_toggle_true(self):
        # Arrange
        nt = _normal_type()
        standard_move = MoveFactory(
            name="StdToggleOn", move_type=nt, power=60,
            slot_type=MoveSlotType.STANDARD,
        )
        mystery_move = MoveFactory(
            name="MysToggleOn", move_type=nt, power=80,
            slot_type=MoveSlotType.MYSTERY,
        )
        battle, team1, team2, slots1, slots2 = build_battle_pair(
            p1_moves=[standard_move, mystery_move],
        )
        attacker = slots1[0]

        # Act
        actions = _svc.prepare_player_actions(
            battle, team1, {attacker.pk: {"use_mystery": True}}
        )

        # Assert — mystery move was selected
        slot_action = next((a for a in actions if a["slot_id"] == attacker.pk), None)
        assert slot_action is not None
        assert slot_action["move_id"] == mystery_move.pk

    @allure.story("Falls back to standard when use_mystery=False despite mystery being available")
    @allure.severity(allure.severity_level.NORMAL)
    def test_falls_back_to_standard_when_toggle_false(self):
        # Arrange
        nt = _normal_type()
        standard_move = MoveFactory(
            name="StdFallback", move_type=nt, power=60,
            slot_type=MoveSlotType.STANDARD,
        )
        mystery_move = MoveFactory(
            name="MysFallback", move_type=nt, power=80,
            slot_type=MoveSlotType.MYSTERY,
        )
        battle, team1, team2, slots1, slots2 = build_battle_pair(
            p1_moves=[standard_move, mystery_move],
        )
        attacker = slots1[0]

        # Act
        actions = _svc.prepare_player_actions(
            battle, team1, {attacker.pk: {"use_mystery": False}}
        )

        # Assert — standard move used, not mystery
        slot_action = next((a for a in actions if a["slot_id"] == attacker.pk), None)
        assert slot_action is not None
        assert slot_action["move_id"] == standard_move.pk


# ===========================================================================
# TestMysteryBlockedByStatus
# ===========================================================================

@allure.epic("Battle")
@allure.feature("Phase 1 — Action Model")
class TestMysteryBlockedByStatus(BaseTest):
    """Mystery is blocked by ACUPUNCTURED or TAUNTED; falls back to standard."""

    @allure.story("ACUPUNCTURED blocks mystery move — standard used instead")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_acupunctured_blocks_mystery(self):
        # Arrange
        acupunctured_se = _get_or_create_se(
            StatusName.ACUPUNCTURED, StatusCategory.NARUTO
        )
        nt = _normal_type()
        standard_move = MoveFactory(
            name="StdAcupu", move_type=nt, power=60,
            slot_type=MoveSlotType.STANDARD,
        )
        mystery_move = MoveFactory(
            name="MysAcupu", move_type=nt, power=80,
            slot_type=MoveSlotType.MYSTERY,
        )
        battle, team1, team2, slots1, slots2 = build_battle_pair(
            p1_moves=[standard_move, mystery_move],
        )
        attacker = slots1[0]
        ActiveStatusEffectFactory(slot=attacker, status=acupunctured_se)

        # Act — player requests mystery but slot is ACUPUNCTURED
        actions = _svc.prepare_player_actions(
            battle, team1, {attacker.pk: {"use_mystery": True}}
        )

        # Assert — standard used, not mystery
        slot_action = next((a for a in actions if a["slot_id"] == attacker.pk), None)
        assert slot_action is not None
        assert slot_action["move_id"] == standard_move.pk

    @allure.story("TAUNTED blocks mystery move — standard used instead")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_taunted_blocks_mystery(self):
        # Arrange
        taunted_se = _get_or_create_se(StatusName.TAUNTED, StatusCategory.VOLATILE)
        nt = _normal_type()
        standard_move = MoveFactory(
            name="StdTaunt", move_type=nt, power=60,
            slot_type=MoveSlotType.STANDARD,
        )
        mystery_move = MoveFactory(
            name="MysTaunt", move_type=nt, power=80,
            slot_type=MoveSlotType.MYSTERY,
        )
        battle, team1, team2, slots1, slots2 = build_battle_pair(
            p1_moves=[standard_move, mystery_move],
        )
        attacker = slots1[0]
        ActiveStatusEffectFactory(slot=attacker, status=taunted_se)

        # Act
        actions = _svc.prepare_player_actions(
            battle, team1, {attacker.pk: {"use_mystery": True}}
        )

        # Assert
        slot_action = next((a for a in actions if a["slot_id"] == attacker.pk), None)
        assert slot_action is not None
        assert slot_action["move_id"] == standard_move.pk

    @allure.story("Mystery fires normally when neither ACUPUNCTURED nor TAUNTED")
    @allure.severity(allure.severity_level.NORMAL)
    def test_mystery_fires_without_blocking_status(self):
        # Arrange — no blocking status applied
        nt = _normal_type()
        standard_move = MoveFactory(
            name="StdNoBlock", move_type=nt, power=60,
            slot_type=MoveSlotType.STANDARD,
        )
        mystery_move = MoveFactory(
            name="MysNoBlock", move_type=nt, power=80,
            slot_type=MoveSlotType.MYSTERY,
        )
        battle, team1, team2, slots1, slots2 = build_battle_pair(
            p1_moves=[standard_move, mystery_move],
        )
        attacker = slots1[0]

        # Act — no blocking status, mystery toggle on
        actions = _svc.prepare_player_actions(
            battle, team1, {attacker.pk: {"use_mystery": True}}
        )

        # Assert — mystery fires
        slot_action = next((a for a in actions if a["slot_id"] == attacker.pk), None)
        assert slot_action is not None
        assert slot_action["move_id"] == mystery_move.pk
