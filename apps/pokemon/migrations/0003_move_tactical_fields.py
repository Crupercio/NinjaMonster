"""Add tactical 4v4 fields to Move: slot_type, cooldown, priority, always_first, always_last, is_charge_move."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pokemon", "0002_ownedpokemon"),
    ]

    operations = [
        migrations.AddField(
            model_name="move",
            name="slot_type",
            field=models.TextField(
                choices=[
                    ("standard", "Standard Attack"),
                    ("chase", "Chase"),
                    ("special", "Special"),
                    ("support", "Support"),
                    ("passive", "Passive"),
                ],
                default="standard",
                db_index=True,
            ),
        ),
        migrations.AddField(
            model_name="move",
            name="cooldown",
            field=models.PositiveSmallIntegerField(
                default=0,
                help_text="Rounds that must pass before this move can be used again.",
            ),
        ),
        migrations.AddField(
            model_name="move",
            name="priority",
            field=models.SmallIntegerField(
                default=0,
                help_text="Higher priority acts before lower within the same speed tier.",
            ),
        ),
        migrations.AddField(
            model_name="move",
            name="always_first",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="move",
            name="always_last",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="move",
            name="is_charge_move",
            field=models.BooleanField(default=False),
        ),
    ]
