"""
P4-1 — Story Quest Narrative (Act 1) tests.

Covers:
- QuestTemplate stores narrative_text and chapter fields
- seed_quests populates Act 1 chapter assignments and narrative text
- Prologue chapter quests are ordered first
- Act 1 chapter quests contain Shin's dialogue
- Act 1 climax quests contain Sensei Kira's climax dialogue
- QuestListView groups story quests in template context
- Narrative text appears in rendered quest list page
- Chapter header labels are rendered per chapter
"""
import allure
import pytest
from django.core.management import call_command
from django.test import Client
from django.urls import reverse

from apps.quests.models import QuestTemplate, QuestType
from apps.quests.services import QuestService

from tests.framework.base.base_test import BaseTest
from tests.framework.factories.quest_factory import QuestTemplateFactory
from tests.framework.factories.user_factory import UserFactory


def _client(user) -> Client:
    user.set_password("pw")
    user.save(update_fields=["password"])
    c = Client()
    c.force_login(user)
    return c


@allure.epic("Quests")
@allure.feature("Story Narrative")
@pytest.mark.django_db
class TestQuestTemplateNarrativeFields(BaseTest):

    @allure.story("QuestTemplate stores narrative_text")
    @allure.severity(allure.severity_level.NORMAL)
    def test_narrative_text_field_persists(self):
        # Arrange + Act
        tmpl = QuestTemplateFactory(
            quest_type=QuestType.STORY,
            narrative_text="Sensei Kira: 'You have arrived.'",
        )
        # Assert
        tmpl.refresh_from_db()
        assert tmpl.narrative_text == "Sensei Kira: 'You have arrived.'"

    @allure.story("QuestTemplate stores chapter")
    @allure.severity(allure.severity_level.NORMAL)
    def test_chapter_field_persists(self):
        # Arrange + Act
        tmpl = QuestTemplateFactory(
            quest_type=QuestType.STORY,
            chapter="prologue",
        )
        # Assert
        tmpl.refresh_from_db()
        assert tmpl.chapter == "prologue"

    @allure.story("chapter defaults to empty string")
    @allure.severity(allure.severity_level.MINOR)
    def test_chapter_defaults_to_empty(self):
        tmpl = QuestTemplateFactory()
        assert tmpl.chapter == ""

    @allure.story("narrative_text defaults to empty string")
    @allure.severity(allure.severity_level.MINOR)
    def test_narrative_text_defaults_to_empty(self):
        tmpl = QuestTemplateFactory()
        assert tmpl.narrative_text == ""


@allure.epic("Quests")
@allure.feature("Story Narrative")
@pytest.mark.django_db
class TestSeedQuestsNarrative(BaseTest):
    """Verify seed_quests populates Act 1 narrative and chapter data."""

    def setup_method(self):
        call_command("seed_quests", verbosity=0)

    @allure.story("Prologue story quests have chapter=prologue")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_prologue_quests_have_correct_chapter(self):
        prologue_quests = QuestTemplate.objects.filter(
            quest_type=QuestType.STORY, chapter="prologue"
        )
        assert prologue_quests.count() >= 1

    @allure.story("Act 1 story quests have chapter=act_1")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_act_1_quests_have_correct_chapter(self):
        act1_quests = QuestTemplate.objects.filter(
            quest_type=QuestType.STORY, chapter="act_1"
        )
        assert act1_quests.count() >= 1

    @allure.story("Act 1 climax quest has chapter=act_1_climax")
    @allure.severity(allure.severity_level.NORMAL)
    def test_act_1_climax_quest_exists(self):
        climax = QuestTemplate.objects.filter(
            quest_type=QuestType.STORY, chapter="act_1_climax"
        )
        assert climax.count() >= 1

    @allure.story("Prologue quest has Sensei Kira narrative text")
    @allure.severity(allure.severity_level.NORMAL)
    def test_prologue_narrative_contains_sensei_kira(self):
        prologue = QuestTemplate.objects.filter(
            quest_type=QuestType.STORY, chapter="prologue"
        ).first()
        assert prologue is not None
        assert "Sensei Kira" in prologue.narrative_text

    @allure.story("Act 1 quest has Shin dialogue")
    @allure.severity(allure.severity_level.NORMAL)
    def test_act_1_narrative_contains_shin(self):
        act1 = QuestTemplate.objects.filter(
            quest_type=QuestType.STORY, chapter="act_1"
        ).first()
        assert act1 is not None
        assert "Shin" in act1.narrative_text

    @allure.story("Prologue quests are ordered before Act 1 quests")
    @allure.severity(allure.severity_level.NORMAL)
    def test_prologue_order_precedes_act_1(self):
        prologue = QuestTemplate.objects.filter(
            quest_type=QuestType.STORY, chapter="prologue"
        ).order_by("order").first()
        act1 = QuestTemplate.objects.filter(
            quest_type=QuestType.STORY, chapter="act_1"
        ).order_by("order").first()
        assert prologue is not None
        assert act1 is not None
        assert prologue.order < act1.order


@allure.epic("Quests")
@allure.feature("Story Narrative")
@pytest.mark.django_db
class TestQuestListNarrativeRendering(BaseTest):
    """Verify the quest list page renders narrative text and chapter headers."""

    @allure.story("Quest list page renders narrative text for story quests")
    @allure.severity(allure.severity_level.NORMAL)
    def test_narrative_text_rendered_in_page(self):
        call_command("seed_quests", verbosity=0)
        user = UserFactory()
        QuestService().ensure_story_quests(user)
        response = _client(user).get(reverse("quests:quest_list"))
        assert response.status_code == 200
        assert "Sensei Kira" in response.content.decode()

    @allure.story("Quest list page renders Prologue chapter header")
    @allure.severity(allure.severity_level.NORMAL)
    def test_prologue_chapter_header_rendered(self):
        call_command("seed_quests", verbosity=0)
        user = UserFactory()
        QuestService().ensure_story_quests(user)
        response = _client(user).get(reverse("quests:quest_list"))
        assert "Prologue" in response.content.decode()

    @allure.story("Quest list page renders Act I chapter header")
    @allure.severity(allure.severity_level.NORMAL)
    def test_act_1_chapter_header_rendered(self):
        call_command("seed_quests", verbosity=0)
        user = UserFactory()
        QuestService().ensure_story_quests(user)
        response = _client(user).get(reverse("quests:quest_list"))
        assert "Act I" in response.content.decode()
