import pytest

from apps.users.services import (
    base_sell_value_for_level,
    purchase_training_slot_upgrade,
    sell_value_for_level,
)
from tests.framework.factories.user_factory import UserFactory


@pytest.mark.django_db
def test_sell_value_uses_tiers_with_bond_bonus_lock():
    assert base_sell_value_for_level(1) == 1500
    assert sell_value_for_level(1) == 375
    assert sell_value_for_level(9) == 375
    assert sell_value_for_level(10) == 1500
    assert sell_value_for_level(50) == 1500
    assert sell_value_for_level(51) == 2500
    assert sell_value_for_level(99) == 3000
    assert sell_value_for_level(100) == 5000


@pytest.mark.django_db
def test_training_slot_caps_follow_level_gates_and_purchases():
    user = UserFactory(trainer_level=1, training_slot_upgrade_level=0)
    assert user.max_training_slots == 10

    user.trainer_level = 10
    user.training_slot_upgrade_level = 1
    assert user.max_training_slots == 15

    user.training_slot_upgrade_level = 2
    assert user.max_training_slots == 20

    user.trainer_level = 25
    user.training_slot_upgrade_level = 3
    assert user.max_training_slots == 30

    user.trainer_level = 40
    user.training_slot_upgrade_level = 4
    assert user.max_training_slots == 40


@pytest.mark.django_db
def test_purchase_training_slot_upgrade_deducts_ryo_and_expands_capacity():
    user = UserFactory(trainer_level=10, ryo=15_000, training_slot_upgrade_level=0)

    result = purchase_training_slot_upgrade(user)

    user.refresh_from_db()
    assert result == {"cost": 10_000, "max_training_slots": 15}
    assert user.ryo == 5_000
    assert user.training_slot_upgrade_level == 1
