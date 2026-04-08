"""Add achievement badge tracking fields to users_user (GDD §14.4)."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0004_tutorial_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="perfect_victories",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="user",
            name="hard_ai_wins",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="user",
            name="daily_claim_streak",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="user",
            name="max_daily_claim_streak",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="user",
            name="trades_completed",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
