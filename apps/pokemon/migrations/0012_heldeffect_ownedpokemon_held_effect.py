"""
Phase 4 — Held-Effect System

- Creates HeldEffect model
- Adds held_effect FK to OwnedPokemon
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("pokemon", "0011_phase2_chakra_element"),
    ]

    operations = [
        migrations.CreateModel(
            name="HeldEffect",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.TextField(unique=True)),
                ("description", models.TextField(blank=True, default="")),
                (
                    "trigger_condition",
                    models.TextField(
                        choices=[
                            ("on_hit", "On Hit"),
                            ("on_faint", "On Faint"),
                            ("on_status", "On Status"),
                            ("passive", "Passive (each round)"),
                        ],
                        db_index=True,
                    ),
                ),
                (
                    "effect_data",
                    models.JSONField(
                        default=dict,
                        help_text="Effect parameters: heal_fraction, damage_reflect, status_cleanse, revive_hp_fraction.",
                    ),
                ),
                (
                    "activation_chance",
                    models.FloatField(
                        default=1.0,
                        help_text="Probability (0.0–1.0) that this fires when triggered.",
                    ),
                ),
                (
                    "max_activations",
                    models.PositiveIntegerField(
                        default=0,
                        help_text="Max activations per battle (0 = unlimited).",
                    ),
                ),
            ],
            options={
                "verbose_name": "held effect",
                "verbose_name_plural": "held effects",
                "ordering": ["trigger_condition", "name"],
            },
        ),
        migrations.AddField(
            model_name="ownedpokemon",
            name="held_effect",
            field=models.ForeignKey(
                blank=True,
                db_index=True,
                help_text="Held effect equipped by this Pokémon.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="holders",
                to="pokemon.heldeffect",
            ),
        ),
    ]
