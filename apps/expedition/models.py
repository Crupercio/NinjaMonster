"""Expedition system models — zones, spawn tables, sessions, encounter logs."""
import logging

from django.conf import settings
from django.db import models

logger = logging.getLogger(__name__)


class Zone(models.Model):
    """A named exploration area with a spawn table and entry cost."""

    key = models.TextField(unique=True, help_text="Stable slug, e.g. 'meadow_route'")
    name = models.TextField()
    description = models.TextField(blank=True, default="")
    flavor_intro = models.TextField(blank=True, default="", help_text="Text shown when entering the zone.")
    flavor_walking = models.TextField(blank=True, default="", help_text="Short text shown between encounters.")
    cost = models.PositiveIntegerField(help_text="Ryo cost per expedition run.")
    encounters_per_run = models.PositiveIntegerField(default=5)
    min_trainer_level = models.PositiveIntegerField(default=1)
    order = models.PositiveIntegerField(default=0)
    bg_gradient = models.TextField(blank=True, default="", help_text="CSS gradient for zone background.")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order"]

    def __str__(self) -> str:
        return self.name


class ZoneSpawnEntry(models.Model):
    """Maps a Pokémon species to a zone with a relative spawn weight."""

    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name="spawns")
    species = models.ForeignKey(
        "pokemon.Pokemon", on_delete=models.CASCADE, related_name="zone_spawns"
    )
    weight = models.PositiveIntegerField(default=10, help_text="Relative spawn probability.")

    class Meta:
        unique_together = [("zone", "species")]
        ordering = ["-weight", "species__name"]

    def __str__(self) -> str:
        return f"{self.zone.name} — {self.species.name} (w={self.weight})"


class ExpeditionSession(models.Model):
    """One paid expedition run. Used to enforce daily attempt limits."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="expedition_sessions"
    )
    zone = models.ForeignKey(Zone, on_delete=models.PROTECT, related_name="sessions")
    session_date = models.DateField()
    encounters_total = models.PositiveIntegerField()
    encounters_used = models.PositiveIntegerField(default=0)
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user} in {self.zone.name} ({self.session_date})"

    @property
    def encounters_remaining(self) -> int:
        return max(0, self.encounters_total - self.encounters_used)

    @property
    def is_finished(self) -> bool:
        return self.completed or self.encounters_remaining == 0


class EncounterLog(models.Model):
    """Records the outcome of one encounter within an expedition session."""

    session = models.ForeignKey(ExpeditionSession, on_delete=models.CASCADE, related_name="encounters")
    species = models.ForeignKey("pokemon.Pokemon", on_delete=models.PROTECT, related_name="encounter_logs")
    base_bond_rate = models.PositiveIntegerField(help_text="Random 15–90 before candy.")
    candy_used = models.TextField(blank=True, default="", help_text="Candy type or empty.")
    final_bond_rate = models.PositiveIntegerField(help_text="After candy, capped at 90.")
    bonded = models.BooleanField()
    owned_pokemon = models.ForeignKey(
        "pokemon.OwnedPokemon", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="encounter_origin",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.species.name} — {'bonded' if self.bonded else 'fled'}"
