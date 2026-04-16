"""
StatusEffectEngine — apply, remove, tick, and query status effects on BattleSlots.

This module is the single source of truth for all status effect logic.
It is used by game/services.py (ComboChainEngine, BattleService).
"""
import logging
import random
from typing import TYPE_CHECKING

from django.db.models import QuerySet

from .constants import (
    ADVANCED_STATUSES,
    DAMAGE_PER_TURN_SIXTEENTHS,
    NARUTO_STATUSES,
    PERSISTENT_STATUSES,
    PHYSICAL_STATUSES,
    STAT_MODIFIERS,
    TYPE_IMMUNITIES,
    UTILITY_STATUSES,
    VOLATILE_STATUSES,
    StatusName,
)
from .models import ActiveStatusEffect, StatusEffect

if TYPE_CHECKING:
    from apps.game.models import BattleSlot

logger = logging.getLogger(__name__)

# Probability of thawing from Frozen each turn (20%)
_FREEZE_THAW_CHANCE = 0.20
# Probability of waking from sleep (resolved by remaining_turns countdown)
# Probability of losing a turn due to paralysis (25%)
_PARALYSIS_SKIP_CHANCE = 0.25
# Probability of hitting self when confused (33%)
_CONFUSION_SELF_HIT_CHANCE = 0.33
# Probability of refusing to attack when infatuated (50%)
_INFATUATION_REFUSE_CHANCE = 0.50


class StatusEffectEngine:
    """
    Stateless engine that manages all status effects on BattleSlots.

    All methods are pure operations on the database; no internal state is kept.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def apply_status(
        self,
        slot: "BattleSlot",
        status: StatusEffect,
        round_number: int,
        duration_override: int | None = None,
        applied_by_slot: "BattleSlot | None" = None,
    ) -> ActiveStatusEffect | None:
        """
        Apply a status effect to a BattleSlot.

        Returns the created ActiveStatusEffect, or None if the application
        failed (immune, mutually exclusive, or already active).
        """
        if self._check_immunity(slot, status):
            logger.debug("%s is immune to %s", slot, status.name)
            return None

        if status.name in PERSISTENT_STATUSES and self._has_any_persistent(slot):
            logger.debug("%s already has a persistent status; cannot apply %s", slot, status.name)
            return None

        # Physical states are mutually exclusive: clear the current one before applying a new one
        if status.name in PHYSICAL_STATUSES and self._has_any_physical(slot):
            self.clear_physical_statuses(slot)

        # Idempotent: no stacking of the same status
        if self.has_status(slot, status.name):
            logger.debug("%s already has %s", slot, status.name)
            return None

        duration = duration_override if duration_override is not None else self._roll_duration(status)

        active = ActiveStatusEffect.objects.create(
            slot=slot,
            status=status,
            remaining_turns=duration,
            applied_at_round=round_number,
            turns_active=0,
            applied_by_slot=applied_by_slot,
        )
        logger.info("Applied %s to %s (duration=%s)", status.name, slot, duration)
        return active

    def remove_status(self, slot: "BattleSlot", status: StatusEffect) -> bool:
        """
        Remove a specific status from a BattleSlot.

        Returns True if the status was found and removed.
        """
        deleted, _ = ActiveStatusEffect.objects.filter(slot=slot, status=status).delete()
        removed = deleted > 0
        if removed:
            logger.info("Removed %s from %s", status.name, slot)
        return removed

    def remove_volatile_statuses(self, slot: "BattleSlot") -> int:
        """
        Remove all volatile, physical, utility, and advanced statuses from a BattleSlot.

        Called when a Pokemon switches out. Returns the count removed.
        """
        clearable_names = (
            list(VOLATILE_STATUSES)
            + list(NARUTO_STATUSES)
            + list(PHYSICAL_STATUSES)
            + list(UTILITY_STATUSES)
            + list(ADVANCED_STATUSES)
        )
        deleted, _ = ActiveStatusEffect.objects.filter(
            slot=slot,
            status__name__in=clearable_names,
        ).delete()
        if deleted:
            logger.info("Cleared %d volatile/physical/utility statuses from %s", deleted, slot)
        return deleted

    def tick_statuses(
        self, slot: "BattleSlot", round_number: int  # noqa: ARG002
    ) -> list[dict]:
        """
        Process all active statuses on a slot for the current round.

        - Deals damage-per-turn effects
        - Decrements remaining_turns
        - Removes expired statuses
        - Escalates badly_poisoned and corroded

        Returns a list of result dicts for logging/UI:
          {"status": str, "damage": int, "expired": bool, "message": str}
        """
        results: list[dict] = []
        active_statuses = (
            ActiveStatusEffect.objects.filter(slot=slot)
            .select_related("status", "applied_by_slot__pokemon")
        )

        for active in active_statuses:
            result = self._tick_single(slot, active)
            if result:
                results.append(result)

        return results

    def get_active_statuses(self, slot: "BattleSlot") -> QuerySet:
        """Return a QuerySet of all ActiveStatusEffects on a slot."""
        return ActiveStatusEffect.objects.filter(slot=slot).select_related("status")

    def has_status(self, slot: "BattleSlot", status_name: str) -> bool:
        """Return True if the slot has the named status currently active."""
        return ActiveStatusEffect.objects.filter(
            slot=slot, status__name=status_name
        ).exists()

    def can_act(self, slot: "BattleSlot") -> tuple[bool, str]:
        """
        Determine whether the Pokemon can take an action this turn.

        Returns (can_act: bool, reason: str).
        The reason is empty string when can_act is True.
        """
        active_statuses = list(
            ActiveStatusEffect.objects.filter(slot=slot).select_related("status")
        )
        status_names = {a.status.name for a in active_statuses}

        if StatusName.FROZEN in status_names:
            if random.random() < _FREEZE_THAW_CHANCE:
                self._expire_status_by_name(slot, StatusName.FROZEN)
                return True, ""
            return False, "frozen"

        if StatusName.ASLEEP in status_names:
            # Sleep wakes based on remaining_turns reaching 0 (handled in tick)
            asleep_active = next(
                (a for a in active_statuses if a.status.name == StatusName.ASLEEP), None
            )
            if asleep_active and (asleep_active.remaining_turns is None or asleep_active.remaining_turns > 0):
                return False, "asleep"

        if StatusName.PARALYZED in status_names:
            if random.random() < _PARALYSIS_SKIP_CHANCE:
                return False, "paralyzed"

        if StatusName.IMMOBILE in status_names:
            return False, "immobile"

        if StatusName.FLINCHED in status_names:
            return False, "flinched"

        if StatusName.INTERRUPTED in status_names:
            return False, "interrupted"

        # P2-4: INFATUATED — 50% chance to refuse to attack
        if StatusName.INFATUATED in status_names:
            if random.random() < _INFATUATION_REFUSE_CHANCE:
                return False, "infatuated"

        # Confusion — may hit self (handled in battle service, not here)
        return True, ""

    def get_stat_modifiers(self, slot: "BattleSlot") -> dict[str, float]:
        """
        Aggregate all stat multipliers from active statuses on a slot.

        Returns a dict of stat_name → cumulative_multiplier.
        """
        modifiers: dict[str, float] = {}
        active_statuses = (
            ActiveStatusEffect.objects.filter(slot=slot)
            .select_related("status")
        )

        for active in active_statuses:
            stat_mods = STAT_MODIFIERS.get(active.status.name, {})
            for stat, multiplier in stat_mods.items():
                if stat in modifiers:
                    modifiers[stat] *= multiplier
                else:
                    modifiers[stat] = multiplier

            # Corroded worsens each turn: sp_defense drops by 10% per turn active
            if active.status.name == StatusName.CORRODED:
                penalty = max(0.1, 1.0 - (active.turns_active * 0.1))
                modifiers["sp_defense"] = modifiers.get("sp_defense", 1.0) * penalty

        return modifiers

    def get_active_status_names(self, slot: "BattleSlot") -> set[str]:
        """Return the set of status names currently active on a slot."""
        return set(
            ActiveStatusEffect.objects.filter(slot=slot).values_list("status__name", flat=True)
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _check_immunity(self, slot: "BattleSlot", status: StatusEffect) -> bool:
        """Return True if the slot's Pokemon type(s) are immune to this status."""
        immune_types = TYPE_IMMUNITIES.get(status.name, [])
        if not immune_types:
            return False
        slot_types = {slot.pokemon.primary_type.name}
        if slot.pokemon.secondary_type:
            slot_types.add(slot.pokemon.secondary_type.name)
        return bool(slot_types & set(immune_types))

    def _has_any_persistent(self, slot: "BattleSlot") -> bool:
        """Return True if any persistent status is currently active on the slot."""
        return ActiveStatusEffect.objects.filter(
            slot=slot, status__name__in=list(PERSISTENT_STATUSES)
        ).exists()

    def _has_any_physical(self, slot: "BattleSlot") -> bool:
        """Return True if any physical state (Airborne/Launched/Knockback) is active."""
        return ActiveStatusEffect.objects.filter(
            slot=slot, status__name__in=list(PHYSICAL_STATUSES)
        ).exists()

    def clear_physical_statuses(self, slot: "BattleSlot") -> int:
        """Remove all active physical states from a slot. Returns count removed."""
        deleted, _ = ActiveStatusEffect.objects.filter(
            slot=slot, status__name__in=list(PHYSICAL_STATUSES)
        ).delete()
        if deleted:
            logger.debug("Cleared %d physical state(s) from %s", deleted, slot)
        return deleted

    def is_grounded(self, slot: "BattleSlot") -> bool:
        """
        True when the slot is in the default Grounded state.

        GROUNDED is implicit — a slot is grounded when it has no active
        Airborne / Launched / Knockback state.
        """
        return not self._has_any_physical(slot)

    def _roll_duration(self, status: StatusEffect) -> int | None:
        """Roll a random duration for statuses with variable durations."""
        if status.name == StatusName.ASLEEP:
            return random.randint(2, 5)
        if status.name == StatusName.CONFUSED:
            return random.randint(1, 4)
        if status.name == StatusName.BOUND:
            return random.randint(4, 5)
        return status.default_duration

    def _tick_single(
        self, slot: "BattleSlot", active: ActiveStatusEffect
    ) -> dict | None:
        """Process one active status for one turn. Returns a result dict or None."""
        status_name = active.status.name
        result: dict = {"status": status_name, "damage": 0, "expired": False, "message": ""}

        # Increment turns_active counter
        active.turns_active += 1

        # --- Damage per turn ---
        damage = self._calculate_dot_damage(slot, active)
        if damage > 0:
            result["damage"] = damage
            result["message"] = f"{slot} takes {damage} damage from {status_name}!"
            # Apply damage to the slot's HP (slot is a BattleSlot with current_hp)
            slot.current_hp = max(0, slot.current_hp - damage)
            slot.save(update_fields=["current_hp"])

            if slot.current_hp == 0:
                slot.is_fainted = True
                slot.save(update_fields=["is_fainted"])

            # P2-6: SEEDED drain — heal the slot that planted the seed
            if status_name == StatusName.SEEDED and active.applied_by_slot_id:
                healer = active.applied_by_slot
                if healer and not healer.is_fainted:
                    healer.current_hp = min(healer.max_hp, healer.current_hp + damage)
                    healer.save(update_fields=["current_hp"])
                    result["message"] += f" {healer.pokemon.name} absorbed {damage} HP!"

        # --- Nightmare: extra damage only while asleep ---
        if status_name == StatusName.NIGHTMARE and self.has_status(slot, StatusName.ASLEEP):
            nightmare_dmg = max(1, slot.pokemon.calculate_max_hp(slot.level) // 4)
            slot.current_hp = max(0, slot.current_hp - nightmare_dmg)
            slot.save(update_fields=["current_hp"])
            result["damage"] += nightmare_dmg

        # --- Yawning: falls asleep next turn (yawning expires, sleep applies) ---
        if status_name == StatusName.YAWNING and active.turns_active >= 1:
            try:
                sleep_status = StatusEffect.objects.get(name=StatusName.ASLEEP)
                self.apply_status(slot, sleep_status, active.applied_at_round + 1)
            except StatusEffect.DoesNotExist:
                logger.warning("Asleep StatusEffect not found in database")

        # --- Decrement remaining_turns ---
        if active.remaining_turns is not None:
            active.remaining_turns -= 1
            if active.remaining_turns <= 0:
                active.delete()
                result["expired"] = True
                result["message"] += f" {status_name} wore off!"
                # perish_song: Pokemon faints when the counter reaches 0
                if status_name == StatusName.PERISH_SONG:
                    slot.current_hp = 0
                    slot.is_fainted = True
                    slot.save(update_fields=["current_hp", "is_fainted"])
                    result["message"] += f" {slot.pokemon.name} fainted from Perish Song!"
                return result

        active.save(update_fields=["turns_active", "remaining_turns"])
        return result if (result["damage"] or result["message"]) else None

    def _calculate_dot_damage(
        self, slot: "BattleSlot", active: ActiveStatusEffect
    ) -> int:
        """Calculate damage-per-turn for DoT statuses."""
        status_name = active.status.name
        if status_name not in DAMAGE_PER_TURN_SIXTEENTHS:
            return 0

        max_hp = slot.pokemon.calculate_max_hp(slot.level)
        sixteenths = DAMAGE_PER_TURN_SIXTEENTHS[status_name]

        if status_name == StatusName.BADLY_POISONED:
            # Escalates: 1/16, 2/16, 3/16... up to 15/16
            sixteenths = min(15, active.turns_active)

        if status_name == StatusName.CORRODED:
            # Worsens each turn
            sixteenths = min(8, active.turns_active)

        # Nightmare is handled separately (only while asleep)
        if status_name == StatusName.NIGHTMARE:
            return 0

        return max(1, (max_hp * sixteenths) // 16)

    def _expire_status_by_name(self, slot: "BattleSlot", status_name: str) -> None:
        """Remove a status by name (used for thawing, waking, etc.)."""
        ActiveStatusEffect.objects.filter(
            slot=slot, status__name=status_name
        ).delete()
        logger.info("Expired %s on %s", status_name, slot)
