from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("game", "0018_loteriaprizeclaim"),
    ]

    operations = [
        migrations.AddField(
            model_name="loteriaroom",
            name="pause_remaining_seconds",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="loteriaroom",
            name="paused_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
