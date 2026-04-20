"""
BattleAIService — computer-controlled opponent for single-player battles.

Three difficulty tiers:
  easy   — fully random moves and targets (respects cooldowns)
  medium — prefers status-applying moves on clean targets; sets up own combo chains
  hard   — type-aware, targets low-HP Pokemon, aggressive combo setup, chaos baiting
"""
import logging
import random
from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.db import transaction

from apps.effects.models import ActiveStatusEffect
from apps.pokemon.models import Move, MoveSlotType, Pokemon

from .models import AIDifficulty, BattleSlot, BattleTeam, MoveCooldown

if TYPE_CHECKING:
    from .models import Battle

User = get_user_model()
logger = logging.getLogger(__name__)

_AI_USERNAME = "__ai_trainer__"
_AI_EMAIL = "ai@pokemon-battle.local"

_SUPER_EFFECTIVE: dict[str, list[str]] = {
    "Fire":     ["Grass", "Ice", "Bug", "Steel"],
    "Water":    ["Fire", "Rock", "Ground"],
    "Electric": ["Water", "Flying"],
    "Grass":    ["Water", "Rock", "Ground"],
    "Ice":      ["Grass", "Ground", "Flying", "Dragon"],
    "Fighting": ["Normal", "Ice", "Rock", "Dark", "Steel"],
    "Poison":   ["Grass", "Fairy"],
    "Ground":   ["Fire", "Electric", "Poison", "Rock", "Steel"],
    "Flying":   ["Grass", "Fighting", "Bug"],
    "Psychic":  ["Fighting", "Poison"],
    "Bug":      ["Grass", "Psychic", "Dark"],
    "Rock":     ["Fire", "Ice", "Flying", "Bug"],
    "Ghost":    ["Psychic", "Ghost"],
    "Dragon":   ["Dragon"],
    "Dark":     ["Psychic", "Ghost"],
    "Steel":    ["Ice", "Rock", "Fairy"],
    "Fairy":    ["Fighting", "Dragon", "Dark"],
}

_CHAOS_STATUSES = {"chaos", "confused"}


def _type_multiplier(move_type_name: str, defender_primary: str, defender_secondary: str | None) -> float:
    se_against = _SUPER_EFFECTIVE.get(move_type_name, [])
    if defender_primary in se_against or (defender_secondary and defender_secondary in se_against):
        return 1.5
    return 1.0


def _score_move_easy(_slot: BattleSlot, _move: Move, _target: BattleSlot) -> float:
    return random.random()


def _score_move_medium(_slot: BattleSlot, move: Move, target: BattleSlot, ai_team: BattleTeam) -> float:
    score = float(move.power)

    if move.applies_status:
        has_status = ActiveStatusEffect.objects.filter(
            slot=target, status=move.applies_status
        ).exists()
        if not has_status:
            score += 20.0

        triggers_combo = Move.objects.filter(
            learned_by__battle_slots__team=ai_team,
            trigger_status=move.applies_status,
        ).exists()
        if triggers_combo:
            score += 10.0

    return score + random.uniform(0, 3)


def _score_move_hard(
    _slot: BattleSlot,
    move: Move,
    target: BattleSlot,
    ai_team: BattleTeam,
    player_combo_trigger_statuses: set[str],
) -> float:
    defender_primary = target.pokemon.primary_type.name
    defender_secondary = (
        target.pokemon.secondary_type.name if target.pokemon.secondary_type else None
    )
    type_mult = _type_multiplier(move.move_type.name, defender_primary, defender_secondary)
    score = float(move.power) * type_mult

    if target.max_hp > 0 and (target.current_hp / target.max_hp) < 0.30 and move.power >= 60:
        score += 30.0

    if move.applies_status:
        status_name = move.applies_status.name

        has_status = ActiveStatusEffect.objects.filter(
            slot=target, status=move.applies_status
        ).exists()
        if not has_status:
            score += 10.0

        triggers_ai_combo = Move.objects.filter(
            learned_by__battle_slots__team=ai_team,
            trigger_status=move.applies_status,
        ).exists()
        if triggers_ai_combo:
            score += 25.0

        if status_name in _CHAOS_STATUSES and status_name in player_combo_trigger_statuses:
            score += 20.0

        if status_name in {"enfeebled", "weakened", "tagged", "corroded"}:
            score += 15.0

    return score + random.uniform(0, 2)


class BattleAIService:
    """Manages AI opponent logic — user creation, team building, and action generation."""

    def get_or_create_ai_user(self) -> "User":  # type: ignore[return]
        """Return (or create) the singleton AI system user."""
        user, created = User.objects.get_or_create(
            username=_AI_USERNAME,
            defaults={
                "email": _AI_EMAIL,
                "display_name": "AI Trainer",
                "is_active": True,
            },
        )
        if created:
            user.set_unusable_password()
            user.save(update_fields=["password"])
            logger.info("Created AI system user")
        return user

    def build_ai_team_pokemon_ids(self) -> list[int]:
        """Select 6 random Pokemon PKs for the AI team."""
        all_ids = list(Pokemon.objects.values_list("pk", flat=True))
        if len(all_ids) < 6:
            raise ValueError("Not enough Pokemon in the database to build an AI team (need ≥6)")
        return random.sample(all_ids, 6)

    def build_tutorial_ai_team_pokemon_ids(self) -> list[int]:
        """Select 6 random Gen 1 Pokemon PKs for the tutorial AI opponent."""
        gen1_ids = list(
            Pokemon.objects.filter(pokedex_number__lte=151).values_list("pk", flat=True)
        )
        if len(gen1_ids) < 6:
            gen1_ids = list(Pokemon.objects.values_list("pk", flat=True))
        if len(gen1_ids) < 6:
            raise ValueError("Not enough Pokemon in the database to build a tutorial AI team (need >=6)")
        return random.sample(gen1_ids, 6)

    @transaction.atomic
    def get_ai_actions(self, battle: "Battle") -> list[dict]:
        """
        Generate one action per non-fainted active AI slot.

        Respects cooldowns: passive and on-cooldown moves are excluded.
        Returns a list of {"slot_id": int, "move_id": int, "target_id": int}.
        """
        ai_user = self.get_or_create_ai_user()
        ai_team = battle.teams.filter(owner=ai_user).prefetch_related(
            "slots__pokemon__moves__applies_status",
            "slots__pokemon__moves__trigger_status",
            "slots__pokemon__primary_type",
            "slots__pokemon__secondary_type",
            "slots__move_cooldowns__move",
        ).first()

        if ai_team is None:
            return []

        player_team = battle.teams.exclude(owner=ai_user).prefetch_related(
            "slots__pokemon__moves__trigger_status",
            "slots__pokemon__primary_type",
            "slots__pokemon__secondary_type",
        ).first()

        if player_team is None:
            return []

        alive_player_slots = [
            s for s in player_team.slots.all()
            if not s.is_fainted and s.is_active
        ]
        if not alive_player_slots:
            return []

        difficulty = battle.ai_difficulty or AIDifficulty.MEDIUM

        player_combo_trigger_statuses: set[str] = set()
        if difficulty == AIDifficulty.HARD:
            for pslot in player_team.slots.all():
                for pmove in pslot.pokemon.moves.all():
                    if pmove.trigger_status:
                        player_combo_trigger_statuses.add(pmove.trigger_status.name)

        # Build cooldown set for AI slots: (slot_id, move_id)
        cooldown_set: set[tuple[int, int]] = set(
            MoveCooldown.objects.filter(
                slot__team=ai_team,
                remaining_rounds__gt=0,
            ).values_list("slot_id", "move_id")
        )

        # Chakra budget — lock row so we safely read-and-deduct
        from apps.game.services import CHAKRA_MAX  # avoid circular at module level
        locked_ai_team = BattleTeam.objects.select_for_update().get(pk=ai_team.pk)
        chakra_remaining: int = locked_ai_team.chakra_pool

        active_slots = [s for s in ai_team.slots.all() if not s.is_fainted and s.is_active]

        # Greedy mystery selection: score every slot's mystery move, spend highest-value first
        mystery_candidates: list[tuple[float, BattleSlot, Move]] = []
        for slot in active_slots:
            mystery_move = self._get_mystery_move(slot, cooldown_set)
            if mystery_move is None:
                continue
            cost = mystery_move.chakra_cost or 0
            if cost <= chakra_remaining:
                score = mystery_move.power or 0
                mystery_candidates.append((score, slot, mystery_move))

        mystery_candidates.sort(key=lambda x: x[0], reverse=True)
        slot_mystery_map: dict[int, Move] = {}
        for score, slot, mystery_move in mystery_candidates:
            cost = mystery_move.chakra_cost or 0
            if cost <= chakra_remaining:
                slot_mystery_map[slot.pk] = mystery_move
                chakra_remaining -= cost

        locked_ai_team.chakra_pool = chakra_remaining
        locked_ai_team.save(update_fields=["chakra_pool"])

        actions: list[dict] = []
        for slot in active_slots:
            moves = self._get_available_moves(slot, cooldown_set)
            if not moves:
                continue

            target = self._pick_target(alive_player_slots, difficulty)

            # Use greedy-selected mystery if this slot got one, else normal pick
            if slot.pk in slot_mystery_map:
                move = slot_mystery_map[slot.pk]
            else:
                non_mystery = [m for m in moves if m.slot_type != MoveSlotType.MYSTERY]
                move = self._pick_move(
                    slot, non_mystery or moves, target, difficulty, ai_team, player_combo_trigger_statuses
                )

            actions.append({
                "slot_id": slot.pk,
                "move_id": move.pk,
                "target_id": target.pk,
            })

        return actions

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_available_moves(
        slot: BattleSlot, cooldown_set: set[tuple[int, int]]
    ) -> list[Move]:
        """Return moves that are not passive and not on cooldown."""
        available = [
            m for m in slot.pokemon.moves.all()
            if m.slot_type != MoveSlotType.PASSIVE_2
            and (slot.pk, m.pk) not in cooldown_set
        ]
        if available:
            return available
        # If all non-passive moves are on cooldown, try standard as emergency fallback
        standard = [m for m in slot.pokemon.moves.all() if m.slot_type == MoveSlotType.STANDARD]
        return standard

    @staticmethod
    def _get_mystery_move(slot: BattleSlot, cooldown_set: set[tuple[int, int]]) -> "Move | None":
        """Return the slot's mystery move if it exists and is not on cooldown."""
        if slot.owned_pokemon_id is not None and slot.owned_pokemon and slot.owned_pokemon.move_special:
            m = slot.owned_pokemon.move_special
            if (slot.pk, m.pk) not in cooldown_set:
                return m
        for m in slot.pokemon.moves.all():
            if m.slot_type == MoveSlotType.MYSTERY and (slot.pk, m.pk) not in cooldown_set:
                return m
        return None

    def _pick_target(self, alive_slots: list[BattleSlot], difficulty: str) -> BattleSlot:
        if difficulty == AIDifficulty.EASY:
            return random.choice(alive_slots)
        return min(alive_slots, key=lambda s: s.current_hp / max(s.max_hp, 1))

    def _pick_move(
        self,
        slot: BattleSlot,
        moves: list[Move],
        target: BattleSlot,
        difficulty: str,
        ai_team: BattleTeam,
        player_combo_trigger_statuses: set[str],
    ) -> Move:
        if difficulty == AIDifficulty.EASY:
            return random.choice(moves)

        if difficulty == AIDifficulty.MEDIUM:
            scored = [
                (m, _score_move_medium(slot, m, target, ai_team))
                for m in moves
            ]
        else:
            scored = [
                (m, _score_move_hard(slot, m, target, ai_team, player_combo_trigger_statuses))
                for m in moves
            ]

        return max(scored, key=lambda x: x[1])[0]
