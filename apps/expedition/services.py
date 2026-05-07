"""Business logic for the expedition system."""
import logging
import random
from datetime import date

from django.db import transaction
from apps.users.services import (
    BOND_RATE_CAP,
    CANDY_BOOST,
    award_trainer_xp,
    deduct_ryo,
    use_candy,
)

from .models import EncounterLog, ExpeditionSession, Zone, ZoneSpawnEntry

logger = logging.getLogger(__name__)

BASE_BOND_MIN = 15
BASE_BOND_MAX = 90

# Hint text shown to user based on base bond rate (before candy)
BOND_HINTS = [
    (30,  "seems very wary of you"),
    (50,  "watches you cautiously"),
    (70,  "appears curious about you"),
    (91,  "seems happy to see you!"),
]


def get_bond_hint(rate: int) -> str:
    for threshold, text in BOND_HINTS:
        if rate < threshold:
            return text
    return "seems happy to see you!"


def get_zones_for_user(user) -> list[dict]:
    """Return all active zones with availability info for the given user."""
    zones = Zone.objects.filter(is_active=True).prefetch_related("spawns__species")
    today = date.today()
    sessions_today = (
        ExpeditionSession.objects
        .filter(user=user, session_date=today)
        .count()
    )
    max_expeditions = user.max_daily_expeditions

    result = []
    for zone in zones:
        spawn_count = zone.spawns.count()
        sample_species = list(
            zone.spawns.order_by("-weight", "species__name")
            .values_list("species__name", "species__pokedex_number")[:8]
        )
        result.append({
            "zone": zone,
            "unlocked": user.trainer_level >= zone.min_trainer_level,
            "can_afford": user.ryo >= zone.cost,
            "sessions_today": sessions_today,
            "expeditions_left": max(0, max_expeditions - sessions_today),
            "max_expeditions": max_expeditions,
            "spawn_count": spawn_count,
            "sample_species": sample_species,
        })
    return result


@transaction.atomic
def start_expedition(user, zone_pk: int) -> ExpeditionSession:
    """
    Pay the zone entry fee and create a new ExpeditionSession.

    Raises ValueError if:
    - Zone doesn't exist or is inactive
    - User hasn't unlocked this zone (trainer level too low)
    - User has hit their daily expedition limit
    - User can't afford the entry fee
    """
    zone = Zone.objects.filter(pk=zone_pk, is_active=True).first()
    if zone is None:
        raise ValueError("Zone not found.")

    if user.trainer_level < zone.min_trainer_level:
        raise ValueError(
            f"You need Trainer Level {zone.min_trainer_level} to enter {zone.name}."
        )

    today = date.today()
    sessions_today = ExpeditionSession.objects.filter(user=user, session_date=today).count()
    if sessions_today >= user.max_daily_expeditions:
        raise ValueError(
            f"You've used all {user.max_daily_expeditions} expedition(s) for today. "
            "Come back tomorrow!"
        )

    deduct_ryo(user, zone.cost)  # raises ValueError if insufficient

    session = ExpeditionSession.objects.create(
        user=user,
        zone=zone,
        session_date=today,
        encounters_total=zone.encounters_per_run,
    )
    logger.info("%s started expedition in %s (session #%d).", user, zone.name, session.pk)
    return session


def draw_encounter(session: ExpeditionSession):
    """
    Pick a random species from the zone's spawn table (weighted).

    Returns a dict with species info and bond hint — does NOT consume an encounter slot.
    Call resolve_encounter() to actually record the attempt.
    """
    spawns = list(
        ZoneSpawnEntry.objects
        .filter(zone=session.zone)
        .select_related("species__primary_type")
    )
    if not spawns:
        raise ValueError(f"Zone {session.zone.name} has no spawn entries.")

    weights = [s.weight for s in spawns]
    chosen = random.choices(spawns, weights=weights, k=1)[0]
    species = chosen.species

    base_rate = random.randint(BASE_BOND_MIN, BASE_BOND_MAX)

    from apps.pokemon.models import OwnedPokemon
    already_owned = OwnedPokemon.objects.filter(
        owner=session.user, species=species
    ).exists()

    return {
        "species_id": species.pk,
        "species_name": species.name,
        "pokedex_number": species.pokedex_number,
        "type": species.primary_type.name if species.primary_type else "",
        "sprite_url": species.sprite_url or "",
        "base_bond_rate": base_rate,
        "hint": get_bond_hint(base_rate),
        "already_owned": already_owned,
    }


@transaction.atomic
def resolve_encounter(
    session: ExpeditionSession,
    species_pk: int,
    base_bond_rate: int,
    candy_type: str = "",
) -> dict:
    """
    Record the outcome of an encounter — with or without candy.

    Consumes one encounter slot. If bonded, creates an OwnedPokemon.

    Returns dict with keys:
        bonded (bool), species_name (str), candy_boost (int),
        final_rate (int), owned_pk (int|None), encounters_remaining (int)
    """
    from apps.pokemon.models import Pokemon
    from apps.pokemon.services import create_owned_pokemon

    if session.is_finished:
        raise ValueError("This expedition is already finished.")

    species = Pokemon.objects.select_related("primary_type", "secondary_type").get(pk=species_pk)

    # Apply candy if provided
    candy_boost = 0
    if candy_type and candy_type in CANDY_BOOST:
        candy_boost = use_candy(session.user, candy_type)  # raises if none left

    final_rate = min(BOND_RATE_CAP, base_bond_rate + candy_boost)

    # Bond attempt
    roll = random.randint(1, 100)
    bonded = roll <= final_rate

    owned_pokemon = None
    if bonded:
        owned_pokemon = create_owned_pokemon(owner=session.user, species=species, level=1)
        award_trainer_xp(session.user, 30, source="bond_pokemon")
        from apps.quests.services import QuestService
        QuestService().on_pokemon_bonded(session.user, species=species)

    EncounterLog.objects.create(
        session=session,
        species=species,
        base_bond_rate=base_bond_rate,
        candy_used=candy_type,
        final_bond_rate=final_rate,
        bonded=bonded,
        owned_pokemon=owned_pokemon,
    )

    session.encounters_used += 1
    if session.encounters_used >= session.encounters_total:
        session.completed = True
    session.save(update_fields=["encounters_used", "completed"])

    if session.completed:
        from apps.quests.services import QuestService
        QuestService().on_expedition_completed(session.user)

    logger.info(
        "%s encountered %s (base=%d%%, candy=%s +%d%%, final=%d%%, roll=%d) -> %s",
        session.user, species.name,
        base_bond_rate, candy_type or "none", candy_boost,
        final_rate, roll,
        "BONDED" if bonded else "fled",
    )

    return {
        "bonded": bonded,
        "species_name": species.name,
        "pokedex_number": species.pokedex_number,
        "candy_boost": candy_boost,
        "final_rate": final_rate,
        "roll": roll,
        "owned_pk": owned_pokemon.pk if owned_pokemon else None,
        "encounters_remaining": session.encounters_remaining,
        "session_complete": session.is_finished,
    }
