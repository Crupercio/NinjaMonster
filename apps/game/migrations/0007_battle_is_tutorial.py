from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0006_alter_battleslot_grid_position_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='battle',
            name='is_tutorial',
            field=models.BooleanField(db_index=True, default=False),
        ),
    ]
