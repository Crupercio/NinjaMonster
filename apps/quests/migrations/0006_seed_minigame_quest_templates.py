"""Seed QuestTemplate rows for all three mini-games.

Creates daily, weekly, and story quests for:
  - PLAY_SILHOUETTE (Silhouette Tower)
  - PLAY_MEMORY    (Sticker Memory)
  - PLAY_LOTERIA   (Pokemon Loteria)

Safe to run multiple times — uses get_or_create keyed on (name, quest_type, condition).
"""

from django.db import migrations


TEMPLATES = [
    # ── DAILY ────────────────────────────────────────────────────────────────
    {
        "name": "Tower Scout",
        "description": "Play 1 Silhouette Tower run today.",
        "quest_type": "daily",
        "condition": "play_silhouette",
        "condition_value": 1,
        "reward_type": "ryo",
        "reward_value": 400,
        "reward_dust": 5,
        "reward_candy_type": "",
        "reward_candy_qty": 0,
        "order": 10,
        "chapter": "",
        "narrative_text": "",
    },
    {
        "name": "Memory Warm-Up",
        "description": "Clear 1 Memory board today.",
        "quest_type": "daily",
        "condition": "play_memory",
        "condition_value": 1,
        "reward_type": "ryo",
        "reward_value": 350,
        "reward_dust": 5,
        "reward_candy_type": "trail_mix",
        "reward_candy_qty": 1,
        "order": 11,
        "chapter": "",
        "narrative_text": "",
    },
    {
        "name": "Loteria Round",
        "description": "Play 1 Loteria round today.",
        "quest_type": "daily",
        "condition": "play_loteria",
        "condition_value": 1,
        "reward_type": "ryo",
        "reward_value": 300,
        "reward_dust": 8,
        "reward_candy_type": "",
        "reward_candy_qty": 0,
        "order": 12,
        "chapter": "",
        "narrative_text": "",
    },
    # ── DAILY (higher targets) ────────────────────────────────────────────────
    {
        "name": "Tower Climber",
        "description": "Play 3 Silhouette Tower runs today.",
        "quest_type": "daily",
        "condition": "play_silhouette",
        "condition_value": 3,
        "reward_type": "ryo",
        "reward_value": 900,
        "reward_dust": 12,
        "reward_candy_type": "",
        "reward_candy_qty": 0,
        "order": 13,
        "chapter": "",
        "narrative_text": "",
    },
    {
        "name": "Memory Streak",
        "description": "Clear 3 Memory boards today.",
        "quest_type": "daily",
        "condition": "play_memory",
        "condition_value": 3,
        "reward_type": "ryo",
        "reward_value": 800,
        "reward_dust": 15,
        "reward_candy_type": "trail_mix",
        "reward_candy_qty": 2,
        "order": 14,
        "chapter": "",
        "narrative_text": "",
    },
    {
        "name": "Loteria Night",
        "description": "Play 3 Loteria rounds today.",
        "quest_type": "daily",
        "condition": "play_loteria",
        "condition_value": 3,
        "reward_type": "ryo",
        "reward_value": 750,
        "reward_dust": 18,
        "reward_candy_type": "",
        "reward_candy_qty": 0,
        "order": 15,
        "chapter": "",
        "narrative_text": "",
    },
    # ── WEEKLY ────────────────────────────────────────────────────────────────
    {
        "name": "Floor Grinder",
        "description": "Complete 10 Silhouette Tower runs this week.",
        "quest_type": "weekly",
        "condition": "play_silhouette",
        "condition_value": 10,
        "reward_type": "ryo",
        "reward_value": 3500,
        "reward_dust": 40,
        "reward_candy_type": "sweet_berry",
        "reward_candy_qty": 2,
        "order": 20,
        "chapter": "",
        "narrative_text": "",
    },
    {
        "name": "Board Master",
        "description": "Clear 10 Memory boards this week.",
        "quest_type": "weekly",
        "condition": "play_memory",
        "condition_value": 10,
        "reward_type": "ryo",
        "reward_value": 3000,
        "reward_dust": 50,
        "reward_candy_type": "sweet_berry",
        "reward_candy_qty": 3,
        "order": 21,
        "chapter": "",
        "narrative_text": "",
    },
    {
        "name": "Loteria Regular",
        "description": "Play 10 Loteria rounds this week.",
        "quest_type": "weekly",
        "condition": "play_loteria",
        "condition_value": 10,
        "reward_type": "ryo",
        "reward_value": 2800,
        "reward_dust": 45,
        "reward_candy_type": "",
        "reward_candy_qty": 0,
        "order": 22,
        "chapter": "",
        "narrative_text": "",
    },
    {
        "name": "Arcade Week",
        "description": "Play at least 5 runs across all three mini-games this week.",
        "quest_type": "weekly",
        "condition": "play_silhouette",
        "condition_value": 5,
        "reward_type": "sticker_pack",
        "reward_value": 1,
        "reward_dust": 30,
        "reward_candy_type": "golden_apple",
        "reward_candy_qty": 1,
        "order": 23,
        "chapter": "",
        "narrative_text": "",
    },
    # ── STORY ────────────────────────────────────────────────────────────────
    {
        "name": "First Step into the Tower",
        "description": "Play your first Silhouette Tower run.",
        "quest_type": "story",
        "condition": "play_silhouette",
        "condition_value": 1,
        "reward_type": "ryo",
        "reward_value": 500,
        "reward_dust": 10,
        "reward_candy_type": "",
        "reward_candy_qty": 0,
        "order": 30,
        "chapter": "prologue",
        "narrative_text": (
            "The tower looms at the edge of the Fun Lane. "
            "Silhouettes flicker on the screen — each one a Pokemon waiting to be named. "
            "Step up. The first floor is yours."
        ),
    },
    {
        "name": "Memory Initiated",
        "description": "Clear your first Memory board.",
        "quest_type": "story",
        "condition": "play_memory",
        "condition_value": 1,
        "reward_type": "ryo",
        "reward_value": 500,
        "reward_dust": 10,
        "reward_candy_type": "trail_mix",
        "reward_candy_qty": 1,
        "order": 31,
        "chapter": "prologue",
        "narrative_text": (
            "Biscuit sets out the cards. "
            "\"The grid doesn't lie,\" she says. \"Remember what you saw.\" "
            "Flip your first pair and prove your memory."
        ),
    },
    {
        "name": "¡Lotería!",
        "description": "Play your first Loteria round.",
        "quest_type": "story",
        "condition": "play_loteria",
        "condition_value": 1,
        "reward_type": "ryo",
        "reward_value": 500,
        "reward_dust": 10,
        "reward_candy_type": "",
        "reward_candy_qty": 0,
        "order": 32,
        "chapter": "prologue",
        "narrative_text": (
            "The caller takes the deck. The room fills. "
            "Your tabla is ready — every space a Pokemon waiting to be called. "
            "Listen. Mark. Win."
        ),
    },
    {
        "name": "Tower Veteran",
        "description": "Complete 20 Silhouette Tower runs total.",
        "quest_type": "story",
        "condition": "play_silhouette",
        "condition_value": 20,
        "reward_type": "sticker_pack",
        "reward_value": 1,
        "reward_dust": 50,
        "reward_candy_type": "sweet_berry",
        "reward_candy_qty": 2,
        "order": 40,
        "chapter": "act_1",
        "narrative_text": (
            "Twenty runs. You've climbed the Rookie floors and pushed into the Regional bracket. "
            "The silhouettes are sharper now — or maybe your eyes are."
        ),
    },
    {
        "name": "Collector's Memory",
        "description": "Clear 15 Memory boards total.",
        "quest_type": "story",
        "condition": "play_memory",
        "condition_value": 15,
        "reward_type": "sticker_pack",
        "reward_value": 1,
        "reward_dust": 40,
        "reward_candy_type": "sweet_berry",
        "reward_candy_qty": 1,
        "order": 41,
        "chapter": "act_1",
        "narrative_text": (
            "Fifteen clears. Rex watches from the corner. "
            "\"You've earned the Collector board,\" he says. \"Don't waste it.\""
        ),
    },
    {
        "name": "Loteria Devotee",
        "description": "Play 20 Loteria rounds total.",
        "quest_type": "story",
        "condition": "play_loteria",
        "condition_value": 20,
        "reward_type": "sticker_pack",
        "reward_value": 1,
        "reward_dust": 40,
        "reward_candy_type": "",
        "reward_candy_qty": 0,
        "order": 42,
        "chapter": "act_1",
        "narrative_text": (
            "Twenty rounds. You know the caller's rhythm now. "
            "You don't watch the card — you listen for the name."
        ),
    },
]


def seed_templates(apps, schema_editor):
    QuestTemplate = apps.get_model("quests", "QuestTemplate")
    created = 0
    for data in TEMPLATES:
        obj, was_created = QuestTemplate.objects.get_or_create(
            name=data["name"],
            quest_type=data["quest_type"],
            condition=data["condition"],
            defaults={k: v for k, v in data.items() if k not in ("name", "quest_type", "condition")},
        )
        if was_created:
            created += 1


def unseed_templates(apps, schema_editor):
    QuestTemplate = apps.get_model("quests", "QuestTemplate")
    names = [d["name"] for d in TEMPLATES]
    QuestTemplate.objects.filter(name__in=names).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("quests", "0005_add_minigame_quest_conditions"),
    ]

    operations = [
        migrations.RunPython(seed_templates, reverse_code=unseed_templates),
    ]
