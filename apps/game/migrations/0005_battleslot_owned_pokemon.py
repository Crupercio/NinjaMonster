"""Add owned_pokemon FK to BattleSlot to link the specific OwnedPokemon instance."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("game", "0004_battleslot_grid_movecooldown"),
        ("pokemon", "0007_ownedpokemon_move_slots"),
    ]

    operations = [
        migrations.AddField(
            model_name="battleslot",
            name="owned_pokemon",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="battle_slots",
                to="pokemon.ownedpokemon",
                db_index=True,
                help_text="The specific OwnedPokemon instance used for this slot (null for AI/legacy).",
            ),
        ),
    ]
