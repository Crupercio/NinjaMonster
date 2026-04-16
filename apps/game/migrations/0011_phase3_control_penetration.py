"""Phase 3 — Add control and penetration FloatFields to BattleSlot."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("game", "0010_phase2_seeded_applied_by_slot"),
    ]

    operations = [
        migrations.AddField(
            model_name="battleslot",
            name="control",
            field=models.FloatField(
                default=100.0,
                help_text="CC success rate; higher values improve status application vs control_resist.",
            ),
        ),
        migrations.AddField(
            model_name="battleslot",
            name="penetration",
            field=models.FloatField(
                default=0.0,
                help_text="Fraction of target's defense ignored (0.0–1.0). Derived from primary_role.",
            ),
        ),
    ]
