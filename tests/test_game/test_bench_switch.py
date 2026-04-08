"""
P2-7 — Bench switching in battle tests (GDD §5.6).

Covers:
- Successful switch swaps is_active and grid_position between slots
- Switch clears volatile statuses from the outgoing Pokemon
- Switch keeps persistent statuses on the outgoing Pokemon
- Cannot switch in a fainted bench slot (raises ValueError)
- Cannot switch out a slot that is already on the bench (raises ValueError)
- Cannot switch a fainted active slot (raises ValueError)
- Wrong-team slot raises ValueError
- Selected move / target cleared for both slots after switch
- Battle log entry created on switch
- BattleActionView processes switch_ POST params before round
- Switched slot is excluded from player_actions (passes its attack turn)
"""
import allure
import pytest
from django.test import Client
from django.urls import reverse

from apps.effects.models import ActiveStatusEffect
from apps.game.models import BattleLog, BattleSlot, BattleStatus, GridPosition
from apps.game.services import BattleService

from tests.framework.base.base_test import BaseTest
from tests.framework.factories.battle_factory import (
    BattleFactory,
    BattleSlotFactory,
    BattleTeamFactory,
)
from tests.framework.factories.effects_factory import (
    ActiveStatusEffectFactory,
    StatusEffectFactory,
)
from tests.framework.factories.pokemon_factory import MoveFactory, PokemonFactory, PokemonTypeFactory
from tests.framework.factories.user_factory import UserFactory


def _make_team_with_bench(battle, owner):
    """Create a BattleTeam with 4 active + 2 bench slots. Returns (team, actives, benches)."""
    team = BattleTeamFactory(battle=battle, owner=owner)
    normal_type = PokemonTypeFactory(name="Normal")
    actives = []
    grid_positions = [
        GridPosition.FRONT_LEFT,
        GridPosition.FRONT_RIGHT,
        GridPosition.BACK_LEFT,
        GridPosition.BACK_RIGHT,
    ]
    for i, gp in enumerate(grid_positions, start=1):
        poke = PokemonFactory(primary_type=normal_type)
        slot = BattleSlotFactory(
            team=team, pokemon=poke, position=i,
            is_active=True, grid_position=gp,
        )
        actives.append(slot)

    benches = []
    for i, gp in enumerate([GridPosition.BENCH_1, GridPosition.BENCH_2], start=5):
        poke = PokemonFactory(primary_type=normal_type)
        slot = BattleSlotFactory(
            team=team, pokemon=poke, position=i,
            is_active=False, grid_position=gp,
        )
        benches.append(slot)

    return team, actives, benches


@allure.epic("Game")
@allure.feature("Bench Switching")
@pytest.mark.django_db
class TestBenchSwitchService(BaseTest):

    @allure.story("Successful switch swaps is_active and grid_position")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_switch_swaps_is_active_and_grid_position(self):
        user = UserFactory()
        battle = BattleFactory(player_one=user, status=BattleStatus.ACTIVE)
        team, actives, benches = _make_team_with_bench(battle, user)
        svc = BattleService()

        active_slot = actives[0]  # FRONT_LEFT, is_active=True
        bench_slot = benches[0]   # BENCH_1, is_active=False
        original_active_grid = active_slot.grid_position
        original_bench_grid = bench_slot.grid_position

        svc.bench_switch(battle, team, active_slot, bench_slot)

        active_slot.refresh_from_db()
        bench_slot.refresh_from_db()

        assert active_slot.is_active is False
        assert active_slot.grid_position == original_bench_grid
        assert bench_slot.is_active is True
        assert bench_slot.grid_position == original_active_grid

    @allure.story("Volatile statuses cleared from switching-out Pokemon")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_switch_clears_volatile_statuses(self):
        user = UserFactory()
        battle = BattleFactory(player_one=user, status=BattleStatus.ACTIVE)
        team, actives, benches = _make_team_with_bench(battle, user)
        svc = BattleService()

        active_slot = actives[0]
        bench_slot = benches[0]

        confused = StatusEffectFactory(confused=True)
        ActiveStatusEffectFactory(slot=active_slot, status=confused)
        assert ActiveStatusEffect.objects.filter(slot=active_slot).count() == 1

        svc.bench_switch(battle, team, active_slot, bench_slot)

        assert ActiveStatusEffect.objects.filter(slot=active_slot).count() == 0

    @allure.story("Persistent statuses kept on switching-out Pokemon")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_switch_keeps_persistent_statuses(self):
        user = UserFactory()
        battle = BattleFactory(player_one=user, status=BattleStatus.ACTIVE)
        team, actives, benches = _make_team_with_bench(battle, user)
        svc = BattleService()

        active_slot = actives[0]
        bench_slot = benches[0]

        burned = StatusEffectFactory(burned=True)
        ActiveStatusEffectFactory(slot=active_slot, status=burned)

        svc.bench_switch(battle, team, active_slot, bench_slot)

        assert ActiveStatusEffect.objects.filter(slot=active_slot).count() == 1

    @allure.story("Cannot switch in a fainted bench slot")
    @allure.severity(allure.severity_level.NORMAL)
    def test_switch_fainted_bench_raises(self):
        user = UserFactory()
        battle = BattleFactory(player_one=user, status=BattleStatus.ACTIVE)
        team, actives, benches = _make_team_with_bench(battle, user)
        svc = BattleService()

        bench_slot = benches[0]
        bench_slot.is_fainted = True
        bench_slot.save(update_fields=["is_fainted"])

        with pytest.raises(ValueError, match="fainted"):
            svc.bench_switch(battle, team, actives[0], bench_slot)

    @allure.story("Cannot switch out a fainted active slot")
    @allure.severity(allure.severity_level.NORMAL)
    def test_switch_fainted_active_raises(self):
        user = UserFactory()
        battle = BattleFactory(player_one=user, status=BattleStatus.ACTIVE)
        team, actives, benches = _make_team_with_bench(battle, user)
        svc = BattleService()

        active_slot = actives[0]
        active_slot.is_fainted = True
        active_slot.save(update_fields=["is_fainted"])

        with pytest.raises(ValueError, match="fainted"):
            svc.bench_switch(battle, team, active_slot, benches[0])

    @allure.story("Slot not on field raises ValueError")
    @allure.severity(allure.severity_level.NORMAL)
    def test_switch_slot_not_on_field_raises(self):
        user = UserFactory()
        battle = BattleFactory(player_one=user, status=BattleStatus.ACTIVE)
        team, actives, benches = _make_team_with_bench(battle, user)
        svc = BattleService()

        # Try to "switch out" a bench slot as if it were active
        with pytest.raises(ValueError, match="not on the field"):
            svc.bench_switch(battle, team, benches[0], benches[1])

    @allure.story("Wrong-team slot raises ValueError")
    @allure.severity(allure.severity_level.NORMAL)
    def test_switch_wrong_team_raises(self):
        user = UserFactory()
        other_user = UserFactory()
        battle = BattleFactory(player_one=user, player_two=other_user, status=BattleStatus.ACTIVE)
        team, actives, _ = _make_team_with_bench(battle, user)
        other_team, other_actives, other_benches = _make_team_with_bench(battle, other_user)
        svc = BattleService()

        with pytest.raises(ValueError, match="same team"):
            svc.bench_switch(battle, team, actives[0], other_benches[0])

    @allure.story("Selected move and target cleared for both slots after switch")
    @allure.severity(allure.severity_level.NORMAL)
    def test_switch_clears_selected_move_and_target(self):
        user = UserFactory()
        battle = BattleFactory(player_one=user, status=BattleStatus.ACTIVE)
        team, actives, benches = _make_team_with_bench(battle, user)
        svc = BattleService()

        normal_type = PokemonTypeFactory(name="Normal")
        move = MoveFactory(name="Tackle", move_type=normal_type, power=40)
        active_slot = actives[0]
        bench_slot = benches[0]

        active_slot.selected_move = move
        active_slot.save(update_fields=["selected_move"])
        bench_slot.selected_move = move
        bench_slot.save(update_fields=["selected_move"])

        svc.bench_switch(battle, team, active_slot, bench_slot)

        active_slot.refresh_from_db()
        bench_slot.refresh_from_db()
        assert active_slot.selected_move is None
        assert bench_slot.selected_move is None

    @allure.story("Battle log entry created on switch")
    @allure.severity(allure.severity_level.NORMAL)
    def test_switch_creates_battle_log(self):
        user = UserFactory()
        battle = BattleFactory(player_one=user, status=BattleStatus.ACTIVE)
        team, actives, benches = _make_team_with_bench(battle, user)
        svc = BattleService()

        outgoing_name = actives[0].pokemon.name
        incoming_name = benches[0].pokemon.name

        svc.bench_switch(battle, team, actives[0], benches[0])

        log = BattleLog.objects.filter(battle=battle).last()
        assert log is not None
        assert outgoing_name in log.message
        assert incoming_name in log.message

    @allure.story("Already-on-field bench slot raises ValueError")
    @allure.severity(allure.severity_level.NORMAL)
    def test_switch_bench_already_active_raises(self):
        user = UserFactory()
        battle = BattleFactory(player_one=user, status=BattleStatus.ACTIVE)
        team, actives, _ = _make_team_with_bench(battle, user)
        svc = BattleService()

        # Try to switch active[0] for active[1] (both are on field)
        with pytest.raises(ValueError, match="already on the field"):
            svc.bench_switch(battle, team, actives[0], actives[1])


@allure.epic("Game")
@allure.feature("Bench Switching")
@pytest.mark.django_db
class TestBenchSwitchView(BaseTest):

    def _make_full_battle(self):
        """Two-team battle with bench slots, returns (battle, p1, p1_team, p1_actives, p1_benches)."""
        p1 = UserFactory()
        p2 = UserFactory()
        battle = BattleFactory(
            player_one=p1, player_two=p2,
            status=BattleStatus.ACTIVE, is_ai_battle=False,
        )
        team1, actives1, benches1 = _make_team_with_bench(battle, p1)
        team2, actives2, _ = _make_team_with_bench(battle, p2)

        # Give each slot a move so execute_round doesn't skip them
        normal_type = PokemonTypeFactory(name="Normal")
        move = MoveFactory(name="Tackle", move_type=normal_type, power=40)
        for slot in actives1 + actives2:
            slot.pokemon.moves.add(move)

        return battle, p1, team1, actives1, benches1, actives2

    def _client(self, user) -> Client:
        user.set_password("pw")
        user.save(update_fields=["password"])
        client = Client()
        client.force_login(user)
        return client

    @allure.story("View processes switch_ POST param — slot swaps before round")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_view_processes_bench_switch(self):
        battle, p1, team1, actives1, benches1, actives2 = self._make_full_battle()
        client = self._client(p1)

        active_slot = actives1[0]
        bench_slot = benches1[0]

        data = {
            f"switch_{active_slot.pk}": bench_slot.pk,
            # Provide moves/targets for remaining 3 active slots
        }
        for slot in actives1[1:]:
            enemy = actives2[0]
            move = slot.pokemon.moves.first()
            if move:
                data[f"move_{slot.pk}"] = move.pk
                data[f"target_{slot.pk}"] = enemy.pk

        url = reverse("game:battle_action", kwargs={"pk": battle.pk})
        response = client.post(url, data)

        assert response.status_code == 302

        active_slot.refresh_from_db()
        bench_slot.refresh_from_db()
        assert active_slot.is_active is False
        assert bench_slot.is_active is True

    @allure.story("Switched slot does not appear in player_actions (passes turn)")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_switched_slot_excluded_from_round(self):
        """After a switch, a battle log entry from the incoming slot does NOT appear
        for attacks this round (the slot passes its attack)."""
        battle, p1, team1, actives1, benches1, actives2 = self._make_full_battle()
        client = self._client(p1)

        active_slot = actives1[0]
        bench_slot = benches1[0]

        data = {f"switch_{active_slot.pk}": bench_slot.pk}
        for slot in actives1[1:]:
            move = slot.pokemon.moves.first()
            enemy = actives2[0]
            if move:
                data[f"move_{slot.pk}"] = move.pk
                data[f"target_{slot.pk}"] = enemy.pk

        url = reverse("game:battle_action", kwargs={"pk": battle.pk})
        client.post(url, data)

        # The bench_slot (now on field) should not have any attack log this round
        incoming_name = bench_slot.pokemon.name
        attack_logs = BattleLog.objects.filter(
            battle=battle,
            message__contains=f"{incoming_name} uses",
        )
        assert attack_logs.count() == 0
