from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("game", "0015_move_seeded_loteria_boards_to_starter_slot"),
    ]

    operations = [
        migrations.AddField(
            model_name="loteriaroom",
            name="entry_fee_ryo",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="loteriaroom",
            name="pattern_claims",
            field=models.JSONField(default=list, help_text="Resolved pattern prizes claimed in this room."),
        ),
        migrations.AddField(
            model_name="loteriaroom",
            name="side_pattern_reward_ryo",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
