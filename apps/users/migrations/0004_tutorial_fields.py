from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_pity_counters'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='tutorial_complete',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='user',
            name='tutorial_starter',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
    ]
