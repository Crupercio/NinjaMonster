"""
TutorialService — orchestrates the first-time trainer experience.

Flow:
  1. New user logs in → dashboard redirects to /battle/tutorial/.
  2. TutorialStarterSelectView shows three starter choices.
  3. User picks a starter → assign_starter_team() creates 6 OwnedPokemon and
     updates the user's persistent Team.
  4. create_tutorial_battle() creates an EASY AI battle, sets both teams, and
     starts the battle.  Returns the Battle ready for play.
  5. After winning, TutorialCompleteView marks tutorial_complete = True.
"""
import logging
from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.db import transaction

from apps.pokemon.models import Move, MoveSlotType, OwnedPokemon, Pokemon, Team, TeamSlot

if TYPE_CHECKING:
    from apps.game.models import Battle

User = get_user_model()
logger = logging.getLogger(__name__)

STARTER_NAMES: tuple[str, ...] = ("Charmander", "Squirtle", "Bulbasaur")

# ---------------------------------------------------------------------------
# Predetermined starter teams (Option A — hand-curated)
#
# Each entry maps a starter name to an ordered list of 6 species definitions.
# Position 1 is always the starter itself.
#
# Each slot dict:
#   species  — Pokemon.name (exact, case-sensitive)
#   standard — move name for move_standard  (slot_type="standard")
#   chase    — move name for move_chase     (slot_type="chase")
#   mystery  — move name for move_special   (slot_type="mystery")
#   support  — move name for move_support   (slot_type="passive_1")
#
# Team 1 — CHARMANDER: "The Inferno Chain"
#   Philosophy: Avalanche burst.  Ember applies BURNED, entire team piles on.
#   Chain: burned→(Arcanine Fire Punch→ignited)→(Ninetales Fire Punch→ignited)
#          burned→(Pikachu Thunder Punch→paralyzed)
#
# Team 2 — SQUIRTLE: "The Iron Tide"
#   Philosophy: Slow suffocation.  Whirlpool applies WEAKENED, three chasers
#   branch into FROZEN, IMPRISONED, and POISONED simultaneously.
#
# Team 3 — BULBASAUR: "The Spore Web"
#   Philosophy: Total denial.  Razor Leaf seeds, chaser poisons, Haunter
#   confuses, Golbat piles toxins, Parasect blinds.
# ---------------------------------------------------------------------------
STARTER_TEAMS: dict[str, list[dict[str, str]]] = {
    "Charmander": [
        # Slot 1 — Charmander (burst): Ember starts the burned chain every round
        {
            "species":  "Charmander",
            "standard": "Ember",
            "chase":    "Fire Punch",
            "mystery":  "V-create",
            "support":  "Burning Will",
        },
        # Slot 2 — Arcanine (burst): burned→Fire Punch→ignited, massive damage
        {
            "species":  "Arcanine",
            "standard": "Flame Charge",
            "chase":    "Fire Punch",
            "mystery":  "V-create",
            "support":  "Burning Will",
        },
        # Slot 3 — Ninetales (combo): burned→Fire Punch→ignited, keeps chain escalating
        {
            "species":  "Ninetales",
            "standard": "Ember",
            "chase":    "Mystical Fire",
            "mystery":  "Blue Flare",
            "support":  "Burning Will",
        },
        # Slot 4 — Pikachu (combo): burned→Thunder Punch→paralyzed, cross-type extension
        {
            "species":  "Pikachu",
            "standard": "Charge Beam",
            "chase":    "Thunder Punch",
            "mystery":  "Bolt Strike",
            "support":  "Discharge Field",
        },
        # Slot 5 — Geodude (burst): flinched→Rock Slide→airborne, secondary chain layer
        {
            "species":  "Geodude",
            "standard": "Rock Throw",
            "chase":    "Rock Slide",
            "mystery":  "Head Smash",
            "support":  "Stone Wall Pact",
        },
        # Slot 6 — Gastly (control): confused primer, emergency control chain
        {
            "species":  "Gastly",
            "standard": "Last Respects",
            "chase":    "Hex",
            "mystery":  "Astral Barrage",
            "support":  "Spirit Link",
        },
    ],

    "Squirtle": [
        # Slot 1 — Squirtle (control): Whirlpool applies WEAKENED, fans 3-way chase
        {
            "species":  "Squirtle",
            "standard": "Whirlpool",
            "chase":    "Brine",
            "mystery":  "Hydro Cannon",
            "support":  "Tidal Flow",
        },
        # Slot 2 — Tentacruel (tank): weakened→Venom Current→poisoned, Rocky Helmet chip
        {
            "species":  "Tentacruel",
            "standard": "Aqua Jet",
            "chase":    "Venom Current",
            "mystery":  "Hydro Cannon",
            "support":  "Tidal Flow",
        },
        # Slot 3 — Slowbro (tank): weakened→Psychic Wave→imprisoned (no mystery moves)
        {
            "species":  "Slowbro",
            "standard": "Bubble",
            "chase":    "Psychic Wave",
            "mystery":  "Water Spout",
            "support":  "Tidal Flow",
        },
        # Slot 4 — Cloyster (tank): weakened→Blizzard Current→frozen (enemy skips turn)
        {
            "species":  "Cloyster",
            "standard": "Aqua Jet",
            "chase":    "Blizzard Current",
            "mystery":  "Water Spout",
            "support":  "Tidal Flow",
        },
        # Slot 5 — Gengar (combo): confused standard primer, asleep→Hex Venom→poisoned
        {
            "species":  "Gengar",
            "standard": "Last Respects",
            "chase":    "Hex Venom",
            "mystery":  "Astral Barrage",
            "support":  "Spirit Link",
        },
        # Slot 6 — Golbat (tank): confused→Cross Poison→poisoned, drain sustain
        {
            "species":  "Golbat",
            "standard": "Acid",
            "chase":    "Cross Poison",
            "mystery":  "Malignant Chain",
            "support":  "Toxic Network",
        },
    ],

    "Bulbasaur": [
        # Slot 1 — Bulbasaur (burst): Razor Leaf seeds every round, Root Network reduces CC
        {
            "species":  "Bulbasaur",
            "standard": "Razor Leaf",
            "chase":    "Giga Drain",
            "mystery":  "Frenzy Plant",
            "support":  "Root Network",
        },
        # Slot 2 — Weepinbell (control): seeded→Horn Leech→poisoned, double primer
        {
            "species":  "Weepinbell",
            "standard": "Branch Poke",
            "chase":    "Horn Leech",
            "mystery":  "Frenzy Plant",
            "support":  "Root Network",
        },
        # Slot 3 — Haunter (combo): Last Respects→confused primer, asleep→Hex Venom→poisoned
        {
            "species":  "Haunter",
            "standard": "Last Respects",
            "chase":    "Hex Venom",
            "mystery":  "Astral Barrage",
            "support":  "Spirit Link",
        },
        # Slot 4 — Golbat (tank): confused→Cross Poison→poisoned, Toxic Network on-hit
        {
            "species":  "Golbat",
            "standard": "Acid",
            "chase":    "Cross Poison",
            "mystery":  "Malignant Chain",
            "support":  "Toxic Network",
        },
        # Slot 5 — Venomoth (control): weakened→Bug Bite→confused, second web layer
        {
            "species":  "Venomoth",
            "standard": "Fury Cutter",
            "chase":    "Bug Bite",
            "mystery":  "Megahorn",
            "support":  "Swarm Mind",
        },
        # Slot 6 — Parasect (support): Fell Stinger→blinded (enemy can't standard attack)
        {
            "species":  "Parasect",
            "standard": "Fell Stinger",
            "chase":    "Spore Bite",
            "mystery":  "Lunge",
            "support":  "Swarm Mind",
        },
    ],
}

# Level for all player tutorial Pokemon and the opposing AI tutorial team
_TUTORIAL_LEVEL: int = 5

STARTER_INFO: dict[str, dict[str, str]] = {
    "Charmander": {
        "type": "Fire",
        "role": "Chain Starter",
        "description": "Burns enemies with fiery attacks, setting up devastating combo chains.",
        "playstyle": "Aggressive — apply Burn, then watch your team pile on.",
        "color": "#f97316",
    },
    "Squirtle": {
        "type": "Water",
        "role": "Chain Sustainer",
        "description": "Shields allies and extends combo chains with disciplined water techniques.",
        "playstyle": "Defensive — keep the chain alive while protecting your team.",
        "color": "#38bdf8",
    },
    "Bulbasaur": {
        "type": "Grass / Poison",
        "role": "Chain Extender",
        "description": "Poisons and puts foes to sleep, building long unstoppable chains.",
        "playstyle": "Control — stack status effects and let the chain multiply damage.",
        "color": "#4ade80",
    },
}


class TutorialService:
    """Handles first-time tutorial setup for new trainers."""

    def assign_starter_team(self, user: User, starter_name: str) -> list[int]:
        """
        Create the tutorial team (6 hand-curated OwnedPokemon) and save them to the
        user's persistent Team.

        Each team member's moves are resolved by name from the Move table; any move
        not found falls back to whatever _get_moves_for_species() returns for that slot
        so OwnedPokemon always have all four slots filled.

        Returns the list of OwnedPokemon PKs in position order (1–6).
        Raises ValueError for an unrecognised starter_name or missing DB data.
        """
        if starter_name not in STARTER_NAMES:
            raise ValueError(
                f"Invalid starter choice: {starter_name!r}. "
                f"Choose from: {', '.join(STARTER_NAMES)}."
            )

        slot_defs = STARTER_TEAMS[starter_name]  # guaranteed to be a 6-entry list

        with transaction.atomic():
            # Resolve all species up-front so we fail fast on bad data
            species_names = [s["species"] for s in slot_defs]
            species_map = {
                p.name: p
                for p in Pokemon.objects.filter(name__in=species_names)
            }
            missing_species = [n for n in species_names if n not in species_map]
            if missing_species:
                raise ValueError(
                    f"Species not found in database: {', '.join(missing_species)}. "
                    "Ensure seed data has been loaded."
                )

            # Resolve moves by name — one bulk query per slot key
            all_move_names: set[str] = set()
            for slot in slot_defs:
                all_move_names.update([slot["standard"], slot["chase"], slot["mystery"], slot["support"]])
            move_map = {
                m.name: m
                for m in Move.objects.filter(name__in=all_move_names)
            }

            owned_pks: list[int] = []
            for slot in slot_defs:
                species = species_map[slot["species"]]

                # Look up each named move; fall back to species pool if not found
                fallback = self._get_moves_for_species(species)

                def _resolve(move_name: str, slot_type: str) -> "Move | None":
                    return move_map.get(move_name) or fallback.get(slot_type)

                op = OwnedPokemon.objects.create(
                    owner=user,
                    species=species,
                    level=_TUTORIAL_LEVEL,
                    move_standard=_resolve(slot["standard"], MoveSlotType.STANDARD),
                    move_chase=_resolve(slot["chase"], MoveSlotType.CHASE),
                    move_special=_resolve(slot["mystery"], MoveSlotType.MYSTERY),
                    move_support=_resolve(slot["support"], MoveSlotType.PASSIVE_1),
                )
                owned_pks.append(op.pk)

            # Persist to the user's saved team slot
            team, _ = Team.objects.get_or_create(owner=user)
            TeamSlot.objects.filter(team=team).delete()
            TeamSlot.objects.bulk_create([
                TeamSlot(team=team, pokemon_id=pk, position=pos)
                for pos, pk in enumerate(owned_pks, start=1)
            ])

            user.tutorial_starter = starter_name
            user.save(update_fields=["tutorial_starter"])

        logger.info("Assigned tutorial starter '%s' to user %s", starter_name, user)
        return owned_pks

    def create_tutorial_battle(self, user: User, owned_pks: list[int]) -> "Battle":
        """
        Create an Easy AI battle flagged as a tutorial, set both teams, and start
        the battle.  Returns the Battle in ACTIVE status ready for the first round.

        Raises ValueError if team setup or battle start fails.
        """
        from apps.game.ai import BattleAIService
        from apps.game.services import BattleService

        battle_service = BattleService()
        ai_service = BattleAIService()

        with transaction.atomic():
            ai_user = ai_service.get_or_create_ai_user()
            battle = battle_service.create_battle(
                player_one=user,
                player_two=ai_user,
                is_ai_battle=True,
                ai_difficulty="easy",
            )
            battle.is_tutorial = True
            battle.save(update_fields=["is_tutorial"])

            # AI team — built from early-gen species; capped at tutorial level
            ai_pokemon_ids = ai_service.build_tutorial_ai_team_pokemon_ids()
            battle_service.set_team(battle, ai_user, ai_pokemon_ids, level=_TUTORIAL_LEVEL)

            # Player team — their newly created tutorial OwnedPokemon
            battle_service.set_team_from_owned(battle, user, owned_pks)

            battle_service.start_battle(battle)

        logger.info("Created tutorial Battle #%d for user %s", battle.pk, user)
        return battle

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_moves_for_species(self, species: Pokemon) -> dict[str, Move | None]:
        """
        Return one Move per required slot type for this species.

        Queries SpeciesMovePool (the authoritative curated pool) first.
        For any slot type still missing, falls back to any Move in the DB
        of that type so the tutorial OwnedPokemon always have all four slots filled.
        """
        from apps.pokemon.models import SpeciesMovePool

        required: list[str] = [
            MoveSlotType.STANDARD,
            MoveSlotType.CHASE,
            MoveSlotType.MYSTERY,
            MoveSlotType.PASSIVE_1,
        ]
        result: dict[str, Move | None] = {s: None for s in required}

        for entry in (
            SpeciesMovePool.objects
            .filter(species=species, slot_type__in=required)
            .select_related("move")
            .order_by("slot_type", "move__pk")
        ):
            if result[entry.slot_type] is None:
                result[entry.slot_type] = entry.move

        missing = [s for s in required if result[s] is None]
        if missing:
            logger.warning(
                "Species '%s' has no SpeciesMovePool entries for slot(s): %s — using global fallback.",
                species.name,
                ", ".join(missing),
            )
            used_pks: set[int] = {m.pk for m in result.values() if m is not None}
            fallbacks = list(
                Move.objects.filter(slot_type__in=missing).order_by("slot_type", "pk")
            )
            for slot_type in missing:
                for move in fallbacks:
                    if move.slot_type == slot_type and move.pk not in used_pks:
                        result[slot_type] = move
                        used_pks.add(move.pk)
                        break

        return result
