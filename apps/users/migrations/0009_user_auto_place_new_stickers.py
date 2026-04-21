from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0008_user_training_slot_upgrade_level"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="auto_place_new_stickers",
            field=models.BooleanField(
                default=False,
                help_text="Automatically place newly earned stickers into empty album slots when possible.",
            ),
        ),
    ]
