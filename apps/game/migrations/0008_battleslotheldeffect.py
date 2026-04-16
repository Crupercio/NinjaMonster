"""
Phase 4 — Held-Effect System

- Creates BattleSlotHeldEffect model (OneToOne → BattleSlot)
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("game", "0007_battle_is_tutorial"),
        ("pokemon", "0012_heldeffect_ownedpokemon_held_effect"),
    ]

    operations = [
        migrations.CreateModel(
            name="BattleSlotHeldEffect",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "slot",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="held_effect_state",
                        to="game.battleslot",
                    ),
                ),
                (
                    "effect",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="battle_states",
                        to="pokemon.heldeffect",
                    ),
                ),
                ("activations_used", models.PositiveIntegerField(default=0)),
            ],
            options={
                "verbose_name": "battle slot held effect",
                "verbose_name_plural": "battle slot held effects",
            },
        ),
    ]
