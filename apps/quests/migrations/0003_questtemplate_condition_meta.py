"""Add condition_meta JSONField to QuestTemplate for type-based quest variants."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("quests", "0002_questtemplate_narrative"),
    ]

    operations = [
        migrations.AddField(
            model_name="questtemplate",
            name="condition_meta",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text=(
                    "Optional extra constraints for the condition. "
                    "For achieve_combo: {'min_type_count': 3, 'type_names': ['Fire']} "
                    "or {'mono_type': true} or {'all_chakra_elements': true}."
                ),
            ),
        ),
    ]
