from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0009_user_auto_place_new_stickers"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="arcade_daily_progress",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Per-day collector arcade progress used by the Fun Hub daily challenge widget.",
            ),
        ),
    ]
