"""Add AlbumCompletionReward model for P4-3 album completion rewards."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stickers", "0003_alter_sticker_variant"),
        ("pokemon", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AlbumCompletionReward",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("user", models.ForeignKey(
                    db_index=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="album_completion_rewards",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("reward_type", models.TextField(
                    choices=[
                        ("pokemon_complete", "Pokemon Collection Complete"),
                        ("full_dex", "Full Pokedex Complete"),
                    ],
                    db_index=True,
                )),
                ("pokemon", models.ForeignKey(
                    blank=True,
                    db_index=True,
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="completion_rewards",
                    to="pokemon.pokemon",
                )),
                ("dust_awarded", models.PositiveIntegerField(default=0)),
                ("ryo_awarded", models.PositiveIntegerField(default=0)),
                ("packs_awarded", models.PositiveIntegerField(default=0)),
                ("claimed_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "album completion reward",
                "verbose_name_plural": "album completion rewards",
                "ordering": ["-claimed_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="albumcompletionreward",
            constraint=models.UniqueConstraint(
                fields=["user", "reward_type", "pokemon"],
                name="unique_album_completion_reward",
            ),
        ),
    ]
