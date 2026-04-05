# Generated migration for Team and TeamSlot models.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pokemon", "0002_ownedpokemon"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Team",
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
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "owner",
                    models.OneToOneField(
                        db_index=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="team",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "team",
                "verbose_name_plural": "teams",
            },
        ),
        migrations.CreateModel(
            name="TeamSlot",
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
                ("position", models.PositiveSmallIntegerField()),
                (
                    "pokemon",
                    models.ForeignKey(
                        db_index=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="team_slots",
                        to="pokemon.ownedpokemon",
                    ),
                ),
                (
                    "team",
                    models.ForeignKey(
                        db_index=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="slots",
                        to="pokemon.team",
                    ),
                ),
            ],
            options={
                "verbose_name": "team slot",
                "verbose_name_plural": "team slots",
                "ordering": ["position"],
            },
        ),
        migrations.AddConstraint(
            model_name="teamslot",
            constraint=models.UniqueConstraint(
                fields=["team", "position"], name="unique_team_position"
            ),
        ),
        migrations.AddConstraint(
            model_name="teamslot",
            constraint=models.UniqueConstraint(
                fields=["team", "pokemon"], name="unique_team_pokemon"
            ),
        ),
    ]
