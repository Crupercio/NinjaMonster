"""
Signal: assign 6 random Gen 1 Pokemon to every new user.

Django signals work like event listeners. When a User row is saved for the
first time (created=True), this function fires automatically and creates
6 OwnedPokemon rows linked to that user.
"""
import logging
import random

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Pokemon, Team
from .services import create_owned_pokemon

logger = logging.getLogger(__name__)

STARTER_POOL_SIZE = 6
# Gen 1 = pokedex numbers 1–151
GEN1_MAX_DEX = 151


@receiver(post_save, sender=get_user_model())
def assign_starter_pokemon(
    sender: type,
    instance: object,
    created: bool,
    **kwargs: object,
) -> None:
    """
    Fire once when a new User row is inserted.

    Picks STARTER_POOL_SIZE unique Gen 1 Pokemon at random and creates
    an OwnedPokemon for each, all at level 1 with 0 EXP.
    """
    if not created:
        # User was updated (e.g. password change) — do nothing.
        return

    gen1_ids: list[int] = list(
        Pokemon.objects.filter(pokedex_number__lte=GEN1_MAX_DEX)
        .values_list("pk", flat=True)
    )

    if len(gen1_ids) < STARTER_POOL_SIZE:
        logger.warning(
            "Only %d Gen 1 Pokemon in DB; need %d. "
            "Run: python manage.py seed_gen1",
            len(gen1_ids),
            STARTER_POOL_SIZE,
        )
        chosen_ids = gen1_ids  # assign whatever is available
    else:
        chosen_ids = random.sample(gen1_ids, STARTER_POOL_SIZE)

    species_list = list(Pokemon.objects.filter(pk__in=chosen_ids))
    count = 0
    for species in species_list:
        try:
            create_owned_pokemon(owner=instance, species=species)
            count += 1
        except Exception:
            logger.exception(
                "Failed to create starter %s for user '%s'.",
                species.name,
                instance,
            )

    logger.info(
        "Assigned %d starter Pokemon to new user '%s'.",
        count,
        instance,  # type: ignore[attr-defined]
    )

    Team.objects.create(owner=instance)
    logger.info("Created persistent team for new user '%s'.", instance)  # type: ignore[attr-defined]
