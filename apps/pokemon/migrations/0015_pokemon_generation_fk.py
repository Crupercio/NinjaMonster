"""Add generation FK to Pokemon (which gen introduced this species)."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pokemon", "0014_move_chase_condition"),
    ]

    operations = [
        migrations.AddField(
            model_name="pokemon",
            name="generation",
            field=models.ForeignKey(
                blank=True,
                db_index=True,
                help_text="The generation this species was first introduced in.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="introduced_pokemon",
                to="pokemon.generation",
            ),
        ),
    ]
