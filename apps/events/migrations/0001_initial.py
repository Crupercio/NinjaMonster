"""Initial migration for the seasonal events app (P4-2)."""
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies: list = []

    operations = [
        migrations.CreateModel(
            name="SeasonalEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.TextField()),
                ("description", models.TextField(blank=True, default="")),
                ("flavor_text", models.TextField(blank=True, default="", help_text="Narrative / lore blurb shown on the event banner.")),
                ("event_type", models.TextField(
                    choices=[
                        ("bonus_ryo", "Bonus Ryo on Win"),
                        ("bonus_dust", "Bonus Sticker Dust on Win"),
                        ("double_combo_dust", "Double Dust for Combo Wins"),
                        ("bonus_pack_chance", "Reduced Pack Win Threshold"),
                    ],
                    db_index=True,
                )),
                ("bonus_value", models.PositiveIntegerField(
                    help_text="Bonus Ryo or Sticker Dust awarded per qualifying win. Ignored for BONUS_PACK_CHANCE.",
                )),
                ("start_at", models.DateTimeField(db_index=True)),
                ("end_at", models.DateTimeField(db_index=True)),
                ("is_active", models.BooleanField(
                    default=True,
                    db_index=True,
                    help_text="Master on/off switch — set False to disable without deleting.",
                )),
            ],
            options={
                "verbose_name": "seasonal event",
                "verbose_name_plural": "seasonal events",
                "ordering": ["-start_at"],
            },
        ),
    ]
