"""Initial migration for the guilds app (P4-5)."""
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Guild",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.TextField(unique=True)),
                ("tag", models.CharField(
                    max_length=4,
                    unique=True,
                    help_text="2–4 uppercase letters/digits shown next to member names.",
                )),
                ("description", models.TextField(blank=True, default="")),
                ("created_by", models.ForeignKey(
                    db_index=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="guilds_founded",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("is_recruiting", models.BooleanField(
                    default=True,
                    help_text="When False, no new members can join via the public join button.",
                )),
            ],
            options={"verbose_name": "guild", "verbose_name_plural": "guilds", "ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="GuildMembership",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("user", models.OneToOneField(
                    db_index=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="guild_membership",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("guild", models.ForeignKey(
                    db_index=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="memberships",
                    to="guilds.guild",
                )),
                ("role", models.TextField(
                    choices=[("owner", "Owner"), ("officer", "Officer"), ("member", "Member")],
                    db_index=True,
                    default="member",
                )),
                ("joined_at", models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={"verbose_name": "guild membership", "verbose_name_plural": "guild memberships", "ordering": ["joined_at"]},
        ),
    ]
