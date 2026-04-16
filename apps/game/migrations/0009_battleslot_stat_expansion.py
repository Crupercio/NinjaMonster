"""
Phase 5 — Stat Expansion

- Adds critical_rate, combo_rate, control_resist to BattleSlot
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("game", "0008_battleslotheldeffect"),
    ]

    operations = [
        migrations.AddField(
            model_name="battleslot",
            name="critical_rate",
            field=models.FloatField(
                default=0.05,
                help_text="Probability (0.0–1.0) of landing a critical hit (×1.5 damage).",
            ),
        ),
        migrations.AddField(
            model_name="battleslot",
            name="combo_rate",
            field=models.FloatField(
                default=0.10,
                help_text="Bonus damage multiplier applied to non-initial combo chain hits.",
            ),
        ),
        migrations.AddField(
            model_name="battleslot",
            name="control_resist",
            field=models.FloatField(
                default=0.00,
                help_text="Probability (0.0–1.0) to resist a status/CC application.",
            ),
        ),
    ]
