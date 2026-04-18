"""Add generation-specific pack types (gen1–gen8) to StickerPack.pack_type choices."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stickers", "0007_stickerpack_pack_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="stickerpack",
            name="pack_type",
            field=models.TextField(
                choices=[
                    ("standard", "Standard Pack"),
                    ("bundle", "Bundle Pack"),
                    ("gen1", "Kanto Pack (Gen 1)"),
                    ("gen2", "Johto Pack (Gen 2)"),
                    ("gen3", "Hoenn Pack (Gen 3)"),
                    ("gen4", "Sinnoh Pack (Gen 4)"),
                    ("gen5", "Unova Pack (Gen 5)"),
                    ("gen6", "Kalos Pack (Gen 6)"),
                    ("gen7", "Alola Pack (Gen 7)"),
                    ("gen8", "Galar Pack (Gen 8)"),
                ],
                default="standard",
                db_index=True,
                help_text=(
                    "standard = 5 stickers; bundle = 10 stickers with improved odds; "
                    "gen1–gen8 = 5 stickers from that generation only."
                ),
            ),
        ),
    ]
