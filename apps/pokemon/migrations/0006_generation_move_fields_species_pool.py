"""
Add Generation model, new Move fields (themed_name, generation FK,
combo_starter, combo_trigger, support_flag), Pokemon.generation_sources M2M,
and SpeciesMovePool model.

Does NOT modify existing battle fields — zero impact on current battle flow.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pokemon", "0005_training_fields"),
    ]

    operations = [
        # ── 1. Generation model ──────────────────────────────────────────────
        migrations.CreateModel(
            name="Generation",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=50, unique=True)),
                ("number", models.PositiveSmallIntegerField(unique=True)),
                ("description", models.TextField(blank=True, default="")),
            ],
            options={
                "verbose_name": "generation",
                "verbose_name_plural": "generations",
                "ordering": ["number"],
            },
        ),
        # ── 2. New fields on Move ────────────────────────────────────────────
        migrations.AddField(
            model_name="move",
            name="themed_name",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Alternate display name for lore or themed variants.",
                max_length=100,
            ),
        ),
        migrations.AddField(
            model_name="move",
            name="combo_starter",
            field=models.BooleanField(
                default=False,
                help_text="This move can initiate a combo chain sequence.",
            ),
        ),
        migrations.AddField(
            model_name="move",
            name="combo_trigger",
            field=models.BooleanField(
                default=False,
                help_text="This move can fire automatically as part of a combo chain.",
            ),
        ),
        migrations.AddField(
            model_name="move",
            name="support_flag",
            field=models.BooleanField(
                default=False,
                help_text="Marks this move as having a support effect (heal, shield, buff, etc.).",
            ),
        ),
        migrations.AddField(
            model_name="move",
            name="generation",
            field=models.ForeignKey(
                blank=True,
                db_index=True,
                help_text="Which generation introduced this move.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="moves",
                to="pokemon.generation",
            ),
        ),
        # ── 3. generation_sources M2M on Pokemon ────────────────────────────
        migrations.AddField(
            model_name="pokemon",
            name="generation_sources",
            field=models.ManyToManyField(
                blank=True,
                help_text=(
                    "Generations this species draws its move pool from. "
                    "At least one generation source is required per species."
                ),
                related_name="species",
                to="pokemon.generation",
            ),
        ),
        # ── 4. SpeciesMovePool model ─────────────────────────────────────────
        migrations.CreateModel(
            name="SpeciesMovePool",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "slot_type",
                    models.TextField(
                        choices=[
                            ("standard", "Standard Attack"),
                            ("chase", "Chase"),
                            ("special", "Special"),
                            ("support", "Support"),
                            ("passive", "Passive"),
                        ],
                        db_index=True,
                        default="standard",
                        help_text="Which battle slot this move occupies for this species.",
                    ),
                ),
                (
                    "species",
                    models.ForeignKey(
                        db_index=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="move_pool",
                        to="pokemon.pokemon",
                    ),
                ),
                (
                    "move",
                    models.ForeignKey(
                        db_index=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="species_pools",
                        to="pokemon.move",
                    ),
                ),
            ],
            options={
                "verbose_name": "species move pool entry",
                "verbose_name_plural": "species move pool entries",
                "ordering": ["species", "slot_type", "move"],
            },
        ),
        migrations.AddConstraint(
            model_name="speciesmovepool",
            constraint=models.UniqueConstraint(
                fields=["species", "move"],
                name="unique_species_move",
            ),
        ),
    ]
