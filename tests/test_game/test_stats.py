"""
Phase 7 — Control + Penetration stat tests.

Covers:
  - control formula: success_prob = control / (control + control_resist * 1000)
    - control_resist=0 → status always applies (prob=1.0)
    - very low control vs high control_resist → status almost never applies
  - penetration: effective_defense = defense * (1 - penetration)
    - higher penetration → higher damage dealt
    - zero penetration uses full defense
"""
from unittest.mock import patch

import allure
import pytest

from apps.effects.constants import StatusCategory, StatusName
from apps.effects.models import StatusEffect
from apps.game.models import BattleAction
from apps.game.services import ComboChainEngine

from tests.framework.base.base_test import BaseTest
from tests.framework.factories.effects_factory import StatusEffectFactory
from tests.framework.factories.pokemon_factory import MoveFactory, PokemonTypeFactory
from tests.framework.helpers.battle_helpers import build_battle_pair, ensure_round

_chain = ComboChainEngine()


def _get_or_create_se(name: str, category: str) -> StatusEffect:
    se, _ = StatusEffect.objects.get_or_create(
        name=name,
        defaults={"category": category, "description": "test"},
    )
    return se


def _minimal_battle():
    """Return (battle, team1, team2, slots1, slots2, round_obj)."""
    battle, team1, team2, slots1, slots2 = build_battle_pair()
    round_obj = ensure_round(battle, round_number=1)
    return battle, team1, team2, slots1, slots2, round_obj


# ===========================================================================
# TestControlFormula
# ===========================================================================

@allure.epic("Battle")
@allure.feature("Phase 3 — Control Stat")
class TestControlFormula(BaseTest):
    """
    CC resist formula: success_prob = control / (control + control_resist * 1000).

    - control_resist=0 → prob=1.0 → status always applied
    - control_resist=1000 with default control=100 → prob≈0.0001 → almost never
    """

    @allure.story("control_resist=0 — status always applied (prob=1.0)")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_status_always_applies_when_control_resist_zero(self):
        # Arrange
        burn_se = StatusEffectFactory(burned=True)
        nt = PokemonTypeFactory(name="Normal")
        move = MoveFactory(
            name="BurnCtrl0", move_type=nt, power=60, applies_status=burn_se,
        )
        battle, team1, team2, slots1, slots2, round_obj = _minimal_battle()
        attacker = slots1[0]
        target = slots2[0]

        # control_resist=0 → denominator = control + 0 = control → prob = 1.0
        attacker.control = 100.0
        attacker.save(update_fields=["control"])
        target.control_resist = 0.0
        target.save(update_fields=["control_resist"])

        # Act — patch random so critical hit / damage roll is deterministic
        with patch("apps.game.services.random.random", return_value=0.5):
            with patch("apps.game.services.random.randint", return_value=100):
                action = _chain._execute_move(
                    round_obj=round_obj,
                    attacker_slot=attacker,
                    move=move,
                    target_slot=target,
                    chain_position=0,
                    is_combo=False,
                )

        # Assert — status applied
        assert action.status_applied is not None
        assert action.status_applied.name == StatusName.BURNED

    @allure.story("status resisted when random >= success_prob (high control_resist)")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_status_resisted_when_random_above_prob(self):
        """
        With control=1.0 and control_resist=1.0:
        success_prob = 1.0 / (1.0 + 1.0 * 1000) = 1/1001 ≈ 0.001.
        Patching random.random to return 0.5 → 0.5 >= 0.001 → resisted.
        """
        # Arrange
        burn_se = StatusEffectFactory(burned=True)
        nt = PokemonTypeFactory(name="Normal")
        move = MoveFactory(
            name="BurnCtrlHigh", move_type=nt, power=60, applies_status=burn_se,
        )
        battle, team1, team2, slots1, slots2, round_obj = _minimal_battle()
        attacker = slots1[0]
        target = slots2[0]

        attacker.control = 1.0
        attacker.save(update_fields=["control"])
        target.control_resist = 1.0
        target.save(update_fields=["control_resist"])

        # Act — random=0.5 → resisted (0.5 >= 0.001)
        with patch("apps.game.services.random.random", return_value=0.5):
            with patch("apps.game.services.random.randint", return_value=100):
                action = _chain._execute_move(
                    round_obj=round_obj,
                    attacker_slot=attacker,
                    move=move,
                    target_slot=target,
                    chain_position=0,
                    is_combo=False,
                )

        # Assert — status NOT applied
        from apps.effects.engine import StatusEffectEngine
        engine = StatusEffectEngine()
        assert action.status_applied is None
        assert not engine.has_status(target, StatusName.BURNED)

    @allure.story("status applies when random < success_prob (moderate control_resist)")
    @allure.severity(allure.severity_level.NORMAL)
    def test_status_applies_when_random_below_prob(self):
        """
        With control=100 and control_resist=0 → prob=1.0.
        Patching random to return 0.0 → 0.0 < 1.0 → applied.
        """
        # Arrange
        burn_se = StatusEffectFactory(burned=True)
        nt = PokemonTypeFactory(name="Normal")
        move = MoveFactory(
            name="BurnCtrlApply", move_type=nt, power=60, applies_status=burn_se,
        )
        battle, team1, team2, slots1, slots2, round_obj = _minimal_battle()
        attacker = slots1[0]
        target = slots2[0]

        attacker.control = 100.0
        attacker.save(update_fields=["control"])
        target.control_resist = 0.0
        target.save(update_fields=["control_resist"])

        # Act — random=0.0 → not resisted (0.0 < 1.0)
        with patch("apps.game.services.random.random", return_value=0.0):
            with patch("apps.game.services.random.randint", return_value=100):
                action = _chain._execute_move(
                    round_obj=round_obj,
                    attacker_slot=attacker,
                    move=move,
                    target_slot=target,
                    chain_position=0,
                    is_combo=False,
                )

        # Assert — status applied
        assert action.status_applied is not None


# ===========================================================================
# TestPenetration
# ===========================================================================

@allure.epic("Battle")
@allure.feature("Phase 3 — Penetration Stat")
class TestPenetration(BaseTest):
    """
    Penetration ignores a fraction of the defender's defense:
    effective_defense = defense * (1 - penetration).

    Higher penetration → lower effective_defense → more damage.
    """

    @allure.story("Higher penetration deals more damage than zero penetration")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_high_penetration_deals_more_damage(self):
        # Arrange — two identical battles, differing only in attacker penetration
        nt = PokemonTypeFactory(name="Normal")
        move_a = MoveFactory(name="PenHighDmg", move_type=nt, power=100)
        move_b = MoveFactory(name="PenZeroDmg", move_type=nt, power=100)

        # Battle A: attacker has high penetration
        battle_a, team_a1, team_a2, slots_a1, slots_a2 = build_battle_pair(
            p1_moves=[move_a],
        )
        round_a = ensure_round(battle_a, round_number=1)
        attacker_a = slots_a1[0]
        target_a = slots_a2[0]
        attacker_a.penetration = 0.90  # 90% defense ignored
        attacker_a.save(update_fields=["penetration"])

        # Battle B: attacker has zero penetration (baseline)
        battle_b, team_b1, team_b2, slots_b1, slots_b2 = build_battle_pair(
            p1_moves=[move_b],
        )
        round_b = ensure_round(battle_b, round_number=1)
        attacker_b = slots_b1[0]
        target_b = slots_b2[0]
        attacker_b.penetration = 0.0
        attacker_b.save(update_fields=["penetration"])

        # Act — deterministic rolls (no crit, 100% damage)
        with patch("apps.game.services.random.random", return_value=0.99):
            with patch("apps.game.services.random.randint", return_value=100):
                action_high = _chain._execute_move(
                    round_obj=round_a,
                    attacker_slot=attacker_a,
                    move=move_a,
                    target_slot=target_a,
                    chain_position=0,
                    is_combo=False,
                )
                action_zero = _chain._execute_move(
                    round_obj=round_b,
                    attacker_slot=attacker_b,
                    move=move_b,
                    target_slot=target_b,
                    chain_position=0,
                    is_combo=False,
                )

        # Assert — high penetration deals strictly more damage
        assert action_high.damage_dealt > action_zero.damage_dealt

    @allure.story("Zero penetration uses full defender defense in damage formula")
    @allure.severity(allure.severity_level.NORMAL)
    def test_zero_penetration_uses_full_defense(self):
        # Arrange — very high defense; zero penetration should reduce damage significantly
        nt = PokemonTypeFactory(name="Normal")
        from tests.framework.factories.pokemon_factory import PokemonFactory
        from apps.pokemon.models import Pokemon

        # Create a tank-stat pokemon with extremely high defense
        tanky = PokemonFactory(
            name="Tanky", primary_type=nt, base_defense=255, base_attack=80,
            base_ninjutsu=80, base_initiative=80,
        )
        move = MoveFactory(name="PenFullDef", move_type=nt, power=100)
        tanky.moves.add(move)

        battle, team1, team2, slots1, slots2 = build_battle_pair(
            p1_moves=[move],
        )
        round_obj = ensure_round(battle, round_number=1)

        attacker = slots1[0]
        # Assign the tanky pokemon to the target slot
        target = slots2[0]
        target.pokemon = tanky
        target.save(update_fields=["pokemon"])

        attacker.penetration = 0.0
        attacker.save(update_fields=["penetration"])

        # Same attacker but with 0.95 pen for comparison
        attacker_b = slots1[1]
        attacker_b.penetration = 0.95
        attacker_b.save(update_fields=["penetration"])

        # Act — both shots on the same tanky target
        with patch("apps.game.services.random.random", return_value=0.99):
            with patch("apps.game.services.random.randint", return_value=100):
                action_no_pen = _chain._execute_move(
                    round_obj=round_obj,
                    attacker_slot=attacker,
                    move=move,
                    target_slot=target,
                    chain_position=0,
                    is_combo=False,
                )
                # Refresh target HP for second shot
                target.refresh_from_db()
                if target.is_fainted:
                    target.current_hp = target.max_hp
                    target.is_fainted = False
                    target.save(update_fields=["current_hp", "is_fainted"])

                action_high_pen = _chain._execute_move(
                    round_obj=round_obj,
                    attacker_slot=attacker_b,
                    move=move,
                    target_slot=target,
                    chain_position=0,
                    is_combo=False,
                )

        # Assert — penetration reduces effective defense → more damage
        assert action_high_pen.damage_dealt >= action_no_pen.damage_dealt
