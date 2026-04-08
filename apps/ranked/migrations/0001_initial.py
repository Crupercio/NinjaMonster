"""Initial migration for the ranked app."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("game", "0007_battle_is_tutorial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="RankedSeason",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("number", models.PositiveIntegerField(unique=True, help_text="Season number (1, 2, 3, …)")),
                ("name", models.CharField(max_length=120, help_text='e.g. "Season of Kizuna"')),
                ("theme", models.CharField(max_length=120, blank=True)),
                ("start_date", models.DateField()),
                ("end_date", models.DateField()),
                ("is_active", models.BooleanField(default=False, db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "ranked season",
                "verbose_name_plural": "ranked seasons",
                "ordering": ["-number"],
            },
        ),
        migrations.CreateModel(
            name="RankedProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("rank_points", models.PositiveIntegerField(default=0)),
                ("tier", models.TextField(choices=[
                    ("bronze", "Bronze"), ("silver", "Silver"), ("gold", "Gold"),
                    ("platinum", "Platinum"), ("diamond", "Diamond"), ("champion", "Champion"),
                ], default="bronze", db_index=True)),
                ("sub_tier", models.PositiveSmallIntegerField(default=3)),
                ("win_streak", models.PositiveSmallIntegerField(default=0)),
                ("season_wins", models.PositiveIntegerField(default=0)),
                ("season_losses", models.PositiveIntegerField(default=0)),
                ("reward_claimed", models.BooleanField(default=False)),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="ranked_profiles",
                    to=settings.AUTH_USER_MODEL,
                    db_index=True,
                )),
                ("season", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="profiles",
                    to="ranked.rankedseason",
                    db_index=True,
                )),
            ],
            options={
                "verbose_name": "ranked profile",
                "verbose_name_plural": "ranked profiles",
                "ordering": ["-rank_points"],
                "unique_together": {("user", "season")},
            },
        ),
        migrations.CreateModel(
            name="MatchmakingEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("rank_points", models.PositiveIntegerField(default=0)),
                ("status", models.TextField(choices=[
                    ("waiting", "Waiting"), ("matched", "Matched"), ("cancelled", "Cancelled"),
                ], default="waiting", db_index=True)),
                ("entered_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="queue_entries",
                    to=settings.AUTH_USER_MODEL,
                    db_index=True,
                )),
                ("battle", models.ForeignKey(
                    null=True,
                    blank=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="matchmaking_entries",
                    to="game.battle",
                )),
            ],
            options={
                "verbose_name": "matchmaking entry",
                "verbose_name_plural": "matchmaking entries",
                "ordering": ["entered_at"],
            },
        ),
    ]
