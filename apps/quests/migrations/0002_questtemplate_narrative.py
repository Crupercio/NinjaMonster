"""Add narrative_text and chapter fields to QuestTemplate (P4-1)."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("quests", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="questtemplate",
            name="chapter",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                help_text="Act/chapter grouping for story quests (e.g. 'prologue', 'act_1').",
                max_length=50,
            ),
        ),
        migrations.AddField(
            model_name="questtemplate",
            name="narrative_text",
            field=models.TextField(
                blank=True,
                default="",
                help_text="In-world dialogue or lore text shown alongside this quest.",
            ),
        ),
    ]
