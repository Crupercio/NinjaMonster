"""
Phase 5 — Stat Expansion

- Renames base_sp_attack → base_ninjutsu on Pokemon
- Renames base_speed   → base_initiative on Pokemon
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("pokemon", "0012_heldeffect_ownedpokemon_held_effect"),
    ]

    operations = [
        migrations.RenameField(
            model_name="pokemon",
            old_name="base_sp_attack",
            new_name="base_ninjutsu",
        ),
        migrations.RenameField(
            model_name="pokemon",
            old_name="base_speed",
            new_name="base_initiative",
        ),
    ]
