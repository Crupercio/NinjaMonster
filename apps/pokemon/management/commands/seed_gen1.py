"""
Management command: seed all 151 Gen 1 Pokemon.

Usage:
    python manage.py seed_gen1

Safe to re-run — uses get_or_create so existing Pokemon are never duplicated.
Only newly created Pokemon get moves assigned. Existing ones keep their moves.
"""
import logging
from typing import Optional

from django.core.management.base import BaseCommand

from apps.pokemon.models import Move, Pokemon, PokemonType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Type → default move PKs
# Each type maps to up to 3 move PKs from the existing moves fixture.
# These are the same move PKs already used by the handpicked 30.
# ---------------------------------------------------------------------------
TYPE_MOVES: dict[str, list[int]] = {
    "Normal":   [1, 2, 3],      # Tackle, Scratch, Quick Attack
    "Fire":     [6, 4, 41],     # Ember, Flamethrower, Ignition Blast
    "Water":    [9, 10, 11],    # Surf, Waterfall, Hydro Pump
    "Electric": [13, 14, 16],   # Thunderbolt, Thunder Wave, Discharge
    "Grass":    [18, 20, 21],   # Razor Leaf, Leech Seed, Giga Drain
    "Ice":      [23, 26, 27],   # Ice Beam, Freeze-Dry, Aurora Beam
    "Fighting": [1, 42, 53],    # Tackle, Seal Strike, Shatter Strike
    "Poison":   [28, 29, 30],   # Sludge Bomb, Toxic, Poison Jab
    "Ground":   [1, 44, 2],     # Tackle, Sand Veil, Scratch
    "Flying":   [1, 3, 38],     # Tackle, Quick Attack, Hurricane
    "Psychic":  [36, 43, 48],   # Dream Eater, Chaos Orb, Feeblemind
    "Bug":      [1, 2, 45],     # Tackle, Scratch, Needle Jab
    "Rock":     [1, 2, 3],      # Tackle, Scratch, Quick Attack (no Rock moves yet)
    "Ghost":    [32, 33, 35],   # Shadow Ball, Curse, Night Shade
    "Dragon":   [38, 23, 3],    # Hurricane, Ice Beam, Quick Attack (no Dragon moves yet)
    "Dark":     [39, 40, 47],   # Taunt, Torment, Mark of Shame
    "Steel":    [1, 2, 3],      # Tackle, Scratch, Quick Attack (no Steel moves yet)
    "Fairy":    [1, 3, 2],      # Tackle, Quick Attack, Scratch (no Fairy moves yet)
}

# ---------------------------------------------------------------------------
# All 151 Gen 1 Pokemon
# Format: (name, dex_number, primary_type, secondary_type_or_None,
#           hp, atk, def, sp_atk, sp_def, spd)
# ---------------------------------------------------------------------------
GEN1_POKEMON: list[tuple] = [
    # --- Starters ---
    ("Bulbasaur",   1,   "Grass",    "Poison",   45,  49,  49, 65,  65,  45),
    ("Ivysaur",     2,   "Grass",    "Poison",   60,  62,  63, 80,  80,  60),
    ("Venusaur",    3,   "Grass",    "Poison",   80,  82,  83, 100, 100, 80),
    ("Charmander",  4,   "Fire",     None,       39,  52,  43, 60,  50,  65),
    ("Charmeleon",  5,   "Fire",     None,       58,  64,  58, 80,  65,  80),
    ("Charizard",   6,   "Fire",     "Flying",   78,  84,  78, 109, 85,  100),
    ("Squirtle",    7,   "Water",    None,       44,  48,  65, 50,  64,  43),
    ("Wartortle",   8,   "Water",    None,       59,  63,  80, 65,  80,  58),
    ("Blastoise",   9,   "Water",    None,       79,  83, 100, 85,  105, 78),
    # --- Bug line ---
    ("Caterpie",    10,  "Bug",      None,       45,  30,  35, 20,  20,  45),
    ("Metapod",     11,  "Bug",      None,       50,  20,  55, 25,  25,  30),
    ("Butterfree",  12,  "Bug",      "Flying",   60,  45,  50, 90,  80,  70),
    ("Weedle",      13,  "Bug",      "Poison",   40,  35,  30, 20,  20,  50),
    ("Kakuna",      14,  "Bug",      "Poison",   45,  25,  50, 25,  25,  35),
    ("Beedrill",    15,  "Bug",      "Poison",   65,  90,  40, 45,  80,  75),
    # --- Birds ---
    ("Pidgey",      16,  "Normal",   "Flying",   40,  45,  40, 35,  35,  56),
    ("Pidgeotto",   17,  "Normal",   "Flying",   63,  60,  55, 50,  50,  71),
    ("Pidgeot",     18,  "Normal",   "Flying",   83,  80,  75, 70,  70,  101),
    # --- Rats ---
    ("Rattata",     19,  "Normal",   None,       30,  56,  35, 25,  35,  72),
    ("Raticate",    20,  "Normal",   None,       55,  81,  60, 50,  70,  97),
    # --- Spearow line ---
    ("Spearow",     21,  "Normal",   "Flying",   40,  60,  30, 31,  31,  70),
    ("Fearow",      22,  "Normal",   "Flying",   65,  90,  65, 61,  61,  100),
    # --- Snake line ---
    ("Ekans",       23,  "Poison",   None,       35,  60,  44, 40,  54,  55),
    ("Arbok",       24,  "Poison",   None,       60,  85,  69, 65,  79,  80),
    # --- Pikachu line ---
    ("Pikachu",     25,  "Electric", None,       35,  55,  40, 50,  50,  90),
    ("Raichu",      26,  "Electric", None,       60,  90,  55, 90,  80,  110),
    # --- Sandshrew line ---
    ("Sandshrew",   27,  "Ground",   None,       50,  75,  85, 20,  30,  40),
    ("Sandslash",   28,  "Ground",   None,       75, 100, 110, 45,  55,  65),
    # --- Nidoran lines ---
    ("Nidoran-F",   29,  "Poison",   None,       55,  47,  52, 40,  40,  41),
    ("Nidorina",    30,  "Poison",   None,       70,  62,  67, 55,  55,  56),
    ("Nidoqueen",   31,  "Poison",   "Ground",   90,  92,  87, 75,  85,  76),
    ("Nidoran-M",   32,  "Poison",   None,       46,  57,  40, 40,  40,  50),
    ("Nidorino",    33,  "Poison",   None,       61,  72,  57, 55,  55,  65),
    ("Nidoking",    34,  "Poison",   "Ground",   81, 102,  77, 85,  75,  85),
    # --- Clefairy line ---
    ("Clefairy",    35,  "Normal",   "Fairy",    70,  45,  48, 60,  65,  35),
    ("Clefable",    36,  "Normal",   "Fairy",    95,  70,  73, 95,  90,  60),
    # --- Vulpix line ---
    ("Vulpix",      37,  "Fire",     None,       38,  41,  40, 50,  65,  65),
    ("Ninetales",   38,  "Fire",     None,       73,  76,  75, 81,  100, 100),
    # --- Jigglypuff line ---
    ("Jigglypuff",  39,  "Normal",   "Fairy",   115,  45,  20, 45,  25,  20),
    ("Wigglytuff",  40,  "Normal",   "Fairy",   140,  70,  45, 85,  50,  45),
    # --- Zubat line ---
    ("Zubat",       41,  "Poison",   "Flying",   40,  45,  35, 30,  40,  55),
    ("Golbat",      42,  "Poison",   "Flying",   75,  80,  70, 65,  75,  90),
    # --- Oddish line ---
    ("Oddish",      43,  "Grass",    "Poison",   45,  50,  55, 75,  65,  30),
    ("Gloom",       44,  "Grass",    "Poison",   60,  65,  70, 85,  75,  40),
    ("Vileplume",   45,  "Grass",    "Poison",   75,  80,  85, 110, 90,  50),
    # --- Paras line ---
    ("Paras",       46,  "Bug",      "Grass",    35,  70,  55, 45,  55,  25),
    ("Parasect",    47,  "Bug",      "Grass",    60,  95,  80, 60,  80,  30),
    # --- Venonat line ---
    ("Venonat",     48,  "Bug",      "Poison",   60,  55,  50, 40,  55,  45),
    ("Venomoth",    49,  "Bug",      "Poison",   70,  65,  60, 90,  75,  90),
    # --- Diglett line ---
    ("Diglett",     50,  "Ground",   None,       10,  55,  25, 35,  45,  95),
    ("Dugtrio",     51,  "Ground",   None,       35, 100,  50, 50,  70,  120),
    # --- Meowth line ---
    ("Meowth",      52,  "Normal",   None,       40,  45,  35, 40,  40,  90),
    ("Persian",     53,  "Normal",   None,       65,  70,  60, 65,  65,  115),
    # --- Psyduck line ---
    ("Psyduck",     54,  "Water",    None,       50,  52,  48, 65,  50,  55),
    ("Golduck",     55,  "Water",    None,       80,  82,  78, 95,  80,  85),
    # --- Mankey line ---
    ("Mankey",      56,  "Fighting", None,       40,  80,  35, 35,  45,  70),
    ("Primeape",    57,  "Fighting", None,       65, 105,  60, 60,  70,  95),
    # --- Growlithe line ---
    ("Growlithe",   58,  "Fire",     None,       55,  70,  45, 70,  50,  60),
    ("Arcanine",    59,  "Fire",     None,       90, 110,  80, 100, 80,  95),
    # --- Poliwag line ---
    ("Poliwag",     60,  "Water",    None,       40,  50,  40, 40,  40,  90),
    ("Poliwhirl",   61,  "Water",    None,       65,  65,  65, 50,  50,  90),
    ("Poliwrath",   62,  "Water",    "Fighting", 90,  95,  95, 70,  90,  70),
    # --- Abra line ---
    ("Abra",        63,  "Psychic",  None,       25,  20,  15, 105, 55,  90),
    ("Kadabra",     64,  "Psychic",  None,       40,  35,  30, 120, 70,  105),
    ("Alakazam",    65,  "Psychic",  None,       55,  50,  45, 135, 95,  120),
    # --- Machop line ---
    ("Machop",      66,  "Fighting", None,       70,  80,  50, 35,  35,  35),
    ("Machoke",     67,  "Fighting", None,       80, 100,  70, 50,  60,  45),
    ("Machamp",     68,  "Fighting", None,       90, 130,  80, 65,  85,  55),
    # --- Bellsprout line ---
    ("Bellsprout",  69,  "Grass",    "Poison",   50,  75,  35, 70,  30,  40),
    ("Weepinbell",  70,  "Grass",    "Poison",   65,  90,  50, 85,  45,  55),
    ("Victreebel",  71,  "Grass",    "Poison",   80, 105,  65, 100, 60,  70),
    # --- Tentacool line ---
    ("Tentacool",   72,  "Water",    "Poison",   40,  40,  35, 50,  100, 70),
    ("Tentacruel",  73,  "Water",    "Poison",   80,  70,  65, 80,  120, 100),
    # --- Geodude line ---
    ("Geodude",     74,  "Rock",     "Ground",   40,  80, 100, 30,  30,  20),
    ("Graveler",    75,  "Rock",     "Ground",   55,  95, 115, 45,  45,  35),
    ("Golem",       76,  "Rock",     "Ground",   80, 120, 130, 55,  65,  45),
    # --- Ponyta line ---
    ("Ponyta",      77,  "Fire",     None,       50,  85,  55, 65,  65,  90),
    ("Rapidash",    78,  "Fire",     None,       65, 100,  70, 80,  80,  105),
    # --- Slowpoke line ---
    ("Slowpoke",    79,  "Water",    "Psychic",  90,  65,  65, 40,  40,  15),
    ("Slowbro",     80,  "Water",    "Psychic",  95,  75, 110, 100, 80,  30),
    # --- Magnemite line ---
    ("Magnemite",   81,  "Electric", "Steel",    25,  35,  70, 95,  55,  45),
    ("Magneton",    82,  "Electric", "Steel",    50,  60,  95, 120, 70,  70),
    # --- Farfetch'd ---
    ("Farfetch'd",  83,  "Normal",   "Flying",   52,  90,  55, 58,  62,  60),
    # --- Doduo line ---
    ("Doduo",       84,  "Normal",   "Flying",   35,  85,  45, 35,  35,  75),
    ("Dodrio",      85,  "Normal",   "Flying",   60, 110,  70, 60,  60,  100),
    # --- Seel line ---
    ("Seel",        86,  "Water",    None,       65,  45,  55, 45,  70,  45),
    ("Dewgong",     87,  "Water",    "Ice",      90,  70,  80, 70,  95,  70),
    # --- Grimer line ---
    ("Grimer",      88,  "Poison",   None,       80,  80,  50, 40,  50,  25),
    ("Muk",         89,  "Poison",   None,      105, 105,  75, 65,  100, 50),
    # --- Shellder line ---
    ("Shellder",    90,  "Water",    None,       30,  65, 100, 45,  25,  40),
    ("Cloyster",    91,  "Water",    "Ice",      50,  95, 180, 85,  45,  70),
    # --- Gastly line ---
    ("Gastly",      92,  "Ghost",    "Poison",   30,  35,  30, 100, 35,  80),
    ("Haunter",     93,  "Ghost",    "Poison",   45,  50,  45, 115, 55,  95),
    ("Gengar",      94,  "Ghost",    "Poison",   60,  65,  60, 130, 75,  110),
    # --- Onix ---
    ("Onix",        95,  "Rock",     "Ground",   35,  45, 160, 30,  45,  70),
    # --- Drowzee line ---
    ("Drowzee",     96,  "Psychic",  None,       60,  48,  45, 43,  90,  42),
    ("Hypno",       97,  "Psychic",  None,       85,  73,  70, 73,  115, 67),
    # --- Krabby line ---
    ("Krabby",      98,  "Water",    None,       30, 105,  90, 25,  25,  50),
    ("Kingler",     99,  "Water",    None,       55, 130, 115, 50,  50,  75),
    # --- Voltorb line ---
    ("Voltorb",    100,  "Electric", None,       40,  30,  50, 55,  55,  100),
    ("Electrode",  101,  "Electric", None,       60,  50,  70, 80,  80,  150),
    # --- Exeggcute line ---
    ("Exeggcute",  102,  "Grass",    "Psychic",  60,  40,  80, 60,  45,  40),
    ("Exeggutor",  103,  "Grass",    "Psychic",  95,  95,  85, 125, 65,  55),
    # --- Cubone line ---
    ("Cubone",     104,  "Ground",   None,       50,  50,  95, 40,  50,  35),
    ("Marowak",    105,  "Ground",   None,       60,  80, 110, 50,  80,  45),
    # --- Hitmon line ---
    ("Hitmonlee",  106,  "Fighting", None,       50, 120,  53, 35,  110, 87),
    ("Hitmonchan", 107,  "Fighting", None,       50, 105,  79, 35,  110, 76),
    # --- Lickitung ---
    ("Lickitung",  108,  "Normal",   None,       90,  55,  75, 60,  75,  30),
    # --- Koffing line ---
    ("Koffing",    109,  "Poison",   None,       40,  65,  95, 60,  45,  35),
    ("Weezing",    110,  "Poison",   None,       65,  90, 120, 85,  70,  60),
    # --- Rhyhorn line ---
    ("Rhyhorn",    111,  "Ground",   "Rock",     80,  85,  95, 30,  30,  25),
    ("Rhydon",     112,  "Ground",   "Rock",    105, 130, 120, 45,  45,  40),
    # --- Chansey ---
    ("Chansey",    113,  "Normal",   None,      250,   5,   5, 35,  105, 50),
    # --- Tangela ---
    ("Tangela",    114,  "Grass",    None,       65,  55, 115, 100, 40,  60),
    # --- Kangaskhan ---
    ("Kangaskhan", 115,  "Normal",   None,      105,  95,  80, 40,  80,  90),
    # --- Horsea line ---
    ("Horsea",     116,  "Water",    None,       30,  40,  70, 70,  25,  60),
    ("Seadra",     117,  "Water",    None,       55,  65,  95, 95,  45,  85),
    # --- Goldeen line ---
    ("Goldeen",    118,  "Water",    None,       45,  67,  60, 35,  50,  63),
    ("Seaking",    119,  "Water",    None,       80,  92,  65, 65,  80,  68),
    # --- Staryu line ---
    ("Staryu",     120,  "Water",    None,       30,  45,  55, 70,  55,  85),
    ("Starmie",    121,  "Water",    "Psychic",  60,  75,  85, 100, 85,  115),
    # --- Mr. Mime ---
    ("Mr. Mime",   122,  "Psychic",  "Fairy",    40,  45,  65, 100, 120, 90),
    # --- Scyther ---
    ("Scyther",    123,  "Bug",      "Flying",   70, 110,  80, 55,  80,  105),
    # --- Jynx ---
    ("Jynx",       124,  "Ice",      "Psychic",  65,  50,  35, 115, 95,  95),
    # --- Electabuzz ---
    ("Electabuzz", 125,  "Electric", None,       65,  83,  57, 95,  85,  105),
    # --- Magmar ---
    ("Magmar",     126,  "Fire",     None,       65,  95,  57, 100, 85,  93),
    # --- Pinsir ---
    ("Pinsir",     127,  "Bug",      None,       65, 125, 100, 55,  70,  85),
    # --- Tauros ---
    ("Tauros",     128,  "Normal",   None,       75, 100,  95, 40,  70,  110),
    # --- Magikarp line ---
    ("Magikarp",   129,  "Water",    None,       20,  10,  55, 15,  20,  80),
    ("Gyarados",   130,  "Water",    "Flying",   95, 125,  79, 60,  100, 81),
    # --- Lapras ---
    ("Lapras",     131,  "Water",    "Ice",     130,  85,  80, 85,  95,  60),
    # --- Ditto ---
    ("Ditto",      132,  "Normal",   None,       48,  48,  48, 48,  48,  48),
    # --- Eevee and Eeveelutions ---
    ("Eevee",      133,  "Normal",   None,       55,  55,  50, 45,  65,  55),
    ("Vaporeon",   134,  "Water",    None,      130,  65,  60, 110, 95,  65),
    ("Jolteon",    135,  "Electric", None,       65,  65,  60, 110, 95,  130),
    ("Flareon",    136,  "Fire",     None,       65, 130,  60, 95,  110, 65),
    # --- Porygon ---
    ("Porygon",    137,  "Normal",   None,       65,  60,  70, 85,  75,  40),
    # --- Fossil Pokemon ---
    ("Omanyte",    138,  "Rock",     "Water",    35,  40, 100, 90,  55,  35),
    ("Omastar",    139,  "Rock",     "Water",    70,  60, 125, 115, 70,  55),
    ("Kabuto",     140,  "Rock",     "Water",    30,  80,  90, 55,  45,  55),
    ("Kabutops",   141,  "Rock",     "Water",    60, 115, 105, 65,  70,  80),
    ("Aerodactyl", 142,  "Rock",     "Flying",   80, 105,  65, 60,  75,  130),
    # --- Snorlax ---
    ("Snorlax",    143,  "Normal",   None,      160, 110,  65, 65,  110, 30),
    # --- Legendary birds ---
    ("Articuno",   144,  "Ice",      "Flying",   90,  85, 100, 95,  125, 85),
    ("Zapdos",     145,  "Electric", "Flying",   90,  90,  85, 125, 90,  100),
    ("Moltres",    146,  "Fire",     "Flying",   90, 100,  90, 125, 85,  90),
    # --- Dratini line ---
    ("Dratini",    147,  "Dragon",   None,       41,  64,  45, 50,  50,  50),
    ("Dragonair",  148,  "Dragon",   None,       61,  84,  65, 70,  70,  70),
    ("Dragonite",  149,  "Dragon",   "Flying",   91, 134,  95, 100, 100, 80),
    # --- Psychic legends ---
    ("Mewtwo",     150,  "Psychic",  None,      106, 110,  90, 154, 90,  130),
    ("Mew",        151,  "Psychic",  None,      100, 100, 100, 100, 100, 100),
]


def _pick_moves(primary: str, secondary: Optional[str]) -> list[int]:
    """
    Return up to 4 move PKs for a newly created Pokemon.

    Strategy: 3 from primary type, then 1 from secondary type (if different).
    Falls back to Normal moves if a type has no entry in TYPE_MOVES.
    """
    fallback = TYPE_MOVES["Normal"]
    primary_moves = TYPE_MOVES.get(primary, fallback)[:3]

    extra: list[int] = []
    if secondary and secondary != primary:
        secondary_pool = TYPE_MOVES.get(secondary, fallback)
        for pk in secondary_pool:
            if pk not in primary_moves:
                extra = [pk]
                break

    return primary_moves + extra


class Command(BaseCommand):
    help = "Seed all 151 Gen 1 Pokemon. Safe to re-run."

    def handle(self, *args: object, **options: object) -> None:
        # Load all types into a dict keyed by name for fast lookup.
        types: dict[str, PokemonType] = {
            t.name: t for t in PokemonType.objects.all()
        }

        # Pre-fetch all Move objects we might assign.
        all_move_pks: set[int] = {
            pk for pks in TYPE_MOVES.values() for pk in pks
        }
        moves: dict[int, Move] = {
            m.pk: m for m in Move.objects.filter(pk__in=all_move_pks)
        }

        created_count = 0
        skipped_count = 0

        for entry in GEN1_POKEMON:
            (
                name, dex_num, primary_name, secondary_name,
                hp, atk, def_, sp_atk, sp_def, spd,
            ) = entry

            primary_type = types.get(primary_name)
            if primary_type is None:
                self.stderr.write(f"  SKIP {name}: type '{primary_name}' not in DB")
                continue

            secondary_type = types.get(secondary_name) if secondary_name else None

            pokemon, created = Pokemon.objects.get_or_create(
                name=name,
                defaults={
                    "pokedex_number": dex_num,
                    "primary_type": primary_type,
                    "secondary_type": secondary_type,
                    "base_hp": hp,
                    "base_attack": atk,
                    "base_defense": def_,
                    "base_sp_attack": sp_atk,
                    "base_sp_defense": sp_def,
                    "base_speed": spd,
                },
            )

            if created:
                move_pks = _pick_moves(primary_name, secondary_name)
                pokemon.moves.set(
                    [moves[pk] for pk in move_pks if pk in moves]
                )
                self.stdout.write(f"  + {dex_num:>3}. {name}")
                created_count += 1
            else:
                skipped_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone: {created_count} created, {skipped_count} already existed."
            )
        )
