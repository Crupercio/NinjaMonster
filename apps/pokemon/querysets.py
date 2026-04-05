"""Custom querysets for the pokemon app."""
from django.db import models


class PokemonQuerySet(models.QuerySet):
    """Custom queryset methods for Pokemon."""

    def by_type(self, type_name: str) -> "PokemonQuerySet":
        """Filter Pokemon by primary or secondary type name."""
        return self.filter(
            models.Q(primary_type__name__iexact=type_name)
            | models.Q(secondary_type__name__iexact=type_name)
        )

    def with_combo_moves(self) -> "PokemonQuerySet":
        """Filter Pokemon that have at least one move with a trigger_status."""
        return self.filter(moves__trigger_status__isnull=False).distinct()

    def with_status_moves(self) -> "PokemonQuerySet":
        """Filter Pokemon that have at least one move with an applies_status."""
        return self.filter(moves__applies_status__isnull=False).distinct()
