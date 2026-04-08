"""
Ranked season and matchmaking services.

RankedSeasonService  — ranked point awards, tier calculation, season management.
MatchmakingService   — queue join/leave, opponent matching, battle creation.
"""
import logging
from typing import TYPE_CHECKING

from django.db import transaction
from django.db.models import Q

from .models import (
    POINTS_LOSS,
    POINTS_WIN,
    STREAK_BONUS,
    STREAK_THRESHOLD,
    TIER_FLOORS,
    TIER_ORDER,
    TIER_WIN_BONUS_RYO,
    MatchmakingEntry,
    MatchmakingStatus,
    RankedProfile,
    RankedSeason,
    RankedTier,
)

if TYPE_CHECKING:
    from django.contrib.auth import get_user_model

    User = get_user_model()

logger = logging.getLogger(__name__)

# Points tolerance for matchmaking: search this many points above/below.
MATCH_TOLERANCE = 500


class RankedSeasonService:
    """Manages ranked seasons, profiles, and point awards."""

    # ------------------------------------------------------------------
    # Profile access
    # ------------------------------------------------------------------

    @staticmethod
    def get_active_season() -> RankedSeason | None:
        """Return the currently active season, or None if none exists."""
        return RankedSeason.objects.filter(is_active=True).first()

    @staticmethod
    def get_or_create_profile(user: "User", season: RankedSeason) -> RankedProfile:
        """Return the user's ranked profile for this season, creating if needed."""
        profile, _ = RankedProfile.objects.get_or_create(
            user=user,
            season=season,
            defaults={"rank_points": 0, "tier": RankedTier.BRONZE, "sub_tier": 3},
        )
        return profile

    # ------------------------------------------------------------------
    # Point awards (called by _end_battle hook)
    # ------------------------------------------------------------------

    @transaction.atomic
    def record_win(self, winner: "User", loser: "User") -> tuple[RankedProfile, int]:
        """
        Award ranked points to the winner and deduct from the loser.

        Returns (winner_profile, points_awarded).
        """
        season = self.get_active_season()
        if season is None:
            logger.debug("No active ranked season — skipping ranked point award.")
            return None, 0  # type: ignore[return-value]

        winner_profile = self.get_or_create_profile(winner, season)
        loser_profile = self.get_or_create_profile(loser, season)

        # Winner: base points + streak bonus (GDD §15.3)
        winner_profile.win_streak += 1
        streak_bonus = STREAK_BONUS if winner_profile.win_streak >= STREAK_THRESHOLD else 0
        points_earned = POINTS_WIN + streak_bonus
        winner_profile.rank_points += points_earned
        winner_profile.season_wins += 1
        winner_profile.tier = self._compute_tier(winner_profile.rank_points)
        winner_profile.sub_tier = self._compute_sub_tier(winner_profile.rank_points, winner_profile.tier)
        winner_profile.save(update_fields=[
            "rank_points", "tier", "sub_tier", "win_streak", "season_wins",
        ])

        # Loser: deduct points but floor at tier minimum (no demotion past floor)
        loser_profile.win_streak = 0
        new_points = max(
            loser_profile.tier_floor,
            loser_profile.rank_points + POINTS_LOSS,
        )
        loser_profile.rank_points = new_points
        loser_profile.season_losses += 1
        # Check for demotion (floor at current tier floor, then recompute tier)
        loser_profile.tier = self._compute_tier(loser_profile.rank_points)
        loser_profile.sub_tier = self._compute_sub_tier(loser_profile.rank_points, loser_profile.tier)
        loser_profile.save(update_fields=[
            "rank_points", "tier", "sub_tier", "win_streak", "season_losses",
        ])

        logger.info(
            "Ranked: %s +%d pts (streak %d) | %s %d pts (total %d)",
            winner, points_earned, winner_profile.win_streak,
            loser, POINTS_LOSS, loser_profile.rank_points,
        )
        return winner_profile, points_earned

    # ------------------------------------------------------------------
    # Tier computation
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_tier(rank_points: int) -> str:
        """Return the tier for a given rank_points total."""
        tier = RankedTier.BRONZE
        for t in TIER_ORDER:
            if rank_points >= TIER_FLOORS[t]:
                tier = t
        return tier

    @staticmethod
    def _compute_sub_tier(rank_points: int, tier: str) -> int:
        """
        Compute sub-tier (1–3) within a tier.

        Sub-tier 3 is the lowest entry point; sub-tier 1 is closest to promotion.
        """
        floor = TIER_FLOORS[tier]
        # Find the ceiling (floor of next tier, or +1500 for the top tier)
        tier_idx = TIER_ORDER.index(tier)
        if tier_idx + 1 < len(TIER_ORDER):
            ceiling = TIER_FLOORS[TIER_ORDER[tier_idx + 1]]
        else:
            ceiling = floor + 1_500

        span = max(ceiling - floor, 1)
        progress = (rank_points - floor) / span  # 0.0 – 1.0

        if progress >= 2 / 3:
            return 1
        if progress >= 1 / 3:
            return 2
        return 3

    # ------------------------------------------------------------------
    # Season management (admin helpers)
    # ------------------------------------------------------------------

    @staticmethod
    def tier_win_bonus_ryo(tier: str) -> int:
        """Extra Ryo awarded per ranked PvP win based on tier."""
        return TIER_WIN_BONUS_RYO.get(tier, 0)


class MatchmakingService:
    """Manages the PvP matchmaking queue."""

    _ranked_svc = RankedSeasonService()

    # ------------------------------------------------------------------
    # Queue operations
    # ------------------------------------------------------------------

    @transaction.atomic
    def join_queue(self, user: "User") -> MatchmakingEntry:
        """
        Add the player to the matchmaking queue.

        If the player already has a waiting entry, returns it unchanged.
        Immediately attempts to find a match; if found, creates a battle and
        marks both entries as matched.
        """
        # Cancel any stale entries (matched/cancelled) and return if already waiting.
        existing = (
            MatchmakingEntry.objects.filter(user=user)
            .order_by("-entered_at")
            .first()
        )
        if existing and existing.status == MatchmakingStatus.WAITING:
            return existing

        season = self._ranked_svc.get_active_season()
        rank_pts = 0
        if season:
            profile = self._ranked_svc.get_or_create_profile(user, season)
            rank_pts = profile.rank_points

        entry = MatchmakingEntry.objects.create(
            user=user,
            rank_points=rank_pts,
            status=MatchmakingStatus.WAITING,
        )

        # Immediately try to match this player.
        self._try_match(entry)
        return entry

    @transaction.atomic
    def leave_queue(self, user: "User") -> None:
        """Cancel all waiting queue entries for this user."""
        MatchmakingEntry.objects.filter(
            user=user,
            status=MatchmakingStatus.WAITING,
        ).update(status=MatchmakingStatus.CANCELLED)

    def get_waiting_entry(self, user: "User") -> MatchmakingEntry | None:
        """Return the player's current waiting entry, or None."""
        return MatchmakingEntry.objects.filter(
            user=user, status=MatchmakingStatus.WAITING
        ).order_by("-entered_at").first()

    def get_latest_entry(self, user: "User") -> MatchmakingEntry | None:
        """Return the player's most recent queue entry regardless of status."""
        return MatchmakingEntry.objects.filter(user=user).order_by("-entered_at").first()

    # ------------------------------------------------------------------
    # Matching logic
    # ------------------------------------------------------------------

    def _try_match(self, entry: MatchmakingEntry) -> bool:
        """
        Attempt to pair this entry with an existing waiting opponent.

        Match criteria:
        1. Not the same user.
        2. Within MATCH_TOLERANCE rank points.
        3. Oldest waiting entry wins (FIFO fairness).

        If matched, creates a PvP battle and updates both entries.
        Returns True if a match was made.
        """
        from apps.game.services import BattleService

        opponent_entry = (
            MatchmakingEntry.objects.select_for_update()
            .filter(
                status=MatchmakingStatus.WAITING,
                rank_points__gte=entry.rank_points - MATCH_TOLERANCE,
                rank_points__lte=entry.rank_points + MATCH_TOLERANCE,
            )
            .exclude(user=entry.user)
            .order_by("entered_at")
            .first()
        )

        if opponent_entry is None:
            logger.debug("No opponent found for %s (pts=%d)", entry.user, entry.rank_points)
            return False

        # Create the ranked PvP battle.
        svc = BattleService()
        battle = svc.create_battle(
            player_one=entry.user,
            player_two=opponent_entry.user,
            is_ai_battle=False,
        )

        # Mark both entries as matched.
        for e, u in [(entry, entry.user), (opponent_entry, opponent_entry.user)]:
            e.status = MatchmakingStatus.MATCHED
            e.battle = battle
            e.save(update_fields=["status", "battle", "updated_at"])

        logger.info(
            "Matchmaking: %s vs %s → Battle #%d",
            entry.user, opponent_entry.user, battle.pk,
        )
        return True
