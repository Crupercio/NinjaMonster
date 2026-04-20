"""
Data migration: rename sticker rarity and variant values to match new design.

  StickerRarity:
    holographic → prismatic

  StickerVariant:
    chibi             → watercolor
    manga_panel       → sketch
    full_illustration → neon_glow

Updates both the Sticker table and RegionalAlbumPage table for the rarity rename.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("stickers", "0008_stickerpack_gen_pack_types"),
    ]

    operations = [
        # ── Rarity rename: holographic → prismatic ───────────────────────────
        migrations.RunSQL(
            sql="""
                UPDATE stickers_sticker
                SET rarity = 'prismatic'
                WHERE rarity = 'holographic';

                UPDATE stickers_regionalalbumpage
                SET rarity = 'prismatic'
                WHERE rarity = 'holographic';
            """,
            reverse_sql="""
                UPDATE stickers_sticker
                SET rarity = 'holographic'
                WHERE rarity = 'prismatic';

                UPDATE stickers_regionalalbumpage
                SET rarity = 'holographic'
                WHERE rarity = 'prismatic';
            """,
        ),
        # ── Variant renames ──────────────────────────────────────────────────
        migrations.RunSQL(
            sql="""
                UPDATE stickers_sticker
                SET variant = 'watercolor'
                WHERE variant = 'chibi';

                UPDATE stickers_sticker
                SET variant = 'sketch'
                WHERE variant = 'manga_panel';

                UPDATE stickers_sticker
                SET variant = 'neon_glow'
                WHERE variant = 'full_illustration';
            """,
            reverse_sql="""
                UPDATE stickers_sticker
                SET variant = 'chibi'
                WHERE variant = 'watercolor';

                UPDATE stickers_sticker
                SET variant = 'manga_panel'
                WHERE variant = 'sketch';

                UPDATE stickers_sticker
                SET variant = 'full_illustration'
                WHERE variant = 'neon_glow';
            """,
        ),
    ]
