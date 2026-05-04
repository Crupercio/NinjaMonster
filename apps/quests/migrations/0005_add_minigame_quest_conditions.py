"""Add mini-game QuestCondition choices (PLAY_SILHOUETTE, PLAY_MEMORY, PLAY_LOTERIA).

These are TextChoices additions only — no DB schema change needed.
Django validates choices at the application layer, not in the DB column,
so this migration is a no-op SQL-wise but documents the model change.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("quests", "0004_questtemplate_reward_candy_and_userquest_progress_meta"),
    ]

    operations = [
        # TextChoices additions are purely Python-level — no AlterField needed
        # because Django stores the raw string value, not the display name.
        # This migration exists to mark the dependency chain correctly.
    ]
