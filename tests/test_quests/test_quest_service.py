"""
P2-2 — Quest & Mission System tests.

Covers:
- assign_daily_quests creates 3 quests with today's period_key
- assign_daily_quests is idempotent (second call returns same set)
- assign_weekly_quests creates 3 quests with this week's period_key
- ensure_story_quests creates one UserQuest per story template
- on_battle_won increments WIN_BATTLES progress
- on_battle_won completes quest when target reached
- on_battle_won completes ACHIEVE_COMBO when chain is sufficient
- on_battle_won does NOT complete ACHIEVE_COMBO when chain is too short
- on_pack_opened increments OPEN_PACKS progress
- claim_reward awards Ryo and marks rewarded
- claim_reward raises ValueError when quest is not completed
- claim_reward raises ValueError when reward already claimed
"""
from datetime import date

import allure
import pytest

from apps.quests.models import QuestCondition, QuestType, RewardType, UserQuest
from apps.quests.services import QuestService, _daily_period_key, _weekly_period_key

from tests.framework.base.base_test import BaseTest
from tests.framework.factories.quest_factory import QuestTemplateFactory, UserQuestFactory
from tests.framework.factories.user_factory import UserFactory


def _make_mock_battle(max_combo_chain: int = 0):
    """Return a minimal object that looks like a Battle to QuestService."""
    class _FakeBattle:
        pk = 99999
    obj = _FakeBattle()
    obj.max_combo_chain = max_combo_chain
    return obj


@allure.epic("Quests")
@allure.feature("Quest Assignment")
@pytest.mark.django_db
class TestAssignDailyQuests(BaseTest):

    @allure.story("Creates 3 daily quests with today's period_key")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_creates_three_daily_quests(self):
        # Arrange — 5 daily templates in the DB
        for _ in range(5):
            QuestTemplateFactory(quest_type=QuestType.DAILY)
        user = UserFactory()
        svc = QuestService()

        # Act
        quests = svc.assign_daily_quests(user)

        # Assert
        assert len(quests) == 3
        assert all(uq.period_key == _daily_period_key() for uq in quests)
        assert UserQuest.objects.filter(user=user, period_key=_daily_period_key()).count() == 3

    @allure.story("assign_daily_quests is idempotent")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_idempotent(self):
        # Arrange
        for _ in range(5):
            QuestTemplateFactory(quest_type=QuestType.DAILY)
        user = UserFactory()
        svc = QuestService()

        # Act — call twice
        first = svc.assign_daily_quests(user)
        second = svc.assign_daily_quests(user)

        # Assert — same PKs, no duplicates
        assert {uq.pk for uq in first} == {uq.pk for uq in second}
        assert UserQuest.objects.filter(user=user, period_key=_daily_period_key()).count() == 3

    @allure.story("Returns empty list when no daily templates exist")
    @allure.severity(allure.severity_level.NORMAL)
    def test_empty_when_no_templates(self):
        user = UserFactory()
        svc = QuestService()
        quests = svc.assign_daily_quests(user)
        assert quests == []


@allure.epic("Quests")
@allure.feature("Quest Assignment")
@pytest.mark.django_db
class TestAssignWeeklyQuests(BaseTest):

    @allure.story("Creates 3 weekly quests with this week's period_key")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_creates_three_weekly_quests(self):
        # Arrange
        for _ in range(4):
            QuestTemplateFactory(quest_type=QuestType.WEEKLY)
        user = UserFactory()
        svc = QuestService()

        # Act
        quests = svc.assign_weekly_quests(user)

        # Assert
        assert len(quests) == 3
        assert all(uq.period_key == _weekly_period_key() for uq in quests)


@allure.epic("Quests")
@allure.feature("Quest Assignment")
@pytest.mark.django_db
class TestEnsureStoryQuests(BaseTest):

    @allure.story("Creates one UserQuest per active story template")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_creates_story_quests(self):
        # Arrange — 3 story templates
        for i in range(3):
            QuestTemplateFactory(quest_type=QuestType.STORY, order=i)
        user = UserFactory()
        svc = QuestService()

        # Act
        quests = svc.ensure_story_quests(user)

        # Assert
        assert len(quests) == 3
        assert all(uq.period_key == "story" for uq in quests)

    @allure.story("ensure_story_quests is idempotent")
    @allure.severity(allure.severity_level.NORMAL)
    def test_idempotent(self):
        # Arrange
        for i in range(3):
            QuestTemplateFactory(quest_type=QuestType.STORY, order=i)
        user = UserFactory()
        svc = QuestService()

        # Act — twice
        svc.ensure_story_quests(user)
        svc.ensure_story_quests(user)

        # Assert — still exactly 3
        assert UserQuest.objects.filter(user=user, period_key="story").count() == 3


@allure.epic("Quests")
@allure.feature("Progress Tracking")
@pytest.mark.django_db
class TestOnBattleWon(BaseTest):

    @allure.story("Increments WIN_BATTLES progress by 1")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_increments_win_battles(self):
        # Arrange
        user = UserFactory()
        tmpl = QuestTemplateFactory(
            quest_type=QuestType.DAILY,
            condition=QuestCondition.WIN_BATTLES,
            condition_value=3,
        )
        uq = UserQuestFactory(user=user, template=tmpl, period_key=_daily_period_key(), progress=0)
        svc = QuestService()

        # Act
        svc.on_battle_won(user, _make_mock_battle())

        # Assert
        uq.refresh_from_db()
        assert uq.progress == 1
        assert uq.completed is False

    @allure.story("Marks quest completed when WIN_BATTLES target reached")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_completes_on_target(self):
        # Arrange — need 2 wins, already at 1
        user = UserFactory()
        tmpl = QuestTemplateFactory(
            quest_type=QuestType.DAILY,
            condition=QuestCondition.WIN_BATTLES,
            condition_value=2,
        )
        uq = UserQuestFactory(user=user, template=tmpl, period_key=_daily_period_key(), progress=1)
        svc = QuestService()

        # Act
        svc.on_battle_won(user, _make_mock_battle())

        # Assert
        uq.refresh_from_db()
        assert uq.progress == 2
        assert uq.completed is True
        assert uq.completed_at is not None

    @allure.story("Completes ACHIEVE_COMBO when chain is sufficient")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_achieves_combo_when_chain_sufficient(self):
        # Arrange — need chain of 3; battle has chain of 5
        user = UserFactory()
        tmpl = QuestTemplateFactory(
            quest_type=QuestType.DAILY,
            condition=QuestCondition.ACHIEVE_COMBO,
            condition_value=3,
        )
        uq = UserQuestFactory(user=user, template=tmpl, period_key=_daily_period_key())
        svc = QuestService()

        # Act
        svc.on_battle_won(user, _make_mock_battle(max_combo_chain=5))

        # Assert
        uq.refresh_from_db()
        assert uq.completed is True
        assert uq.progress == 3

    @allure.story("Does NOT complete ACHIEVE_COMBO when chain too short")
    @allure.severity(allure.severity_level.NORMAL)
    def test_does_not_achieve_combo_when_chain_too_short(self):
        # Arrange — need chain of 5; battle has chain of 2
        user = UserFactory()
        tmpl = QuestTemplateFactory(
            quest_type=QuestType.DAILY,
            condition=QuestCondition.ACHIEVE_COMBO,
            condition_value=5,
        )
        uq = UserQuestFactory(user=user, template=tmpl, period_key=_daily_period_key())
        svc = QuestService()

        # Act
        svc.on_battle_won(user, _make_mock_battle(max_combo_chain=2))

        # Assert — no change
        uq.refresh_from_db()
        assert uq.completed is False
        assert uq.progress == 0


@allure.epic("Quests")
@allure.feature("Progress Tracking")
@pytest.mark.django_db
class TestOnPackOpened(BaseTest):

    @allure.story("Increments OPEN_PACKS progress by 1")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_increments_open_packs(self):
        # Arrange
        user = UserFactory()
        tmpl = QuestTemplateFactory(
            quest_type=QuestType.DAILY,
            condition=QuestCondition.OPEN_PACKS,
            condition_value=2,
        )
        uq = UserQuestFactory(user=user, template=tmpl, period_key=_daily_period_key(), progress=0)
        svc = QuestService()

        # Act
        svc.on_pack_opened(user)

        # Assert
        uq.refresh_from_db()
        assert uq.progress == 1
        assert uq.completed is False

    @allure.story("Completes quest when OPEN_PACKS target reached")
    @allure.severity(allure.severity_level.NORMAL)
    def test_completes_on_target(self):
        # Arrange — need 1 pack, progress already 0
        user = UserFactory()
        tmpl = QuestTemplateFactory(
            quest_type=QuestType.DAILY,
            condition=QuestCondition.OPEN_PACKS,
            condition_value=1,
        )
        uq = UserQuestFactory(user=user, template=tmpl, period_key=_daily_period_key(), progress=0)
        svc = QuestService()

        # Act
        svc.on_pack_opened(user)

        # Assert
        uq.refresh_from_db()
        assert uq.completed is True


@allure.epic("Quests")
@allure.feature("Reward Claiming")
@pytest.mark.django_db
class TestClaimReward(BaseTest):

    @allure.story("Awards Ryo and marks quest as rewarded")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_claims_ryo_reward(self):
        # Arrange
        user = UserFactory()
        user.ryo = 0
        user.save(update_fields=["ryo"])
        tmpl = QuestTemplateFactory(
            reward_type=RewardType.RYO,
            reward_value=250,
        )
        uq = UserQuestFactory(user=user, template=tmpl, completed=True, rewarded=False,
                               period_key=_daily_period_key())
        svc = QuestService()

        # Act
        summary = svc.claim_reward(user, uq)

        # Assert
        assert summary == {"ryo": 250}
        user.refresh_from_db()
        assert user.ryo == 250
        uq.refresh_from_db()
        assert uq.rewarded is True

    @allure.story("Raises ValueError when quest is not completed")
    @allure.severity(allure.severity_level.NORMAL)
    def test_raises_if_not_completed(self):
        user = UserFactory()
        tmpl = QuestTemplateFactory()
        uq = UserQuestFactory(user=user, template=tmpl, completed=False,
                               period_key=_daily_period_key())
        svc = QuestService()

        with pytest.raises(ValueError, match="not yet completed"):
            svc.claim_reward(user, uq)

    @allure.story("Raises ValueError when reward already claimed")
    @allure.severity(allure.severity_level.NORMAL)
    def test_raises_if_already_rewarded(self):
        user = UserFactory()
        tmpl = QuestTemplateFactory()
        uq = UserQuestFactory(user=user, template=tmpl, completed=True, rewarded=True,
                               period_key=_daily_period_key())
        svc = QuestService()

        with pytest.raises(ValueError, match="already been claimed"):
            svc.claim_reward(user, uq)
