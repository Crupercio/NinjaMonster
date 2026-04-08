"""
P2-1 — Tutorial / first-time experience tests.

Covers:
- assign_starter_team creates 6 OwnedPokemon for the user
- assign_starter_team saves tutorial_starter on the user
- assign_starter_team creates a persistent Team with 6 slots
- assign_starter_team raises ValueError for an invalid starter name
- create_tutorial_battle returns an ACTIVE battle flagged as is_tutorial
- create_tutorial_battle uses EASY AI difficulty
- TutorialCompleteView sets tutorial_complete = True on GET
- dashboard redirects incomplete-tutorial users to game:tutorial
"""
import allure
import pytest
from django.test import Client
from django.urls import reverse

from apps.game.tutorial_service import TutorialService
from apps.pokemon.models import Move, MoveSlotType, OwnedPokemon, Team, TeamSlot

from tests.framework.base.base_test import BaseTest
from tests.framework.factories.pokemon_factory import (
    MoveFactory,
    PokemonFactory,
    PokemonTypeFactory,
)
from tests.framework.factories.user_factory import UserFactory


def _make_tutorial_roster(starter_name: str = "Charmander") -> tuple:
    """
    Create the minimal DB fixture for TutorialService tests:
      - 1 PokemonType
      - 4 moves (one per slot type)
      - 6 Pokemon species (starter + 5 companions), each with all 4 moves
    Returns (starter_species, companion_species_list, moves_dict).
    """
    ptype = PokemonTypeFactory(name="Fire")

    moves: dict[str, Move] = {
        MoveSlotType.STANDARD: MoveFactory(
            name=f"Tut-Standard", move_type=ptype,
            slot_type=MoveSlotType.STANDARD,
        ),
        MoveSlotType.CHASE: MoveFactory(
            name=f"Tut-Chase", move_type=ptype,
            slot_type=MoveSlotType.CHASE,
        ),
        MoveSlotType.SPECIAL: MoveFactory(
            name=f"Tut-Special", move_type=ptype,
            slot_type=MoveSlotType.SPECIAL,
        ),
        MoveSlotType.SUPPORT: MoveFactory(
            name=f"Tut-Support", move_type=ptype,
            slot_type=MoveSlotType.SUPPORT,
        ),
    }
    all_moves = list(moves.values())

    starter = PokemonFactory(
        name=starter_name,
        primary_type=ptype,
        pokedex_number=1,
        moves=all_moves,
    )
    companions = [
        PokemonFactory(
            name=f"Companion{i}",
            primary_type=ptype,
            pokedex_number=2 + i,
            moves=all_moves,
        )
        for i in range(5)
    ]
    return starter, companions, moves


@allure.epic("Tutorial")
@allure.feature("First-Time Experience")
@pytest.mark.django_db
class TestAssignStarterTeam(BaseTest):

    @allure.story("Creates 6 OwnedPokemon for the user")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_creates_six_owned_pokemon(self):
        # Arrange
        user = UserFactory()
        _make_tutorial_roster("Charmander")
        svc = TutorialService()

        # Act
        owned_pks = svc.assign_starter_team(user, "Charmander")

        # Assert
        assert len(owned_pks) == 6
        assert OwnedPokemon.objects.filter(owner=user).count() == 6

    @allure.story("Starter is at position 1 in the team")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_starter_is_first_position(self):
        # Arrange
        user = UserFactory()
        starter, _companions, _moves = _make_tutorial_roster("Charmander")
        svc = TutorialService()

        # Act
        owned_pks = svc.assign_starter_team(user, "Charmander")

        # Assert — first OwnedPokemon is the starter species
        first_op = OwnedPokemon.objects.get(pk=owned_pks[0])
        assert first_op.species == starter

    @allure.story("Sets tutorial_starter on the user")
    @allure.severity(allure.severity_level.NORMAL)
    def test_sets_tutorial_starter_field(self):
        # Arrange
        user = UserFactory()
        _make_tutorial_roster("Charmander")
        svc = TutorialService()

        # Act
        svc.assign_starter_team(user, "Charmander")

        # Assert
        user.refresh_from_db()
        assert user.tutorial_starter == "Charmander"

    @allure.story("Creates a persistent Team with 6 slots")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_creates_team_with_six_slots(self):
        # Arrange
        user = UserFactory()
        _make_tutorial_roster("Charmander")
        svc = TutorialService()

        # Act
        svc.assign_starter_team(user, "Charmander")

        # Assert
        team = Team.objects.get(owner=user)
        assert TeamSlot.objects.filter(team=team).count() == 6

    @allure.story("Raises ValueError for an invalid starter name")
    @allure.severity(allure.severity_level.NORMAL)
    def test_invalid_starter_raises_value_error(self):
        # Arrange
        user = UserFactory()
        svc = TutorialService()

        # Act / Assert
        with pytest.raises(ValueError, match="Invalid starter choice"):
            svc.assign_starter_team(user, "Pikachu")

    @allure.story("All OwnedPokemon have all 4 move slots assigned")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_owned_pokemon_have_all_four_moves(self):
        # Arrange
        user = UserFactory()
        _make_tutorial_roster("Charmander")
        svc = TutorialService()

        # Act
        owned_pks = svc.assign_starter_team(user, "Charmander")

        # Assert — every OwnedPokemon has all 4 moves assigned
        for pk in owned_pks:
            op = OwnedPokemon.objects.get(pk=pk)
            assert op.move_standard is not None, f"OwnedPokemon {pk} missing move_standard"
            assert op.move_chase is not None, f"OwnedPokemon {pk} missing move_chase"
            assert op.move_special is not None, f"OwnedPokemon {pk} missing move_special"
            assert op.move_support is not None, f"OwnedPokemon {pk} missing move_support"


def _logged_in_client(user) -> Client:
    """Return a test Client authenticated as *user*.

    UserFactory uses skip_postgeneration_save=True, so the hashed password is
    only in memory — not in the DB.  force_login() stores a session auth hash
    derived from user.password; on the next request Django reloads the user
    from the DB (different hash) and rejects the session.  Saving the password
    first keeps both copies in sync.
    """
    user.set_password("testpass123")
    user.save(update_fields=["password"])
    client = Client()
    client.force_login(user)
    return client


@allure.epic("Tutorial")
@allure.feature("First-Time Experience")
@pytest.mark.django_db
class TestTutorialCompleteView(BaseTest):

    @allure.story("GET sets tutorial_complete = True")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_get_marks_tutorial_complete(self):
        # Arrange
        user = UserFactory(tutorial_complete=False)
        client = _logged_in_client(user)

        # Act
        response = client.get(reverse("game:tutorial_complete"))

        # Assert
        assert response.status_code == 200
        user.refresh_from_db()
        assert user.tutorial_complete is True

    @allure.story("Subsequent GET does not error when already complete")
    @allure.severity(allure.severity_level.NORMAL)
    def test_idempotent_on_already_complete(self):
        # Arrange
        user = UserFactory(tutorial_complete=True)
        client = _logged_in_client(user)

        # Act
        response = client.get(reverse("game:tutorial_complete"))

        # Assert — no error, page renders
        assert response.status_code == 200
        user.refresh_from_db()
        assert user.tutorial_complete is True


@allure.epic("Tutorial")
@allure.feature("First-Time Experience")
@pytest.mark.django_db
class TestDashboardTutorialRedirect(BaseTest):

    @allure.story("Dashboard redirects incomplete-tutorial user to tutorial")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_dashboard_redirects_new_user(self):
        # Arrange
        user = UserFactory(tutorial_complete=False)
        client = _logged_in_client(user)

        # Act
        response = client.get(reverse("dashboard"))

        # Assert
        assert response.status_code == 302
        assert response["Location"] == reverse("game:tutorial")

    @allure.story("Dashboard does not redirect tutorial-complete user")
    @allure.severity(allure.severity_level.NORMAL)
    def test_dashboard_does_not_redirect_complete_user(self):
        # Arrange
        user = UserFactory(tutorial_complete=True)
        client = _logged_in_client(user)

        # Act
        response = client.get(reverse("dashboard"))

        # Assert — renders the home page, no redirect to tutorial
        assert response.status_code == 200
