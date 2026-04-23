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
    """Named 3×2 grid positions per team side (Phase 3 — 6v6 expansion)."""

    FRONT_LEFT = "front_left", "Front Left"
    FRONT_CENTER = "front_center", "Front Center"
    FRONT_RIGHT = "front_right", "Front Right"
    BACK_LEFT = "back_left", "Back Left"
    BACK_CENTER = "back_center", "Back Center"
    BACK_RIGHT = "back_right", "Back Right"
    # Legacy bench slots — kept for DB compatibility with pre-Phase 3 battles.
    BENCH_1 = "bench_1", "Bench 1"
    BENCH_2 = "bench_2", "Bench 2"


# All six field positions — bench is implicit (no bench in 6v6).
ACTIVE_GRID_POSITIONS: frozenset[str] = frozenset({
    GridPosition.FRONT_LEFT,
    GridPosition.FRONT_CENTER,
    GridPosition.FRONT_RIGHT,
    GridPosition.BACK_LEFT,
    GridPosition.BACK_CENTER,
    GridPosition.BACK_RIGHT,
})

# Integer order used for tie-breaking turn resolution (lower = higher priority).
# Front row acts before back row; left→center→right within each row.
GRID_TURN_ORDER: dict[str, int] = {
    GridPosition.FRONT_LEFT:   1,
    GridPosition.FRONT_CENTER: 2,
    GridPosition.FRONT_RIGHT:  3,
    GridPosition.BACK_LEFT:    4,
    GridPosition.BACK_CENTER:  5,
    GridPosition.BACK_RIGHT:   6,
    GridPosition.BENCH_1:      7,
    GridPosition.BENCH_2:      8,
}

# Maps slot position (1-6) → GridPosition value.
# Positions 1–3: front row (L/C/R); Positions 4–6: back row (L/C/R).
POSITION_TO_GRID: dict[int, str] = {
    1: GridPosition.FRONT_LEFT,
    2: GridPosition.FRONT_CENTER,
    3: GridPosition.FRONT_RIGHT,
    4: GridPosition.BACK_LEFT,
    5: GridPosition.BACK_CENTER,
    6: GridPosition.BACK_RIGHT,
}


class Battle(models.Model):
    """Represents a single 6v6 battle between two players (or player vs AI)."""

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

    chakra_pool = models.PositiveSmallIntegerField(
        default=0,
        help_text="Shared team chakra (0–100). Regenerates each round; spent on mystery moves.",
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
    # Phase 5 — Stat Expansion
    critical_rate = models.FloatField(
        default=0.05,
        help_text="Probability (0.0–1.0) of landing a critical hit (×1.5 damage).",
    )
    combo_rate = models.FloatField(
        default=0.10,
        help_text="Bonus damage multiplier applied to non-initial combo chain hits.",
    )
    control_resist = models.FloatField(
        default=0.00,
        help_text="Probability (0.0–1.0) to resist a status/CC application.",
    )
    # Phase 3 — Control + Penetration
    control = models.FloatField(
        default=100.0,
        help_text="CC success rate; higher values improve status application vs control_resist.",
    )
    penetration = models.FloatField(
        default=0.0,
        help_text="Fraction of target's defense ignored (0.0–1.0). Derived from primary_role.",
    )

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


class BattleSlotHeldEffect(models.Model):
    """
    Tracks in-battle state of a slot's held effect: how many times it has fired.

    Created by BattleService.set_team_from_owned() when OwnedPokemon.held_effect is set.
    """

    slot = models.OneToOneField(
        BattleSlot,
        on_delete=models.CASCADE,
        related_name="held_effect_state",
    )
    effect = models.ForeignKey(
        "pokemon.HeldEffect",
        on_delete=models.CASCADE,
        related_name="battle_states",
    )
    activations_used = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "battle slot held effect"
        verbose_name_plural = "battle slot held effects"

    def __str__(self) -> str:
        return f"{self.slot.pokemon.name} — {self.effect.name}"

    @property
    def can_activate(self) -> bool:
        """True if the effect has not reached its per-battle cap (0 = unlimited)."""
        if self.effect.max_activations == 0:
            return True
        return self.activations_used < self.effect.max_activations


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


class LoteriaStatus(models.TextChoices):
    """Lifecycle for a live Loteria room."""

    WAITING = "waiting", "Waiting"
    ACTIVE = "active", "Active"
    FINISHED = "finished", "Finished"


class LoteriaBoardTemplate(models.Model):
    """A saved 4x4 player board for one Loteria generation deck."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="loteria_boards",
        db_index=True,
    )
    deck_key = models.CharField(max_length=32, db_index=True)
    board_slot = models.PositiveSmallIntegerField(help_text="Saved slot number within this deck (1-3).")
    title = models.CharField(max_length=80, default="Collector Board")
    species_ids = models.JSONField(default=list, help_text="Ordered list of 16 Pokemon ids for the 4x4 board.")
    seeded_by_system = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["deck_key", "board_slot"]
        unique_together = [("owner", "deck_key", "board_slot")]
        verbose_name = "loteria board template"
        verbose_name_plural = "loteria board templates"

    def __str__(self) -> str:
        return f"{self.owner} · {self.deck_key} · Board {self.board_slot}"


class LoteriaRoom(models.Model):
    """One live room that deals a shared sequence of Pokemon cards."""

    deck_key = models.CharField(max_length=32, db_index=True)
    title = models.CharField(max_length=80)
    status = models.CharField(max_length=16, choices=LoteriaStatus.choices, default=LoteriaStatus.WAITING, db_index=True)
    round_number = models.PositiveIntegerField(default=1)
    prize_pool_ryo = models.PositiveIntegerField(default=0)
    deck_order = models.JSONField(default=list, help_text="Ordered list of Pokemon ids to deal for this room.")
    called_species_ids = models.JSONField(default=list, help_text="Pokemon ids already called this round.")
    next_tick_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "loteria room"
        verbose_name_plural = "loteria rooms"

    def __str__(self) -> str:
        return f"{self.title} · Round {self.round_number} ({self.status})"


class LoteriaRoomEntry(models.Model):
    """A player or NPC board entered into a specific Loteria room."""

    room = models.ForeignKey(
        LoteriaRoom,
        on_delete=models.CASCADE,
        related_name="entries",
        db_index=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="loteria_entries",
        db_index=True,
    )
    board_template = models.ForeignKey(
        LoteriaBoardTemplate,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="room_entries",
    )
    display_name = models.CharField(max_length=80)
    board_slot = models.PositiveSmallIntegerField(default=1)
    species_ids = models.JSONField(default=list, help_text="Snapshot of board species ids when the room entry was created.")
    is_npc = models.BooleanField(default=False, db_index=True)
    is_winner = models.BooleanField(default=False, db_index=True)
    reward_ryo = models.PositiveIntegerField(default=0)
    entered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["entered_at", "pk"]
        verbose_name = "loteria room entry"
        verbose_name_plural = "loteria room entries"

    def __str__(self) -> str:
        return f"{self.display_name} · {self.room}"
