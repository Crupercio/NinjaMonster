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
        Create the tutorial team (starter + 5 companions) as OwnedPokemon and save
        them to the user's persistent Team.

        Returns the list of OwnedPokemon PKs in position order (1–6).
        Raises ValueError for an unrecognised starter_name or missing DB data.
        """
        if starter_name not in STARTER_NAMES:
            raise ValueError(
                f"Invalid starter choice: {starter_name!r}. "
                f"Choose from: {', '.join(STARTER_NAMES)}."
            )

        with transaction.atomic():
            starter_species = Pokemon.objects.filter(name__iexact=starter_name).first()
            if starter_species is None:
                raise ValueError(
                    f"Starter species '{starter_name}' not found in the database. "
                    "Ensure the seed data has been loaded."
                )

            companion_species = list(
                Pokemon.objects.exclude(pk=starter_species.pk)
                .order_by("pokedex_number", "pk")[:5]
            )
            if len(companion_species) < 5:
                raise ValueError(
                    "Not enough Pokemon species in the database for the tutorial team "
                    f"(need 5 companions, found {len(companion_species)})."
                )

            owned_pks: list[int] = []
            for species in [starter_species, *companion_species]:
                moves = self._get_moves_for_species(species)
                op = OwnedPokemon.objects.create(
                    owner=user,
                    species=species,
                    level=5,
                    move_standard=moves[MoveSlotType.STANDARD],
                    move_chase=moves[MoveSlotType.CHASE],
                    move_special=moves[MoveSlotType.SPECIAL],
                    move_support=moves[MoveSlotType.SUPPORT],
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

            # AI team — built from species pool used by the AI service
            ai_pokemon_ids = ai_service.build_ai_team_pokemon_ids()
            battle_service.set_team(battle, ai_user, ai_pokemon_ids)

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

        Queries the species' own learnset first.  For any slot type that the
        species lacks, falls back to any other Move in the DB of that type so
        the tutorial OwnedPokemon always have all four slots filled.
        """
        required: list[str] = [
            MoveSlotType.STANDARD,
            MoveSlotType.CHASE,
            MoveSlotType.SPECIAL,
            MoveSlotType.SUPPORT,
        ]
        result: dict[str, Move | None] = {s: None for s in required}

        for move in species.moves.filter(slot_type__in=required):
            slot = move.slot_type
            if result[slot] is None:
                result[slot] = move

        missing = [s for s in required if result[s] is None]
        if missing:
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
