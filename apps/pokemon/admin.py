"""Admin registrations for the pokemon app."""
import logging

from django.contrib import admin
from django.db.models import Count, QuerySet
from django.http import HttpRequest

from .models import (
    Generation,
    Move,
    MoveSlotType,
    OwnedPokemon,
    Pokemon,
    PokemonType,
    SpeciesMovePool,
    Team,
    TeamSlot,
)


@admin.register(PokemonType)
class PokemonTypeAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Generation)
class GenerationAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "description")
    ordering = ("number",)
    search_fields = ("name",)


@admin.register(Move)
class MoveAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "themed_name",
        "slot_type",
        "move_type",
        "power",
        "accuracy",
        "cooldown",
        "priority",
        "generation",
        "always_first",
        "always_last",
        "is_charge_move",
        "combo_starter",
        "combo_trigger",
        "support_flag",
        "applies_status",
        "trigger_status",
    )
    list_filter = (
        "slot_type",
        "move_type",
        "generation",
        "always_first",
        "always_last",
        "is_charge_move",
        "combo_starter",
        "combo_trigger",
        "support_flag",
    )
    search_fields = ("name", "themed_name")


class SpeciesMovePoolInline(admin.TabularInline):
    model = SpeciesMovePool
    extra = 1
    fields = ("slot_type", "role_tag", "move")
    autocomplete_fields = ("move",)


class BattleReadyFilter(admin.SimpleListFilter):
    title = "battle ready"
    parameter_name = "battle_ready"

    def lookups(self, _request: HttpRequest, _model_admin: admin.ModelAdmin):
        return [("yes", "Yes"), ("no", "No")]

    def queryset(self, _request: HttpRequest, queryset: QuerySet) -> QuerySet:
        annotated = queryset.annotate(
            pool_slot_count=Count("move_pool__slot_type", distinct=True)
        )
        required = len(MoveSlotType.values)
        if self.value() == "yes":
            return annotated.filter(pool_slot_count__gte=required)
        if self.value() == "no":
            return annotated.filter(pool_slot_count__lt=required)
        return queryset


@admin.register(Pokemon)
class PokemonAdmin(admin.ModelAdmin):
    list_display = (
        "name", "primary_type", "secondary_type",
        "base_hp", "base_speed", "primary_role", "battle_ready",
    )
    list_filter = ("primary_type", "secondary_type", "generation_sources", "primary_role", BattleReadyFilter)
    search_fields = ("name",)
    filter_horizontal = ("moves", "generation_sources")
    inlines = [SpeciesMovePoolInline]

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return (
            super()
            .get_queryset(request)
            .annotate(pool_slot_count=Count("move_pool__slot_type", distinct=True))
        )

    @admin.display(boolean=True, description="Battle Ready")
    def battle_ready(self, obj: Pokemon) -> bool:
        return obj.pool_slot_count >= len(MoveSlotType.values)  # type: ignore[attr-defined]


@admin.register(SpeciesMovePool)
class SpeciesMovePoolAdmin(admin.ModelAdmin):
    list_display = ("species", "slot_type", "role_tag", "move", "move_generation")
    list_filter = ("slot_type", "role_tag", "move__generation")
    search_fields = ("species__name", "move__name")
    raw_id_fields = ("species", "move")

    @admin.display(description="Move Gen", ordering="move__generation__number")
    def move_generation(self, obj: SpeciesMovePool) -> str:
        if obj.move.generation:
            return str(obj.move.generation)
        return "—"


logger = logging.getLogger(__name__)


@admin.register(OwnedPokemon)
class OwnedPokemonAdmin(admin.ModelAdmin):
    list_display = ("species", "owner", "level", "experience", "is_training", "created_at")
    list_filter = ("is_training", "level")
    search_fields = ("species__name", "owner__username")
    raw_id_fields = ("owner", "species")

    def save_model(
        self, request: HttpRequest, obj: OwnedPokemon, form: object, change: bool
    ) -> None:
        super().save_model(request, obj, form, change)
        if change:
            return
        # Fill any empty move slots on creation. assign_random_moveset skips slots
        # that already have a move, so manually-set moves are always preserved.
        from .services import assign_random_moveset

        try:
            assign_random_moveset(obj)
        except Exception:
            logger.exception(
                "Failed to assign moveset to OwnedPokemon pk=%s via admin.", obj.pk
            )


class TeamSlotInline(admin.TabularInline):
    model = TeamSlot
    extra = 0
    raw_id_fields = ("pokemon",)


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("owner", "created_at")
    search_fields = ("owner__username",)
    raw_id_fields = ("owner",)
    inlines = [TeamSlotInline]


@admin.register(TeamSlot)
class TeamSlotAdmin(admin.ModelAdmin):
    list_display = ("team", "position", "pokemon")
    list_filter = ("position",)
    raw_id_fields = ("team", "pokemon")
