from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("guilds", "0002_guild_progress_album_and_quests"),
        ("game", "0016_loteria_room_pattern_prizes"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="loteriaroom",
            name="guild",
            field=models.ForeignKey(
                blank=True,
                db_index=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="loteria_rooms",
                to="guilds.guild",
            ),
        ),
        migrations.AddField(
            model_name="loteriaroom",
            name="room_code",
            field=models.CharField(blank=True, db_index=True, max_length=8, null=True, unique=True),
        ),
        migrations.CreateModel(
            name="LoteriaRoomParticipant",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_host", models.BooleanField(db_index=True, default=False)),
                ("is_ready", models.BooleanField(db_index=True, default=False)),
                ("joined_at", models.DateTimeField(auto_now_add=True)),
                (
                    "room",
                    models.ForeignKey(
                        db_index=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="participants",
                        to="game.loteriaroom",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        db_index=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="loteria_room_participations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "loteria room participant",
                "verbose_name_plural": "loteria room participants",
                "ordering": ["-is_host", "joined_at", "pk"],
                "unique_together": {("room", "user")},
            },
        ),
    ]
