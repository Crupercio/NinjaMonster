"""QuestService — assigns, tracks, and rewards quests (GDD Section 14)."""
import logging
from datetime import date
from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from .models import QuestCondition, QuestTemplate, QuestType, RewardType, UserQuest

if TYPE_CHECKING:
    from apps.game.models import Battle

User = get_user_model()
logger = logging.getLogger(__name__)


def _daily_period_key() -> str:
    return f"daily:{date.today().isoformat()}"


def _weekly_period_key() -> str:
    iso = date.today().isocalendar()
    return f"weekly:{iso.year}-W{iso.week:02d}"


class QuestService:
    """Orchestrates all quest assignment, progress tracking, and reward claiming."""

    # ------------------------------------------------------------------
    # Assignment
    # ------------------------------------------------------------------

    def assign_daily_quests(self, user: User) -> list[UserQuest]:
        """
        Ensure the user has 3 daily quest instances for today.

        Idempotent: if already assigned, returns existing quests unchanged.
        Returns an empty list if no daily templates are configured.
        """
        period_key = _daily_period_key()
        existing = list(
            UserQuest.objects.filter(
                user=user,
                template__quest_type=QuestType.DAILY,
                period_key=period_key,
            ).select_related("template")
        )
        if existing:
            return existing

        templates = list(
            QuestTemplate.objects.filter(
                quest_type=QuestType.DAILY, is_active=True
            ).order_by("?")[:3]
        )
        if not templates:
            return []

        created = UserQuest.objects.bulk_create([
            UserQuest(user=user, template=t, period_key=period_key)
            for t in templates
        ])
        logger.debug("Assigned %d daily quests to %s (%s)", len(created), user, period_key)
        return created

    def assign_weekly_quests(self, user: User) -> list[UserQuest]:
        """
        Ensure the user has 3 weekly challenge instances for this week.

        Idempotent: if already assigned, returns existing quests unchanged.
        """
        period_key = _weekly_period_key()
        existing = list(
            UserQuest.objects.filter(
                user=user,
                template__quest_type=QuestType.WEEKLY,
                period_key=period_key,
            ).select_related("template")
        )
        if existing:
            return existing

        templates = list(
            QuestTemplate.objects.filter(
                quest_type=QuestType.WEEKLY, is_active=True
            ).order_by("?")[:3]
        )
        if not templates:
            return []

        created = UserQuest.objects.bulk_create([
            UserQuest(user=user, template=t, period_key=period_key)
            for t in templates
        ])
        logger.debug("Assigned %d weekly quests to %s (%s)", len(created), user, period_key)
        return created

    def ensure_story_quests(self, user: User) -> list[UserQuest]:
        """
        Ensure one UserQuest exists per active story QuestTemplate for the user.

        Idempotent: skips templates already assigned.
        """
        templates = QuestTemplate.objects.filter(
            quest_type=QuestType.STORY, is_active=True
        ).order_by("order", "pk")

        quests: list[UserQuest] = []
        for tmpl in templates:
            uq, _ = UserQuest.objects.get_or_create(
                user=user,
                template=tmpl,
                period_key="story",
            )
            quests.append(uq)
        return quests

    # ------------------------------------------------------------------
    # Progress hooks (called from BattleService / StickerService)
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Type-constraint helpers (for condition_meta on achieve_combo quests)
    # ------------------------------------------------------------------

    @staticmethod
    def _get_user_team_types(user: User, battle: "Battle") -> tuple[list[str], list[str]]:
        """
        Return (type_names, chakra_elements) for the user's team in this battle.

        type_names — lowercase primary+secondary type names of every slot (no duplicates).
        chakra_elements — lowercase chakra element names present in the team.
        """
        from apps.game.models import BattleSlot, BattleTeam
        try:
            team = BattleTeam.objects.get(battle=battle, owner=user)
        except BattleTeam.DoesNotExist:
            return [], []

        slots = list(
            BattleSlot.objects.filter(team=team)
            .select_related(
                "pokemon__primary_type__chakra_element",
                "pokemon__secondary_type__chakra_element",
            )
        )

        slot_primary_types: list[list[str]] = []  # per-slot type lists
        all_types: set[str] = set()
        all_chakra: set[str] = set()

        for slot in slots:
            poke = slot.pokemon
            slot_types: list[str] = []
            for ptype in [poke.primary_type, poke.secondary_type]:
                if ptype is None:
                    continue
                name = ptype.name.lower()
                slot_types.append(name)
                all_types.add(name)
                if ptype.chakra_element:
                    all_chakra.add(ptype.chakra_element.name.lower())
            slot_primary_types.append(slot_types)

        return list(all_types), list(all_chakra), slot_primary_types  # type: ignore[return-value]

    @staticmethod
    def _team_meets_meta(meta: dict, _all_types: list[str], all_chakra: list[str], slot_types: list[list[str]]) -> bool:
        """
        Return True if the team satisfies the condition_meta constraints.

        Supported keys:
          type_names       list[str]  — at least min_type_count slots share one of these types
          min_type_count   int        — minimum slots that must carry the required type (default 3)
          mono_type        bool       — all 6 slots must share at least one common type
          all_chakra_elements bool   — team must have ≥1 Pokémon from each of the 5 chakra elements
        """
        if not meta:
            return True  # no constraints → always satisfied

        if meta.get("mono_type"):
            if not slot_types:
                return False
            # Find types common to every slot
            common = set(slot_types[0])
            for st in slot_types[1:]:
                common &= set(st)
            if not common:
                return False

        if meta.get("all_chakra_elements"):
            required = {"fire", "water", "earth", "lightning", "wind"}
            if not required.issubset(set(all_chakra)):
                return False

        if "type_names" in meta:
            required_types = {t.lower() for t in meta["type_names"]}
            min_count = meta.get("min_type_count", 3)
            # Count slots that have at least one of the required types
            qualifying = sum(
                1 for st in slot_types
                if required_types.intersection(st)
            )
            if qualifying < min_count:
                return False

        return True

    def on_battle_won(self, user: User, battle: "Battle") -> None:
        """
        Update active WIN_BATTLES and ACHIEVE_COMBO quests after the user wins.

        Called from BattleService._end_battle().
        """
        period_keys = [_daily_period_key(), _weekly_period_key(), "story"]
        active_quests = list(
            UserQuest.objects.filter(
                user=user,
                completed=False,
                period_key__in=period_keys,
                template__condition__in=[
                    QuestCondition.WIN_BATTLES,
                    QuestCondition.ACHIEVE_COMBO,
                ],
            ).select_related("template")
        )

        # Lazy-load team type data only if any combo quest has condition_meta
        _types_loaded = False
        all_types: list[str] = []
        all_chakra: list[str] = []
        slot_types: list[list[str]] = []

        for uq in active_quests:
            tmpl = uq.template
            if tmpl.condition == QuestCondition.WIN_BATTLES:
                uq.progress = min(uq.progress + 1, tmpl.condition_value)
            elif tmpl.condition == QuestCondition.ACHIEVE_COMBO:
                if battle.max_combo_chain < tmpl.condition_value:
                    continue  # chain not long enough — no change

                # Check type constraints if present
                if tmpl.condition_meta:
                    if not _types_loaded:
                        all_types, all_chakra, slot_types = self._get_user_team_types(user, battle)  # type: ignore[assignment]
                        _types_loaded = True
                    if not self._team_meets_meta(tmpl.condition_meta, all_types, all_chakra, slot_types):
                        continue  # team composition doesn't satisfy the constraint

                uq.progress = tmpl.condition_value

            if uq.progress >= tmpl.condition_value:
                uq.completed = True
                uq.completed_at = timezone.now()

            uq.save(update_fields=["progress", "completed", "completed_at"])

        logger.debug(
            "on_battle_won: updated %d quest(s) for %s (battle #%d)",
            len(active_quests),
            user,
            battle.pk,
        )

    def on_expedition_completed(self, user: User) -> None:
        """Called when an expedition session finishes (all encounters used)."""
        period_keys = [_daily_period_key(), _weekly_period_key(), "story"]
        active_quests = list(
            UserQuest.objects.filter(
                user=user,
                completed=False,
                period_key__in=period_keys,
                template__condition=QuestCondition.COMPLETE_EXPEDITIONS,
            ).select_related("template")
        )
        for uq in active_quests:
            uq.progress = min(uq.progress + 1, uq.template.condition_value)
            if uq.progress >= uq.template.condition_value:
                uq.completed = True
                uq.completed_at = timezone.now()
            uq.save(update_fields=["progress", "completed", "completed_at"])

    def on_pokemon_bonded(self, user: User, species=None) -> None:
        """Called when an expedition encounter results in a successful bond."""
        period_keys = [_daily_period_key(), _weekly_period_key(), "story"]
        active_quests = list(
            UserQuest.objects.filter(
                user=user,
                completed=False,
                period_key__in=period_keys,
                template__condition=QuestCondition.BOND_POKEMON,
            ).select_related("template")
        )
        for uq in active_quests:
            unique_type_target = uq.template.condition_meta.get("unique_type_count", 0)
            if unique_type_target and species is not None:
                bonded_types = set(uq.progress_meta.get("bonded_types", []))
                for pokemon_type in (species.primary_type, species.secondary_type):
                    if pokemon_type:
                        bonded_types.add(pokemon_type.name.lower())
                uq.progress_meta["bonded_types"] = sorted(bonded_types)
                uq.progress = min(len(bonded_types), uq.template.condition_value)
            else:
                uq.progress = min(uq.progress + 1, uq.template.condition_value)
            if uq.progress >= uq.template.condition_value:
                uq.completed = True
                uq.completed_at = timezone.now()
            uq.save(update_fields=["progress", "progress_meta", "completed", "completed_at"])

    def on_pack_opened(self, user: User) -> None:
        """
        Increment OPEN_PACKS quest progress after the user opens a sticker pack.

        Called from StickerService.open_pack().
        """
        period_keys = [_daily_period_key(), _weekly_period_key(), "story"]
        active_quests = list(
            UserQuest.objects.filter(
                user=user,
                completed=False,
                period_key__in=period_keys,
                template__condition=QuestCondition.OPEN_PACKS,
            ).select_related("template")
        )

        for uq in active_quests:
            uq.progress = min(uq.progress + 1, uq.template.condition_value)
            if uq.progress >= uq.template.condition_value:
                uq.completed = True
                uq.completed_at = timezone.now()
            uq.save(update_fields=["progress", "completed", "completed_at"])

        logger.debug(
            "on_pack_opened: updated %d quest(s) for %s",
            len(active_quests),
            user,
        )

    # ------------------------------------------------------------------
    # Reward claiming
    # ------------------------------------------------------------------

    @transaction.atomic
    def claim_reward(self, user: User, user_quest: UserQuest) -> dict[str, object]:
        """
        Award the quest reward to the user and mark the quest as rewarded.

        Returns a dict summarising what was granted, e.g. {"ryo": 250}.
        Raises ValueError if the quest is not complete, already rewarded,
        or does not belong to this user.
        """
        if user_quest.user_id != user.pk:
            raise ValueError("This quest does not belong to you.")
        if not user_quest.completed:
            raise ValueError("Quest is not yet completed.")
        if user_quest.rewarded:
            raise ValueError("Reward has already been claimed.")

        tmpl = user_quest.template
        summary: dict[str, object] = {}

        fields_to_save: list[str] = []

        if tmpl.reward_type == RewardType.RYO:
            user.ryo += tmpl.reward_value
            fields_to_save.append("ryo")
            summary["ryo"] = tmpl.reward_value
        elif tmpl.reward_type == RewardType.STICKER_DUST:
            user.sticker_dust += tmpl.reward_value
            fields_to_save.append("sticker_dust")
            summary["sticker_dust"] = tmpl.reward_value
        elif tmpl.reward_type == RewardType.STICKER_PACK:
            from apps.stickers.models import StickerPack
            StickerPack.objects.create(owner=user)
            summary["sticker_pack"] = 1

        if tmpl.reward_dust > 0:
            user.sticker_dust += tmpl.reward_dust
            if "sticker_dust" not in fields_to_save:
                fields_to_save.append("sticker_dust")
            summary["sticker_dust"] = summary.get("sticker_dust", 0) + tmpl.reward_dust

        if tmpl.reward_candy_qty > 0 and tmpl.reward_candy_type:
            from apps.users.services import award_candy

            award_candy(user, tmpl.reward_candy_type, tmpl.reward_candy_qty)
            summary["candy_qty"] = tmpl.reward_candy_qty
            summary["candy_label"] = tmpl.reward_candy_type.replace("_", " ").title()

        if fields_to_save:
            user.save(update_fields=fields_to_save)

        user_quest.rewarded = True
        user_quest.save(update_fields=["rewarded"])

        # Award trainer XP for completing a quest (50 XP per quest claim)
        from apps.users.services import award_trainer_xp
        award_trainer_xp(user, 50, source="quest")

        logger.info(
            "Quest reward claimed: user=%s quest='%s' reward=%s",
            user,
            tmpl.name,
            summary,
        )
        return summary

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_quests_for_display(self, user: User) -> dict[str, list[UserQuest]]:
        """
        Return all quest categories for the quest list page, assigning any that
        are missing for today / this week.
        """
        daily = self.assign_daily_quests(user)
        weekly = self.assign_weekly_quests(user)
        story = self.ensure_story_quests(user)
        return {"daily": daily, "weekly": weekly, "story": story}
