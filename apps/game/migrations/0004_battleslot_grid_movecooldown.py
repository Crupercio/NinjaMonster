"""Add grid position + selection state to BattleSlot; introduce MoveCooldown model."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("game", "0003_battle_ai_fields"),
        ("pokemon", "0003_move_tactical_fields"),
    ]

    operations = [
        # ── BattleSlot new fields ────────────────────────────────────────────
        migrations.AddField(
            model_name="battleslot",
            name="grid_position",
            field=models.TextField(
                choices=[
                    ("front_left", "Front Left"),
                    ("front_right", "Front Right"),
                    ("back_left", "Back Left"),
                    ("back_right", "Back Right"),
                    ("bench_1", "Bench 1"),
                    ("bench_2", "Bench 2"),
                ],
                default="front_left",
                help_text="Named grid cell for the 4v4 battlefield.",
            ),
        ),
        migrations.AddField(
            model_name="battleslot",
            name="is_active",
            field=models.BooleanField(
                default=True,
                db_index=True,
                help_text="True if the slot is on the field (not bench).",
            ),
        ),
        migrations.AddField(
            model_name="battleslot",
            name="selected_move",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="pokemon.move",
                help_text="Persisted move selection for this slot.",
            ),
        ),
        migrations.AddField(
            model_name="battleslot",
            name="selected_target",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="game.battleslot",
                help_text="Persisted target selection for this slot.",
            ),
        ),
        # ── MoveCooldown model ───────────────────────────────────────────────
        migrations.CreateModel(
            name="MoveCooldown",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                (
                    "slot",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="move_cooldowns",
                        to="game.battleslot",
                        db_index=True,
                    ),
                ),
                (
                    "move",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to="pokemon.move",
                        db_index=True,
                    ),
                ),
                ("remaining_rounds", models.PositiveSmallIntegerField(default=0)),
            ],
            options={
                "verbose_name": "move cooldown",
                "verbose_name_plural": "move cooldowns",
                "unique_together": {("slot", "move")},
            },
        ),
    ]
