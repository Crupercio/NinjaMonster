"""Admin registrations for the game app."""
from django.contrib import admin

from .models import Battle, BattleAction, BattleLog, BattleRound, BattleSlot, BattleTeam, MoveCooldown


@admin.register(Battle)
class BattleAdmin(admin.ModelAdmin):
    list_display = ("pk", "player_one", "player_two", "status", "current_round", "winner", "created_at")
    list_filter = ("status",)
    raw_id_fields = ("player_one", "player_two", "winner")


@admin.register(BattleTeam)
class BattleTeamAdmin(admin.ModelAdmin):
    list_display = ("pk", "battle", "owner")
    raw_id_fields = ("battle", "owner")


@admin.register(BattleSlot)
class BattleSlotAdmin(admin.ModelAdmin):
    list_display = ("pk", "team", "pokemon", "grid_position", "is_active", "current_hp", "max_hp", "is_fainted")
    list_filter = ("is_fainted", "is_active", "grid_position")
    raw_id_fields = ("team", "pokemon")


@admin.register(MoveCooldown)
class MoveCooldownAdmin(admin.ModelAdmin):
    list_display = ("pk", "slot", "move", "remaining_rounds")
    list_filter = ("move",)
    raw_id_fields = ("slot", "move")


@admin.register(BattleRound)
class BattleRoundAdmin(admin.ModelAdmin):
    list_display = ("pk", "battle", "round_number", "created_at")


@admin.register(BattleAction)
class BattleActionAdmin(admin.ModelAdmin):
    list_display = ("pk", "round", "attacker_slot", "move", "damage_dealt", "is_combo_triggered", "order_in_chain")
    list_filter = ("is_combo_triggered",)


@admin.register(BattleLog)
class BattleLogAdmin(admin.ModelAdmin):
    list_display = ("pk", "battle", "round_number", "log_type", "message", "created_at")
    list_filter = ("log_type",)
