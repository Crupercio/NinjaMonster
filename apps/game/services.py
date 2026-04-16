"""
Battle services: ComboChainEngine and BattleService.

ComboChainEngine — resolves the Naruto-inspired combo chain system.
BattleService    — orchestrates battle lifecycle and round execution.
"""
import logging
import random
from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.db import transaction

from apps.effects.constants import StatusName
from apps.effects.engine import StatusEffectEngine
from apps.pokemon.models import Move, MoveSlotType, OwnedPokemon, Pokemon, SpeciesMovePool, Team
from apps.pokemon.services import award_battle_exp as _award_battle_exp  # noqa: F401
from apps.events.services import SeasonalEventService
from apps.quests.services import QuestService
from apps.stickers.services import StickerService
from apps.users.services import BATTLE_LOSS_RYO, BATTLE_WIN_RYO, award_ryo

_sticker_service = StickerService()
_quest_service = QuestService()
_event_service = SeasonalEventService()

from .models import (
    ACTIVE_GRID_POSITIONS,
    GRID_TURN_ORDER,
    POSITION_TO_GRID,
    AIDifficulty,
    Battle,
    BattleAction,
    BattleLog,
    BattleRound,
    BattleSlot,
    BattleSlotHeldEffect,
    BattleStatus,
    BattleTeam,
    GridPosition,
    LogType,
    MoveCooldown,
)

if TYPE_CHECKING:
    pass

User = get_user_model()
logger = logging.getLogger(__name__)

# Maximum combo chain depth to prevent infinite loops
MAX_CHAIN_DEPTH = 10

# Damage amplification multiplier per chain link (GDD Section 6.3).
# Index = chain_position (0 = initial move, 1 = link 2, …, 9 = link 10).
# Beyond index 9, the max ×2.50 is used.
COMBO_AMP: tuple[float, ...] = (
    1.00,  # Link 1 — initial move, no amplification
    1.10,  # Link 2
    1.20,  # Link 3
    1.35,  # Link 4
    1.50,  # Link 5
    1.65,  # Link 6
    1.80,  # Link 7
    2.00,  # Link 8
    2.25,  # Link 9
    2.50,  # Link 10 (maximum)
)

# Chakra element advantage cycle (Phase 2 — GDD Section 7).
# Key chakra beats value chakra: Fire→Wind, Wind→Lightning, Lightning→Earth, Earth→Water, Water→Fire.
CHAKRA_BEATS: dict[str, str] = {
    "fire": "wind",
    "wind": "lightning",
    "lightning": "earth",
    "earth": "water",
    "water": "fire",
}

# Phase 3 — penetration by primary_role (fraction of defense ignored)
_ROLE_PENETRATION: dict[str, float] = {
    "combo": 0.10,
    "burst": 0.05,
    "control": 0.08,
    "tank": 0.0,
    "support": 0.0,
}

_effect_engine = StatusEffectEngine()


def _resolve_held_effect(
    trigger: str,
    slot: "BattleSlot",
    round_obj: "BattleRound",
    *,
    damage_taken: int = 0,
    attacker_slot: "BattleSlot | None" = None,
) -> None:
    """
    Fire a slot's held effect if trigger matches, chance passes, and cap not reached.

    Implements: heal_fraction, damage_reflect, status_cleanse, revive_hp_fraction.
    Called from ComboChainEngine._execute_move (on_hit / on_faint / on_status)
    and BattleService.execute_round (passive).
    """
    try:
        hes: BattleSlotHeldEffect = slot.held_effect_state  # type: ignore[attr-defined]
    except Exception:
        return

    effect = hes.effect
    if effect.trigger_condition != trigger:
        return
    if not hes.can_activate:
        return
    if random.random() > effect.activation_chance:
        return

    hes.activations_used += 1
    hes.save(update_fields=["activations_used"])

    data: dict = effect.effect_data
    parts: list[str] = [f"{slot.pokemon.name}'s {effect.name} activates!"]

    # heal_fraction: restore fraction of max HP to self
    if "heal_fraction" in data:
        heal = max(1, int(slot.max_hp * data["heal_fraction"]))
        slot.current_hp = min(slot.max_hp, slot.current_hp + heal)
        slot.save(update_fields=["current_hp"])
        parts.append(f"+{heal} HP")

    # damage_reflect: deal fraction of damage_taken back to attacker
    if "damage_reflect" in data and damage_taken > 0 and attacker_slot and not attacker_slot.is_fainted:
        reflected = max(1, int(damage_taken * data["damage_reflect"]))
        attacker_slot.current_hp = max(0, attacker_slot.current_hp - reflected)
        if attacker_slot.current_hp == 0:
            attacker_slot.is_fainted = True
        attacker_slot.save(update_fields=["current_hp", "is_fainted"])
        parts.append(f"{attacker_slot.pokemon.name} takes {reflected} reflected damage")

    # status_cleanse: remove all active statuses from self
    if data.get("status_cleanse"):
        from apps.effects.models import ActiveStatusEffect
        ActiveStatusEffect.objects.filter(slot=slot).delete()
        parts.append("all statuses cleared")

    # revive_hp_fraction: revive a fainted slot (on_faint only)
    if "revive_hp_fraction" in data and slot.is_fainted:
        revive_hp = max(1, int(slot.max_hp * data["revive_hp_fraction"]))
        slot.current_hp = revive_hp
        slot.is_fainted = False
        slot.save(update_fields=["current_hp", "is_fainted"])
        parts.append(f"revived with {revive_hp} HP!")

    BattleLog.objects.create(
        battle=round_obj.battle,
        round_number=round_obj.round_number,
        message=" — ".join(parts),
        log_type=LogType.STATUS,
    )
    logger.debug("Held effect %s fired on %s (trigger=%s)", effect.name, slot.pokemon.name, trigger)


class BattleValidator:
    """
    Pre-battle sanity checks.

    Call validate() before start_battle().  Raises ValueError listing all
    failures found, so the caller can surface them to the user in one shot.
    """

    _REQUIRED_SLOTS = 6  # active field slots per team (Phase 3 — 6v6)

    def validate(self, battle: "Battle") -> None:
        """
        Verify that both teams are ready to fight.

        Checks:
          1. Both teams exist and each has exactly 6 active slots.
          2. Every slot's OwnedPokemon has all 4 active move slots assigned
             (standard, chase, special, support).  AI slots (no owned_pokemon)
             are validated against the species move pool instead.
          3. All Move PKs referenced by the slots exist in the database.

        Raises ValueError with a newline-separated list of issues if any are
        found.  Does nothing if the battle is clean.
        """
        errors: list[str] = []

        teams = list(battle.teams.prefetch_related(
            "slots__owned_pokemon",
            "slots__pokemon__moves",
        ).select_related("owner"))

        if len(teams) < 2:
            raise ValueError(f"Battle needs 2 teams; only {len(teams)} registered.")

        move_ids_to_check: set[int] = set()

        for team in teams:
            active_slots = [s for s in team.slots.all() if s.is_active]
            if len(active_slots) != self._REQUIRED_SLOTS:
                errors.append(
                    f"Team '{team.owner}' has {len(active_slots)} active slot(s); "
                    f"expected {self._REQUIRED_SLOTS}."
                )

            for slot in active_slots:
                if slot.owned_pokemon_id is not None:
                    op = slot.owned_pokemon
                    missing = [
                        label
                        for attr, label in (
                            ("move_standard", "standard"),
                            ("move_chase", "chase"),
                            ("move_special", "mystery"),
                            ("move_support", "passive_1"),
                        )
                        if getattr(op, attr) is None
                    ]
                    if missing:
                        errors.append(
                            f"{slot.pokemon.name} (team '{team.owner}') is missing "
                            f"move slot(s): {', '.join(missing)}."
                        )
                    else:
                        for attr in ("move_standard", "move_chase", "move_special", "move_support"):
                            m = getattr(op, attr)
                            if m is not None:
                                move_ids_to_check.add(m.pk)
                else:
                    # AI / legacy slot — must have at least one move in the species pool.
                    species_move_count = SpeciesMovePool.objects.filter(
                        species=slot.pokemon
                    ).count()
                    if species_move_count == 0:
                        errors.append(
                            f"{slot.pokemon.name} (AI team) has no moves in its species pool."
                        )

        # Bulk-check that every referenced Move PK actually exists.
        if move_ids_to_check:
            existing_ids = set(
                Move.objects.filter(pk__in=move_ids_to_check).values_list("pk", flat=True)
            )
            missing_ids = move_ids_to_check - existing_ids
            if missing_ids:
                errors.append(
                    f"Move PK(s) not found in database: {sorted(missing_ids)}."
                )

        if errors:
            raise ValueError("\n".join(errors))


class ComboChainEngine:
    """
    Resolves the combo chain system.

    When a move applies a status, this engine scans the attacker's team for
    other moves whose trigger_status matches any currently active enemy status.
    Those moves fire automatically, potentially extending the chain further.
    Only active (non-bench) slots participate in combo chains.
    """

    def resolve_combo_chain(
        self,
        battle: "Battle",
        attacker_slot: "BattleSlot",
        move: Move,
        target_slot: "BattleSlot",
        round_number: int,
    ) -> list[BattleAction]:
        """
        Execute an initial move and resolve any resulting combo chain.

        Returns the full ordered list of BattleActions (initial + all triggered).
        """
        round_obj = BattleRound.objects.get(battle=battle, round_number=round_number)
        actions: list[BattleAction] = []
        fired_pairs: set[tuple[int, int]] = set()

        action = self._execute_move(
            round_obj=round_obj,
            attacker_slot=attacker_slot,
            move=move,
            target_slot=target_slot,
            chain_position=0,
            is_combo=False,
        )
        actions.append(action)
        fired_pairs.add((attacker_slot.pk, move.pk))

        chain_depth = 1
        while chain_depth <= MAX_CHAIN_DEPTH:
            if target_slot.is_fainted:
                break

            friendly_team = attacker_slot.team
            enemy_team = (
                battle.teams.exclude(pk=friendly_team.pk)
                .prefetch_related("slots__active_statuses__status")
                .first()
            )
            if enemy_team is None:
                break

            active_enemy_statuses = self._collect_enemy_statuses(enemy_team)
            if not active_enemy_statuses:
                break

            candidates = self._find_combo_candidates(
                friendly_team, active_enemy_statuses, fired_pairs
            )
            if not candidates:
                break

            fired_any = False
            for trigger_slot, trigger_move in candidates:
                if chain_depth > MAX_CHAIN_DEPTH:
                    logger.warning(
                        "Max combo chain depth %d reached in Battle #%d",
                        MAX_CHAIN_DEPTH,
                        battle.pk,
                    )
                    break

                combo_target = self._select_target(enemy_team, trigger_move)
                if combo_target is None:
                    continue

                # Phase 6: chase_condition — move only fires if target is in the required physical state
                if trigger_move.chase_condition:
                    cond = trigger_move.chase_condition
                    if cond == StatusName.GROUNDED:
                        if not _effect_engine.is_grounded(combo_target):
                            continue
                    elif not _effect_engine.has_status(combo_target, cond):
                        continue

                combo_action = self._execute_move(
                    round_obj=round_obj,
                    attacker_slot=trigger_slot,
                    move=trigger_move,
                    target_slot=combo_target,
                    chain_position=chain_depth,
                    is_combo=True,
                )
                actions.append(combo_action)
                fired_pairs.add((trigger_slot.pk, trigger_move.pk))
                fired_any = True
                chain_depth += 1

                # Phase 6: CHAIN_BREAKER — target's state halts chain after this hit
                if _effect_engine.has_status(combo_target, StatusName.CHAIN_BREAKER):
                    logger.debug(
                        "Combo chain broken by CHAIN_BREAKER on %s", combo_target.pokemon.name
                    )
                    fired_any = False  # force loop exit
                    break

            if not fired_any:
                break

        if len(actions) > 1:
            self._log_combo_chain(battle, actions, round_number)
            if len(actions) > battle.max_combo_chain:
                battle.max_combo_chain = len(actions)
                battle.save(update_fields=["max_combo_chain"])

        return actions

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _execute_move(
        self,
        round_obj: BattleRound,
        attacker_slot: BattleSlot,
        move: Move,
        target_slot: BattleSlot,
        chain_position: int,
        is_combo: bool,
    ) -> BattleAction:
        """Execute a single move: calculate damage, apply status, create BattleAction."""
        damage = 0
        status_applied = None

        # Phase 6: Charge move — 2-round wind-up mechanic
        if move.is_charge_move:
            from apps.effects.models import StatusEffect as _ChargeSE
            if _effect_engine.has_status(attacker_slot, StatusName.CHARGING):
                # Round 2: release — remove CHARGING and fall through to deal damage
                try:
                    charging_se = _ChargeSE.objects.get(name=StatusName.CHARGING)
                    _effect_engine.remove_status(attacker_slot, charging_se)
                except _ChargeSE.DoesNotExist:
                    pass
                BattleLog.objects.create(
                    battle=round_obj.battle,
                    round_number=round_obj.round_number,
                    message=f"{attacker_slot.pokemon.name} released {move.name}!",
                    log_type=LogType.INFO,
                )
            else:
                # Round 1: enter charging — apply CHARGING, skip damage this round
                try:
                    charging_se = _ChargeSE.objects.get(name=StatusName.CHARGING)
                    _effect_engine.apply_status(attacker_slot, charging_se, round_obj.round_number)
                except _ChargeSE.DoesNotExist:
                    pass
                BattleLog.objects.create(
                    battle=round_obj.battle,
                    round_number=round_obj.round_number,
                    message=f"{attacker_slot.pokemon.name} is charging {move.name}...",
                    log_type=LogType.STATUS,
                )
                attacker_slot.last_move_used = move
                attacker_slot.save(update_fields=["last_move_used"])
                return BattleAction.objects.create(
                    round=round_obj,
                    attacker_slot=attacker_slot,
                    move=move,
                    target_slot=target_slot,
                    damage_dealt=0,
                    status_applied=None,
                    is_combo_triggered=is_combo,
                    order_in_chain=chain_position,
                )

        if not target_slot.is_fainted:
            # Phase 6: SHIELDED absorbs one incoming hit entirely
            if _effect_engine.has_status(target_slot, StatusName.SHIELDED):
                from apps.effects.models import StatusEffect as _SE
                try:
                    shield_se = _SE.objects.get(name=StatusName.SHIELDED)
                    _effect_engine.remove_status(target_slot, shield_se)
                except _SE.DoesNotExist:
                    pass
                BattleLog.objects.create(
                    battle=round_obj.battle,
                    round_number=round_obj.round_number,
                    message=f"{target_slot.pokemon.name}'s shield absorbed the hit!",
                    log_type=LogType.STATUS,
                )
            else:
                damage = self._calculate_damage(attacker_slot, move, target_slot, chain_position)
                if damage > 0:
                    target_slot.current_hp = max(0, target_slot.current_hp - damage)
                    if target_slot.current_hp == 0:
                        target_slot.is_fainted = True
                    target_slot.save(update_fields=["current_hp", "is_fainted"])

                    # on_hit: fires whenever damage lands
                    _resolve_held_effect(
                        "on_hit", target_slot, round_obj,
                        damage_taken=damage, attacker_slot=attacker_slot,
                    )
                    # on_faint: fires if the hit was lethal
                    if target_slot.is_fainted:
                        _resolve_held_effect(
                            "on_faint", target_slot, round_obj,
                            damage_taken=damage, attacker_slot=attacker_slot,
                        )

                    # Phase 6: Airborne → Launched transition on any damaging hit
                    if (
                        not target_slot.is_fainted
                        and _effect_engine.has_status(target_slot, StatusName.AIRBORNE)
                        and not _effect_engine.has_status(target_slot, StatusName.STATE_LOCKED)
                    ):
                        from apps.effects.models import StatusEffect as _SE2
                        try:
                            airborne_se = _SE2.objects.get(name=StatusName.AIRBORNE)
                            launched_se = _SE2.objects.get(name=StatusName.LAUNCHED)
                            _effect_engine.remove_status(target_slot, airborne_se)
                            _effect_engine.apply_status(
                                target_slot, launched_se, round_obj.round_number
                            )
                            BattleLog.objects.create(
                                battle=round_obj.battle,
                                round_number=round_obj.round_number,
                                message=f"{target_slot.pokemon.name} was Launched!",
                                log_type=LogType.STATUS,
                            )
                        except _SE2.DoesNotExist:
                            pass

            if move.applies_status and not target_slot.is_fainted:
                # Phase 6: IMMUNE — skip status application entirely
                if _effect_engine.has_status(target_slot, StatusName.IMMUNE):
                    BattleLog.objects.create(
                        battle=round_obj.battle,
                        round_number=round_obj.round_number,
                        message=f"{target_slot.pokemon.name} is immune to status effects!",
                        log_type=LogType.STATUS,
                    )
                else:
                    # CC resist formula (Phase 3): success prob = control / (control + control_resist * 1000)
                    cc_success_prob = attacker_slot.control / (
                        attacker_slot.control + target_slot.control_resist * 1000
                    )
                    resisted = random.random() >= cc_success_prob
                    if resisted:
                        BattleLog.objects.create(
                            battle=round_obj.battle,
                            round_number=round_obj.round_number,
                            message=f"{target_slot.pokemon.name} resisted the status effect!",
                            log_type=LogType.STATUS,
                        )
                    else:
                        applied = _effect_engine.apply_status(
                            slot=target_slot,
                            status=move.applies_status,
                            round_number=round_obj.round_number,
                            applied_by_slot=attacker_slot if move.applies_status.name == StatusName.SEEDED else None,
                        )
                        if applied:
                            status_applied = move.applies_status
                            # on_status: fires when a status is successfully applied
                            _resolve_held_effect("on_status", target_slot, round_obj)
                            # Phase 6: KNOCKBACK — shift the target to back-row position
                            if move.applies_status.name == StatusName.KNOCKBACK:
                                self._apply_knockback_position(target_slot)

        attacker_slot.last_move_used = move
        attacker_slot.save(update_fields=["last_move_used"])

        action = BattleAction.objects.create(
            round=round_obj,
            attacker_slot=attacker_slot,
            move=move,
            target_slot=target_slot,
            damage_dealt=damage,
            status_applied=status_applied,
            is_combo_triggered=is_combo,
            order_in_chain=chain_position,
        )

        # Build the per-action combat log line visible in the battle log panel.
        move_display = move.themed_name or move.name
        if is_combo:
            msg_parts = [f"↳ [COMBO] {attacker_slot.pokemon.name} → {move_display} → {target_slot.pokemon.name}"]
        else:
            msg_parts = [f"{attacker_slot.pokemon.name} → {move_display} → {target_slot.pokemon.name}"]

        if damage > 0:
            msg_parts.append(f"({damage} dmg)")
        if status_applied is not None:
            msg_parts.append(f"[{status_applied.name} applied!]")
        if target_slot.is_fainted:
            msg_parts.append("💀 KO!")

        BattleLog.objects.create(
            battle=round_obj.battle,
            round_number=round_obj.round_number,
            message=" ".join(msg_parts),
            log_type=LogType.COMBO if is_combo else LogType.ACTION,
            chain_position=chain_position if is_combo else None,
        )

        if target_slot.is_fainted:
            BattleLog.objects.create(
                battle=round_obj.battle,
                round_number=round_obj.round_number,
                message=f"{target_slot.pokemon.name} fainted!",
                log_type=LogType.FAINT,
            )

        logger.debug(
            "Executed: %s uses %s on %s (damage=%d, chain=%d)",
            attacker_slot.pokemon.name,
            move.name,
            target_slot.pokemon.name,
            damage,
            chain_position,
        )
        return action

    def _calculate_damage(
        self, attacker: BattleSlot, move: Move, defender: BattleSlot, chain_position: int = 0
    ) -> int:
        """Standard damage formula with type effectiveness, status, positional, and combo modifiers."""
        if move.power == 0:
            return 0

        atk_modifiers = _effect_engine.get_stat_modifiers(attacker)
        def_modifiers = _effect_engine.get_stat_modifiers(defender)

        attack_stat = attacker.pokemon.calculate_stat(attacker.pokemon.base_attack, attacker.level)
        defense_stat = defender.pokemon.calculate_stat(defender.pokemon.base_defense, defender.level)

        attack_stat = int(attack_stat * atk_modifiers.get("attack", 1.0))
        defense_stat = int(defense_stat * def_modifiers.get("defense", 1.0))

        # Penetration (Phase 3): fraction of defense ignored based on attacker role
        effective_defense = max(1, int(defense_stat * (1.0 - attacker.penetration)))

        damage = int(((2 * attacker.level / 5 + 2) * move.power * attack_stat / effective_defense) / 50 + 2)

        attacker_types = {attacker.pokemon.primary_type.name}
        if attacker.pokemon.secondary_type:
            attacker_types.add(attacker.pokemon.secondary_type.name)
        if move.move_type.name in attacker_types:
            damage = int(damage * 1.5)

        if "damage_output" in atk_modifiers:
            damage = int(damage * atk_modifiers["damage_output"])

        # Positional modifier: back-row targets take 80% damage from direct attacks
        if defender.grid_position in (
            GridPosition.BACK_LEFT, GridPosition.BACK_CENTER, GridPosition.BACK_RIGHT
        ):
            damage = int(damage * 0.80)

        # Combo chain amplification (GDD Section 6.3): Link 1 = ×1.00, Link 10 = ×2.50
        amp = COMBO_AMP[min(chain_position, len(COMBO_AMP) - 1)]
        if amp != 1.0:
            damage = int(damage * amp)

        # combo_rate bonus: non-initial chain links gain extra damage from the attacker's combo rate
        if chain_position > 0 and attacker.combo_rate > 0:
            damage = int(damage * (1.0 + attacker.combo_rate))

        # Critical hit (Phase 5): attacker.critical_rate chance → ×1.5 damage
        if random.random() < attacker.critical_rate:
            damage = int(damage * 1.5)

        # Chakra element modifiers (Phase 2 — GDD Section 7)
        # Mastery  (+20%): move chakra == attacker species chakra
        # Advantage (+15%): move chakra beats defender species chakra
        # Both      (+35%): mastery + advantage stack
        # Resistance(−10%): defender chakra beats move chakra
        move_el = getattr(getattr(move.move_type, "chakra_element", None), "name", None)
        atk_el = getattr(getattr(attacker.pokemon.primary_type, "chakra_element", None), "name", None)
        def_el = getattr(getattr(defender.pokemon.primary_type, "chakra_element", None), "name", None)

        if move_el:
            mastery = move_el == atk_el
            advantage = def_el is not None and CHAKRA_BEATS.get(move_el) == def_el
            resistance = def_el is not None and CHAKRA_BEATS.get(def_el) == move_el

            if mastery and advantage:
                damage = int(damage * 1.35)
            elif mastery:
                damage = int(damage * 1.20)
            elif advantage:
                damage = int(damage * 1.15)
            elif resistance:
                damage = int(damage * 0.90)

        # Formation bonus (Phase F): same-type allies alive on the attacker's team
        # 2 same-type alive (including self) → +10%
        # 3+ same-type alive (including self) → +25%
        attacker_primary_type = attacker.pokemon.primary_type_id
        same_type_alive = BattleSlot.objects.filter(
            team=attacker.team,
            is_fainted=False,
            is_active=True,
            pokemon__primary_type_id=attacker_primary_type,
        ).count()
        if same_type_alive >= 3:
            damage = int(damage * 1.25)
        elif same_type_alive == 2:
            damage = int(damage * 1.10)

        damage = int(damage * random.randint(85, 100) / 100)
        return max(1, damage)

    def _collect_enemy_statuses(self, enemy_team: BattleTeam) -> set[str]:
        """Return the set of all status names active on any non-fainted active enemy slot."""
        from apps.effects.models import ActiveStatusEffect

        return set(
            ActiveStatusEffect.objects.filter(
                slot__team=enemy_team,
                slot__is_fainted=False,
                slot__is_active=True,
            ).values_list("status__name", flat=True)
        )

    def _find_combo_candidates(
        self,
        friendly_team: BattleTeam,
        active_enemy_statuses: set[str],
        fired_pairs: set[tuple[int, int]],
    ) -> list[tuple[BattleSlot, Move]]:
        """
        Find (slot, move) pairs on the friendly active team that can trigger given the
        active enemy statuses, excluding already-fired pairs.
        """
        candidates: list[tuple[BattleSlot, Move]] = []
        slots = (
            BattleSlot.objects.filter(team=friendly_team, is_fainted=False, is_active=True)
            .select_related(
                "owned_pokemon__move_standard__trigger_status",
                "owned_pokemon__move_chase__trigger_status",
                "owned_pokemon__move_special__trigger_status",
                "owned_pokemon__move_support__trigger_status",
            )
            .prefetch_related("pokemon__moves__trigger_status")
        )

        for slot in slots:
            # Use the OwnedPokemon's 4 equipped moves when available (the actual
            # assigned moves carry trigger_status). Fall back to the species pool
            # for AI/legacy slots that have no owned_pokemon.
            if slot.owned_pokemon_id:
                op = slot.owned_pokemon
                candidate_moves: list[Move] = [
                    m for m in (
                        op.move_standard,
                        op.move_chase,
                        op.move_special,
                        op.move_support,
                    )
                    if m is not None
                ]
            else:
                candidate_moves = list(slot.pokemon.moves.all())

            for move in candidate_moves:
                if move.slot_type == MoveSlotType.PASSIVE_2:
                    continue
                if move.trigger_status is None:
                    continue
                if move.trigger_status.name not in active_enemy_statuses:
                    continue
                if (slot.pk, move.pk) in fired_pairs:
                    continue
                candidates.append((slot, move))

        return candidates

    def _select_target(
        self, enemy_team: BattleTeam, _move: Move
    ) -> BattleSlot | None:
        """
        Select the best active target on the enemy team.

        Enforces front-row-first: if any front-row slot is alive, the AI must
        target it. Selects the lowest-HP target within the valid pool.
        """
        alive_slots = list(
            BattleSlot.objects.filter(
                team=enemy_team, is_fainted=False, is_active=True
            ).order_by("current_hp")
        )
        # Phase 6: HIDDEN slots cannot be targeted
        alive_slots = [s for s in alive_slots if not _effect_engine.has_status(s, StatusName.HIDDEN)]
        if not alive_slots:
            return None

        front_positions = {GridPosition.FRONT_LEFT, GridPosition.FRONT_RIGHT}
        front_alive = [s for s in alive_slots if s.grid_position in front_positions]
        if front_alive:
            return min(front_alive, key=lambda s: s.current_hp)
        return alive_slots[0]

    def _apply_knockback_position(self, slot: BattleSlot) -> None:
        """
        Shift a slot from front row to its back-row equivalent when KNOCKBACK is applied.

        Only moves front-row slots; back-row slots are already at the furthest position.
        """
        knockback_map = {
            GridPosition.FRONT_LEFT:   GridPosition.BACK_LEFT,
            GridPosition.FRONT_CENTER: GridPosition.BACK_CENTER,
            GridPosition.FRONT_RIGHT:  GridPosition.BACK_RIGHT,
        }
        new_pos = knockback_map.get(slot.grid_position)
        if new_pos is not None:
            slot.grid_position = new_pos
            slot.save(update_fields=["grid_position"])
            logger.debug(
                "Knockback: %s pushed from front row to %s", slot.pokemon.name, new_pos
            )

    def _log_combo_chain(
        self, battle: Battle, actions: list[BattleAction], round_number: int
    ) -> None:
        """Create BattleLog entries summarising the full combo chain for UI display."""
        move_names = " → ".join(a.move.themed_name or a.move.name for a in actions)
        chain_len = len(actions)
        message = f"Chain x{chain_len} — {move_names}!"

        BattleLog.objects.create(
            battle=battle,
            round_number=round_number,
            message=message,
            log_type=LogType.COMBO,
            chain_position=0,
            chain_total=chain_len,
        )

        logs_to_create = []
        for i, action in enumerate(actions):
            dmg_str = f" ({action.damage_dealt} dmg)" if action.damage_dealt else ""
            status_str = f" [{action.status_applied.name}]" if action.status_applied else ""
            logs_to_create.append(
                BattleLog(
                    battle=battle,
                    round_number=round_number,
                    message=(
                        f"{'[COMBO] ' if action.is_combo_triggered else ''}"
                        f"{action.attacker_slot.pokemon.name} uses "
                        f"{action.move.themed_name or action.move.name}{dmg_str}{status_str}"
                    ),
                    log_type=LogType.COMBO if action.is_combo_triggered else LogType.ACTION,
                    chain_position=i,
                    chain_total=chain_len,
                )
            )
        BattleLog.objects.bulk_create(logs_to_create)


class BattleService:
    """
    Orchestrates the full battle lifecycle.

    create_battle → set_team (×2) → start_battle → execute_round (×N) → end
    """

    def __init__(self) -> None:
        self._combo_engine = ComboChainEngine()
        self._validator = BattleValidator()

    @transaction.atomic
    def create_battle(
        self,
        player_one: User,
        player_two: User | None = None,
        is_ai_battle: bool = False,
        ai_difficulty: str = "medium",
    ) -> Battle:
        """Create a new battle in setup status."""
        battle = Battle.objects.create(
            player_one=player_one,
            player_two=player_two,
            status=BattleStatus.SETUP,
            is_ai_battle=is_ai_battle,
            ai_difficulty=ai_difficulty,
        )
        logger.info("Created Battle #%d: %s vs %s", battle.pk, player_one, player_two or "AI")
        return battle

    def try_auto_load_player_team(self, battle: Battle, user: User) -> bool:
        """
        Attempt to load the player's saved team into the battle automatically.

        Looks up the user's persistent Team, takes the first 4 OwnedPokemon
        (positions 1–4), pads with bench slots if 5–6 exist, then calls
        set_team_from_owned.  Returns True if the team was loaded successfully,
        False if the team is incomplete/invalid (caller should show manual
        selection screen).

        Requirements for auto-load:
          - User has a Team with at least 4 non-training OwnedPokemon slots.
          - The first 4 slots must all be valid and not in training.
          - If only 4 slots exist, positions 5 and 6 are left empty (we need
            exactly 6 for set_team_from_owned, so we fall back to manual if
            the team has fewer than 6 filled slots).
        """
        try:
            team = Team.objects.get(owner=user)
        except Team.DoesNotExist:
            logger.debug("No persistent team found for %s — showing team select.", user)
            return False

        ordered = list(
            team.slots.select_related(
                "pokemon__species__primary_type",
                "pokemon__species__secondary_type",
            ).order_by("position")
        )

        if len(ordered) < 6:
            logger.debug(
                "Persistent team for %s has only %d slots (need 6) — showing team select.",
                user,
                len(ordered),
            )
            return False

        owned_ids = [slot.pokemon_id for slot in ordered[:6]]

        try:
            self.set_team_from_owned(battle, user, owned_ids)
        except ValueError as exc:
            logger.debug("Auto-load failed for %s: %s — showing team select.", user, exc)
            return False

        logger.info("Auto-loaded persistent team for %s into Battle #%d", user, battle.pk)
        return True

    @transaction.atomic
    def set_team(
        self, battle: Battle, user: User, pokemon_ids: list[int]
    ) -> BattleTeam:
        """
        Assign a team of exactly 6 Pokemon to a battle participant.

        pokemon_ids: list of Pokemon PKs in slot order (index 0 = slot 1).
        Positions 1–4 are active; positions 5–6 are bench.
        """
        if len(pokemon_ids) != 6:
            raise ValueError(f"A team must have exactly 6 Pokemon, got {len(pokemon_ids)}")
        if battle.status != BattleStatus.SETUP:
            raise ValueError("Cannot modify teams after the battle has started")

        BattleTeam.objects.filter(battle=battle, owner=user).delete()
        team = BattleTeam.objects.create(battle=battle, owner=user)

        pokemon_list = list(
            Pokemon.objects.filter(pk__in=pokemon_ids)
            .select_related("primary_type", "secondary_type")
            .prefetch_related("moves")
        )
        pokemon_map = {p.pk: p for p in pokemon_list}

        slots_to_create = []
        for position, poke_id in enumerate(pokemon_ids, start=1):
            pokemon = pokemon_map.get(poke_id)
            if pokemon is None:
                raise ValueError(f"Pokemon with id {poke_id} does not exist")

            level = 50
            max_hp = pokemon.calculate_max_hp(level)
            grid_pos = POSITION_TO_GRID[position]
            is_active = grid_pos in ACTIVE_GRID_POSITIONS
            standard_move = self._pick_default_move(pokemon)
            slots_to_create.append(
                BattleSlot(
                    team=team,
                    pokemon=pokemon,
                    position=position,
                    grid_position=grid_pos,
                    is_active=is_active,
                    level=level,
                    current_hp=max_hp,
                    max_hp=max_hp,
                    selected_move=standard_move,
                )
            )

        BattleSlot.objects.bulk_create(slots_to_create)
        logger.info("Set team for %s in Battle #%d", user, battle.pk)
        return team

    @transaction.atomic
    def set_team_from_owned(
        self, battle: Battle, user: User, owned_pokemon_ids: list[int]
    ) -> BattleTeam:
        """
        Assign a battle team using the player's OwnedPokemon PKs.

        Unlike set_team (which hardcodes level 50), this uses each Pokemon's
        real level from OwnedPokemon. Training Pokemon are rejected.
        Positions 1–4 are active field; positions 5–6 are bench.
        """
        if len(owned_pokemon_ids) != 6:
            raise ValueError(f"A team must have exactly 6 Pokemon, got {len(owned_pokemon_ids)}")
        if battle.status != BattleStatus.SETUP:
            raise ValueError("Cannot modify teams after the battle has started")

        owned_list = list(
            OwnedPokemon.objects.filter(
                pk__in=owned_pokemon_ids,
                owner=user,
            ).select_related("species__primary_type", "species__secondary_type", "held_effect")
            .prefetch_related("species__moves")
        )
        if len(owned_list) != 6:
            raise ValueError("One or more selected Pokemon do not belong to you.")

        training = [op for op in owned_list if op.is_training]
        if training:
            names = ", ".join(op.species.name for op in training)
            raise ValueError(f"{names} are in training and cannot battle.")

        owned_map = {op.pk: op for op in owned_list}

        BattleTeam.objects.filter(battle=battle, owner=user).delete()
        team = BattleTeam.objects.create(battle=battle, owner=user)

        slots_to_create = []
        for position, op_id in enumerate(owned_pokemon_ids, start=1):
            op = owned_map[op_id]
            level = op.level
            max_hp = op.species.calculate_max_hp(level)
            grid_pos = POSITION_TO_GRID[position]
            is_active = grid_pos in ACTIVE_GRID_POSITIONS
            selected_move = op.move_standard or self._pick_default_move(op.species)
            # Phase 3 — control scales 50–150 from base_ninjutsu (0–255)
            slot_control = 50.0 + (op.species.base_ninjutsu / 255.0) * 100.0
            slot_penetration = _ROLE_PENETRATION.get(op.species.primary_role, 0.0)
            slots_to_create.append(
                BattleSlot(
                    team=team,
                    pokemon=op.species,
                    owned_pokemon=op,
                    position=position,
                    grid_position=grid_pos,
                    is_active=is_active,
                    level=level,
                    current_hp=max_hp,
                    max_hp=max_hp,
                    selected_move=selected_move,
                    control=slot_control,
                    penetration=slot_penetration,
                )
            )

        created_slots = BattleSlot.objects.bulk_create(slots_to_create)

        # Create BattleSlotHeldEffect for slots whose OwnedPokemon has a held effect
        held_effect_rows = []
        for slot in created_slots:
            if slot.owned_pokemon_id:
                op = owned_map.get(slot.owned_pokemon_id)
                if op and op.held_effect_id:
                    held_effect_rows.append(
                        BattleSlotHeldEffect(slot=slot, effect_id=op.held_effect_id)
                    )
        if held_effect_rows:
            BattleSlotHeldEffect.objects.bulk_create(held_effect_rows)

        logger.info("Set team (owned) for %s in Battle #%d", user, battle.pk)
        return team

    @transaction.atomic
    def start_battle(self, battle: Battle) -> Battle:
        """Validate both teams are set and transition battle to active."""
        if battle.status != BattleStatus.SETUP:
            raise ValueError(f"Battle is not in setup state (current: {battle.status})")

        team_count = battle.teams.count()
        if team_count < 2:
            raise ValueError(f"Need 2 teams to start; only {team_count} set")

        self._validator.validate(battle)

        battle.status = BattleStatus.ACTIVE
        battle.save(update_fields=["status"])
        BattleLog.objects.create(
            battle=battle,
            round_number=0,
            message="Battle started! (6v6 — 3 front, 3 back per side)",
            log_type=LogType.INFO,
        )
        logger.info("Battle #%d started", battle.pk)
        return battle

    @transaction.atomic
    def execute_round(
        self,
        battle: Battle,
        player_one_actions: list[dict],
        player_two_actions: list[dict],
    ) -> BattleRound:
        """
        Execute one full round of battle.

        Each action dict: {"slot_id": int, "move_id": int, "target_id": int}

        Turn order:
          1. always_first moves
          2. move priority (descending)
          3. effective speed (descending)
          4. grid position (front before back)
          5. random tie-breaker
        """
        if battle.status != BattleStatus.ACTIVE:
            raise ValueError(f"Battle is not active (current: {battle.status})")

        round_obj = BattleRound.objects.create(
            battle=battle,
            round_number=battle.current_round,
        )

        # Passive held effects fire at the start of each round
        for team in battle.teams.prefetch_related("slots__held_effect_state__effect").all():
            for slot in team.slots.all():
                if not slot.is_fainted and slot.is_active:
                    _resolve_held_effect("passive", slot, round_obj)

        all_actions = player_one_actions + player_two_actions
        sorted_actions = self._sort_actions(all_actions)

        for action_data in sorted_actions:
            try:
                attacker_slot = BattleSlot.objects.select_related(
                    "pokemon__primary_type",
                    "pokemon__secondary_type",
                    "team__battle",
                ).get(pk=action_data["slot_id"])
                move = Move.objects.select_related(
                    "applies_status", "trigger_status", "move_type"
                ).get(pk=action_data["move_id"])
                target_slot = BattleSlot.objects.select_related(
                    "pokemon__primary_type",
                    "pokemon__secondary_type",
                ).get(pk=action_data["target_id"])
            except (BattleSlot.DoesNotExist, Move.DoesNotExist):
                logger.warning("Invalid action data in round %d: %s", battle.current_round, action_data)
                continue

            if attacker_slot.is_fainted or not attacker_slot.is_active:
                continue

            # Passive 2 moves never execute directly
            if move.slot_type == MoveSlotType.PASSIVE_2:
                continue

            can_act, reason = _effect_engine.can_act(attacker_slot)
            if not can_act:
                BattleLog.objects.create(
                    battle=battle,
                    round_number=battle.current_round,
                    message=f"{attacker_slot.pokemon.name} is {reason} and cannot move!",
                    log_type=LogType.STATUS,
                )
                continue

            # P2-1: BLINDED — cannot use standard attacks
            if (
                move.slot_type == MoveSlotType.STANDARD
                and _effect_engine.has_status(attacker_slot, StatusName.BLINDED)
            ):
                BattleLog.objects.create(
                    battle=battle,
                    round_number=battle.current_round,
                    message=f"{attacker_slot.pokemon.name} is blinded and cannot use standard attacks!",
                    log_type=LogType.STATUS,
                )
                continue

            # P2-3: CONFUSED — 33% chance to hit self instead
            if _effect_engine.has_status(attacker_slot, StatusName.CONFUSED):
                if random.random() < 0.33:
                    atk = attacker_slot.pokemon.calculate_stat(
                        attacker_slot.pokemon.base_attack, attacker_slot.level
                    )
                    def_ = attacker_slot.pokemon.calculate_stat(
                        attacker_slot.pokemon.base_defense, attacker_slot.level
                    )
                    self_dmg = max(1, int(((2 * attacker_slot.level / 5 + 2) * 40 * atk / def_) / 50 + 2))
                    attacker_slot.current_hp = max(0, attacker_slot.current_hp - self_dmg)
                    if attacker_slot.current_hp == 0:
                        attacker_slot.is_fainted = True
                    attacker_slot.save(update_fields=["current_hp", "is_fainted"])
                    BattleLog.objects.create(
                        battle=battle,
                        round_number=battle.current_round,
                        message=f"{attacker_slot.pokemon.name} is confused and hurt itself! ({self_dmg} damage)",
                        log_type=LogType.STATUS,
                    )
                    continue

            self._combo_engine.resolve_combo_chain(
                battle=battle,
                attacker_slot=attacker_slot,
                move=move,
                target_slot=target_slot,
                round_number=battle.current_round,
            )

            # Apply cooldown for this move
            self._apply_move_cooldown(attacker_slot, move)

        # ── Support move rotation (PASSIVE_1 fires automatically on cooldown) ──
        self._execute_support_moves(battle, round_obj)
        self._apply_formation_passives(battle, round_obj)

        # Decrement all cooldowns at end of round
        self._tick_cooldowns(battle)

        # Tick all status effects
        self._tick_all_statuses(battle, battle.current_round)

        # Check for battle end
        winner = self.check_winner(battle)
        if winner is not None:
            self._end_battle(battle, winner)
        else:
            battle.current_round += 1
            battle.save(update_fields=["current_round"])

        return round_obj

    @transaction.atomic
    def substitute_pokemon(
        self,
        battle: Battle,
        team: BattleTeam,
        fainted_slot: BattleSlot,
        bench_slot: BattleSlot,
    ) -> None:
        """
        Replace a fainted active slot with an alive bench slot.

        Instead of swapping positions (which would violate the unique_together
        constraint on (team, position) during sequential saves), we update the
        active slot in-place with the incoming pokemon's data, then mark the
        bench slot as fainted (consumed).
        """
        if not fainted_slot.is_fainted:
            raise ValueError(f"{fainted_slot.pokemon.name} has not fainted.")
        if bench_slot.is_fainted:
            raise ValueError(f"{bench_slot.pokemon.name} has already fainted.")
        if fainted_slot.team_id != team.pk or bench_slot.team_id != team.pk:
            raise ValueError("Both slots must belong to the same team.")
        if bench_slot.is_active:
            raise ValueError(f"{bench_slot.pokemon.name} is already on the field.")

        incoming_name = bench_slot.pokemon.name
        outgoing_name = fainted_slot.pokemon.name

        # Update the active slot in-place with the bench pokemon's data.
        # This avoids touching `position`/`grid_position`, so the
        # unique_together constraint on (team, position) is never violated.
        fainted_slot.pokemon = bench_slot.pokemon
        fainted_slot.owned_pokemon = bench_slot.owned_pokemon
        fainted_slot.level = bench_slot.level
        fainted_slot.current_hp = bench_slot.current_hp
        fainted_slot.max_hp = bench_slot.max_hp
        fainted_slot.is_fainted = False
        fainted_slot.selected_move = bench_slot.selected_move
        fainted_slot.selected_target = None
        fainted_slot.last_move_used = None
        fainted_slot.save(update_fields=[
            "pokemon", "owned_pokemon", "level", "current_hp", "max_hp",
            "is_fainted", "selected_move", "selected_target", "last_move_used",
        ])

        # Mark the bench slot as consumed so it is excluded from future
        # substitution candidates and counted toward the team's faint total.
        bench_slot.is_fainted = True
        bench_slot.save(update_fields=["is_fainted"])

        BattleLog.objects.create(
            battle=battle,
            round_number=battle.current_round,
            message=(
                f"{incoming_name} enters the field, replacing {outgoing_name}!"
            ),
            log_type=LogType.INFO,
        )

    @transaction.atomic
    def bench_switch(
        self,
        battle: Battle,
        team: BattleTeam,
        active_slot: BattleSlot,
        bench_slot: BattleSlot,
    ) -> None:
        """
        Voluntarily swap an active Pokemon to the bench, bringing a bench Pokemon
        to the field.

        GDD §5.6 rules:
        - Switching is an action — the slot passes its attack turn this round.
        - The switch happens at the START of the round (called before execute_round).
        - Volatile statuses are CLEARED from the switching-out Pokemon.
        - Persistent statuses are KEPT on both Pokemon.
        - Cannot switch into a fainted slot.
        """
        if active_slot.is_fainted:
            raise ValueError(f"{active_slot.pokemon.name} has already fainted.")
        if bench_slot.is_fainted:
            raise ValueError(
                f"{bench_slot.pokemon.name} has already fainted — cannot switch in."
            )
        if active_slot.team_id != team.pk or bench_slot.team_id != team.pk:
            raise ValueError("Both slots must belong to the same team.")
        if not active_slot.is_active:
            raise ValueError(f"{active_slot.pokemon.name} is not on the field.")
        if bench_slot.is_active:
            raise ValueError(f"{bench_slot.pokemon.name} is already on the field.")

        outgoing_name = active_slot.pokemon.name
        incoming_name = bench_slot.pokemon.name

        # Swap is_active and grid_position; position (1-6) stays fixed.
        active_grid = active_slot.grid_position
        bench_grid = bench_slot.grid_position

        active_slot.is_active = False
        active_slot.grid_position = bench_grid
        active_slot.selected_move = None
        active_slot.selected_target = None
        active_slot.save(update_fields=[
            "is_active", "grid_position", "selected_move", "selected_target",
        ])

        bench_slot.is_active = True
        bench_slot.grid_position = active_grid
        bench_slot.selected_move = None
        bench_slot.selected_target = None
        bench_slot.save(update_fields=[
            "is_active", "grid_position", "selected_move", "selected_target",
        ])

        # Clear volatile statuses from the switching-out Pokemon (GDD §5.6).
        _effect_engine.remove_volatile_statuses(active_slot)

        BattleLog.objects.create(
            battle=battle,
            round_number=battle.current_round,
            message=f"{outgoing_name} is recalled! {incoming_name} enters the field!",
            log_type=LogType.INFO,
        )

    def get_battle_state(self, battle: Battle) -> dict:
        """Return a complete snapshot of the current battle state for the UI."""
        teams = list(
            battle.teams.prefetch_related(
                "slots__pokemon__primary_type",
                "slots__pokemon__secondary_type",
                "slots__pokemon__moves",
                "slots__active_statuses__status",
                "slots__move_cooldowns__move",
                "slots__selected_move",
                "slots__selected_target",
            ).select_related("owner")
        )

        logs = list(
            battle.logs.filter(round_number=battle.current_round)
            .order_by("created_at")
        )
        combo_logs = list(battle.logs.filter(log_type=LogType.COMBO).order_by("created_at"))

        return {
            "battle": battle,
            "teams": teams,
            "logs": logs,
            "combo_logs": combo_logs,
            "current_round": battle.current_round,
            "status": battle.status,
        }

    def check_winner(self, battle: Battle) -> User | None:
        """
        Return the winner User if one team has all 6 slots fainted, else None.

        A team loses only when both the 4 active AND 2 bench slots are all fainted
        (no replacements remain).
        """
        teams = list(battle.teams.prefetch_related("slots").all())
        if len(teams) < 2:
            return None

        for team in teams:
            all_fainted = all(slot.is_fainted for slot in team.slots.all())
            if all_fainted:
                other_team = next(t for t in teams if t.pk != team.pk)
                return other_team.owner

        return None

    def prepare_player_actions(
        self,
        battle: Battle,
        player_team: BattleTeam,
        submitted: dict[int, dict],
    ) -> list[dict]:
        """
        Build player actions from mystery toggle inputs (Naruto Online style).

        submitted: {slot_id: {"use_mystery": bool}}

        For each active non-fainted slot:
        - If use_mystery=True and mystery move not on cooldown → fire mystery move
        - Otherwise → fire standard move (auto)
        - Target auto-selected: lowest-HP front-row enemy (front-row-first rule)

        Returns list[{"slot_id": int, "move_id": int, "target_id": int}].
        """
        enemy_team = battle.teams.exclude(pk=player_team.pk).first()
        alive_enemies = list(
            BattleSlot.objects.filter(
                team=enemy_team, is_fainted=False, is_active=True
            ).select_related("pokemon")
        ) if enemy_team else []

        if not alive_enemies:
            return []

        # Auto-select target: lowest-HP front-row enemy, else lowest-HP alive.
        # Exclude HIDDEN slots (Phase 6 — cannot be targeted).
        front_positions = {
            GridPosition.FRONT_LEFT,
            GridPosition.FRONT_CENTER,
            GridPosition.FRONT_RIGHT,
        }
        alive_visible = [
            s for s in alive_enemies
            if not _effect_engine.has_status(s, StatusName.HIDDEN)
        ]
        front_alive = [s for s in alive_visible if s.grid_position in front_positions]
        pool = front_alive or alive_visible
        if not pool:
            return []
        auto_target = min(pool, key=lambda s: s.current_hp)

        cooldown_set: set[tuple[int, int]] = set(
            MoveCooldown.objects.filter(
                slot__team=player_team,
                remaining_rounds__gt=0,
            ).values_list("slot_id", "move_id")
        )

        active_slots = list(
            BattleSlot.objects.filter(
                team=player_team, is_fainted=False, is_active=True
            ).select_related(
                "pokemon",
                "owned_pokemon",
                "owned_pokemon__move_standard",
                "owned_pokemon__move_special",
            )
            .prefetch_related("pokemon__moves")
        )

        actions: list[dict] = []
        for slot in active_slots:
            sub = submitted.get(slot.pk, {})
            use_mystery = sub.get("use_mystery", False)

            move = None
            if use_mystery:
                # P2-2: ACUPUNCTURED — cannot use mystery moves
                # P2-5: TAUNTED — forced to use standard, mystery blocked
                mystery_blocked = (
                    _effect_engine.has_status(slot, StatusName.ACUPUNCTURED)
                    or _effect_engine.has_status(slot, StatusName.TAUNTED)
                )
                if not mystery_blocked:
                    mystery = self._get_mystery_move(slot)
                    if mystery and (slot.pk, mystery.pk) not in cooldown_set:
                        move = mystery

            if move is None:
                move = self._get_standard_move(slot)

            if move is None:
                logger.warning(
                    "Slot %d (%s) has no usable move, skipping.",
                    slot.pk,
                    slot.pokemon.name,
                )
                continue

            actions.append({
                "slot_id": slot.pk,
                "move_id": move.pk,
                "target_id": auto_target.pk,
            })

        return actions

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _pick_default_move(pokemon: Pokemon) -> Move | None:
        """Return the standard-slot move for the pokemon, or the first move if none."""
        moves = list(pokemon.moves.all())
        for m in moves:
            if m.slot_type == MoveSlotType.STANDARD:
                return m
        return moves[0] if moves else None

    @staticmethod
    def _get_move_for_slot(slot: BattleSlot, move_id: int) -> Move | None:
        """Return the Move if it belongs to this slot, else None.

        For owned slots, only the 4 assigned active moves are valid.
        Falls back to the species move pool for AI/legacy slots.
        """
        if slot.owned_pokemon_id is not None:
            op = slot.owned_pokemon
            for m in (op.move_standard, op.move_chase, op.move_special, op.move_support):
                if m is not None and m.pk == move_id:
                    return m
            return None
        try:
            return slot.pokemon.moves.get(pk=move_id)
        except Move.DoesNotExist:
            return None

    @staticmethod
    def _get_standard_move(slot: BattleSlot) -> Move | None:
        """Return the standard-type move for the slot."""
        if slot.owned_pokemon_id is not None and slot.owned_pokemon.move_standard:
            return slot.owned_pokemon.move_standard
        try:
            return slot.pokemon.moves.filter(slot_type=MoveSlotType.STANDARD).first()
        except Move.DoesNotExist:
            return None

    @staticmethod
    def _get_mystery_move(slot: BattleSlot) -> Move | None:
        """Return the mystery-type move for the slot."""
        if slot.owned_pokemon_id is not None and slot.owned_pokemon.move_special:
            return slot.owned_pokemon.move_special
        return slot.pokemon.moves.filter(slot_type=MoveSlotType.MYSTERY).first()

    @staticmethod
    def _validate_target(
        target_id: int | None,
        alive_enemies: list[BattleSlot],
    ) -> BattleSlot | None:
        """
        Resolve the intended target, enforcing front-row-first targeting.

        If the player targets a back-row slot but a living front-row ally exists
        on the same side, the attack is redirected to the lowest-HP front-row slot.
        This mirrors physical card-game rules: you must clear the front before
        hitting the back.
        """
        if target_id is None:
            return None
        intended: BattleSlot | None = None
        for slot in alive_enemies:
            if slot.pk == target_id:
                intended = slot
                break
        if intended is None:
            return None

        # If target is in back row, check whether any front-row ally is still alive
        back_positions = {GridPosition.BACK_LEFT, GridPosition.BACK_RIGHT}
        front_positions = {GridPosition.FRONT_LEFT, GridPosition.FRONT_RIGHT}
        if intended.grid_position in back_positions:
            living_front = [
                s for s in alive_enemies if s.grid_position in front_positions
            ]
            if living_front:
                # Redirect to lowest-HP front-row target
                return min(living_front, key=lambda s: s.current_hp)

        return intended

    def _sort_actions(self, actions: list[dict]) -> list[dict]:
        """
        Sort actions by turn order:
          1. always_first (moves with always_first=True go first, always_last go last)
          2. priority (descending)
          3. effective speed (descending)
          4. grid position order (lower = earlier)
          5. random tie-breaker
        """
        slot_ids = [a["slot_id"] for a in actions]
        move_ids = [a["move_id"] for a in actions]

        slots_by_id = {
            s.pk: s
            for s in BattleSlot.objects.filter(pk__in=slot_ids).select_related("pokemon")
        }
        moves_by_id = {
            m.pk: m
            for m in Move.objects.filter(pk__in=move_ids)
        }

        def sort_key(action: dict) -> tuple:
            slot = slots_by_id.get(action["slot_id"])
            move = moves_by_id.get(action["move_id"])
            if slot is None or move is None:
                return (1, 0, 0, 99, random.random())

            forced = -1 if move.always_first else (1 if move.always_last else 0)
            priority = -move.priority
            speed = slot.pokemon.calculate_stat(slot.pokemon.base_initiative, slot.level)
            modifiers = _effect_engine.get_stat_modifiers(slot)
            effective_speed = -int(speed * modifiers.get("speed", 1.0))
            grid_order = GRID_TURN_ORDER.get(slot.grid_position, 99)
            return (forced, priority, effective_speed, grid_order, random.random())

        return sorted(actions, key=sort_key)

    def _execute_support_moves(self, battle: Battle, round_obj: BattleRound) -> None:
        """
        Fire PASSIVE_1 (support) moves automatically on their cooldown schedule.

        A support move fires for a slot when:
          - The slot has an OwnedPokemon with move_support assigned
          - The move_support has no active MoveCooldown for that slot (i.e. cooldown expired)
          - The slot is alive and active

        Support moves target the lowest-HP ally on the same team (heal/buff scenario).
        If the move has power > 0 (offensive support), it targets the lowest-HP enemy.
        """
        slots = BattleSlot.objects.filter(
            team__battle=battle,
            is_fainted=False,
            is_active=True,
            owned_pokemon__isnull=False,
        ).select_related(
            "owned_pokemon__move_support__applies_status",
            "team",
        )

        for slot in slots:
            support_move = slot.owned_pokemon.move_support
            if support_move is None:
                continue

            # Check whether support move is on cooldown
            on_cd = MoveCooldown.objects.filter(slot=slot, move=support_move).exists()
            if on_cd:
                continue

            # Choose target: offensive (power > 0) → lowest-HP enemy; otherwise → lowest-HP ally
            if support_move.power and support_move.power > 0:
                enemy_team = battle.teams.exclude(pk=slot.team_id).first()
                target = self._combo_engine._select_target(enemy_team, support_move) if enemy_team else None
            else:
                # Friendly target: lowest-HP non-fainted ally (heal the most wounded)
                allies = BattleSlot.objects.filter(
                    team=slot.team, is_fainted=False, is_active=True
                ).order_by("current_hp")
                target = allies.first()

            if target is None:
                continue

            BattleLog.objects.create(
                battle=battle,
                round_number=round_obj.round_number,
                message=(
                    f"✦ {slot.pokemon.name} used {support_move.themed_name or support_move.name} "
                    f"[Support]!"
                ),
                log_type=LogType.STATUS,
            )

            self._combo_engine._execute_move(
                round_obj=round_obj,
                attacker_slot=slot,
                move=support_move,
                target_slot=target,
                chain_position=0,
                is_combo=False,
            )
            self._apply_move_cooldown(slot, support_move)

    def _apply_formation_passives(self, battle: Battle, round_obj: BattleRound) -> None:
        """
        End-of-round formation passive effects:

        Last Stand  — if a slot's current HP <= 30% of max, it gets a +30% attack bonus
                      (stored as a BattleLog STATUS message; the attack buff is handled in
                      _calculate_damage via the slot's stat modifiers on the NEXT round).
        Medic       — if a slot's current HP <= 50% of max, heal 10% of max HP.
        """
        slots = BattleSlot.objects.filter(
            team__battle=battle,
            is_fainted=False,
            is_active=True,
        ).select_related("pokemon", "team")

        for slot in slots:
            max_hp = slot.pokemon.calculate_stat(slot.pokemon.base_hp, slot.level)
            if max_hp <= 0:
                continue
            hp_pct = slot.current_hp / max_hp

            # Medic: heal 10% of max HP if below 50%
            if hp_pct <= 0.50:
                heal = max(1, int(max_hp * 0.10))
                new_hp = min(max_hp, slot.current_hp + heal)
                if new_hp != slot.current_hp:
                    slot.current_hp = new_hp
                    slot.save(update_fields=["current_hp"])
                    BattleLog.objects.create(
                        battle=battle,
                        round_number=round_obj.round_number,
                        message=f"+ {slot.pokemon.name} recovers {heal} HP [Medic Passive]",
                        log_type=LogType.STATUS,
                    )

    @staticmethod
    def _apply_move_cooldown(slot: BattleSlot, move: Move) -> None:
        """Set cooldown for this move if it has one."""
        if move.cooldown <= 0:
            return
        MoveCooldown.objects.update_or_create(
            slot=slot,
            move=move,
            defaults={"remaining_rounds": move.cooldown},
        )

    @staticmethod
    def _tick_cooldowns(battle: Battle) -> None:
        """Decrement all active cooldowns by 1; delete those that reach 0."""
        cooldowns = MoveCooldown.objects.filter(slot__team__battle=battle)
        to_delete = []
        to_update = []
        for cd in cooldowns:
            cd.remaining_rounds -= 1
            if cd.remaining_rounds <= 0:
                to_delete.append(cd.pk)
            else:
                to_update.append(cd)

        if to_delete:
            MoveCooldown.objects.filter(pk__in=to_delete).delete()
        for cd in to_update:
            cd.save(update_fields=["remaining_rounds"])

    def _tick_all_statuses(self, battle: Battle, round_number: int) -> None:
        """Tick status effects on all non-fainted active slots in the battle."""
        slots = BattleSlot.objects.filter(
            team__battle=battle, is_fainted=False, is_active=True
        )
        for slot in slots:
            results = _effect_engine.tick_statuses(slot, round_number)
            for result in results:
                if result.get("message"):
                    BattleLog.objects.create(
                        battle=battle,
                        round_number=round_number,
                        message=result["message"],
                        log_type=LogType.STATUS,
                    )
                    if slot.is_fainted:
                        BattleLog.objects.create(
                            battle=battle,
                            round_number=round_number,
                            message=f"{slot.pokemon.name} fainted from status!",
                            log_type=LogType.FAINT,
                        )

    def _end_battle(self, battle: Battle, winner: User) -> None:
        """Finalise the battle — set status, record winner, award EXP, Ryo, and stickers."""
        battle.status = BattleStatus.FINISHED
        battle.winner = winner
        battle.save(update_fields=["status", "winner"])

        # Update winner stats
        winner.battles_won += 1
        winner.battles_played += 1
        if battle.max_combo_chain > winner.longest_combo_chain:
            winner.longest_combo_chain = battle.max_combo_chain

        # Badge: Perfect Victory — win with no fainted Pokemon on winner's team
        winner_team = battle.teams.filter(owner=winner).first()
        if winner_team and not winner_team.slots.filter(is_fainted=True).exists():
            winner.perfect_victories += 1

        # Badge: AI Breaker — beat Hard AI
        if battle.ai_difficulty == AIDifficulty.HARD:
            winner.hard_ai_wins += 1

        winner.save(update_fields=[
            "battles_won", "battles_played", "longest_combo_chain",
            "perfect_victories", "hard_ai_wins",
        ])

        # Update loser battles_played (previously not tracked)
        AI_USERNAME = "__ai_trainer__"
        for team in battle.teams.select_related("owner"):
            if team.owner_id != winner.pk and team.owner.username != AI_USERNAME:
                team.owner.battles_played += 1
                team.owner.save(update_fields=["battles_played"])

        BattleLog.objects.create(
            battle=battle,
            round_number=battle.current_round,
            message=f"{winner} wins the battle!",
            log_type=LogType.INFO,
        )

        self._award_exp_to_teams(battle, winner)
        self._award_ryo_to_teams(battle, winner)
        self._award_event_bonuses(battle, winner)
        self._award_stickers(battle, winner)
        _quest_service.on_battle_won(winner, battle)

        # Award ranked points for PvP (non-AI, non-tutorial) battles.
        if not battle.is_ai_battle and not battle.is_tutorial:
            self._award_ranked_points(battle, winner)

        logger.info("Battle #%d ended. Winner: %s", battle.pk, winner)

    def _award_stickers(self, battle: Battle, winner: User) -> None:
        """
        Award stickers to the winner after a battle.

        Two possible awards (both checked independently):
        1. Sticker pack — granted every 10 wins via grant_pack_if_eligible().
        2. Full Art sticker — granted if the battle's max combo chain >= 5
           via award_on_combo_win().
        """
        # Award 1: sticker pack every 10 wins
        pack = _sticker_service.grant_pack_if_eligible(winner)
        if pack:
            BattleLog.objects.create(
                battle=battle,
                round_number=battle.current_round,
                message=f"🎁 {winner} earned a sticker pack! (Win #{winner.battles_won})",
                log_type=LogType.INFO,
            )
            logger.info(
                "Sticker pack granted to %s (battle #%d, win #%d)",
                winner,
                battle.pk,
                winner.battles_won,
            )

        # Award 2: Full Art sticker for long combo chains
        if battle.max_combo_chain >= 5:
            sticker = _sticker_service.award_on_combo_win(
                player=winner,
                chain_length=battle.max_combo_chain,
            )
            if sticker:
                BattleLog.objects.create(
                    battle=battle,
                    round_number=battle.current_round,
                    message=(
                        f"⚡ Combo chain of {battle.max_combo_chain}! "
                        f"{winner} earned a Full Art {sticker.pokemon.name} sticker!"
                    ),
                    log_type=LogType.COMBO,
                )
                logger.info(
                    "Full Art sticker awarded to %s for %d-chain (battle #%d)",
                    winner,
                    battle.max_combo_chain,
                    battle.pk,
                )

    def _award_event_bonuses(self, battle: Battle, winner: User) -> None:
        """Apply any active seasonal event bonuses to the winner (GDD §20.11)."""
        from .models import BattleLog, LogType

        summary = _event_service.apply_battle_win_bonus(winner, battle)
        if not summary:
            return

        parts = []
        if "ryo" in summary:
            parts.append(f"+{summary['ryo']} Ryo (event bonus)")
        if "sticker_dust" in summary:
            parts.append(f"+{summary['sticker_dust']} Dust (event bonus)")

        BattleLog.objects.create(
            battle=battle,
            round_number=battle.current_round,
            message="🎉 " + " · ".join(parts),
            log_type=LogType.INFO,
        )

    def _award_ranked_points(self, battle: Battle, winner: User) -> None:
        """Update ranked profiles for both players in a PvP battle (GDD §15.3)."""
        from apps.ranked.services import RankedSeasonService

        loser = None
        for team in battle.teams.select_related("owner"):
            if team.owner_id != winner.pk:
                loser = team.owner
                break

        if loser is None:
            logger.warning("Battle #%d has no loser team — skipping ranked award.", battle.pk)
            return

        ranked_svc = RankedSeasonService()
        winner_profile, pts = ranked_svc.record_win(winner, loser)
        if winner_profile is not None:
            BattleLog.objects.create(
                battle=battle,
                round_number=battle.current_round,
                message=f"Ranked: {winner} +{pts} pts → {winner_profile.get_tier_display()} {winner_profile.sub_tier}",
                log_type=LogType.INFO,
            )

    def _award_ryo_to_teams(self, battle: Battle, winner: User) -> None:
        """Award Ryo to every real (non-AI) player based on win/loss."""
        AI_USERNAME = "__ai_trainer__"
        for team in battle.teams.select_related("owner"):
            if team.owner.username == AI_USERNAME:
                continue
            won = team.owner_id == winner.pk
            amount = BATTLE_WIN_RYO if won else BATTLE_LOSS_RYO
            award_ryo(team.owner, amount)
            logger.debug(
                "Battle #%d: awarded %d Ryo to %s (%s)",
                battle.pk,
                amount,
                team.owner,
                "win" if won else "loss",
            )

    def _award_exp_to_teams(self, battle: Battle, winner: User) -> None:
        """Award battle EXP to every real (non-AI) player's OwnedPokemon."""
        AI_USERNAME = "__ai_trainer__"

        for team in battle.teams.select_related("owner").prefetch_related("slots__pokemon"):
            if team.owner.username == AI_USERNAME:
                continue

            won = team.owner_id == winner.pk
            species_ids = [slot.pokemon_id for slot in team.slots.all()]
            owned_by_species: dict[int, OwnedPokemon] = {}
            for op in OwnedPokemon.objects.filter(
                owner=team.owner,
                species_id__in=species_ids,
            ).select_related("species"):
                owned_by_species.setdefault(op.species_id, op)

            for slot in team.slots.all():
                owned = owned_by_species.get(slot.pokemon_id)
                if owned is None or owned.is_training:
                    continue
                _award_battle_exp(owned, won=won)
