"""
Management command: seed_quests

Populates QuestTemplate with the daily/weekly/story missions from GDD Section 14.
Safe to re-run — uses get_or_create on the name field.

Usage:
    python manage.py seed_quests
"""
from django.core.management.base import BaseCommand

from apps.quests.models import QuestCondition, QuestTemplate, QuestType, RewardType

_TEMPLATES: list[dict] = [
    # ── Daily Missions ────────────────────────────────────────────────────────
    {
        "name": "First Victory",
        "description": "Win 1 battle today.",
        "quest_type": QuestType.DAILY,
        "condition": QuestCondition.WIN_BATTLES,
        "condition_value": 1,
        "reward_type": RewardType.RYO,
        "reward_value": 250,
        "reward_dust": 0,
        "order": 1,
    },
    {
        "name": "Back-to-Back",
        "description": "Win 2 battles today.",
        "quest_type": QuestType.DAILY,
        "condition": QuestCondition.WIN_BATTLES,
        "condition_value": 2,
        "reward_type": RewardType.RYO,
        "reward_value": 400,
        "reward_dust": 0,
        "order": 2,
    },
    {
        "name": "Chain Novice",
        "description": "Achieve a 3-link combo chain in a single battle.",
        "quest_type": QuestType.DAILY,
        "condition": QuestCondition.ACHIEVE_COMBO,
        "condition_value": 3,
        "reward_type": RewardType.RYO,
        "reward_value": 300,
        "reward_dust": 20,
        "order": 3,
    },
    {
        "name": "Pack Hunter",
        "description": "Open 1 sticker pack.",
        "quest_type": QuestType.DAILY,
        "condition": QuestCondition.OPEN_PACKS,
        "condition_value": 1,
        "reward_type": RewardType.RYO,
        "reward_value": 100,
        "reward_dust": 0,
        "order": 4,
    },
    {
        "name": "Triple Threat",
        "description": "Win 3 battles today.",
        "quest_type": QuestType.DAILY,
        "condition": QuestCondition.WIN_BATTLES,
        "condition_value": 3,
        "reward_type": RewardType.RYO,
        "reward_value": 500,
        "reward_dust": 0,
        "order": 5,
    },
    {
        "name": "Chain Adept",
        "description": "Achieve a 5-link combo chain in a single battle.",
        "quest_type": QuestType.DAILY,
        "condition": QuestCondition.ACHIEVE_COMBO,
        "condition_value": 5,
        "reward_type": RewardType.STICKER_DUST,
        "reward_value": 50,
        "reward_dust": 0,
        "order": 6,
    },
    {
        "name": "Double Pack Day",
        "description": "Open 2 sticker packs.",
        "quest_type": QuestType.DAILY,
        "condition": QuestCondition.OPEN_PACKS,
        "condition_value": 2,
        "reward_type": RewardType.RYO,
        "reward_value": 200,
        "reward_dust": 0,
        "order": 7,
    },
    {
        "name": "Winning Streak",
        "description": "Win 4 battles today.",
        "quest_type": QuestType.DAILY,
        "condition": QuestCondition.WIN_BATTLES,
        "condition_value": 4,
        "reward_type": RewardType.STICKER_DUST,
        "reward_value": 30,
        "reward_dust": 0,
        "order": 8,
    },
    # ── Weekly Challenges ─────────────────────────────────────────────────────
    {
        "name": "Battle Veteran",
        "description": "Win 5 battles this week.",
        "quest_type": QuestType.WEEKLY,
        "condition": QuestCondition.WIN_BATTLES,
        "condition_value": 5,
        "reward_type": RewardType.RYO,
        "reward_value": 2000,
        "reward_dust": 0,
        "order": 1,
    },
    {
        "name": "Kizuna Master",
        "description": "Achieve a 6-link combo chain in a single battle.",
        "quest_type": QuestType.WEEKLY,
        "condition": QuestCondition.ACHIEVE_COMBO,
        "condition_value": 6,
        "reward_type": RewardType.RYO,
        "reward_value": 3000,
        "reward_dust": 0,
        "order": 2,
    },
    {
        "name": "Pack Enthusiast",
        "description": "Open 3 sticker packs this week.",
        "quest_type": QuestType.WEEKLY,
        "condition": QuestCondition.OPEN_PACKS,
        "condition_value": 3,
        "reward_type": RewardType.STICKER_PACK,
        "reward_value": 1,
        "reward_dust": 0,
        "order": 3,
    },
    {
        "name": "Undefeated",
        "description": "Win 10 battles this week.",
        "quest_type": QuestType.WEEKLY,
        "condition": QuestCondition.WIN_BATTLES,
        "condition_value": 10,
        "reward_type": RewardType.RYO,
        "reward_value": 5000,
        "reward_dust": 100,
        "order": 4,
    },
    # ── Story Quests — Act 1: The Foundation ─────────────────────────────────
    {
        "name": "First Steps",
        "description": "Win your first battle. Every legend has a beginning.",
        "quest_type": QuestType.STORY,
        "condition": QuestCondition.WIN_BATTLES,
        "condition_value": 1,
        "reward_type": RewardType.STICKER_PACK,
        "reward_value": 1,
        "reward_dust": 0,
        "order": 1,
        "chapter": "prologue",
        "narrative_text": (
            "Sensei Kira: \"You have arrived at last. I sensed your potential the moment "
            "you stepped off the ferry. The Kizuna Method is not simply a technique — it "
            "is a bond. Win your first battle and show me you are ready to learn.\""
        ),
    },
    {
        "name": "Chain Initiation",
        "description": "Achieve a 2-link combo chain. Feel the Kizuna Method.",
        "quest_type": QuestType.STORY,
        "condition": QuestCondition.ACHIEVE_COMBO,
        "condition_value": 2,
        "reward_type": RewardType.RYO,
        "reward_value": 500,
        "reward_dust": 0,
        "order": 2,
        "chapter": "prologue",
        "narrative_text": (
            "Sensei Kira: \"Do you feel it? That moment when your Pokemon's status "
            "resonated with their teammate's trigger — that is the Kizuna. Two hearts, "
            "one chain. Now chain them again, deeper.\""
        ),
    },
    {
        "name": "The Academy Trials",
        "description": "Win 5 battles to prove yourself among your academy classmates.",
        "quest_type": QuestType.STORY,
        "condition": QuestCondition.WIN_BATTLES,
        "condition_value": 5,
        "reward_type": RewardType.RYO,
        "reward_value": 1500,
        "reward_dust": 50,
        "order": 3,
        "chapter": "act_1",
        "narrative_text": (
            "Shin: \"You think the Kizuna Method is impressive? It is nothing but "
            "a cheap trick. Raw power always wins in the end.\" "
            "— Prove him wrong. Win five battles and show that bonds matter."
        ),
    },
    {
        "name": "Academy Qualifier",
        "description": "Achieve a 5-link combo chain — execute it in the qualifier battle.",
        "quest_type": QuestType.STORY,
        "condition": QuestCondition.ACHIEVE_COMBO,
        "condition_value": 5,
        "reward_type": RewardType.STICKER_PACK,
        "reward_value": 1,
        "reward_dust": 0,
        "order": 4,
        "chapter": "act_1",
        "narrative_text": (
            "Sensei Kira: \"The Academy Qualifier is your first real test. Every student "
            "watches. Shin watches. Execute a five-link Kizuna chain and silence the "
            "doubters. Show them what a true bond looks like.\""
        ),
    },
    {
        "name": "Chain of Ten",
        "description": "Achieve a 10-link combo chain — the ultimate Kizuna.",
        "quest_type": QuestType.STORY,
        "condition": QuestCondition.ACHIEVE_COMBO,
        "condition_value": 10,
        "reward_type": RewardType.STICKER_DUST,
        "reward_value": 500,
        "reward_dust": 0,
        "order": 5,
        "chapter": "act_1_climax",
        "narrative_text": (
            "Sensei Kira: \"Ten links. I have not seen a chain that long since my own "
            "championship days. You have surpassed what I thought possible for a student "
            "of your age. The Kizuna is no longer a technique — it is who you are.\""
        ),
    },
]


class Command(BaseCommand):
    help = "Seed QuestTemplate data from the GDD (Section 14). Safe to re-run."

    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0

        for data in _TEMPLATES:
            name = data.pop("name")
            obj, created = QuestTemplate.objects.get_or_create(
                name=name,
                defaults=data,
            )
            if created:
                created_count += 1
            else:
                # Update fields in case values changed
                for field, value in data.items():
                    setattr(obj, field, value)
                obj.save()
                updated_count += 1
            data["name"] = name  # restore for idempotency if called again

        self.stdout.write(
            self.style.SUCCESS(
                f"Quest templates seeded: {created_count} created, {updated_count} updated."
            )
        )
