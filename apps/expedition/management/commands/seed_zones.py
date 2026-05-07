"""
Seed zones and spawn tables for the expedition system.

Usage:
    python manage.py seed_zones
    python manage.py seed_zones --reset   # wipe and re-seed
"""
import logging

from django.core.management.base import BaseCommand

from apps.expedition.models import Zone, ZoneSpawnEntry
from apps.pokemon.models import Pokemon

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Zone definitions
# ---------------------------------------------------------------------------
ZONES = [
    {
        "key": "meadow_route",
        "name": "Meadow Route",
        "description": "A peaceful grassy path where common Pokémon roam freely.",
        "flavor_intro": "You step onto a sunlit path. The grass sways gently in the breeze…",
        "flavor_walking": "You walk quietly along the trail…",
        "cost": 2000,
        "encounters_per_run": 5,
        "min_trainer_level": 1,
        "order": 1,
        "bg_gradient": "linear-gradient(160deg, #0d2a0d 0%, #134a18 45%, #1a5e20 80%, #22762a 100%)",
        "types": ["Normal", "Bug", "Grass", "Poison"],
    },
    {
        "key": "bamboo_forest",
        "name": "Bamboo Forest",
        "description": "A dense forest rustling with life. Watch your step.",
        "flavor_intro": "Tall bamboo towers overhead. Something stirs in the underbrush…",
        "flavor_walking": "Leaves crunch softly beneath your feet…",
        "cost": 5000,
        "encounters_per_run": 5,
        "min_trainer_level": 1,
        "order": 2,
        "bg_gradient": "linear-gradient(160deg, #0a1a0a 0%, #0f2e14 45%, #143d1a 80%, #1a5020 100%)",
        "types": ["Bug", "Grass", "Poison", "Normal", "Water"],
    },
    {
        "key": "coastal_shallows",
        "name": "Coastal Shallows",
        "description": "Sparkling shallows teeming with Water-type Pokémon.",
        "flavor_intro": "The scent of salt fills the air. Waves lap at your feet…",
        "flavor_walking": "You wade through the cool, clear water…",
        "cost": 8000,
        "encounters_per_run": 5,
        "min_trainer_level": 3,
        "order": 3,
        "bg_gradient": "linear-gradient(160deg, #0a1a2e 0%, #0f2d52 45%, #134070 80%, #1050a0 100%)",
        "types": ["Water", "Electric", "Psychic", "Ice"],
    },
    {
        "key": "mountain_pass",
        "name": "Mountain Pass",
        "description": "A rugged trail where hardy Pokémon test their strength.",
        "flavor_intro": "The wind howls across the rocky ledge. You feel the altitude…",
        "flavor_walking": "Loose stones skitter down the slope ahead…",
        "cost": 15000,
        "encounters_per_run": 4,
        "min_trainer_level": 8,
        "order": 4,
        "bg_gradient": "linear-gradient(160deg, #1a1205 0%, #2e2008 45%, #3d2c0a 80%, #4a3510 100%)",
        "types": ["Rock", "Ground", "Fighting", "Fire", "Electric"],
    },
    {
        "key": "hidden_ruins",
        "name": "Hidden Ruins",
        "description": "Ancient stone corridors where rare Pokémon dwell in silence.",
        "flavor_intro": "Vines cover crumbling pillars. The air feels heavy and ancient…",
        "flavor_walking": "Your footsteps echo in the stone corridor…",
        "cost": 30000,
        "encounters_per_run": 3,
        "min_trainer_level": 15,
        "order": 5,
        "bg_gradient": "linear-gradient(160deg, #180830 0%, #241445 45%, #331a5e 80%, #421e78 100%)",
        "types": ["Ghost", "Psychic", "Dragon", "Dark", "Fairy"],
    },
    {
        "key": "storm_summit",
        "name": "Storm Summit",
        "description": "Lightning-wracked peaks where only the rarest of Pokémon survive.",
        "flavor_intro": "Thunder rolls above you. Only the brave dare climb this high…",
        "flavor_walking": "The storm howls. You press forward…",
        "cost": 50000,
        "encounters_per_run": 2,
        "min_trainer_level": 25,
        "order": 6,
        "bg_gradient": "linear-gradient(160deg, #0a0a1e 0%, #12124a 45%, #1a1a60 80%, #222278 100%)",
        "types": ["Dragon", "Electric", "Ice", "Psychic", "Ghost", "Dark"],
    },
]

# Extra high-weight species per zone (appear more often — thematic anchors)
FEATURED_SPECIES: dict[str, list[str]] = {
    "meadow_route":    ["Rattata", "Pidgey", "Caterpie", "Weedle", "Ekans"],
    "bamboo_forest":   ["Oddish", "Bellsprout", "Paras", "Venonat"],
    "coastal_shallows": ["Psyduck", "Staryu", "Tentacool", "Seel", "Poliwag"],
    "mountain_pass":   ["Geodude", "Machop", "Onix", "Mankey", "Ponyta"],
    "hidden_ruins":    ["Gastly", "Abra", "Drowzee", "Ditto"],
    "storm_summit":    ["Dratini", "Jynx", "Electabuzz", "Articuno"],
}


class Command(BaseCommand):
    help = "Seed expedition zones and spawn tables."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Wipe existing zones and re-seed.")

    def handle(self, *args, **options):
        if options["reset"]:
            Zone.objects.all().delete()
            self.stdout.write(self.style.WARNING("Existing zones deleted."))

        created_zones = 0
        created_spawns = 0
        skipped = 0

        for zdef in ZONES:
            zone, z_created = Zone.objects.update_or_create(
                key=zdef["key"],
                defaults={
                    "name": zdef["name"],
                    "description": zdef["description"],
                    "flavor_intro": zdef["flavor_intro"],
                    "flavor_walking": zdef["flavor_walking"],
                    "cost": zdef["cost"],
                    "encounters_per_run": zdef["encounters_per_run"],
                    "min_trainer_level": zdef["min_trainer_level"],
                    "order": zdef["order"],
                    "bg_gradient": zdef["bg_gradient"],
                    "is_active": True,
                },
            )
            if z_created:
                created_zones += 1
                self.stdout.write(f"  Created zone: {zone.name}")
            else:
                self.stdout.write(f"  Updated zone: {zone.name}")

            # Add species whose primary type matches this zone's types
            zone_types = zdef["types"]
            species_qs = Pokemon.objects.filter(
                primary_type__name__in=zone_types,
                pokedex_number__isnull=False,
            ).select_related("primary_type")

            featured = FEATURED_SPECIES.get(zdef["key"], [])

            for species in species_qs:
                weight = 20 if species.name in featured else 10
                _, spawn_created = ZoneSpawnEntry.objects.update_or_create(
                    zone=zone, species=species,
                    defaults={"weight": weight},
                )
                if spawn_created:
                    created_spawns += 1
                else:
                    skipped += 1

            spawn_count = zone.spawns.count()
            self.stdout.write(f"    -> {spawn_count} species in spawn table")

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. Zones: {created_zones} created. "
            f"Spawns: {created_spawns} new, {skipped} updated."
        ))
