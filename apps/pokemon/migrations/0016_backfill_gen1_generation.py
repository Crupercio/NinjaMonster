"""Backfill generation FK for all existing Gen 1 Pokemon (dex #1–151)."""
from django.db import migrations


def backfill_gen1(apps, schema_editor):
    Pokemon = apps.get_model("pokemon", "Pokemon")
    Generation = apps.get_model("pokemon", "Generation")
    gen1 = Generation.objects.filter(number=1).first()
    if gen1 is None:
        return  # Gen 1 not seeded yet — seed_gen1 will handle it
    Pokemon.objects.filter(
        pokedex_number__gte=1,
        pokedex_number__lte=151,
        generation__isnull=True,
    ).update(generation=gen1)


class Migration(migrations.Migration):

    dependencies = [
        ("pokemon", "0015_pokemon_generation_fk"),
    ]

    operations = [
        migrations.RunPython(backfill_gen1, migrations.RunPython.noop),
    ]
