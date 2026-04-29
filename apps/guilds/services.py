"""Guild services for membership, albums, contribution, and perks."""

from __future__ import annotations

import logging
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.stickers.collection_stats import PlacementRecord, build_collection_stats
from apps.users.services import award_trainer_xp, deduct_ryo

from .models import (
    GUILD_CREATE_COST_RYO,
    GUILD_MAX_MEMBERS,
    Guild,
    GuildAlbumEntry,
    GuildMembership,
    GuildQuestClaim,
    GuildQuestPeriod,
    GuildRole,
)

User = get_user_model()
logger = logging.getLogger(__name__)

GUILD_LEVEL_THRESHOLDS: tuple[int, ...] = (0, 120, 280, 520, 860, 1300, 1840, 2480, 3240)

GUILD_PERKS: tuple[dict[str, object], ...] = (
    {"level": 1, "name": "Guild Album", "description": "Members can donate stickers into the guild album."},
    {"level": 2, "name": "Arcade Boost", "description": "+5% Ryo from guild mini-games."},
    {"level": 3, "name": "Quest Bonus", "description": "+5% Ryo from quest rewards."},
    {"level": 4, "name": "Dust Reclaim", "description": "+10% sticker dust from duplicate conversion."},
    {"level": 5, "name": "Board Vault", "description": "+1 saved Loteria board slot for members."},
    {"level": 6, "name": "Guild Cache", "description": "Weekly contributor reward pack for active members."},
    {"level": 7, "name": "Amigo Mentor", "description": "+5% Amigo XP from quest claims and sticker placement."},
    {"level": 8, "name": "Album Frame", "description": "Guild banner and album frame cosmetics unlock."},
)

GUILD_QUESTS: dict[str, dict[str, object]] = {
    "daily_donate": {
        "key": "daily_donate",
        "period": GuildQuestPeriod.DAILY,
        "title": "Daily Donation",
        "description": "Donate 1 sticker to your guild album today.",
        "target": 1,
        "metric": "donations",
        "reward_ryo": 150,
        "reward_amigo_xp": 20,
        "reward_contribution": 25,
        "reward_guild_xp": 40,
    },
    "weekly_support": {
        "key": "weekly_support",
        "period": GuildQuestPeriod.WEEKLY,
        "title": "Weekly Support",
        "description": "Donate 5 stickers to your guild album this week.",
        "target": 5,
        "metric": "donations",
        "reward_ryo": 600,
        "reward_amigo_xp": 60,
        "reward_contribution": 100,
        "reward_guild_xp": 180,
    },
}

RARITY_GUILD_XP: dict[str, int] = {
    "common": 5,
    "uncommon": 8,
    "rare": 12,
    "epic": 18,
    "prismatic": 28,
    "full_art": 40,
    "secret_rare": 60,
}

VARIANT_POINT_MULTIPLIER: dict[str, float] = {
    "base": 1.00,
    "shiny": 1.10,
    "battle_scene": 1.15,
    "watercolor": 1.18,
    "tv_90s": 1.20,
    "cartoon": 1.20,
    "color_swap": 1.25,
    "sketch": 1.25,
    "burn_scroll": 1.25,
    "neon_glow": 1.40,
    "glitter": 1.40,
    "holographic": 1.40,
    "chrome": 1.40,
    "anime": 1.80,
}

RARITY_POINT_BASE: dict[str, int] = {
    "common": 10,
    "uncommon": 20,
    "rare": 35,
    "epic": 55,
    "prismatic": 85,
    "full_art": 125,
    "secret_rare": 180,
}


def _guild_level_for_xp(xp: int) -> int:
    level = 1
    for idx, threshold in enumerate(GUILD_LEVEL_THRESHOLDS, start=1):
        if xp >= threshold:
            level = idx
    return level


def _next_level_xp(level: int) -> int | None:
    if level >= len(GUILD_LEVEL_THRESHOLDS):
        return None
    return GUILD_LEVEL_THRESHOLDS[level]


def _contribution_points_for_sticker(rarity: str, variant: str) -> int:
    base = RARITY_POINT_BASE.get(rarity, 10)
    multiplier = VARIANT_POINT_MULTIPLIER.get(variant, 1.0)
    return max(5, round(base * multiplier))


def _guild_xp_for_sticker(rarity: str) -> int:
    return RARITY_GUILD_XP.get(rarity, 5)


class GuildService:
    """Guild orchestration for membership, albums, and contribution."""

    def get_membership(self, user: User) -> GuildMembership | None:
        """Return the user's current membership, if any."""
        try:
            return user.guild_membership
        except GuildMembership.DoesNotExist:
            return None

    @transaction.atomic
    def create_guild(self, founder: User, name: str, tag: str, description: str = "") -> Guild:
        """Create a guild with the founder as owner."""
        if self.get_membership(founder) is not None:
            raise ValueError("You must leave your current guild before creating one.")

        tag = tag.strip().upper()
        name = name.strip()

        if Guild.objects.filter(name__iexact=name).exists():
            raise ValueError(f"A guild named '{name}' already exists.")
        if Guild.objects.filter(tag__iexact=tag).exists():
            raise ValueError(f"The tag [{tag}] is already taken.")

        deduct_ryo(founder, GUILD_CREATE_COST_RYO)

        guild = Guild.objects.create(
            name=name,
            tag=tag,
            description=description,
            created_by=founder,
        )
        GuildMembership.objects.create(user=founder, guild=guild, role=GuildRole.OWNER)
        logger.info("Guild '%s' [%s] created by %s", name, tag, founder)
        return guild

    @transaction.atomic
    def join_guild(self, user: User, guild: Guild) -> GuildMembership:
        """Join a recruiting guild."""
        if self.get_membership(user) is not None:
            raise ValueError("You must leave your current guild first.")
        if not guild.is_recruiting:
            raise ValueError("This guild is not currently recruiting.")
        if guild.is_full:
            raise ValueError(f"This guild is full ({GUILD_MAX_MEMBERS} members max).")

        membership = GuildMembership.objects.create(user=user, guild=guild, role=GuildRole.MEMBER)
        logger.info("%s joined guild '%s'", user, guild.name)
        return membership

    @transaction.atomic
    def leave_guild(self, user: User) -> None:
        """Leave the current guild or disband it if the owner is alone."""
        membership = self.get_membership(user)
        if membership is None:
            raise ValueError("You are not in a guild.")

        if membership.role == GuildRole.OWNER:
            other_members = membership.guild.memberships.exclude(user=user)
            if other_members.exists():
                raise ValueError("Transfer ownership or remove other members before leaving.")
            guild_name = membership.guild.name
            membership.guild.delete()
            logger.info("%s disbanded guild '%s'", user, guild_name)
        else:
            guild_name = membership.guild.name
            membership.delete()
            logger.info("%s left guild '%s'", user, guild_name)

    @transaction.atomic
    def kick_member(self, actor: User, target: User) -> None:
        """Kick a member from the actor's guild following role rules."""
        actor_m = self.get_membership(actor)
        target_m = self.get_membership(target)

        if actor_m is None:
            raise ValueError("You are not in a guild.")
        if target_m is None or target_m.guild_id != actor_m.guild_id:
            raise ValueError("Target is not in your guild.")
        if actor.pk == target.pk:
            raise ValueError("Use leave_guild to remove yourself.")
        if actor_m.role == GuildRole.MEMBER:
            raise ValueError("Only officers and the owner can kick members.")
        if actor_m.role == GuildRole.OFFICER and target_m.role != GuildRole.MEMBER:
            raise ValueError("Officers can only kick regular members.")

        target_m.delete()
        logger.info("%s kicked %s from guild '%s'", actor, target, actor_m.guild.name)

    @transaction.atomic
    def promote_to_officer(self, owner: User, target: User) -> GuildMembership:
        """Owner promotes a member to officer."""
        owner_m = self._require_owner(owner)
        target_m = self._require_same_guild_member(target, owner_m.guild_id)
        if target_m.role == GuildRole.OFFICER:
            raise ValueError(f"{target} is already an officer.")
        target_m.role = GuildRole.OFFICER
        target_m.save(update_fields=["role"])
        return target_m

    @transaction.atomic
    def demote_to_member(self, owner: User, target: User) -> GuildMembership:
        """Owner demotes an officer to member."""
        owner_m = self._require_owner(owner)
        target_m = self._require_same_guild_member(target, owner_m.guild_id)
        if target_m.role != GuildRole.OFFICER:
            raise ValueError(f"{target} is not an officer.")
        target_m.role = GuildRole.MEMBER
        target_m.save(update_fields=["role"])
        return target_m

    def get_guild_album_entries(self, guild: Guild):
        """Return guild album entries with sticker and donor data."""
        return guild.album_entries.select_related("sticker__pokemon", "donated_by").order_by(
            "sticker__pokemon__pokedex_number", "created_at"
        )

    def get_available_guild_donation_stickers(self, user: User, guild: Guild):
        """Return stickers the member can donate into the guild album."""
        membership = self.get_membership(user)
        if membership is None or membership.guild_id != guild.pk:
            return []

        return list(
            user.stickers.filter(
                is_album_placed=False,
                is_trading=False,
                guild_album_entry__isnull=True,
            )
            .select_related("pokemon")
            .order_by("pokemon__pokedex_number", "-date_caught")[:120]
        )

    @transaction.atomic
    def donate_sticker(self, actor: User, guild: Guild, sticker_id: int) -> GuildAlbumEntry:
        """Donate a sticker into the guild album and make it guild soul-bound."""
        membership = self.get_membership(actor)
        if membership is None or membership.guild_id != guild.pk:
            raise ValueError("You must be a member of this guild to donate stickers.")

        sticker = actor.stickers.select_for_update().filter(pk=sticker_id).select_related("pokemon").first()
        if sticker is None:
            raise ValueError("Sticker not found.")
        if sticker.is_album_placed:
            raise ValueError("Remove this sticker from your personal album before donating it.")
        if sticker.is_trading:
            raise ValueError("You cannot donate a sticker that is listed for trade.")
        if hasattr(sticker, "guild_album_entry"):
            raise ValueError("This sticker is already soul-bound to a guild album.")

        entry = GuildAlbumEntry.objects.create(guild=guild, sticker=sticker, donated_by=actor)
        contribution_points = _contribution_points_for_sticker(sticker.rarity, sticker.variant)
        guild_xp = _guild_xp_for_sticker(sticker.rarity)

        membership.contribution_points += contribution_points
        membership.donated_stickers += 1
        membership.save(update_fields=["contribution_points", "donated_stickers"])

        self._award_guild_xp(guild, guild_xp)
        logger.info("%s donated sticker #%d to guild '%s'", actor, sticker.pk, guild.name)
        return entry

    def get_guild_stats(self, guild: Guild) -> dict:
        """Return guild collection, contribution, and perk stats."""
        entries = list(self.get_guild_album_entries(guild))
        records = [
            PlacementRecord(
                pokemon_id=entry.sticker.pokemon_id,
                pokedex_number=entry.sticker.pokemon.pokedex_number,
                rarity=entry.sticker.rarity,
                variant=entry.sticker.variant,
            )
            for entry in entries
            if entry.sticker.pokemon.pokedex_number is not None
        ]
        collection_stats = build_collection_stats(records)
        memberships = list(guild.memberships.select_related("user").order_by("-contribution_points", "joined_at"))
        next_level = _next_level_xp(guild.level)
        current_floor = GUILD_LEVEL_THRESHOLDS[guild.level - 1]
        xp_progress_percent = 100 if next_level is None else int((guild.xp - current_floor) / max(1, next_level - current_floor) * 100)
        return {
            "collection": collection_stats,
            "album_entries": len(entries),
            "memberships": memberships,
            "top_contributors": memberships[:5],
            "guild_level": guild.level,
            "guild_xp": guild.xp,
            "next_level_xp": next_level,
            "xp_progress_percent": max(0, min(100, xp_progress_percent)),
            "perks": self.get_guild_perks(guild),
        }

    def get_guild_perks(self, guild: Guild) -> list[dict]:
        """Return guild perk unlock states."""
        return [
            {
                **perk,
                "unlocked": guild.level >= int(perk["level"]),
            }
            for perk in GUILD_PERKS
        ]

    def get_guild_quests(self, user: User, guild: Guild) -> list[dict]:
        """Return the member's daily and weekly guild quest progress."""
        membership = self.get_membership(user)
        if membership is None or membership.guild_id != guild.pk:
            return []

        today = timezone.localdate()
        week_start = today - timedelta(days=today.weekday())
        quest_periods = {
            GuildQuestPeriod.DAILY: today,
            GuildQuestPeriod.WEEKLY: week_start,
        }

        results: list[dict] = []
        for quest in GUILD_QUESTS.values():
            period = str(quest["period"])
            period_start = quest_periods[period]
            progress = self._guild_quest_progress(user, guild, str(quest["metric"]), period_start, period)
            claimed = GuildQuestClaim.objects.filter(
                membership=membership,
                quest_key=str(quest["key"]),
                period=period,
                period_start=period_start,
            ).exists()
            results.append(
                {
                    **quest,
                    "progress": progress,
                    "claimed": claimed,
                    "period_start": period_start,
                    "complete": progress >= int(quest["target"]),
                }
            )
        return results

    @transaction.atomic
    def claim_guild_quest(self, user: User, guild: Guild, quest_key: str) -> dict:
        """Claim a completed guild quest and award player plus guild progress."""
        membership = self.get_membership(user)
        if membership is None or membership.guild_id != guild.pk:
            raise ValueError("You are not in this guild.")
        if quest_key not in GUILD_QUESTS:
            raise ValueError("Unknown guild quest.")

        quest = GUILD_QUESTS[quest_key]
        today = timezone.localdate()
        period = str(quest["period"])
        period_start = today if period == GuildQuestPeriod.DAILY else today - timedelta(days=today.weekday())
        progress = self._guild_quest_progress(user, guild, str(quest["metric"]), period_start, period)
        if progress < int(quest["target"]):
            raise ValueError("This guild quest is not complete yet.")

        _, created = GuildQuestClaim.objects.get_or_create(
            guild=guild,
            membership=membership,
            quest_key=quest_key,
            period=period,
            period_start=period_start,
        )
        if not created:
            raise ValueError("You already claimed this guild quest.")

        reward_ryo = int(quest["reward_ryo"])
        reward_amigo_xp = int(quest["reward_amigo_xp"])
        reward_contribution = int(quest["reward_contribution"])
        reward_guild_xp = int(quest["reward_guild_xp"])

        User.objects.filter(pk=user.pk).update(ryo=F("ryo") + reward_ryo)
        membership.contribution_points += reward_contribution
        membership.guild_quests_completed += 1
        membership.save(update_fields=["contribution_points", "guild_quests_completed"])

        award_trainer_xp(user, reward_amigo_xp, source="guild_quest")
        self._award_guild_xp(guild, reward_guild_xp)

        return {
            "ryo": reward_ryo,
            "amigo_xp": reward_amigo_xp,
            "guild_xp": reward_guild_xp,
            "contribution": reward_contribution,
        }

    def _guild_quest_progress(self, user: User, guild: Guild, metric: str, period_start, period: str) -> int:
        queryset = GuildAlbumEntry.objects.filter(guild=guild, donated_by=user)
        if period == GuildQuestPeriod.DAILY:
            queryset = queryset.filter(created_at__date=period_start)
        else:
            queryset = queryset.filter(created_at__date__gte=period_start)

        if metric == "donations":
            return queryset.count()
        return 0

    def _award_guild_xp(self, guild: Guild, amount: int) -> Guild:
        guild.xp += amount
        guild.level = _guild_level_for_xp(guild.xp)
        guild.save(update_fields=["xp", "level"])
        return guild

    def _require_owner(self, user: User) -> GuildMembership:
        membership = self.get_membership(user)
        if membership is None or membership.role != GuildRole.OWNER:
            raise ValueError("Only the guild owner can perform this action.")
        return membership

    def _require_same_guild_member(self, user: User, guild_id: int) -> GuildMembership:
        membership = self.get_membership(user)
        if membership is None or membership.guild_id != guild_id:
            raise ValueError("Target is not in your guild.")
        return membership
