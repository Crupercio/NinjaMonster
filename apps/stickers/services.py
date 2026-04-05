"""
Sticker business logic: StickerService and TradeService.

Implements all award, upgrade, pack-opening, dust conversion, crafting,
and atomic trade mechanics.
"""
import logging
import random
from datetime import datetime, timezone

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count

from apps.pokemon.models import Pokemon
from apps.users.services import deduct_ryo

from .models import (
    CRAFT_COSTS,
    DISMANTLE_VALUES,
    DUST_VALUES,
    Sticker,
    StickerAlbum,
    StickerPack,
    StickerRarity,
    StickerVariant,
    TradeHistory,
    TradeOffer,
)

User = get_user_model()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pack rarity distribution weights
# ---------------------------------------------------------------------------
# Slots 1-3: common / uncommon
_COMMON_POOL_WEIGHTS = {
    StickerRarity.COMMON: 70,
    StickerRarity.UNCOMMON: 30,
}
# Slot 4: guaranteed rare or above
_GUARANTEED_RARE_WEIGHTS = {
    StickerRarity.RARE: 60,
    StickerRarity.EPIC: 25,
    StickerRarity.HOLOGRAPHIC: 10,
    StickerRarity.FULL_ART: 4,
    StickerRarity.SECRET_RARE: 1,
}
# Slot 5: any rarity
_ANY_RARITY_WEIGHTS = {
    StickerRarity.COMMON: 50,
    StickerRarity.UNCOMMON: 25,
    StickerRarity.RARE: 15,
    StickerRarity.EPIC: 6,
    StickerRarity.HOLOGRAPHIC: 3,
    StickerRarity.FULL_ART: 0.7,
    StickerRarity.SECRET_RARE: 0.3,
}

# Variant weights for random assignment
_VARIANT_WEIGHTS = {
    StickerVariant.BASE: 50,
    StickerVariant.SHINY: 25,
    StickerVariant.BATTLE_SCENE: 12,
    StickerVariant.CHIBI: 8,
    StickerVariant.MANGA_PANEL: 4,
    StickerVariant.FULL_ILLUSTRATION: 1,
}

# Level milestones that upgrade sticker rarity
_LEVEL_RARITY_UPGRADES: dict[int, str] = {
    25: StickerRarity.UNCOMMON,
    50: StickerRarity.RARE,
    75: StickerRarity.EPIC,
    100: StickerRarity.HOLOGRAPHIC,
}

# Secret rare drop chance when catching at 1 HP
_SECRET_RARE_HP_CHANCE = 0.03  # 3%

# Minimum combo chain length for full_art award
_FULL_ART_MIN_CHAIN = 5

# Battles won required to earn a sticker pack
_BATTLES_PER_PACK = 10

# ── Shop pricing — change here to affect the whole feature ──────────────────
PACK_PRICE_RYO: int = 500  # cost of one sticker pack
# ────────────────────────────────────────────────────────────────────────────


def _weighted_choice(weights: dict[str, float]) -> str:
    """Return a random key from a dict of {value: weight} using weighted sampling."""
    population = list(weights.keys())
    wt = list(weights.values())
    return random.choices(population, weights=wt, k=1)[0]


def _random_variant() -> str:
    """Return a randomly weighted sticker variant."""
    return _weighted_choice(_VARIANT_WEIGHTS)


def _get_or_create_album(user: User) -> StickerAlbum:
    album, _ = StickerAlbum.objects.get_or_create(owner=user)
    return album


class StickerService:
    """
    Handles all sticker award, upgrade, pack-opening, dust, and crafting logic.
    """

    @transaction.atomic
    def award_on_catch(
        self, player: User, pokemon: Pokemon, hp_remaining: int
    ) -> Sticker:
        """
        Award a sticker when a player catches a Pokemon.

        If the Pokemon was caught at exactly 1 HP, there is a 3% chance of
        awarding a secret_rare sticker instead of common.
        """
        _get_or_create_album(player)

        rarity = StickerRarity.COMMON
        if hp_remaining == 1 and random.random() < _SECRET_RARE_HP_CHANCE:
            rarity = StickerRarity.SECRET_RARE
            logger.info(
                "Secret rare sticker awarded to %s for catching %s at 1 HP!",
                player,
                pokemon.name,
            )

        variant = _random_variant()
        sticker = Sticker.objects.create(
            pokemon=pokemon,
            owner=player,
            rarity=rarity,
            variant=variant,
            awarded_from="catch",
        )
        logger.info("Awarded %s sticker to %s for catching %s", rarity, player, pokemon.name)
        return sticker

    @transaction.atomic
    def award_on_level_up(
        self, player: User, pokemon: Pokemon, new_level: int
    ) -> Sticker | None:
        """
        Award or upgrade a sticker when a caught Pokemon reaches a milestone level.

        Milestones: 25 → uncommon, 50 → rare, 75 → epic, 100 → holographic.
        Returns the new sticker or None if no milestone was hit.
        """
        rarity = _LEVEL_RARITY_UPGRADES.get(new_level)
        if rarity is None:
            return None

        variant = _random_variant()
        sticker = Sticker.objects.create(
            pokemon=pokemon,
            owner=player,
            rarity=rarity,
            variant=variant,
            awarded_from="level_up",
        )
        logger.info(
            "Awarded %s sticker to %s (%s reached level %d)",
            rarity,
            player,
            pokemon.name,
            new_level,
        )
        return sticker

    @transaction.atomic
    def award_on_combo_win(
        self, player: User, chain_length: int, pokemon: Pokemon | None = None
    ) -> Sticker | None:
        """
        Award a full_art sticker when winning with a combo chain >= 5.

        Returns the sticker or None if the chain was too short.
        """
        if chain_length < _FULL_ART_MIN_CHAIN:
            return None

        if pokemon is None:
            pokemon = Pokemon.objects.order_by("?").first()
        if pokemon is None:
            return None

        variant = _random_variant()
        sticker = Sticker.objects.create(
            pokemon=pokemon,
            owner=player,
            rarity=StickerRarity.FULL_ART,
            variant=variant,
            awarded_from="combo_win",
        )
        logger.info(
            "Awarded full_art sticker to %s for combo chain of %d",
            player,
            chain_length,
        )
        return sticker

    @transaction.atomic
    def buy_pack(self, player: User) -> StickerPack:
        """
        Spend PACK_PRICE_RYO to purchase and immediately receive a sticker pack.

        Raises ValueError if the player cannot afford the pack.
        Returns the new (unopened) StickerPack.
        """
        deduct_ryo(player, PACK_PRICE_RYO)
        pack = StickerPack.objects.create(owner=player)
        logger.info(
            "Player %s bought a sticker pack for %d Ryo",
            player,
            PACK_PRICE_RYO,
        )
        return pack

    @transaction.atomic
    def grant_pack_if_eligible(self, player: User) -> StickerPack | None:
        """
        Grant a sticker pack if the player's win count is a multiple of 10.

        Returns the new StickerPack or None if not eligible.
        """
        if player.battles_won > 0 and player.battles_won % _BATTLES_PER_PACK == 0:
            pack = StickerPack.objects.create(owner=player)
            logger.info("Granted sticker pack to %s (wins: %d)", player, player.battles_won)
            return pack
        return None

    @transaction.atomic
    def open_pack(self, player: User, pack: StickerPack) -> list[Sticker]:
        """
        Open a sticker pack and reveal 5 stickers.

        Pack contents:
          Slots 1-3: common or uncommon (weighted)
          Slot 4: guaranteed rare or above
          Slot 5: any rarity (full weighted table)

        Returns the list of 5 Sticker instances.
        """
        if pack.owner != player:
            raise ValueError("This pack does not belong to the player")
        if pack.opened:
            raise ValueError("This pack has already been opened")

        all_pokemon = list(Pokemon.objects.all())
        if not all_pokemon:
            raise ValueError("No Pokemon in database to generate stickers from")

        stickers: list[Sticker] = []

        # Slots 1–3: common/uncommon
        for _ in range(3):
            rarity = _weighted_choice(_COMMON_POOL_WEIGHTS)
            sticker = self._create_random_sticker(player, all_pokemon, rarity, "pack")
            stickers.append(sticker)

        # Slot 4: guaranteed rare+
        rarity = _weighted_choice(_GUARANTEED_RARE_WEIGHTS)
        stickers.append(self._create_random_sticker(player, all_pokemon, rarity, "pack"))

        # Slot 5: any rarity
        rarity = _weighted_choice(_ANY_RARITY_WEIGHTS)
        stickers.append(self._create_random_sticker(player, all_pokemon, rarity, "pack"))

        pack.stickers.add(*stickers)
        pack.opened = True
        pack.opened_at = datetime.now(tz=timezone.utc)
        pack.save(update_fields=["opened", "opened_at"])

        logger.info("Player %s opened a sticker pack — got %d stickers", player, len(stickers))
        return stickers

    @transaction.atomic
    def convert_duplicate(self, player: User, sticker: Sticker) -> int:
        """
        Convert a duplicate sticker to sticker dust.

        A sticker cannot be converted if the player has only one copy of that
        (pokemon, rarity, variant) combination.

        Returns the dust amount gained.
        """
        if sticker.owner != player:
            raise ValueError("This sticker does not belong to the player")
        if sticker.is_trading:
            raise ValueError("Cannot convert a sticker that is currently in a trade")

        # Count copies the player owns of this exact combination
        copy_count = Sticker.objects.filter(
            owner=player,
            pokemon=sticker.pokemon,
            rarity=sticker.rarity,
            variant=sticker.variant,
        ).count()

        if copy_count <= 1:
            raise ValueError(
                f"Cannot convert your only copy of {sticker.pokemon.name} "
                f"[{sticker.rarity}] {sticker.variant}"
            )

        dust = DUST_VALUES.get(sticker.rarity, 5)
        sticker.delete()

        player.sticker_dust += dust
        player.save(update_fields=["sticker_dust"])

        logger.info("Player %s converted a sticker for %d dust", player, dust)
        return dust

    @transaction.atomic
    def dismantle_sticker(self, player: User, sticker_id: int) -> int:
        """
        Dismantle any owned sticker for dust — no duplicate requirement.

        Dust values: Common 5 · Uncommon 10 · Rare 25 · Epic 60 ·
                     Holographic 120 · Full Art 200 · Secret Rare 300.

        Returns the dust amount awarded.
        Raises ValueError if the sticker is not owned by player or is in a trade.
        """
        sticker = Sticker.objects.select_for_update().filter(
            pk=sticker_id, owner=player
        ).first()
        if sticker is None:
            raise ValueError("Sticker not found or does not belong to you")
        if sticker.is_trading:
            raise ValueError("Cannot dismantle a sticker that is listed for trade")
        if sticker.is_favorite:
            raise ValueError("Cannot dismantle a favourited sticker — unfavourite it first")

        dust = DISMANTLE_VALUES.get(sticker.rarity, 5)
        sticker.delete()

        player.sticker_dust += dust
        player.save(update_fields=["sticker_dust"])

        logger.info(
            "Player %s dismantled sticker #%d (%s %s) for %d dust",
            player,
            sticker_id,
            sticker.rarity,
            sticker.variant,
            dust,
        )
        return dust

    @transaction.atomic
    def craft_sticker(
        self,
        player: User,
        pokemon: Pokemon,
        variant: str,
        rarity: str,
    ) -> Sticker:
        """
        Spend sticker dust to craft a specific sticker variant.

        Raises ValueError if insufficient dust or invalid rarity/variant.
        """
        cost = CRAFT_COSTS.get(rarity)
        if cost is None:
            raise ValueError(f"Unknown rarity: {rarity}")
        if variant not in StickerVariant.values:
            raise ValueError(f"Unknown variant: {variant}")
        if player.sticker_dust < cost:
            raise ValueError(
                f"Insufficient dust: need {cost}, have {player.sticker_dust}"
            )

        player.sticker_dust -= cost
        player.save(update_fields=["sticker_dust"])

        sticker = Sticker.objects.create(
            pokemon=pokemon,
            owner=player,
            rarity=rarity,
            variant=variant,
            awarded_from="craft",
        )
        logger.info(
            "Player %s crafted %s [%s] %s for %d dust",
            player,
            pokemon.name,
            rarity,
            variant,
            cost,
        )
        return sticker

    def get_album(self, user: User) -> dict:
        """
        Return album stats for display.

        {
          "total_stickers": int,
          "unique_pokemon": int,
          "rarity_breakdown": {rarity: count},
          "completion_percentage": float,
          "by_type": {type_name: {"total": int, "owned": int, "completion": float}},
          "showcase": [Sticker],
        }
        """
        _get_or_create_album(user)
        owned = Sticker.objects.filter(owner=user).select_related("pokemon__primary_type")
        total_pokemon = Pokemon.objects.count()

        rarity_breakdown: dict[str, int] = {}
        for rarity in StickerRarity.values:
            rarity_breakdown[rarity] = owned.filter(rarity=rarity).count()

        unique_pokemon = owned.values("pokemon").distinct().count()
        completion = round(unique_pokemon / total_pokemon * 100, 1) if total_pokemon else 0.0

        # By-type breakdown
        from apps.pokemon.models import PokemonType

        by_type: dict[str, dict] = {}
        for ptype in PokemonType.objects.all():
            type_pokemon_count = (
                Pokemon.objects.filter(
                    primary_type=ptype
                )
                | Pokemon.objects.filter(secondary_type=ptype)
            ).distinct().count()
            owned_of_type = owned.filter(
                pokemon__primary_type=ptype
            ).values("pokemon").distinct().count()
            by_type[ptype.name] = {
                "total": type_pokemon_count,
                "owned": owned_of_type,
                "completion": round(owned_of_type / type_pokemon_count * 100, 1) if type_pokemon_count else 0.0,
            }

        # Showcase stickers
        album = StickerAlbum.objects.filter(owner=user).first()
        showcase = list(album.showcase_stickers.all()) if album else []

        return {
            "total_stickers": owned.count(),
            "unique_pokemon": unique_pokemon,
            "rarity_breakdown": rarity_breakdown,
            "completion_percentage": completion,
            "by_type": by_type,
            "showcase": showcase,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _create_random_sticker(
        self,
        player: User,
        pokemon_pool: list[Pokemon],
        rarity: str,
        source: str,
    ) -> Sticker:
        """Create a sticker for a random Pokemon from the pool."""
        pokemon = random.choice(pokemon_pool)
        variant = _random_variant()
        return Sticker.objects.create(
            pokemon=pokemon,
            owner=player,
            rarity=rarity,
            variant=variant,
            awarded_from=source,
        )


class TradeService:
    """Handles peer-to-peer sticker trading with atomic ownership swaps."""

    @transaction.atomic
    def create_trade_offer(
        self,
        sender: User,
        sticker: Sticker,
        requested_sticker: Sticker | None = None,
        requested_pokemon: Pokemon | None = None,
        looking_for_note: str = "",
        offered_to: User | None = None,
    ) -> TradeOffer:
        """
        Create a trade offer listing a sticker.

        Validates:
        - Sender owns the sticker
        - Sticker not already in a trade
        - Sender has more than one copy (cannot trade their last copy)
        """
        if sticker.owner != sender:
            raise ValueError("You do not own this sticker")
        if sticker.is_trading:
            raise ValueError("This sticker is already listed for trade")

        # Cannot trade the only copy
        copy_count = Sticker.objects.filter(
            owner=sender,
            pokemon=sticker.pokemon,
            rarity=sticker.rarity,
            variant=sticker.variant,
        ).count()
        if copy_count <= 1:
            raise ValueError(
                "You cannot trade your only copy of "
                f"{sticker.pokemon.name} [{sticker.rarity}] {sticker.variant}"
            )

        sticker.is_trading = True
        sticker.save(update_fields=["is_trading"])

        offer = TradeOffer.objects.create(
            offered_sticker=sticker,
            requested_sticker=requested_sticker,
            requested_pokemon=requested_pokemon,
            looking_for_note=looking_for_note,
            offered_by=sender,
            offered_to=offered_to,
            status=TradeOffer.Status.PENDING,
        )
        logger.info("Trade offer #%d created by %s", offer.pk, sender)
        return offer

    @transaction.atomic
    def accept_trade(
        self, receiver: User, offer: TradeOffer, accepting_sticker: Sticker
    ) -> tuple[Sticker, Sticker]:
        """
        Atomically swap ownership of two stickers to complete a trade.

        Uses select_for_update() to prevent race conditions when two users
        try to accept the same offer simultaneously.

        Returns (sticker_receiver_now_owns, sticker_sender_now_owns).
        """
        # Lock both stickers and the offer for atomic update
        offer = TradeOffer.objects.select_for_update().get(pk=offer.pk)
        offered_sticker = Sticker.objects.select_for_update().get(pk=offer.offered_sticker_id)
        accepting_sticker = Sticker.objects.select_for_update().get(pk=accepting_sticker.pk)

        if offer.status != TradeOffer.Status.PENDING:
            raise ValueError(f"This trade offer is no longer pending (status: {offer.status})")
        if accepting_sticker.owner != receiver:
            raise ValueError("You do not own the sticker you are offering in exchange")
        if accepting_sticker.is_trading:
            raise ValueError("The sticker you are offering is already in another trade")

        # Cannot trade the only copy
        copy_count = Sticker.objects.filter(
            owner=receiver,
            pokemon=accepting_sticker.pokemon,
            rarity=accepting_sticker.rarity,
            variant=accepting_sticker.variant,
        ).count()
        if copy_count <= 1:
            raise ValueError("You cannot trade your only copy of this sticker")

        # Swap ownership
        original_sender = offer.offered_by
        offered_sticker.owner = receiver
        offered_sticker.is_trading = False
        offered_sticker.save(update_fields=["owner", "is_trading"])

        accepting_sticker.owner = original_sender
        accepting_sticker.save(update_fields=["owner"])

        # Finalise offer
        offer.status = TradeOffer.Status.ACCEPTED
        offer.resolved_at = datetime.now(tz=timezone.utc)
        offer.save(update_fields=["status", "resolved_at"])

        # Write history record
        TradeHistory.objects.create(
            offer=offer,
            from_user=original_sender,
            to_user=receiver,
            sticker_given=offered_sticker,
            sticker_received=accepting_sticker,
        )

        logger.info(
            "Trade #%d completed: %s ↔ %s",
            offer.pk,
            original_sender,
            receiver,
        )
        return offered_sticker, accepting_sticker

    @transaction.atomic
    def reject_trade(self, receiver: User, offer: TradeOffer) -> TradeOffer:
        """Reject a trade offer — offered sticker is unlisted."""
        offer = TradeOffer.objects.select_for_update().get(pk=offer.pk)
        if offer.status != TradeOffer.Status.PENDING:
            raise ValueError("This offer is not pending")

        offered_sticker = Sticker.objects.get(pk=offer.offered_sticker_id)
        offered_sticker.is_trading = False
        offered_sticker.save(update_fields=["is_trading"])

        offer.status = TradeOffer.Status.REJECTED
        offer.resolved_at = datetime.now(tz=timezone.utc)
        offer.save(update_fields=["status", "resolved_at"])

        logger.info("Trade #%d rejected by %s", offer.pk, receiver)
        return offer

    @transaction.atomic
    def cancel_trade(self, user: User, offer: TradeOffer) -> TradeOffer:
        """Cancel a trade offer — only the original offerer can cancel."""
        offer = TradeOffer.objects.select_for_update().get(pk=offer.pk)
        if offer.offered_by != user:
            raise ValueError("Only the trade creator can cancel this offer")
        if offer.status != TradeOffer.Status.PENDING:
            raise ValueError("This offer is not pending")

        offered_sticker = Sticker.objects.get(pk=offer.offered_sticker_id)
        offered_sticker.is_trading = False
        offered_sticker.save(update_fields=["is_trading"])

        offer.status = TradeOffer.Status.CANCELLED
        offer.resolved_at = datetime.now(tz=timezone.utc)
        offer.save(update_fields=["status", "resolved_at"])

        logger.info("Trade #%d cancelled by %s", offer.pk, user)
        return offer

    def get_open_offers(self, user: User | None = None):
        """Return pending trade offers, optionally filtered to a specific user."""
        qs = TradeOffer.objects.filter(status=TradeOffer.Status.PENDING).select_related(
            "offered_sticker__pokemon",
            "offered_by",
            "offered_to",
        )
        if user is not None:
            qs = qs.filter(offered_to=user) | qs.filter(offered_to__isnull=True, offered_by=user)
        return qs.order_by("-created_at")
