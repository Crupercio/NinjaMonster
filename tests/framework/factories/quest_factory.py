"""factory_boy factories for QuestTemplate and UserQuest."""
import factory

from apps.quests.models import (
    QuestCondition,
    QuestTemplate,
    QuestType,
    RewardType,
    UserQuest,
)


class QuestTemplateFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = QuestTemplate

    name = factory.Sequence(lambda n: f"Quest Template {n}")
    description = ""
    quest_type = QuestType.DAILY
    condition = QuestCondition.WIN_BATTLES
    condition_value = 1
    reward_type = RewardType.RYO
    reward_value = 250
    reward_dust = 0
    reward_candy_type = ""
    reward_candy_qty = 0
    is_active = True
    order = 0
    chapter = ""
    narrative_text = ""
    condition_meta = factory.LazyFunction(dict)

    class Params:
        daily = factory.Trait(quest_type=QuestType.DAILY)
        weekly = factory.Trait(quest_type=QuestType.WEEKLY)
        story = factory.Trait(quest_type=QuestType.STORY, order=factory.Sequence(lambda n: n))
        win_battles = factory.Trait(condition=QuestCondition.WIN_BATTLES)
        achieve_combo = factory.Trait(condition=QuestCondition.ACHIEVE_COMBO)
        open_packs = factory.Trait(condition=QuestCondition.OPEN_PACKS)


class UserQuestFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = UserQuest

    user = factory.SubFactory("tests.framework.factories.user_factory.UserFactory")
    template = factory.SubFactory(QuestTemplateFactory)
    period_key = "daily:2026-04-07"
    progress = 0
    progress_meta = factory.LazyFunction(dict)
    completed = False
    rewarded = False
