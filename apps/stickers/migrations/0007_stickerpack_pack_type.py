"""Add pack_type field to StickerPack (standard vs bundle)."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stickers", "0006_album_page_model"),
    ]

    operations = [
        migrations.AddField(
            model_name="stickerpack",
            name="pack_type",
            field=models.TextField(
                choices=[("standard", "Standard Pack"), ("bundle", "Bundle Pack")],
                default="standard",
                db_index=True,
                help_text="standard = 5 stickers; bundle = 10 stickers with improved rarity odds.",
            ),
        ),
    ]
