"""
Achievement catalog and claim logic.

All one-time achievements live here. Rewards are credited only when
the player explicitly claims them from the Achievements page.
"""
import logging
from datetime import datetime, timezone
from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction

logger = logging.getLogger(__name__)

User = get_user_model()

# ---------------------------------------------------------------------------
# Catalog definition
# ---------------------------------------------------------------------------

ACHIEVEMENT_CATALOG: list[dict[str, Any]] = [
    # ── Album ───────────────────────────────────────────────────────────────
    {
        "key": "album_pokemon_complete",
        "title": "Pokémon Master",
        "description": "Collect every rarity & variant for any single Pokémon.",
        "ryo_reward": 200_000,
        "icon": "⭐",
        "category": "album",
        "claimable_from_album": True,
    },
    {
        "key": "album_full_dex",
        "title": "Full Pokédex",
        "description": "Complete every Pokémon in the Pokédex (all 905).",
        "ryo_reward": 1_000_000,
        "icon": "🏆",
        "category": "album",
        "claimable_from_album": True,
    },
    {
        "key": "album_prismatic_page",
        "title": "Prismatic Page",
        "description": "Complete a Prismatic regional album page.",
        "ryo_reward": 100_000,
        "icon": "💎",
        "category": "album",
        "claimable_from_album": True,
    },
    {
        "key": "album_full_art_page",
        "title": "Full Art Page",
        "description": "Complete a Full Art regional album page.",
        "ryo_reward": 250_000,
        "icon": "🎨",
        "category": "album",
        "claimable_from_album": True,
    },
    {
        "key": "album_secret_rare_page",
        "title": "Secret Rare Page",
        "description": "Complete a Secret Rare regional album page.",
        "ryo_reward": 500_000,
        "icon": "🌟",
        "category": "album",
        "claimable_from_album": True,
    },
    # ── Memory ───────────────────────────────────────────────────────────────
    {
        "key": "memory_rookie",
        "title": "Memory Rookie",
        "description": "Clear the Rookie memory board (3×4).",
        "ryo_reward": 500,
        "icon": "🃏",
        "category": "memory",
    },
    {
        "key": "memory_standard",
        "title": "Memory Standard",
        "description": "Clear the Standard memory board (4×4).",
        "ryo_reward": 1_000,
        "icon": "🃏",
        "category": "memory",
    },
    {
        "key": "memory_collector",
        "title": "Memory Collector",
        "description": "Clear the Collector memory board (5×4).",
        "ryo_reward": 2_500,
        "icon": "🃏",
        "category": "memory",
    },
    {
        "key": "memory_master",
        "title": "Memory Master",
        "description": "Clear the Master memory board (6×4).",
        "ryo_reward": 10_000,
        "icon": "👑",
        "category": "memory",
    },
    {
        "key": "memory_perfect",
        "title": "Perfect Memory",
        "description": "Earn a Perfect grade on any memory board.",
        "ryo_reward": 5_000,
        "icon": "✨",
        "category": "memory",
    },
    # ── Silhouette Tower ─────────────────────────────────────────────────────
    {
        "key": "silhouette_rookie_clear",
        "title": "Rookie Climber",
        "description": "Clear all 25 floors of the Rookie Silhouette Tower.",
        "ryo_reward": 2_000,
        "icon": "🗼",
        "category": "silhouette",
    },
    {
        "key": "silhouette_regional_clear",
        "title": "Regional Climber",
        "description": "Clear all 100 floors of a Regional Silhouette Tower.",
        "ryo_reward": 20_000,
        "icon": "🗼",
        "category": "silhouette",
    },
    {
        "key": "silhouette_master_clear",
        "title": "Master Climber",
        "description": "Clear all 500 floors of the Master Silhouette Tower.",
        "ryo_reward": 100_000,
        "icon": "🏔️",
        "category": "silhouette",
    },
    {
        "key": "silhouette_national_clear",
        "title": "National Champion",
        "description": "Clear all 905 floors of the National Silhouette Tower.",
        "ryo_reward": 500_000,
        "icon": "🌍",
        "category": "silhouette",
    },
    # ── Loteria ───────────────────────────────────────────────────────────────
    {
        "key": "loteria_first_win",
        "title": "Lucky Card",
        "description": "Win your first Lotería pattern.",
        "ryo_reward": 1_000,
        "icon": "🎴",
        "category": "loteria",
    },
    {
        "key": "loteria_full_board",
        "title": "¡Buena!",
        "description": "Win a full board in Lotería.",
        "ryo_reward": 10_000,
        "icon": "🎉",
        "category": "loteria",
    },
    # ── Login Streak ──────────────────────────────────────────────────────────
    {
        "key": "streak_7",
        "title": "Weekly Devotee",
        "description": "Claim your daily reward 7 days in a row.",
        "ryo_reward": 2_000,
        "icon": "📅",
        "category": "streak",
    },
    {
        "key": "streak_30",
        "title": "Monthly Legend",
        "description": "Claim your daily reward 30 days in a row.",
        "ryo_reward": 10_000,
        "icon": "🗓️",
        "category": "streak",
    },
    # ── Trade ─────────────────────────────────────────────────────────────────
    {
        "key": "first_trade",
        "title": "First Trade",
        "description": "Complete your first sticker trade.",
        "ryo_reward": 500,
        "icon": "🤝",
        "category": "social",
    },
    {
        "key": "trades_10",
        "title": "Trader",
        "description": "Complete 10 sticker trades.",
        "ryo_reward": 5_000,
        "icon": "🤝",
        "category": "social",
    },
    # ── Sticker crafting ─────────────────────────────────────────────────────
    {
        "key": "first_craft",
        "title": "Artisan",
        "description": "Craft your first sticker.",
        "ryo_reward": 1_000,
        "icon": "⚒️",
        "category": "crafting",
    },
    {
        "key": "first_dismantle",
        "title": "Dust Collector",
        "description": "Dismantle your first sticker.",
        "ryo_reward": 500,
        "icon": "💨",
        "category": "crafting",
    },
    # ── Guild ─────────────────────────────────────────────────────────────────
    {
        "key": "join_guild",
        "title": "Guild Member",
        "description": "Join a guild.",
        "ryo_reward": 500,
        "icon": "🏛️",
        "category": "guild",
    },
    {
        "key": "guild_quest",
        "title": "Guild Contributor",
        "description": "Complete a guild quest.",
        "ryo_reward": 2_000,
        "icon": "📜",
        "category": "guild",
    },
]

_CATALOG_BY_KEY: dict[str, dict[str, Any]] = {a["key"]: a for a in ACHIEVEMENT_CATALOG}

CATEGORY_ORDER = ["album", "memory", "silhouette", "loteria", "streak", "social", "crafting", "guild"]
CATEGORY_LABELS = {
    "album": "Album",
    "memory": "Memory",
    "silhouette": "Silhouette Tower",
    "loteria": "Lotería",
    "streak": "Login Streak",
    "social": "Trading",
    "crafting": "Crafting",
    "guild": "Guild",
}


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class AchievementService:

    def earn(self, user: User, key: str) -> bool:
        """
        Record that a player has earned an achievement.

        Creates the GameAchievement row (pending claim) if it doesn't exist.
        Returns True if newly earned, False if already existed.
        """
        from apps.users.models import GameAchievement

        if key not in _CATALOG_BY_KEY:
            logger.warning("Unknown achievement key: %s", key)
            return False

        ryo = _CATALOG_BY_KEY[key]["ryo_reward"]
        _, created = GameAchievement.objects.get_or_create(
            user=user,
            key=key,
            defaults={"ryo_reward": ryo},
        )
        if created:
            logger.info("Achievement earned: user=%s key=%s ryo=%d", user, key, ryo)
        return created

    @transaction.atomic
    def claim(self, user: User, key: str) -> int:
        """
        Claim a pending GameAchievement and credit ryo.

        Returns ryo awarded (0 if already claimed or not earned).
        """
        from apps.users.models import GameAchievement

        ach = (
            GameAchievement.objects
            .select_for_update()
            .filter(user=user, key=key, claimed_at__isnull=True)
            .first()
        )
        if ach is None:
            return 0

        from django.db.models import F

        ach.claimed_at = datetime.now(tz=timezone.utc)
        ach.save(update_fields=["claimed_at"])
        User.objects.filter(pk=user.pk).update(ryo=F("ryo") + ach.ryo_reward)
        logger.info("Achievement claimed: user=%s key=%s ryo=%d", user, key, ach.ryo_reward)
        return ach.ryo_reward

    @transaction.atomic
    def claim_all(self, user: User) -> tuple[int, int]:
        """
        Claim all pending GameAchievements for user.

        Returns (count_claimed, total_ryo).
        """
        from apps.users.models import GameAchievement
        from django.db.models import F, Sum

        now = datetime.now(tz=timezone.utc)
        pending = list(
            GameAchievement.objects
            .select_for_update()
            .filter(user=user, claimed_at__isnull=True)
        )
        if not pending:
            return 0, 0

        total_ryo = sum(a.ryo_reward for a in pending)
        GameAchievement.objects.filter(
            pk__in=[a.pk for a in pending]
        ).update(claimed_at=now)

        user.__class__.objects.filter(pk=user.pk).update(ryo=F("ryo") + total_ryo)
        logger.info(
            "Claim all achievements: user=%s count=%d ryo=%d",
            user, len(pending), total_ryo,
        )
        return len(pending), total_ryo

    def get_all_for_user(self, user: User) -> list[dict[str, Any]]:
        """
        Return all achievements with earned/claimed state for a user.

        Also includes album completion rewards as achievement entries.
        """
        from apps.users.models import GameAchievement
        from apps.stickers.models import AlbumCompletionReward, AlbumRewardType

        earned_map: dict[str, "GameAchievement"] = {
            a.key: a for a in GameAchievement.objects.filter(user=user)
        }

        # Album completion rewards (pokemon_complete counted as one if any exist)
        album_rewards = list(AlbumCompletionReward.objects.filter(user=user).select_related("pokemon"))
        album_keys_earned: set[str] = set()

        for reward in album_rewards:
            if reward.reward_type == AlbumRewardType.POKEMON_COMPLETE:
                key = "album_pokemon_complete"
            else:
                key = "album_full_dex"
            album_keys_earned.add(key)
            # claimed_at is auto_now_add so always set — these are always auto-claimed

        # Regional page rewards
        from apps.stickers.models import RegionalAlbumPage, StickerRarity
        prismatic_complete = RegionalAlbumPage.objects.filter(
            user=user, rarity=StickerRarity.PRISMATIC, reward_claimed=True
        ).exists()
        full_art_complete = RegionalAlbumPage.objects.filter(
            user=user, rarity=StickerRarity.FULL_ART, reward_claimed=True
        ).exists()
        secret_rare_complete = RegionalAlbumPage.objects.filter(
            user=user, rarity=StickerRarity.SECRET_RARE, reward_claimed=True
        ).exists()
        if prismatic_complete:
            album_keys_earned.add("album_prismatic_page")
        if full_art_complete:
            album_keys_earned.add("album_full_art_page")
        if secret_rare_complete:
            album_keys_earned.add("album_secret_rare_page")

        result = []
        for entry in ACHIEVEMENT_CATALOG:
            key = entry["key"]
            game_ach = earned_map.get(key)
            is_album = entry.get("claimable_from_album")

            if is_album:
                earned = key in album_keys_earned
                claimed = earned  # album rewards are auto-credited on earn
                pending_ryo = 0
            else:
                earned = game_ach is not None
                claimed = earned and game_ach.claimed_at is not None
                pending_ryo = game_ach.ryo_reward if earned and not claimed else 0

            result.append({
                **entry,
                "earned": earned,
                "claimed": claimed,
                "pending_ryo": pending_ryo,
                "game_achievement": game_ach,
            })

        return result

    def backfill_state_based(self, user: User) -> None:
        """
        Check current user state and auto-earn any achievements that are
        already satisfied but were never triggered (e.g. pre-system guild join,
        existing streak, existing trades). Safe to call on every page load —
        get_or_create is a no-op when already earned.
        """
        # Guild membership
        try:
            if hasattr(user, "guild_membership") and user.guild_membership is not None:
                self.earn(user, "join_guild")
        except Exception:
            pass

        # Guild membership via DB query (safer)
        try:
            from apps.guilds.models import GuildMembership
            if GuildMembership.objects.filter(user=user).exists():
                self.earn(user, "join_guild")
        except Exception:
            pass

        # Guild quests completed on membership model
        try:
            from apps.guilds.models import GuildMembership
            membership = GuildMembership.objects.filter(user=user).first()
            if membership and membership.guild_quests_completed >= 1:
                self.earn(user, "guild_quest")
        except Exception:
            pass

        # Login streak
        streak = getattr(user, "daily_claim_streak", 0) or 0
        if streak >= 7:
            self.earn(user, "streak_7")
        if streak >= 30:
            self.earn(user, "streak_30")

        # Trades
        trades = getattr(user, "trades_completed", 0) or 0
        if trades >= 1:
            self.earn(user, "first_trade")
        if trades >= 10:
            self.earn(user, "trades_10")

        # Album completions — check AlbumCompletionReward
        try:
            from apps.stickers.models import AlbumCompletionReward, AlbumRewardType
            if AlbumCompletionReward.objects.filter(user=user, reward_type=AlbumRewardType.POKEMON_COMPLETE).exists():
                self.earn(user, "album_pokemon_complete")
            if AlbumCompletionReward.objects.filter(user=user, reward_type=AlbumRewardType.FULL_DEX).exists():
                self.earn(user, "album_full_dex")
        except Exception:
            pass

        # Regional page completions (prismatic/full_art/secret_rare)
        try:
            from apps.stickers.models import RegionalAlbumPage, StickerRarity
            if RegionalAlbumPage.objects.filter(user=user, rarity=StickerRarity.PRISMATIC, reward_claimed=True).exists():
                self.earn(user, "album_prismatic_page")
            if RegionalAlbumPage.objects.filter(user=user, rarity=StickerRarity.FULL_ART, reward_claimed=True).exists():
                self.earn(user, "album_full_art_page")
            if RegionalAlbumPage.objects.filter(user=user, rarity=StickerRarity.SECRET_RARE, reward_claimed=True).exists():
                self.earn(user, "album_secret_rare_page")
        except Exception:
            pass

    def pending_count(self, user: User) -> int:
        """Return count of unclaimed GameAchievements."""
        from apps.users.models import GameAchievement

        return GameAchievement.objects.filter(user=user, claimed_at__isnull=True).count()

    # ------------------------------------------------------------------
    # Trigger helpers — called from game views / services
    # ------------------------------------------------------------------

    def on_memory_complete(self, user: User, board_key: str, grade: str) -> None:
        key_map = {
            "rookie_3x4": "memory_rookie",
            "standard_4x4": "memory_standard",
            "collector_5x4": "memory_collector",
            "master_6x4": "memory_master",
        }
        ach_key = key_map.get(board_key)
        if ach_key:
            self.earn(user, ach_key)
        if grade == "S" or grade.startswith("S"):
            self.earn(user, "memory_perfect")

    def on_silhouette_cleared(self, user: User, tower_key: str) -> None:
        key_map = {
            "rookie": "silhouette_rookie_clear",
            "kanto": "silhouette_regional_clear",
            "johto": "silhouette_regional_clear",
            "hoenn": "silhouette_regional_clear",
            "sinnoh": "silhouette_regional_clear",
            "unova": "silhouette_regional_clear",
            "kalos": "silhouette_regional_clear",
            "alola": "silhouette_regional_clear",
            "galar": "silhouette_regional_clear",
            "master": "silhouette_master_clear",
            "national": "silhouette_national_clear",
        }
        ach_key = key_map.get(tower_key)
        if ach_key:
            self.earn(user, ach_key)

    def on_loteria_win(self, user: User, is_full_board: bool) -> None:
        self.earn(user, "loteria_first_win")
        if is_full_board:
            self.earn(user, "loteria_full_board")

    def on_daily_claim(self, user: User, streak: int) -> None:
        if streak >= 7:
            self.earn(user, "streak_7")
        if streak >= 30:
            self.earn(user, "streak_30")

    def on_trade_complete(self, user: User, total_trades: int) -> None:
        if total_trades >= 1:
            self.earn(user, "first_trade")
        if total_trades >= 10:
            self.earn(user, "trades_10")

    def on_craft(self, user: User) -> None:
        self.earn(user, "first_craft")

    def on_dismantle(self, user: User) -> None:
        self.earn(user, "first_dismantle")

    def on_join_guild(self, user: User) -> None:
        self.earn(user, "join_guild")

    def on_guild_quest_complete(self, user: User) -> None:
        self.earn(user, "guild_quest")
