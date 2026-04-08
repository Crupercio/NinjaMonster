"""Battle game models: Battle, BattleTeam, BattleSlot, BattleRound, BattleAction, BattleLog, MoveCooldown."""
import logging

from django.conf import settings
from django.db import models

logger = logging.getLogger(__name__)


class BattleStatus(models.TextChoices):
    SETUP = "setup", "Setup"
    ACTIVE = "active", "Active"
    FINISHED = "finished", "Finished"


class LogType(models.TextChoices):
    ACTION = "action", "Action"
    COMBO = "combo", "Combo"
    STATUS = "status", "Status"
    FAINT = "faint", "Faint"
    INFO = "info", "Info"


class AIDifficulty(models.TextChoices):
    EASY = "easy", "Easy"
    MEDIUM = "medium", "Medium"
    HARD = "hard", "Hard"


class GridPosition(models.TextChoices):
    """Named 2×2 grid positions per team side, plus two bench slots."""

    FRONT_LEFT = "front_left", "Front Left"
    FRONT_RIGHT = "front_right", "Front Right"
    BACK_LEFT = "back_left", "Back Left"
    BACK_RIGHT = "back_right", "Back Right"
    BENCH_1 = "bench_1", "Bench 1"
    BENCH_2 = "bench_2", "Bench 2"


# Positions considered "on the field" (not bench).
ACTIVE_GRID_POSITIONS: frozenset[str] = frozenset({
    GridPosition.FRONT_LEFT,
    GridPosition.FRONT_RIGHT,
    GridPosition.BACK_LEFT,
    GridPosition.BACK_RIGHT,
})

# Integer order used for tie-breaking turn resolution (lower = higher priority).
GRID_TURN_ORDER: dict[str, int] = {
    GridPosition.FRONT_LEFT: 1,
    GridPosition.FRONT_RIGHT: 2,
    GridPosition.BACK_LEFT: 3,
    GridPosition.BACK_RIGHT: 4,
    GridPosition.BENCH_1: 5,
    GridPosition.BENCH_2: 6,
}

# Maps slot position (1-6) → GridPosition value.
POSITION_TO_GRID: dict[int, str] = {
    1: GridPosition.FRONT_LEFT,
    2: GridPosition.FRONT_RIGHT,
    3: GridPosition.BACK_LEFT,
    4: GridPosition.BACK_RIGHT,
    5: GridPosition.BENCH_1,
    6: GridPosition.BENCH_2,
}


class Battle(models.Model):
    """Represents a single 4v4 battle between two players (or player vs AI)."""

    player_one = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="battles_as_player_one",
        db_index=True,
    )
    player_two = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="battles_as_player_two",
        db_index=True,
    )
    status = models.TextField(choices=BattleStatus.choices, default=BattleStatus.SETUP, db_index=True)
    current_round = models.PositiveIntegerField(default=1)
    winner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="battles_won_set",
        db_index=True,
    )
    max_combo_chain = models.PositiveIntegerField(
        default=0,
        help_text="Longest combo chain achieved in this battle.",
    )
    is_ai_battle = models.BooleanField(default=False, db_index=True)
    ai_difficulty = models.TextField(
        choices=AIDifficulty.choices,
        default=AIDifficulty.MEDIUM,
        blank=True,
    )
    is_tutorial = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "battle"
        verbose_name_plural = "battles"

    def __str__(self) -> str:
        p2 = self.player_two or "AI"
        return f"Battle #{self.pk}: {self.player_one} vs {p2} (Round {self.current_round})"


class BattleTeam(models.Model):
    """Links a User to a Battle as the owner of a team of 6 BattleSlots."""

    battle = models.ForeignKey(
        Battle,
        on_delete=models.CASCADE,
        related_name="teams",
        db_index=True,
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="battle_teams",
        db_index=True,
    )

    class Meta:
        unique_together = [("battle", "owner")]
        verbose_name = "battle team"
        verbose_name_plural = "battle teams"

    def __str__(self) -> str:
        return f"{self.owner}'s team in Battle #{self.battle_id}"


class BattleSlot(models.Model):
    """
    Represents a single Pokemon on the field or bench during a battle.

    Tracks per-battle-per-pokemon mutable state: HP, fainted status, grid position,
    and the player's persisted move/target selection.
    """

    team = models.ForeignKey(
        BattleTeam,
        on_delete=models.CASCADE,
        related_name="slots",
        db_index=True,
    )
    pokemon = models.ForeignKey(
        "pokemon.Pokemon",
        on_delete=models.PROTECT,
        related_name="battle_slots",
        db_index=True,
    )
    owned_pokemon = models.ForeignKey(
        "pokemon.OwnedPokemon",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="battle_slots",
        db_index=True,
        help_text="The specific OwnedPokemon instance used for this slot (null for AI/legacy).",
    )
    position = models.PositiveSmallIntegerField(help_text="Slot position 1–6 on the team.")
    grid_position = models.TextField(
        choices=GridPosition.choices,
        default=GridPosition.FRONT_LEFT,
        help_text="Named grid cell: front_left/front_right/back_left/back_right/bench_1/bench_2.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="True if the slot is on the field (not on the bench).",
        db_index=True,
    )
    level = models.PositiveSmallIntegerField(default=50)
    current_hp = models.PositiveIntegerField()
    max_hp = models.PositiveIntegerField()
    is_fainted = models.BooleanField(default=False)

    # Track last move used (for Encore / Torment logic)
    last_move_used = models.ForeignKey(
        "pokemon.Move",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    # Persisted move / target selection — survives between rounds until overridden.
    selected_move = models.ForeignKey(
        "pokemon.Move",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="The move the player has chosen to use; persists until changed.",
    )
    selected_target = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="The target slot the player has chosen; persists until changed or invalidated.",
    )

    class Meta:
        unique_together = [("team", "position")]
        ordering = ["position"]
        verbose_name = "battle slot"
        verbose_name_plural = "battle slots"

    def __str__(self) -> str:
        pos_label = self.get_grid_position_display()
        return f"{self.pokemon.name} [{pos_label}] (HP {self.current_hp}/{self.max_hp})"

    @property
    def hp_percentage(self) -> float:
        """Return HP as a percentage (0.0–100.0)."""
        if self.max_hp == 0:
            return 0.0
        return round(self.current_hp / self.max_hp * 100, 1)


class MoveCooldown(models.Model):
    """
    Tracks how many rounds remain before a BattleSlot can use a specific Move again.

    Created when a move with cooldown > 0 is used; decremented each round; deleted at 0.
    """

    slot = models.ForeignKey(
        BattleSlot,
        on_delete=models.CASCADE,
        related_name="move_cooldowns",
        db_index=True,
    )
    move = models.ForeignKey(
        "pokemon.Move",
        on_delete=models.CASCADE,
        related_name="+",
        db_index=True,
    )
    remaining_rounds = models.PositiveSmallIntegerField(default=0)

    class Meta:
        unique_together = [("slot", "move")]
        verbose_name = "move cooldown"
        verbose_name_plural = "move cooldowns"

    def __str__(self) -> str:
        return f"{self.slot.pokemon.name} — {self.move.name}: {self.remaining_rounds} round(s) left"


class BattleRound(models.Model):
    """Represents one complete round of battle."""

    battle = models.ForeignKey(
        Battle,
        on_delete=models.CASCADE,
        related_name="rounds",
        db_index=True,
    )
    round_number = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("battle", "round_number")]
        ordering = ["round_number"]
        verbose_name = "battle round"
        verbose_name_plural = "battle rounds"

    def __str__(self) -> str:
        return f"Battle #{self.battle_id} Round {self.round_number}"


class BattleAction(models.Model):
    """
    Records a single move execution — whether player-initiated or combo-triggered.

    is_combo_triggered=True means this action fired automatically as part of a chain.
    order_in_chain tracks the position within the chain (0 = initial move).
    """

    round = models.ForeignKey(
        BattleRound,
        on_delete=models.CASCADE,
        related_name="actions",
        db_index=True,
    )
    attacker_slot = models.ForeignKey(
        BattleSlot,
        on_delete=models.CASCADE,
        related_name="actions_as_attacker",
        db_index=True,
    )
    move = models.ForeignKey(
        "pokemon.Move",
        on_delete=models.PROTECT,
        related_name="battle_actions",
        db_index=True,
    )
    target_slot = models.ForeignKey(
        BattleSlot,
        on_delete=models.CASCADE,
        related_name="actions_as_target",
        db_index=True,
    )
    damage_dealt = models.IntegerField(default=0)
    status_applied = models.ForeignKey(
        "effects.StatusEffect",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    is_combo_triggered = models.BooleanField(default=False)
    order_in_chain = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "order_in_chain"]
        verbose_name = "battle action"
        verbose_name_plural = "battle actions"

    def __str__(self) -> str:
        chain = f" [chain #{self.order_in_chain}]" if self.is_combo_triggered else ""
        return f"{self.attacker_slot.pokemon.name} uses {self.move.name}{chain}"


class BattleLog(models.Model):
    """Append-only log of battle events for replay and UI display."""

    battle = models.ForeignKey(
        Battle,
        on_delete=models.CASCADE,
        related_name="logs",
        db_index=True,
    )
    round_number = models.PositiveIntegerField()
    message = models.TextField()
    log_type = models.TextField(choices=LogType.choices, default=LogType.INFO, db_index=True)
    # Chain metadata for UI display
    chain_position = models.PositiveIntegerField(
        null=True, blank=True, help_text="Position in combo chain, if applicable."
    )
    chain_total = models.PositiveIntegerField(
        null=True, blank=True, help_text="Total chain length when this was logged."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "battle log"
        verbose_name_plural = "battle logs"

    def __str__(self) -> str:
        return f"[Round {self.round_number}] {self.message}"
