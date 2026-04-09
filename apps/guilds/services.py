"""GuildService — create, join, leave, moderate guilds."""
import logging

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Avg, Sum

from apps.users.services import deduct_ryo

from .models import GUILD_CREATE_COST_RYO, GUILD_MAX_MEMBERS, Guild, GuildMembership, GuildRole

User = get_user_model()
logger = logging.getLogger(__name__)


class GuildService:

    # ------------------------------------------------------------------
    # Membership queries
    # ------------------------------------------------------------------

    def get_membership(self, user: User) -> GuildMembership | None:
        """Return the user's current GuildMembership or None."""
        try:
            return user.guild_membership  # type: ignore[union-attr]
        except GuildMembership.DoesNotExist:
            return None

    # ------------------------------------------------------------------
    # Guild creation
    # ------------------------------------------------------------------

    @transaction.atomic
    def create_guild(
        self, founder: User, name: str, tag: str, description: str = ""
    ) -> Guild:
        """
        Create a new guild with the founder as owner.

        Deducts GUILD_CREATE_COST_RYO from the founder.
        Raises ValueError if the founder is already in a guild, the name/tag
        is taken, or the founder cannot afford the cost.
        """
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
            tag=tag.upper(),
            description=description,
            created_by=founder,
        )
        GuildMembership.objects.create(user=founder, guild=guild, role=GuildRole.OWNER)
        logger.info("Guild '%s' [%s] created by %s", name, tag, founder)
        return guild

    # ------------------------------------------------------------------
    # Joining / leaving
    # ------------------------------------------------------------------

    @transaction.atomic
    def join_guild(self, user: User, guild: Guild) -> GuildMembership:
        """
        Add user as a member of guild.

        Raises ValueError if user is already in a guild, guild is full,
        or guild is not recruiting.
        """
        if self.get_membership(user) is not None:
            raise ValueError("You must leave your current guild first.")
        if not guild.is_recruiting:
            raise ValueError("This guild is not currently recruiting.")
        if guild.is_full:
            raise ValueError(f"This guild is full ({GUILD_MAX_MEMBERS} members max).")

        membership = GuildMembership.objects.create(
            user=user, guild=guild, role=GuildRole.MEMBER
        )
        logger.info("%s joined guild '%s'", user, guild.name)
        return membership

    @transaction.atomic
    def leave_guild(self, user: User) -> None:
        """
        Remove user from their guild.

        Raises ValueError if user is not in a guild or is the sole owner
        (they must transfer ownership or disband first).
        """
        membership = self.get_membership(user)
        if membership is None:
            raise ValueError("You are not in a guild.")

        if membership.role == GuildRole.OWNER:
            other_members = membership.guild.memberships.exclude(user=user)
            if other_members.exists():
                raise ValueError(
                    "Transfer ownership to another member before leaving, "
                    "or kick all members first."
                )
            # Last member leaving — disband the guild
            membership.guild.delete()
            logger.info("%s disbanded guild (was last member)", user)
        else:
            guild_name = membership.guild.name
            membership.delete()
            logger.info("%s left guild '%s'", user, guild_name)

    # ------------------------------------------------------------------
    # Moderation
    # ------------------------------------------------------------------

    @transaction.atomic
    def kick_member(self, actor: User, target: User) -> None:
        """
        Remove target from the guild.

        Rules:
        - Actor must be owner or officer in the same guild.
        - Officers cannot kick other officers or the owner.
        - Owner can kick anyone except themselves (use leave_guild).
        """
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
        logger.info("%s promoted %s to officer in '%s'", owner, target, owner_m.guild.name)
        return target_m

    @transaction.atomic
    def demote_to_member(self, owner: User, target: User) -> GuildMembership:
        """Owner demotes an officer back to member."""
        owner_m = self._require_owner(owner)
        target_m = self._require_same_guild_member(target, owner_m.guild_id)
        if target_m.role != GuildRole.OFFICER:
            raise ValueError(f"{target} is not an officer.")
        target_m.role = GuildRole.MEMBER
        target_m.save(update_fields=["role"])
        logger.info("%s demoted %s to member in '%s'", owner, target, owner_m.guild.name)
        return target_m

    @transaction.atomic
    def transfer_ownership(self, owner: User, new_owner: User) -> None:
        """Transfer the owner role to another member."""
        owner_m = self._require_owner(owner)
        new_m = self._require_same_guild_member(new_owner, owner_m.guild_id)
        owner_m.role = GuildRole.MEMBER
        owner_m.save(update_fields=["role"])
        new_m.role = GuildRole.OWNER
        new_m.save(update_fields=["role"])
        logger.info("%s transferred ownership of '%s' to %s", owner, owner_m.guild.name, new_owner)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_guild_stats(self, guild: Guild) -> dict:
        """
        Aggregate win statistics for a guild's members.

        Returns:
          {"total_wins": int, "total_battles": int, "avg_longest_combo": float}
        """
        members = guild.memberships.select_related("user")
        users = [m.user for m in members]
        total_wins = sum(u.battles_won for u in users)
        total_battles = sum(u.battles_played for u in users)
        avg_combo = (
            sum(u.longest_combo_chain for u in users) / len(users) if users else 0.0
        )
        return {
            "total_wins": total_wins,
            "total_battles": total_battles,
            "avg_longest_combo": round(avg_combo, 1),
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

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
