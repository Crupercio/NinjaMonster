"""Pokemon domain models: PokemonType, Move, Pokemon, Team."""
import logging

from django.db import models
from django.utils import timezone

from .querysets import PokemonQuerySet

logger = logging.getLogger(__name__)


class PokemonType(models.Model):
    """Represents a Pokemon elemental type (Fire, Water, etc.)."""

    name = models.TextField(unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Pokemon type"
        verbose_name_plural = "Pokemon types"

    def __str__(self) -> str:
        return self.name


class Generation(models.Model):
    """
    A game generation used to tag moves and species move pools.

    Every species must have at least one generation_source.
    Every move should be tagged to the generation that introduced it.
    """

    name = models.CharField(max_length=50, unique=True)
    number = models.PositiveSmallIntegerField(unique=True)
    description = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["number"]
        verbose_name = "generation"
        verbose_name_plural = "generations"

    def __str__(self) -> str:
        return f"Gen {self.number} — {self.name}"


class MoveSlotType(models.TextChoices):
    STANDARD = "standard", "Basic Technique"
    CHASE = "chase", "Chase Technique"
    SPECIAL = "special", "Secret Technique"
    SUPPORT = "support", "Support Technique"
    PASSIVE = "passive", "Ninja Trait"


class TacticalRole(models.TextChoices):
    DPS = "dps", "DPS"
    ASSASSIN = "assassin", "Assassin"
    TANK = "tank", "Tank"
    SUPPORT = "support", "Support"
    CONTROL = "control", "Control"
    BRUISER = "bruiser", "Bruiser"


# All slot types that must be covered for a species to be battle-ready.
_REQUIRED_SLOT_TYPES: frozenset[str] = frozenset(MoveSlotType.values)


class Move(models.Model):
    """
    A move that a Pokemon can use in battle.

    applies_status: if set, this move inflicts that status on the target.
    trigger_status: if set, this move auto-fires when a friendly Pokemon inflicts
                    the matching status (the combo chain trigger).
    slot_type:      which of the 4 move slots this occupies in the 4v4 system.
    cooldown:       rounds that must pass before this move can be used again (0 = none).
    priority:       higher values act before lower values within the same speed tier.
    always_first:   always acts before all other moves (e.g. Quick Attack).
    always_last:    always acts after all other moves.
    is_charge_move: charges one round, releases the next.
    """

    name = models.TextField(unique=True)
    themed_name = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Alternate display name for lore or themed variants.",
    )
    move_type = models.ForeignKey(
        PokemonType,
        on_delete=models.PROTECT,
        related_name="moves",
        db_index=True,
    )
    power = models.PositiveIntegerField(default=0)
    accuracy = models.PositiveIntegerField(default=100)
    pp = models.PositiveIntegerField(default=10)
    applies_status = models.ForeignKey(
        "effects.StatusEffect",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="applied_by_moves",
        db_index=True,
    )
    trigger_status = models.ForeignKey(
        "effects.StatusEffect",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="triggers_moves",
        db_index=True,
    )
    description = models.TextField(blank=True, default="")
    # --- Tactical 4v4 fields ---
    slot_type = models.TextField(
        choices=MoveSlotType.choices,
        default=MoveSlotType.STANDARD,
        db_index=True,
    )
    cooldown = models.PositiveSmallIntegerField(
        default=0,
        help_text="Rounds that must pass before this move can be used again.",
    )
    priority = models.SmallIntegerField(
        default=0,
        help_text="Higher priority acts before lower within the same speed tier.",
    )
    always_first = models.BooleanField(default=False)
    always_last = models.BooleanField(default=False)
    is_charge_move = models.BooleanField(default=False)
    # --- Combo chain flags ---
    combo_starter = models.BooleanField(
        default=False,
        help_text="This move can initiate a combo chain sequence.",
    )
    combo_trigger = models.BooleanField(
        default=False,
        help_text="This move can fire automatically as part of a combo chain.",
    )
    # --- Support flag ---
    support_flag = models.BooleanField(
        default=False,
        help_text="Marks this move as having a support effect (heal, shield, buff, etc.).",
    )
    # --- Generation tag ---
    generation = models.ForeignKey(
        Generation,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="moves",
        db_index=True,
        help_text="Which generation introduced this move.",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "move"
        verbose_name_plural = "moves"

    def __str__(self) -> str:
        return self.themed_name or self.name

    @property
    def is_combo_trigger(self) -> bool:
        """True if this move participates in the combo chain as a trigger."""
        return self.trigger_status_id is not None

    @property
    def is_status_applier(self) -> bool:
        """True if this move can start a combo chain by applying a status."""
        return self.applies_status_id is not None


class Pokemon(models.Model):
    """
    A Pokemon species with base stats and learnable moves.

    Individual in-battle instances are represented by BattleSlot in the game app.
    """

    name = models.TextField(unique=True)
    primary_type = models.ForeignKey(
        PokemonType,
        on_delete=models.PROTECT,
        related_name="primary_pokemon",
        db_index=True,
    )
    secondary_type = models.ForeignKey(
        PokemonType,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="secondary_pokemon",
        db_index=True,
    )
    # Base stats (used to calculate in-battle stats at a given level)
    base_hp = models.PositiveIntegerField(default=45)
    base_attack = models.PositiveIntegerField(default=45)
    base_defense = models.PositiveIntegerField(default=45)
    base_sp_attack = models.PositiveIntegerField(default=45)
    base_sp_defense = models.PositiveIntegerField(default=45)
    base_speed = models.PositiveIntegerField(default=45)

    moves = models.ManyToManyField(Move, related_name="learned_by", blank=True)
    generation_sources = models.ManyToManyField(
        Generation,
        related_name="species",
        blank=True,
        help_text=(
            "Generations this species draws its move pool from. "
            "At least one generation source is required per species."
        ),
    )
    sprite_url = models.TextField(blank=True, default="")
    pokedex_number = models.PositiveIntegerField(unique=True, null=True, blank=True)
    primary_role = models.TextField(
        choices=TacticalRole.choices,
        default=TacticalRole.DPS,
        blank=True,
        db_index=True,
        help_text="Tactical identity: determines build flavor and pool curation.",
    )

    objects = PokemonQuerySet.as_manager()

    class Meta:
        ordering = ["pokedex_number", "name"]
        verbose_name = "pokemon"
        verbose_name_plural = "pokemon"

    def __str__(self) -> str:
        return self.name

    def calculate_max_hp(self, level: int) -> int:
        """Calculate max HP at the given level using the standard formula."""
        return int((2 * self.base_hp * level) / 100) + level + 10

    def calculate_stat(self, base_stat: int, level: int) -> int:
        """Calculate a non-HP stat at the given level."""
        return int((2 * base_stat * level) / 100) + 5

    @property
    def is_battle_ready(self) -> bool:
        """True if every slot type has at least one SpeciesMovePool entry."""
        covered = frozenset(
            self.move_pool.values_list("slot_type", flat=True).distinct()
        )
        return _REQUIRED_SLOT_TYPES <= covered


class OwnedPokemon(models.Model):
    """
    A specific user's Pokemon instance, tracking level and EXP.

    Each row = one Pokemon belonging to one trainer.
    The species (base stats, moves) lives on the Pokemon FK.
    """

    owner = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="owned_pokemon",
        db_index=True,
    )
    species = models.ForeignKey(
        Pokemon,
        on_delete=models.PROTECT,
        related_name="owned_instances",
        db_index=True,
    )
    level = models.PositiveIntegerField(default=1)
    # EXP toward the next level (resets to 0 on level-up)
    experience = models.PositiveIntegerField(default=0)
    is_training = models.BooleanField(default=False)
    training_started_at = models.DateTimeField(null=True, blank=True)
    training_ends_at = models.DateTimeField(null=True, blank=True)
    training_duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Assigned moveset — one per slot type, drawn from SpeciesMovePool on creation.
    move_standard = models.ForeignKey(
        Move,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Assigned Basic Technique (standard slot).",
    )
    move_chase = models.ForeignKey(
        Move,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Assigned Chase Technique.",
    )
    move_special = models.ForeignKey(
        Move,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Assigned Secret Technique (special slot).",
    )
    move_support = models.ForeignKey(
        Move,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Assigned Support Technique.",
    )
    move_passive = models.ForeignKey(
        Move,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Assigned Ninja Trait (passive slot).",
    )

    class Meta:
        ordering = ["created_at"]
        verbose_name = "owned pokemon"
        verbose_name_plural = "owned pokemon"

    def __str__(self) -> str:
        return f"{self.species.name} (Lv.{self.level}) — {self.owner}"

    @property
    def exp_to_next_level(self) -> int:
        """EXP needed to advance one level. Scales with current level."""
        return self.level * 10

    @property
    def sell_value(self) -> int:
        """Ryo earned by selling this Pokemon. Minimum 100, scales with level."""
        return max(100, self.level * 50)

    @property
    def battle_exp_gain(self) -> int:
        """
        Base EXP this Pokemon earns per battle, based on level bracket.

        Bracket rule: every 10 levels adds 10 EXP.
          Lv 1–9  → 10 EXP
          Lv 10–19 → 20 EXP
          Lv 20–29 → 30 EXP  (and so on)
        """
        return (self.level // 10 + 1) * 10

    @property
    def training_complete(self) -> bool:
        """True when training has finished and the reward can be claimed."""
        if not self.is_training or self.training_ends_at is None:
            return False
        return timezone.now() >= self.training_ends_at

    @property
    def training_seconds_remaining(self) -> int:
        """Seconds until training finishes. Returns 0 if done or not training."""
        if not self.is_training or self.training_ends_at is None:
            return 0
        delta = self.training_ends_at - timezone.now()
        return max(0, int(delta.total_seconds()))


class Team(models.Model):
    """
    A persistent team of up to 6 Pokemon for a user.

    One team per user (OneToOne). Slots are ordered 1–6 via TeamSlot.
    Use Team.get_team(user) for lazy creation.
    """

    owner = models.OneToOneField(
        "users.User",
        on_delete=models.CASCADE,
        related_name="team",
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "team"
        verbose_name_plural = "teams"

    def __str__(self) -> str:
        return f"Team of {self.owner}"

    @classmethod
    def get_team(cls, user: object) -> "Team":
        """Get or lazily create the team for the given user."""
        team, _ = cls.objects.get_or_create(owner=user)
        return team

    def get_ordered_pokemon(self) -> list["OwnedPokemon"]:
        """Return OwnedPokemon instances ordered by slot position (1–6)."""
        return [
            slot.pokemon
            for slot in self.slots.select_related(
                "pokemon__species__primary_type",
                "pokemon__species__secondary_type",
            ).order_by("position")
        ]

    def get_active_four(self) -> list["OwnedPokemon"]:
        """Return first 4 slots' OwnedPokemon (used by battle system)."""
        return self.get_ordered_pokemon()[:4]


class TeamSlot(models.Model):
    """
    A single position in a user's persistent team.

    position must be 1–6 and is unique within a team.
    Each OwnedPokemon may only appear once per team.
    """

    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="slots",
        db_index=True,
    )
    pokemon = models.ForeignKey(
        OwnedPokemon,
        on_delete=models.CASCADE,
        related_name="team_slots",
        db_index=True,
    )
    position = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["position"]
        verbose_name = "team slot"
        verbose_name_plural = "team slots"
        constraints = [
            models.UniqueConstraint(
                fields=["team", "position"], name="unique_team_position"
            ),
            models.UniqueConstraint(
                fields=["team", "pokemon"], name="unique_team_pokemon"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.team} — slot {self.position}: {self.pokemon}"


class SpeciesMovePool(models.Model):
    """
    Species-specific move pool entry.

    Maps a move to a species with an explicit slot assignment.
    Replaces the free-form Pokemon.moves M2M for pool management purposes —
    the legacy M2M remains intact for backward compatibility with existing battle code.

    A species should have at least one Generation in Pokemon.generation_sources.
    The generation of each pool entry is inherited from Move.generation.
    """

    species = models.ForeignKey(
        Pokemon,
        on_delete=models.CASCADE,
        related_name="move_pool",
        db_index=True,
    )
    move = models.ForeignKey(
        Move,
        on_delete=models.CASCADE,
        related_name="species_pools",
        db_index=True,
    )
    slot_type = models.TextField(
        choices=MoveSlotType.choices,
        default=MoveSlotType.STANDARD,
        db_index=True,
        help_text="Which battle slot this move occupies for this species.",
    )
    role_tag = models.TextField(
        choices=TacticalRole.choices,
        blank=True,
        default="",
        db_index=True,
        help_text="Tactical build this pool entry belongs to (optional). Allows multi-build pools later.",
    )

    class Meta:
        ordering = ["species", "slot_type", "move"]
        verbose_name = "species move pool entry"
        verbose_name_plural = "species move pool entries"
        constraints = [
            models.UniqueConstraint(
                fields=["species", "move"],
                name="unique_species_move",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.species.name} — {self.slot_type}: {self.move.name}"
