from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pokemon", "0008_alter_move_slot_type_alter_speciesmovepool_slot_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="pokemon",
            name="primary_role",
            field=models.TextField(
                blank=True,
                choices=[
                    ("dps", "DPS"),
                    ("assassin", "Assassin"),
                    ("tank", "Tank"),
                    ("support", "Support"),
                    ("control", "Control"),
                    ("bruiser", "Bruiser"),
                ],
                db_index=True,
                default="dps",
                help_text="Tactical identity: determines build flavor and pool curation.",
            ),
        ),
        migrations.AddField(
            model_name="speciesmovepool",
            name="role_tag",
            field=models.TextField(
                blank=True,
                choices=[
                    ("dps", "DPS"),
                    ("assassin", "Assassin"),
                    ("tank", "Tank"),
                    ("support", "Support"),
                    ("control", "Control"),
                    ("bruiser", "Bruiser"),
                ],
                db_index=True,
                default="",
                help_text="Tactical build this pool entry belongs to (optional). Allows multi-build pools later.",
            ),
        ),
    ]
