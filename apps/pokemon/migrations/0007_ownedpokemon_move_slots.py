"""Add 5 nullable move FK fields to OwnedPokemon (one per slot type)."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pokemon", "0006_generation_move_fields_species_pool"),
    ]

    operations = [
        migrations.AddField(
            model_name="ownedpokemon",
            name="move_standard",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="pokemon.move",
                help_text="Assigned Basic Technique (standard slot).",
            ),
        ),
        migrations.AddField(
            model_name="ownedpokemon",
            name="move_chase",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="pokemon.move",
                help_text="Assigned Chase Technique.",
            ),
        ),
        migrations.AddField(
            model_name="ownedpokemon",
            name="move_special",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="pokemon.move",
                help_text="Assigned Secret Technique (special slot).",
            ),
        ),
        migrations.AddField(
            model_name="ownedpokemon",
            name="move_support",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="pokemon.move",
                help_text="Assigned Support Technique.",
            ),
        ),
        migrations.AddField(
            model_name="ownedpokemon",
            name="move_passive",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="pokemon.move",
                help_text="Assigned Ninja Trait (passive slot).",
            ),
        ),
    ]
