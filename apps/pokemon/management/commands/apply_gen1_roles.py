"""
Management command: apply_gen1_roles

Applies role assignments from docs/gen1_role_design.md to all 151 Gen 1
Pokemon, then generates role-aware SpeciesMovePool entries for any species
not already covered by seed_move_pools.py's curated SPECIES_POOLS dict.

Roles are assigned by pokedex_number so they are PK-agnostic and safe to
re-run on any database.

Usage:
    python manage.py apply_gen1_roles
    python manage.py apply_gen1_roles --dry-run
    python manage.py apply_gen1_roles --roles-only    # only update primary_role
    python manage.py apply_gen1_roles --pools-only    # only generate move pools
    python manage.py apply_gen1_roles --clear         # wipe Gen 1 pool entries first
"""
from __future__ import annotations

import logging
from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Gen 1 role assignments  (source: docs/gen1_role_design.md)
# Key: pokedex_number   Value: TacticalRole slug
# ---------------------------------------------------------------------------
GEN1_ROLES: dict[int, str] = {
    1: "burst",    # Bulbasaur    — aggressive vine-whip striker
    2: "control",  # Ivysaur      — sleep powder / leech seed controller
    3: "tank",     # Venusaur     — bulky synthesis wall
    4: "burst",    # Charmander
    5: "combo",    # Charmeleon   — slash heat-stack combo chain
    6: "burst",    # Charizard
    7: "control",  # Squirtle     — bubble-slow setup into evolution
    8: "support",  # Wartortle    — rapid-spin cleanser
    9: "tank",     # Blastoise
    10: "control", # Caterpie
    11: "tank",    # Metapod      — harden cocoon endures
    12: "support", # Butterfree   — sleep powder + team heal
    13: "control", # Weedle
    14: "tank",    # Kakuna
    15: "burst",   # Beedrill     — twin-needle physical burst
    16: "control", # Pidgey
    17: "combo",   # Pidgeotto    — wing-attack multi-hit chain
    18: "burst",   # Pidgeot      — sky attack peak striker
    19: "control", # Rattata
    20: "burst",   # Raticate     — hyper fang / super fang burst
    21: "control", # Spearow
    22: "burst",   # Fearow       — drill peck aerial burst
    23: "control", # Ekans
    24: "control", # Arbok        — glare/coil lock
    25: "combo",   # Pikachu
    26: "burst",   # Raichu
    27: "control", # Sandshrew
    28: "burst",   # Sandslash    — slash fury / high crit
    29: "control", # Nidoran-F
    30: "support", # Nidorina
    31: "tank",    # Nidoqueen
    32: "control", # Nidoran-M
    33: "combo",   # Nidorino     — horn drill charge builder
    34: "burst",   # Nidoking     — earthquake burst finisher
    35: "control", # Clefairy     — metronome chaos / sing lock (graduates to support)
    36: "support", # Clefable     — moonblast + wish / the earned payoff
    37: "control", # Vulpix       — will-o-wisp + confuse ray setup
    38: "combo",   # Ninetales    — nasty plot → fire spin → flamethrower chain
    39: "control", # Jigglypuff   — sing sleep lock / disable
    40: "support", # Wigglytuff
    41: "control", # Zubat
    42: "tank",    # Golbat       — leech-life sustain drain tank
    43: "control", # Oddish
    44: "support", # Gloom        — aromatherapy cleanser + moonlight
    45: "control", # Vileplume    — stun spore + petal dance spin-lock
    46: "control", # Paras
    47: "support", # Parasect     — spore + synthesis
    48: "control", # Venonat
    49: "control", # Venomoth     — psybeam confuse + toxic stack
    50: "control", # Diglett
    51: "burst",   # Dugtrio      — earthquake fast burst / arena trap
    52: "control", # Meowth
    53: "combo",   # Persian      — slash crit chains / technician
    54: "control", # Psyduck
    55: "burst",   # Golduck      — hydro pump + psychic burst
    56: "burst",   # Mankey       — karate chop physical aggression
    57: "combo",   # Primeape     — rage-stack berserk combos
    58: "control", # Growlithe
    59: "burst",   # Arcanine     — extreme speed + fire blast
    60: "control", # Poliwag
    61: "combo",   # Poliwhirl    — belly drum → waterfall chain
    62: "tank",    # Poliwrath
    63: "control", # Abra
    64: "control", # Kadabra
    65: "combo",   # Alakazam     — future sight + psychic glass-cannon combo
    66: "burst",   # Machop
    67: "burst",   # Machoke
    68: "tank",    # Machamp
    69: "control", # Bellsprout
    70: "control", # Weepinbell
    71: "burst",   # Victreebel   — solar beam glass cannon
    72: "control", # Tentacool
    73: "tank",    # Tentacruel   — barrier + acid spray toxic tank
    74: "burst",   # Geodude      — rock throw burst / rollout escalate
    75: "burst",   # Graveler     — rock slide AOE / explosion threat
    76: "tank",    # Golem        — earthquake anchor
    77: "control", # Ponyta
    78: "burst",   # Rapidash     — fire spin + stomp burst
    79: "support", # Slowpoke     — amnesia buff + slow sustain
    80: "tank",    # Slowbro      — surf + amnesia psychic-water wall
    81: "control", # Magnemite    — thunder wave paralyze
    82: "burst",   # Magneton     — discharge burst / tri-attack status combo
    83: "combo",   # Farfetch'd   — swords dance → slash crit chain (leek combo)
    84: "control", # Doduo
    85: "combo",   # Dodrio       — tri attack three-head chain
    86: "control", # Seel
    87: "tank",    # Dewgong      — ice shard + rest sustain
    88: "control", # Grimer
    89: "tank",    # Muk          — minimize evasion + toxic sludge barrier
    90: "control", # Shellder
    91: "tank",    # Cloyster     — spike cannon + shell smash fortress
    92: "control", # Gastly       — lick paralyze / hypnosis setup
    93: "combo",   # Haunter      — shadow ball chains + mean look
    94: "combo",   # Gengar       — dream eater + hypnosis sleep-combo
    95: "tank",    # Onix         — iron tail + rock slide stone wall
    96: "control", # Drowzee
    97: "control", # Hypno        — dream eater off sleep / swagger confuse
    98: "control", # Krabby
    99: "burst",   # Kingler      — crabhammer high-power burst / crit machine
    100: "control",# Voltorb
    101: "burst",  # Electrode    — thunder + explosion burst gamble
    102: "control",# Exeggcute
    103: "burst",  # Exeggutor    — psychic + solar beam big-brained nuker
    104: "control",# Cubone       — bone club flinch / growl leer intimidation; grief-lore
    105: "burst",  # Marowak      — bone rush burst / thick club power; trauma resolved
    106: "burst",  # Hitmonlee    — high jump kick burst
    107: "combo",  # Hitmonchan   — mach punch → fire/ice/thunder punch element chain
    108: "support",# Lickitung
    109: "control",# Koffing      — smog blind / smokescreen debuff
    110: "tank",   # Weezing      — pain split + toxic gas barrier
    111: "burst",  # Rhyhorn      — stomp + horn attack aggressive
    112: "tank",   # Rhydon       — earthquake + hammer arm bulky bruiser
    113: "support",# Chansey      — softboiled heal + egg bomb pure support
    114: "control",# Tangela      — bind trap + absorb drain vine
    115: "tank",   # Kangaskhan   — double edge + fake out parental wall
    116: "control",# Horsea
    117: "combo",  # Seadra       — twister → dragon rage combo escalation
    118: "control",# Goldeen
    119: "burst",  # Seaking      — megahorn burst + waterfall striker
    120: "control",# Staryu
    121: "combo",  # Starmie      — rapid spin + psychic + surf rotation
    122: "support",# Mr. Mime     — barrier shield builder + heal support
    123: "burst",  # Scyther      — slash fury + wing attack fast physical
    124: "control",# Jynx         — lovely kiss sleep + blizzard freeze lock
    125: "burst",  # Electabuzz
    126: "burst",  # Magmar
    127: "burst",  # Pinsir
    128: "burst",  # Tauros       — body slam + giga impact rampaging striker
    129: "control",# Magikarp
    130: "burst",  # Gyarados     — waterfall + dragon rage rage-stack chase; power fantasy payoff
    131: "tank",   # Lapras
    132: "combo",  # Ditto        — transform mirrors enemy combo chain
    133: "combo",  # Eevee        — adaptability quick-attack chain
    134: "support",# Vaporeon
    135: "combo",  # Jolteon
    136: "burst",  # Flareon      — flare blitz physical burst (was wrongly tank)
    137: "combo",  # Porygon      — tri attack digital status cycle
    138: "control",# Omanyte
    139: "tank",   # Omastar      — shell smash + hydro pump fortress threat
    140: "control",# Kabuto
    141: "burst",  # Kabutops     — slash + aqua jet fossil blade striker
    142: "combo",  # Aerodactyl   — sky attack + ancient power chain
    143: "tank",   # Snorlax      — rest + body slam immovable wall
    144: "support",# Articuno     — mist + heal wind legendary healer (was tank)
    145: "burst",  # Zapdos
    146: "burst",  # Moltres
    147: "control",# Dratini
    148: "combo",  # Dragonair    — dragon dance → agility speed builder
    149: "burst",  # Dragonite    — outrage + hyper beam apex burst (was tank)
    150: "burst",  # Mewtwo
    151: "support",# Mew
}

# All Gen 1 species now use the role-aware auto-generator.
# The old hand-curated seed_move_pools.py pools had role mismatches (e.g. Flareon
# as tank, Articuno as tank) so we no longer protect them.
ALREADY_CURATED: frozenset[int] = frozenset()

# Status names that count as crowd-control (preferred by control role)
_CC_STATUSES: frozenset[str] = frozenset({
    "paralyzed", "asleep", "confused", "frozen", "bound",
    "flinched", "yawning", "taunted", "tormented",
})

# Status names that trigger burst combo chains
_BURST_STATUSES: frozenset[str] = frozenset({
    "burned", "poisoned", "badly_poisoned", "flinched", "seeded",
})


# ---------------------------------------------------------------------------
# Move scoring
# ---------------------------------------------------------------------------

def _score_move(move: Any, role: str, slot: str) -> int:
    """Higher score = better fit for this role/slot combination."""
    score = 0
    # Deprioritize Z-move / variant duplicates (names ending with " 2", " 3", etc.)
    import re
    if re.search(r" \d+$", move.name):
        score -= 20
    status: str | None = (
        move.applies_status.name if move.applies_status_id else None
    )

    if role == "burst":
        if slot == "standard" and status in _BURST_STATUSES:
            score += 10  # standard that sets up chase
        if slot in ("mystery", "chase") and move.power >= 100:
            score += 12
        elif slot in ("mystery", "chase") and move.power >= 75:
            score += 6
        score += move.power // 10

    elif role == "control":
        if status in _CC_STATUSES:
            score += 12
        if slot == "standard" and status in _CC_STATUSES:
            score += 8   # primary CC applier
        if slot == "chase" and status in _CC_STATUSES:
            score += 5   # CC extender
        score += move.power // 20  # power matters less for control

    elif role == "tank":
        if move.support_flag:
            score += 15
        if slot == "passive_1" and move.power == 0:
            score += 8
        if slot in ("standard", "mystery") and move.power >= 60:
            score += 5
        if status and status not in _CC_STATUSES:
            score += 3   # non-CC status procs (drain, shield)
        score += move.power // 20

    elif role == "support":
        if move.support_flag:
            score += 20
        if slot == "passive_1" and move.power == 0:
            score += 8
        if status and status not in _CC_STATUSES and status not in _BURST_STATUSES:
            score += 8   # buff/cleanse statuses
        score -= move.power // 15  # support prefers lower power

    elif role == "combo":
        if move.always_first or move.priority > 0:
            score += 8
        if move.combo_starter:
            score += 10
        if move.combo_trigger:
            score += 10
        if move.combo_role:
            score += 5
        score += move.power // 12

    return score


def _pick_moves(
    slot: str,
    role: str,
    primary_type_id: int,
    secondary_type_id: int | None,
    normal_type_id: int,
    moves_by_slot: dict[str, list[Any]],
    count: int = 2,
    exclude_pks: set[int] | None = None,
) -> list[int]:
    """
    Select up to `count` move PKs for the given slot + role.

    Type priority: primary → secondary → Normal type → any remaining.
    Within each tier, moves are ranked by _score_move().
    """
    exclude = exclude_pks or set()
    candidates = [m for m in moves_by_slot.get(slot, []) if m.pk not in exclude]

    def _top(pool: list[Any], n: int) -> list[int]:
        ranked = sorted(pool, key=lambda m: _score_move(m, role, slot), reverse=True)
        chosen = ranked[:n]
        return [m.pk for m in chosen]

    # Tier 1 — primary type
    primary = [m for m in candidates if m.move_type_id == primary_type_id]
    result = _top(primary, count)
    if len(result) >= count:
        return result[:count]

    # Tier 2 — secondary type
    if secondary_type_id:
        secondary = [
            m for m in candidates
            if m.move_type_id == secondary_type_id and m.pk not in result
        ]
        extra = _top(secondary, count - len(result))
        result.extend(extra)
    if len(result) >= count:
        return result[:count]

    # Tier 3 — Normal type fallback
    normal = [
        m for m in candidates
        if m.move_type_id == normal_type_id and m.pk not in result
    ]
    extra = _top(normal, count - len(result))
    result.extend(extra)
    if len(result) >= count:
        return result[:count]

    # Tier 4 — anything remaining
    remaining = [m for m in candidates if m.pk not in result]
    extra = _top(remaining, count - len(result))
    result.extend(extra)
    return result[:count]


# ---------------------------------------------------------------------------
# Management command
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = (
        "Apply Gen 1 role assignments from the design doc and generate "
        "role-aware SpeciesMovePool entries for uncurated Gen 1 species."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Show what would be done without writing to the database.",
        )
        parser.add_argument(
            "--roles-only",
            action="store_true",
            default=False,
            help="Only update Pokemon.primary_role; skip move pool generation.",
        )
        parser.add_argument(
            "--pools-only",
            action="store_true",
            default=False,
            help="Only generate move pools; skip role update.",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            default=False,
            help=(
                "Delete existing SpeciesMovePool entries for Gen 1 species "
                "(excluding already-curated ones) before seeding."
            ),
        )

    def handle(self, *args: Any, **options: Any) -> None:
        from apps.pokemon.models import Move, MoveSlotType, Pokemon, SpeciesMovePool

        dry_run: bool = options["dry_run"]
        roles_only: bool = options["roles_only"]
        pools_only: bool = options["pools_only"]
        clear: bool = options["clear"]

        self.stdout.write(self.style.MIGRATE_HEADING("=== apply_gen1_roles ==="))
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no changes will be written."))

        with transaction.atomic():
            gen1_qs = Pokemon.objects.filter(
                pokedex_number__gte=1,
                pokedex_number__lte=151,
            ).select_related("primary_type", "secondary_type")
            gen1_species = list(gen1_qs)

            if not gen1_species:
                self.stdout.write(
                    self.style.ERROR("No Gen 1 species found. Run seed_pokeapi first.")
                )
                return

            # --------------------------------------------------------------
            # Step 1 — Update primary_role
            # --------------------------------------------------------------
            if not pools_only:
                self.stdout.write(
                    self.style.MIGRATE_LABEL("Step 1: Updating primary_role …")
                )
                to_update: list[Pokemon] = []
                for species in gen1_species:
                    dex = species.pokedex_number
                    new_role = GEN1_ROLES.get(dex)
                    if new_role and species.primary_role != new_role:
                        species.primary_role = new_role
                        to_update.append(species)

                if not dry_run:
                    Pokemon.objects.bulk_update(to_update, ["primary_role"])
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  Updated primary_role on {len(to_update)} species."
                        )
                    )
                else:
                    self.stdout.write(
                        f"  [dry-run] Would update primary_role on {len(to_update)} species."
                    )

            # --------------------------------------------------------------
            # Step 2 — Generate SpeciesMovePool entries
            # --------------------------------------------------------------
            if roles_only:
                if dry_run:
                    transaction.set_rollback(True)
                return

            self.stdout.write(
                self.style.MIGRATE_LABEL("Step 2: Generating move pools …")
            )

            # Identify which Gen 1 species to build pools for
            uncurated = [
                s for s in gen1_species
                if s.pokedex_number not in ALREADY_CURATED
            ]

            # Optionally clear existing entries for uncurated species
            if clear and not dry_run:
                uncurated_pks = [s.pk for s in uncurated]
                deleted, _ = SpeciesMovePool.objects.filter(
                    species_id__in=uncurated_pks
                ).delete()
                self.stdout.write(f"  Cleared {deleted} existing entries for uncurated species.")
            elif clear and dry_run:
                uncurated_pks = [s.pk for s in uncurated]
                count_to_del = SpeciesMovePool.objects.filter(
                    species_id__in=uncurated_pks
                ).count()
                self.stdout.write(
                    f"  [dry-run] Would clear {count_to_del} existing entries."
                )

            # Load all moves grouped by slot_type for fast lookup
            all_moves = list(
                Move.objects.select_related(
                    "move_type", "applies_status"
                ).all()
            )
            moves_by_slot: dict[str, list[Any]] = {}
            for move in all_moves:
                moves_by_slot.setdefault(move.slot_type, []).append(move)

            # Normal type ID for fallback
            normal_type_id: int = next(
                m.move_type_id
                for m in all_moves
                if m.move_type.name == "Normal"
            )

            # Existing (species_pk, move_pk) pairs to avoid duplicates
            existing_pairs: set[tuple[int, int]] = set(
                SpeciesMovePool.objects.filter(
                    species_id__in=[s.pk for s in uncurated]
                ).values_list("species_id", "move_id")
            ) if not clear else set()

            entries_to_create: list[SpeciesMovePool] = []
            created_count = 0
            skipped_count = 0

            # Synergy move name -> Move pk lookup (passive_1 by type)
            TYPE_SYNERGY_MOVE: dict[str, str] = {
                "Fire": "Burning Will", "Water": "Tidal Flow", "Grass": "Root Network",
                "Electric": "Discharge Field", "Psychic": "Psi Resonance", "Ice": "Permafrost Pact",
                "Fighting": "Iron Fist Accord", "Poison": "Toxic Network", "Ground": "Tectonic Bond",
                "Rock": "Stone Wall Pact", "Ghost": "Spirit Link", "Dragon": "Dragon's Pride",
                "Dark": "Shadow Pact", "Bug": "Swarm Mind", "Normal": "Versatile Core",
                "Flying": "Wind Riders", "Steel": "Fortified Line", "Fairy": "Enchanted Circle",
            }
            ROLE_ITEM_PASSIVE: dict[str, str] = {
                "burst":   "Life Orb",
                "combo":   "Scope Lens",
                "tank":    "Rocky Helmet",
                "support": "Shell Bell",
                "control": "Susanoo Shard",
            }

            # Pre-build name -> pk maps for synergy and passive_2 moves
            synergy_pk_by_name: dict[str, int] = {
                m.name: m.pk
                for m in Move.objects.filter(
                    slot_type="passive_1",
                    name__in=list(TYPE_SYNERGY_MOVE.values()),
                )
            }
            passive2_pk_by_name: dict[str, int] = {
                m.name: m.pk
                for m in Move.objects.filter(
                    slot_type="passive_2",
                    name__in=list(ROLE_ITEM_PASSIVE.values()),
                )
            }

            slots_config: list[tuple[str, int]] = [
                ("standard", 2),
                ("chase", 2),
                ("mystery", 2),
            ]

            for species in uncurated:
                dex = species.pokedex_number
                role = GEN1_ROLES.get(dex, species.primary_role)
                primary_type_id = species.primary_type_id
                secondary_type_id = (
                    species.secondary_type_id if species.secondary_type else None
                )

                used_pks: set[int] = set()

                for slot, count in slots_config:
                    chosen_pks = _pick_moves(
                        slot=slot,
                        role=role,
                        primary_type_id=primary_type_id,
                        secondary_type_id=secondary_type_id,
                        normal_type_id=normal_type_id,
                        moves_by_slot=moves_by_slot,
                        count=count,
                        exclude_pks=used_pks,
                    )

                    for move_pk in chosen_pks:
                        if (species.pk, move_pk) in existing_pairs:
                            skipped_count += 1
                            continue
                        entries_to_create.append(
                            SpeciesMovePool(
                                species_id=species.pk,
                                move_id=move_pk,
                                slot_type=slot,
                                role_tag=role,
                            )
                        )
                        existing_pairs.add((species.pk, move_pk))
                        used_pks.add(move_pk)
                        created_count += 1

                # Step 3a — passive_1 synergy move (type-matched)
                primary_type_name = (
                    species.primary_type.name if species.primary_type else ""
                )
                synergy_move_name = TYPE_SYNERGY_MOVE.get(primary_type_name)
                if synergy_move_name:
                    synergy_pk = synergy_pk_by_name.get(synergy_move_name)
                    if synergy_pk and (species.pk, synergy_pk) not in existing_pairs:
                        entries_to_create.append(
                            SpeciesMovePool(
                                species_id=species.pk,
                                move_id=synergy_pk,
                                slot_type="passive_1",
                                role_tag=role,
                            )
                        )
                        existing_pairs.add((species.pk, synergy_pk))
                        used_pks.add(synergy_pk)
                        created_count += 1

                # Step 3b — passive_2 display move (role-matched item)
                item_move_name = ROLE_ITEM_PASSIVE.get(role)
                if item_move_name:
                    item_pk = passive2_pk_by_name.get(item_move_name)
                    if item_pk and (species.pk, item_pk) not in existing_pairs:
                        entries_to_create.append(
                            SpeciesMovePool(
                                species_id=species.pk,
                                move_id=item_pk,
                                slot_type="passive_2",
                                role_tag=role,
                            )
                        )
                        existing_pairs.add((species.pk, item_pk))
                        used_pks.add(item_pk)
                        created_count += 1

            if not dry_run:
                SpeciesMovePool.objects.bulk_create(entries_to_create, batch_size=500)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  Created {created_count} new SpeciesMovePool entries "
                        f"({skipped_count} already existed)."
                    )
                )
            else:
                self.stdout.write(
                    f"  [dry-run] Would create {created_count} new SpeciesMovePool entries "
                    f"({skipped_count} already exist)."
                )

            if dry_run:
                transaction.set_rollback(True)

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run complete — database unchanged."))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "apply_gen1_roles complete. "
                    "Run 'python manage.py apply_gen1_roles --dry-run' to preview changes."
                )
            )
