from django.db import migrations, models


def backfill_claimed(apps, schema_editor):
    """Users who already auto-progressed get guide_claimed_step = guide_step."""
    User = apps.get_model("users", "User")
    User.objects.filter(guide_step__gt=0).update(guide_claimed_step=models.F("guide_step"))


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0012_guide_step"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="guide_claimed_step",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.RunPython(backfill_claimed, migrations.RunPython.noop),
    ]
