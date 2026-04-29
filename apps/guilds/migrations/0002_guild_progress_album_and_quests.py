"""Add guild album, quest claim, and progression fields."""

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stickers", "0005_album_placed_regional_badges"),
        ("guilds", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="guild",
            name="level",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="guild",
            name="xp",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="guildmembership",
            name="contribution_points",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="guildmembership",
            name="donated_stickers",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="guildmembership",
            name="guild_quests_completed",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.CreateModel(
            name="GuildAlbumEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "donated_by",
                    models.ForeignKey(
                        db_index=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="guild_album_donations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "guild",
                    models.ForeignKey(
                        db_index=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="album_entries",
                        to="guilds.guild",
                    ),
                ),
                (
                    "sticker",
                    models.OneToOneField(
                        db_index=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="guild_album_entry",
                        to="stickers.sticker",
                    ),
                ),
            ],
            options={
                "verbose_name": "guild album entry",
                "verbose_name_plural": "guild album entries",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="GuildQuestClaim",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quest_key", models.CharField(max_length=32)),
                ("period", models.CharField(choices=[("daily", "Daily"), ("weekly", "Weekly")], max_length=16)),
                ("period_start", models.DateField(db_index=True)),
                ("claimed_at", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "guild",
                    models.ForeignKey(
                        db_index=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="quest_claims",
                        to="guilds.guild",
                    ),
                ),
                (
                    "membership",
                    models.ForeignKey(
                        db_index=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="quest_claims",
                        to="guilds.guildmembership",
                    ),
                ),
            ],
            options={
                "verbose_name": "guild quest claim",
                "verbose_name_plural": "guild quest claims",
                "ordering": ["-claimed_at"],
                "unique_together": {("membership", "quest_key", "period", "period_start")},
            },
        ),
    ]
