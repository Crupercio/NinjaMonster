"""
Phase 2 — Chakra Element System

- Creates ChakraElement model (fire/water/earth/lightning/wind)
- Adds chakra_element FK to PokemonType
- Data-migrates all 18 types to their chakra element
"""
from django.db import migrations, models
import django.db.models.deletion


# Type name → chakra element mapping (from GDD Option C)
_TYPE_CHAKRA_MAP = {
    "fire":      ["Fire", "Dragon", "Dark"],
    "water":     ["Water", "Ice", "Poison", "Fairy"],
    "earth":     ["Ground", "Rock", "Fighting", "Normal"],
    "lightning": ["Electric", "Steel", "Psychic"],
    "wind":      ["Flying", "Grass", "Bug", "Ghost"],
}

_ELEMENT_DISPLAY = {
    "fire": "Fire",
    "water": "Water",
    "earth": "Earth",
    "lightning": "Lightning",
    "wind": "Wind",
}


def create_elements_and_map_types(apps, schema_editor):
    ChakraElement = apps.get_model("pokemon", "ChakraElement")
    PokemonType = apps.get_model("pokemon", "PokemonType")

    for element_name, type_names in _TYPE_CHAKRA_MAP.items():
        element = ChakraElement.objects.create(name=element_name)
        PokemonType.objects.filter(name__in=type_names).update(chakra_element=element)


def remove_elements(apps, schema_editor):
    ChakraElement = apps.get_model("pokemon", "ChakraElement")
    PokemonType = apps.get_model("pokemon", "PokemonType")
    PokemonType.objects.all().update(chakra_element=None)
    ChakraElement.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("pokemon", "0010_phase1_rename_slots_roles_combo_role"),
    ]

    operations = [
        # 1. Create ChakraElement table
        migrations.CreateModel(
            name="ChakraElement",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "name",
                    models.TextField(
                        choices=[
                            ("fire", "Fire"),
                            ("water", "Water"),
                            ("earth", "Earth"),
                            ("lightning", "Lightning"),
                            ("wind", "Wind"),
                        ],
                        unique=True,
                    ),
                ),
            ],
            options={
                "verbose_name": "chakra element",
                "verbose_name_plural": "chakra elements",
                "ordering": ["name"],
            },
        ),
        # 2. Add chakra_element FK to PokemonType (nullable)
        migrations.AddField(
            model_name="pokemontype",
            name="chakra_element",
            field=models.ForeignKey(
                blank=True,
                db_index=True,
                help_text="Chakra nature this type belongs to (fire/water/earth/lightning/wind).",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="types",
                to="pokemon.chakraelement",
            ),
        ),
        # 3. Populate elements and map all 18 types
        migrations.RunPython(create_elements_and_map_types, remove_elements),
    ]
